import json
from datetime import datetime, timedelta
from typing import Any

import functions_framework
import google.cloud.logging
import google.cloud.logging
import requests
from flask import Request
from google.cloud import firestore, tasks_v2
from google.protobuf import timestamp_pb2

from codeforces import CodeforcesAPI
from codeforces.utils import HKT

google.cloud.logging.Client().setup_logging()

try:
    import googleclouddebugger

    googleclouddebugger.enable(breakpoint_enable_canary=False)
except ImportError:
    pass

# load firestore
db = firestore.Client(project='tgbot-340618')

# load cloud task config
task_client = tasks_v2.CloudTasksClient()
task_parent = task_client.queue_path("tgbot-340618", "asia-northeast1", "cfbot-verification")

with open(".credentials") as f:
    tgbot_token = f.read().strip()

tg_chat_id = -1001669733846

cf_client = CodeforcesAPI()


def make_tg_api_request(endpoint, params: dict[str, Any]):
    requests.get(
        f"https://api.telegram.org/bot{tgbot_token}/{endpoint}",
        params=params
    )


def schedule_verify(user_id: int, dt: datetime):
    data = {"user_id": user_id}

    timestamp = timestamp_pb2.Timestamp()
    timestamp.FromDatetime(dt)

    task = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": "https://asia-northeast1-tgbot-340618.cloudfunctions.net/cf_verification",
            "headers": {"Content-type": "application/json"},
            "body": json.dumps(data).encode("utf-8")
        },
        "schedule_time": timestamp
    }
    task_client.create_task(parent=task_parent, task=task)


def verify(handle: str, problem_id: str) -> bool:
    submissions = cf_client.get_status(handle, count=10)
    submissions = [s for s in submissions if s.author.not_team() and s.problem.id == problem_id]
    return any(
        datetime.now(HKT) - submission.time <= timedelta(seconds=10 * 60)
        for submission in submissions
    )


@functions_framework.http
def cf_verification(request: Request):
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

        doc_ref = db.collection("cfbot_handle").document(str(user_id))
        doc_ref.set({"handle": handle})

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
                "chat_id": tg_chat_id,
                "user_id": user_id
            }
        )

        return "verification successful"

    if count < 19:
        now = datetime.utcnow()
        schedule_verify(user_id, now + timedelta(seconds=30))
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
