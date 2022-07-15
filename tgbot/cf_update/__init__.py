import asyncio
import contextlib
import logging
import random
import traceback
from datetime import timedelta

import aiocron
from aiohttp import ClientSession, web
from aiohttp.web_exceptions import HTTPMethodNotAllowed, HTTPNotFound
from aiohttp_middlewares import error_context, error_middleware
from aiotinydb import AIOTinyDB
from prettytable import PrettyTable
from telegram.constants import ParseMode
from telegram.ext import Application, Defaults
from tinydb import Query

from tgbot.cf_update.predicted_deltas import get_predicted_deltas
from tgbot.cf_update.stickers import FAILED_STICKERS, OK_STICKERS, UPCOMING_CONTEST_STICKERS
from tgbot.clist import AsyncClistAPI
from tgbot.codeforces import AsyncCodeforcesAPI, CodeforcesError, Contest, ContestPhase, Submission
from tgbot.config import config
from tgbot.utils import HKT, hkt_now

logging.basicConfig(level="INFO", format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

routes = web.RouteTableDef()
lock = asyncio.Lock()
delta_lock = asyncio.Lock()


def get_handles(app: web.Application) -> list[str]:
    users = app["db"].all()
    return [user["handle"] for user in users]


async def init_user(app: web.Application, handle: str) -> None:
    status = await app["cf_client"].get_status(handle, count=100)
    user = {
        "handle": handle,
        "status": [s.dict() for s in status]
    }
    app["db"].insert(user)


@routes.post("/")
async def init(request: web.Request) -> web.Response:
    if request.headers.get("X-Auth-Token") != config["SECRET"]:
        logger.warning("Endpoint / was accessed without authentication")
        return web.json_response({"success": False, "reason": "Authentication failed"})

    data = await request.json()
    handles = set(data["handles"])
    logger.info(f"Init handles: {list(handles)}")

    async with lock:
        # Delete absent handles
        for handle in get_handles(request.app):
            if handle in handles:
                handles.remove(handle)
            else:
                request.app["db"].remove(Query().handle == handle)

        # Initialize new handles
        await asyncio.gather(*[init_user(request.app, handle) for handle in handles])

    return web.json_response({"success": True})


def create_table(rows: list[tuple[int, str, str]]) -> PrettyTable:
    table = PrettyTable(["#", "Handle", "∆"], sortby="#", align="r")
    table.header_align = "c"
    table.align["Handle"] = "l"

    table.add_rows(rows)
    return table


async def get_delta_table(app: web.Application, contest: Contest, handles: list[str]) -> str:
    predict = True
    if hkt_now() > contest.end_time:
        # Try to get actual rating changes
        try:
            rating_changes = await app["cf_client"].get_rating_changes(contest.id)
            assert rating_changes
        except CodeforcesError as e:
            if "Rating changes are unavailable" not in str(e):
                raise e from None
        except AssertionError:
            pass
        else:
            predict = False

    if predict:
        async with delta_lock:
            rating_changes = await get_predicted_deltas(app, contest.id)
        rows = [rating_changes[h] for h in handles if h in rating_changes]
    else:
        rows = [rating_changes[h].get_table_row() for h in handles if h in rating_changes]

    if rows:
        table = create_table(rows)
        return (
            f"{'Predicted' if predict else 'Official'} rating changes for {contest.linked_name}\n"
            f"<pre>{table}</pre>"
        )
    else:
        return f"No members are competing in {contest.linked_name}"


async def send_delta(app: web.Application, chat_id: int) -> None:
    asyncio.create_task(
        app["bot"].send_chat_action(chat_id, "typing")
    )

    async with lock:
        handles = get_handles(app)

    # Get the most recent contest(s)
    contests = await app["cf_client"].get_contests(phases=())
    contests = [c for c in contests if c.phase != ContestPhase.BEFORE]
    contests.sort(key=lambda c: (c.startTimeSeconds, c.id))
    contests = [c for c in contests if c.startTimeSeconds == contests[-1].startTimeSeconds]

    results = await asyncio.gather(*[get_delta_table(app, c, handles) for c in contests])
    text = "\n\n".join(results)
    if any(c.phase == ContestPhase.SYSTEM_TEST for c in contests):
        text += "\n\nSystem testing is ongoing. The deltas are not yet finalized."

    asyncio.create_task(
        app["bot"].send_message(chat_id, text)
    )


@routes.post("/delta")
async def command_delta(request: web.Request) -> web.Response:
    if request.headers.get("X-Auth-Token") != config["SECRET"]:
        logger.warning("Endpoint /delta was accessed without authentication")
        return web.json_response({"success": False, "reason": "Authentication failed"})

    data = await request.json()
    asyncio.create_task(send_delta(request.app, data["chat_id"]))
    return web.json_response({"success": True})


async def db_retrieve_status(app: web.Application, handle: str) -> list[Submission]:
    users = app["db"].search(Query().handle == handle)
    status = users[0]["status"]
    status = [Submission(**s) for s in status]
    return status


async def update_status(app: web.Application, handle: str) -> None:
    try:
        async with lock:
            old_status, new_status = await asyncio.gather(
                db_retrieve_status(app, handle),
                app["cf_client"].get_status(handle, count=100)
            )

            status_dict = {s.id: s for s in old_status}
            updated_status = [s for s in new_status if s.id not in status_dict or status_dict[s.id] != s]

            contest_ids = {s.author.contestId for s in updated_status}
            # Get all contests simultaneously and cache them
            await asyncio.gather(*(app["cf_client"].get_contest(cid) for cid in contest_ids))

            for submission in updated_status:
                contest = await app["cf_client"].get_contest(submission.author.contestId)
                if submission.should_notify(contest):
                    await app["bot"].send_message(config["CHAT_ID"], str(submission))

                    sticker = random.choice(OK_STICKERS if submission.verdict == "OK" else FAILED_STICKERS)
                    await app["bot"].send_sticker(config["CHAT_ID"], sticker)

            app["db"].update(
                {"status": [s.dict() for s in new_status]},
                Query().handle == handle
            )
    except CodeforcesError as e:
        logger.warning(f"{type(e).__name__}: {e!s}")


async def update_status_forever(app: web.Application) -> None:
    await asyncio.sleep(1)
    while True:
        async with lock:
            handles = get_handles(app)

        for handle in handles:
            try:
                # At least 3s between each update
                await asyncio.gather(update_status(app, handle), asyncio.sleep(2.8))
                await asyncio.sleep(0.2)
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.error("".join(traceback.format_exception(type(e), e, e.__traceback__)))


async def notify_upcoming_contest(app: web.Application) -> None:
    now = hkt_now().replace(second=0, microsecond=0)
    contests = await app["clist_client"].get_upcoming_contests()

    for contest in contests:
        if now + timedelta(minutes=5) == contest.start_time:
            minutes_left = 5
        elif now + timedelta(minutes=15) == contest.start_time:
            minutes_left = 15
        elif now + timedelta(minutes=60) == contest.start_time:
            minutes_left = 60
        else:
            continue

        if minutes_left == 60:
            text = f"{contest.linked_name} begins in 1 hour"
        else:
            text = f"{contest.linked_name} begins in {minutes_left} minutes"
        await app["bot"].send_message(config["CHAT_ID"], text)
        if minutes_left == 5:
            await app["bot"].send_sticker(config["CHAT_ID"], random.choice(UPCOMING_CONTEST_STICKERS))


async def startup(app: web.Application) -> None:
    logger.info("Startup in progress")

    context_stack = contextlib.AsyncExitStack()
    app["context_stack"] = context_stack

    app["cf_client"] = await context_stack.enter_async_context(AsyncCodeforcesAPI())
    app["clist_client"] = await context_stack.enter_async_context(
        AsyncClistAPI(config["CLIST_API_KEY"])
    )

    # aiohttp session
    app["session"] = await context_stack.enter_async_context(ClientSession())

    app["db"] = await context_stack.enter_async_context(AIOTinyDB("db.json"))

    application = (
        Application.builder()
        .token(config["TOKEN"])
        .defaults(Defaults(parse_mode=ParseMode.HTML, disable_web_page_preview=True))
        .build()
    )
    app["bot"] = await context_stack.enter_async_context(application.bot)

    aiocron.crontab("*/5 * * * *", func=notify_upcoming_contest, args=(app,), tz=HKT)
    asyncio.create_task(update_status_forever(app))


async def cleanup(app: web.Application) -> None:
    await app["context_stack"].aclose()


async def default_error_handler(request: web.Request) -> web.Response:
    with error_context(request) as context:
        if isinstance(context.err, CodeforcesError):
            logger.warning(context.message)
        else:
            logger.error(context.message, exc_info=True)
        return web.json_response(context.data, status=context.status)


async def create_app() -> web.Application:
    app = web.Application(
        middlewares=(
            error_middleware(
                default_handler=default_error_handler,
                ignore_exceptions=(HTTPNotFound, HTTPMethodNotAllowed)
            ),
        )
    )
    app.add_routes(routes)
    app.on_startup.append(startup)
    app.on_cleanup.append(cleanup)
    return app
