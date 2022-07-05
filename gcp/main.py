from datetime import datetime, timedelta

import functions_framework
import requests
from flask import Request

from codeforces import CodeforcesAPI
from codeforces.utils import hkt_now
from common import config, db, get_handles, make_tg_api_request, schedule_task

cf_client = CodeforcesAPI()


def verify(handle: str, problem_id: str) -> bool:
    status = cf_client.get_status(handle, count=10)
    status = [s for s in status if s.problem.id == problem_id]
    return any(
        hkt_now() - submission.time <= timedelta(seconds=10 * 60)
        for submission in status
    )


@functions_framework.http
def cf_verification(request: Request) -> str:
    user_id = request.get_json()["user_id"]

    doc_ref = db.collection("cfbot_verification").document(str(user_id))
    doc = doc_ref.get()

    if not doc.exists:
        return "doc was deleted"

    data = doc.to_dict()
    handle = data["handle"]
    problem_id = data["problem_id"]
    chat_id = data["chat_id"]
    message_id = data["message_id"]
    count = data["count"]

    if verify(handle, problem_id):
        doc_ref.delete()

        db.collection("cfbot_handle").document(str(user_id)).set({"handle": handle})

        make_tg_api_request(
            "sendMessage",
            params={
                "chat_id": chat_id,
                "text": f"驗證成功，你的 codeforces handle 為 {handle}",
                "reply_to_message_id": message_id,
                "allow_sending_without_reply": True
            }
        )

        # Will fail (with no effect) if the user never requested to join / is already inside group
        make_tg_api_request(
            "approveChatJoinRequest",
            params={
                "chat_id": config["CHAT_ID"],
                "user_id": user_id
            }
        )

        # Notify cf_update
        requests.post(
            f"{config['CF_UPDATE_URL']}/",
            json={"handles": get_handles()},
            headers={"X-Auth-Token": config["SECRET"]}
        )

        return "verification successful"

    if count < 19:
        schedule_task("cf_verification", user_id, datetime.utcnow() + timedelta(seconds=30))
        doc_ref.update({"count": count + 1})
        return "pending verification"

    doc_ref.delete()
    make_tg_api_request(
        "sendMessage",
        params={
            "chat_id": chat_id,
            "text": "驗證失敗",
            "reply_to_message_id": message_id,
            "allow_sending_without_reply": True
        }
    )

    return "verification failed"


@functions_framework.http
def decline_join_request(request: Request) -> str:
    user_id = request.get_json()["user_id"]

    # Will fail (with no effect) if the user never requested to join / is already inside group
    make_tg_api_request(
        "declineChatJoinRequest",
        params={
            "chat_id": config["CHAT_ID"],
            "user_id": user_id
        }
    )

    return ""
