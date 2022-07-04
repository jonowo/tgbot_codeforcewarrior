import asyncio
import contextlib
import json
import logging
import traceback
from datetime import timedelta
from typing import Any

import aiocron
from aiohttp import ClientSession, web
from aiotinydb import AIOTinyDB
from prettytable import PrettyTable
from tinydb import Query

from clist import AsyncClistAPI
from codeforces import AsyncCodeforcesAPI, CodeforcesError, ContestPhase, Submission
from codeforces.utils import HKT, hkt_now
from predicted_deltas import get_predicted_deltas

logging.basicConfig(level="INFO", format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

with open("config.json") as f:
    config = json.load(f)

routes = web.RouteTableDef()
lock = asyncio.Lock()


async def get_handles(app: web.Application) -> list[str]:
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
        for handle in await get_handles(request.app):
            if handle in handles:
                handles.remove(handle)
            else:
                request.app["db"].remove(Query().handle == handle)

        # Initialize new handles
        await asyncio.gather(*[init_user(request.app, handle) for handle in handles])

    return web.json_response({"success": True})


async def make_tg_api_request(app: web.Application, endpoint: str, params: dict[str, Any]) -> None:
    await app["session"].post(
        f"https://api.telegram.org/bot{config['TOKEN']}/{endpoint}",
        params=params
    )


@routes.post("/delta")
async def send_delta(request: web.Request) -> web.Response:
    if request.headers.get("X-Auth-Token") != config["SECRET"]:
        logger.warning("Endpoint /delta was accessed without authentication")
        return web.json_response({"success": False, "reason": "Authentication failed"})

    async with lock:
        handles = await get_handles(request.app)

    # Get most recent contest
    contests = await request.app["cf_client"].get_contests(phases=())
    contests = [c for c in contests if c.phase != ContestPhase.BEFORE]
    contests.sort(key=lambda c: c.startTimeSeconds, reverse=True)
    contest = contests[0]

    predict = True
    if hkt_now() > contest.end_time:
        # Try to get actual rating changes
        try:
            rating_changes = await request.app["cf_client"].get_rating_changes(contest.id)
        except CodeforcesError as e:
            if "Rating changes are unavailable" not in str(e):
                raise e from None
        else:
            predict = False

    table = PrettyTable(["#", "Handle", "∆"], sortby="#", align="r")
    table.align["Handle"] = "l"
    table.header_align = "c"

    if predict:
        rating_changes = await get_predicted_deltas(request.app, contest.id)
        for h in handles:
            if h in rating_changes:
                table.add_row(rating_changes[h])
    else:
        for h in handles:
            if h in rating_changes:
                table.add_row((rating_changes[h].rank, h, rating_changes[h].delta))

    asyncio.create_task(
        make_tg_api_request(request.app, "sendMessage", params={
            "chat_id": config["CHAT_ID"],
            "text": (
                f"{'Predicted' if predict else 'Official'} rating changes for {contest.linked_name}\n"
                f"<pre>{table}</pre>"
            ),
            "parse_mode": "HTML",
            "disable_web_page_preview": "true"
        })
    )

    return web.json_response({"success": True})


async def db_retrieve_status(app: web.Application, handle: str) -> list[Submission]:
    users = app["db"].search(Query().handle == handle)
    status = users[0]["status"]
    status = [Submission(**s) for s in status]
    return status


async def update_status(app: web.Application, handle: str) -> None:
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
                asyncio.create_task(
                    make_tg_api_request(app, "sendMessage", params={
                        "chat_id": config["CHAT_ID"],
                        "text": str(submission),
                        "parse_mode": "HTML",
                        "disable_web_page_preview": "true"
                    })
                )

        app["db"].update(
            {"status": [s.dict() for s in new_status]},
            Query().handle == handle
        )


async def update_status_forever(app: web.Application) -> None:
    while True:
        await asyncio.sleep(0.1)
        async with lock:
            handles = await get_handles(app)

        for handle in handles:
            try:
                # At least 3s between each update
                await asyncio.gather(update_status(app, handle), asyncio.sleep(3))
            except asyncio.CancelledError:
                return
            except Exception as e:
                logging.error("".join(traceback.format_exception(type(e), e, e.__traceback__)))


async def notify_upcoming_contest(app: web.Application) -> None:
    now = hkt_now().replace(second=0, microsecond=0)
    contests = await app["clist_client"].get_upcoming_contests()

    for contest in contests:
        if now + timedelta(minutes=5) == contest.start_time:
            minutes_left = 5
        elif now + timedelta(minutes=15) == contest.start_time:
            minutes_left = 15
        else:
            continue

        text = f"{contest.linked_name} begins in {minutes_left} minutes"
        asyncio.create_task(
            make_tg_api_request(app, "sendMessage", params={
                "chat_id": config["CHAT_ID"],
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": "true"
            })
        )


async def startup(app: web.Application) -> None:
    context_stack = contextlib.AsyncExitStack()
    app["context_stack"] = context_stack

    app["cf_client"] = await context_stack.enter_async_context(AsyncCodeforcesAPI())
    app["clist_client"] = await context_stack.enter_async_context(
        AsyncClistAPI(config["CLIST_API_KEY"])
    )

    # aiohttp session
    app["session"] = await context_stack.enter_async_context(ClientSession())

    app["db"] = await context_stack.enter_async_context(AIOTinyDB("db.json"))

    aiocron.crontab("*/5 * * * *", func=notify_upcoming_contest, args=(app,), tz=HKT)
    asyncio.create_task(update_status_forever(app))


async def cleanup(app: web.Application) -> None:
    await app["context_stack"].aclose()


def main() -> None:
    app = web.Application()
    app.add_routes(routes)
    app.on_startup.append(startup)
    app.on_cleanup.append(cleanup)
    web.run_app(app, host="0.0.0.0", port=3000, loop=asyncio.get_event_loop())


if __name__ == "__main__":
    main()
