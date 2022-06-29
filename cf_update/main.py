import asyncio
import contextlib
import logging
import os
import traceback
from typing import Any

import aioboto3
from aiohttp import ClientSession, web
from dotenv import load_dotenv
from prettytable import PrettyTable

from codeforces import AsyncCodeforcesAPI, CodeforcesError, ContestPhase, Submission
from codeforces.utils import hkt_now
from predicted_deltas import get_predicted_deltas

logging.basicConfig(level="INFO", format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()
TOKEN = os.environ["TOKEN"]
SECRET = os.environ["SECRET"]
CHAT_ID = -1001669733846

routes = web.RouteTableDef()
boto_session = aioboto3.Session()
lock = asyncio.Lock()


async def init_user(app: web.Application, handle: str) -> None:
    status = await app["cf_client"].get_status(handle, count=100)
    item = {
        "handle": handle,
        "status": [s.dict() for s in status]
    }
    await app["table"].put_item(Item=item)


@routes.post("/")
async def init(request: web.Request) -> web.Response:
    if request.headers.get("X-Auth-Token") != SECRET:
        logger.warning("Endpoint / was accessed without authentication")
        return web.json_response({"success": False, "reason": "Authentication failed"})

    data = await request.json()
    handles = set(data["handles"])
    logger.info(f"Init handles: {list(handles)}")

    async with lock:
        response = await request.app["table"].scan()
        tasks = []

        # Delete absent handles
        for item in response["Items"]:
            if item["handle"] in handles:
                handles.remove(item["handle"])
            else:
                tasks.append(
                    request.app["table"].delete_item(Key={"handle": item["handle"]})
                )

        # Initialize new handles
        tasks += [init_user(request.app, handle) for handle in handles]
        await asyncio.gather(*tasks)

    return web.json_response({"success": True})


async def make_tg_api_request(app: web.Application, endpoint: str, params: dict[str, Any]) -> None:
    await app["session"].post(
        f"https://api.telegram.org/bot{TOKEN}/{endpoint}",
        params=params
    )


async def get_handles(app: web.Application) -> list[str]:
    async with lock:
        response = await app["table"].scan()
        handles = [item["handle"] for item in response["Items"]]
    return handles


@routes.post("/delta")
async def send_delta(request: web.Request) -> web.Response:
    if request.headers.get("X-Auth-Token") != SECRET:
        logger.warning("Endpoint /delta was accessed without authentication")
        return web.json_response({"success": False, "reason": "Authentication failed"})

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
            "chat_id": CHAT_ID,
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
    response = await app["table"].get_item(Key={"handle": handle})
    status = response["Item"]["status"]
    status = [Submission(**s) for s in status]
    return status


async def update(app: web.Application, handle: str) -> None:
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
                        "chat_id": CHAT_ID,
                        "text": str(submission),
                        "parse_mode": "HTML",
                        "disable_web_page_preview": "true"
                    })
                )

        item = {
            "handle": handle,
            "status": [s.dict() for s in new_status]
        }
        await app["table"].put_item(Item=item)


async def update_status_forever(app: web.Application) -> None:
    while True:
        for handle in await get_handles(app):
            try:
                # At least 3s between each update
                await asyncio.gather(update(app, handle), asyncio.sleep(3))
            except asyncio.CancelledError:
                return
            except Exception as e:
                logging.error("".join(traceback.format_exception(type(e), e, e.__traceback__)))


async def startup(app: web.Application) -> None:
    context_stack = contextlib.AsyncExitStack()
    app["context_stack"] = context_stack

    # codeforces client
    app["cf_client"] = await context_stack.enter_async_context(AsyncCodeforcesAPI())

    # aiohttp session
    app["session"] = await context_stack.enter_async_context(ClientSession())

    # dynamodb resource
    app["dynamodb"] = await context_stack.enter_async_context(
        boto_session.resource("dynamodb", region_name="ap-northeast-1")
    )
    app["table"] = await app["dynamodb"].Table("cf-status")

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
