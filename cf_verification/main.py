import json
import os
from datetime import datetime, timedelta
from typing import Any

import functions_framework
import google.cloud.logging
import requests
from dotenv import load_dotenv
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

load_dotenv()
tgbot_token = os.environ["TOKEN"]
SECRET = os.environ["SECRET"]
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
    status = cf_client.get_status(handle, count=10)
    status = [s for s in status if s.problem.id == problem_id]
    return any(
        datetime.now(HKT) - submission.time <= timedelta(seconds=10 * 60)
        for submission in status
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

        handles = []
        for doc in db.collection("cfbot_handle").stream():
            handles.append(doc.to_dict()["handle"])

        # Notify cf_update
        requests.post(
            "http://35.74.183.91/",
            json={"handles": handles},
            headers={"X-Auth-Token": SECRET}
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

# Add new route for delete join request
