import os
from typing import Any

import functions_framework
import google.cloud.logging
import requests
from dotenv import load_dotenv
from flask import Request

google.cloud.logging.Client().setup_logging()

try:
    import googleclouddebugger

    googleclouddebugger.enable(breakpoint_enable_canary=False)
except ImportError:
    pass

load_dotenv()
tgbot_token = os.environ["TOKEN"]
tg_chat_id = -1001669733846


def make_tg_api_request(endpoint, params: dict[str, Any]) -> requests.Response:
    return requests.get(
        f"https://api.telegram.org/bot{tgbot_token}/{endpoint}",
        params=params
    )


@functions_framework.http
def decline_join_request(request: Request) -> str:
    user_id = request.get_json()["user_id"]

    # Will fail (with no effect) if the user never requested to join / is already inside group
    make_tg_api_request(
        "declineChatJoinRequest",
        params={
            "chat_id": tg_chat_id,
            "user_id": user_id
        }
    )

    return ""
