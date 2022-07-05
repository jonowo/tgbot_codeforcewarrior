import json
from datetime import datetime
from typing import Any, Optional

import google.cloud.logging
import requests
from cachetools import TTLCache, cached
from google.cloud import firestore, tasks_v2
from google.protobuf import timestamp_pb2

google.cloud.logging.Client().setup_logging()

try:
    import googleclouddebugger

    googleclouddebugger.enable(breakpoint_enable_canary=False)
except ImportError:
    pass

with open("config.json") as f:
    config = json.load(f)
config["FUNCTIONS_URL"] = config["FUNCTIONS_URL"].rstrip("/")
config["CF_UPDATE_URL"] = config["CF_UPDATE_URL"].rstrip("/")

# load firestore
db = firestore.Client(project=config["PROJECT_ID"])

# load cloud task config
task_client = tasks_v2.CloudTasksClient()
task_parent = task_client.queue_path(config["PROJECT_ID"], "asia-northeast1", "cfbot-verification")

session = requests.Session()


def make_tg_api_request(endpoint, params: dict[str, Any]) -> requests.Response:
    return session.get(
        f"https://api.telegram.org/bot{config['TOKEN']}/{endpoint}",
        params=params,
        timeout=5
    )


def schedule_task(endpoint: str, user_id: int, dt: datetime) -> None:
    data = {"user_id": user_id}

    timestamp = timestamp_pb2.Timestamp()
    timestamp.FromDatetime(dt)

    task = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": f"{config['FUNCTIONS_URL']}/{endpoint}",
            "headers": {"Content-type": "application/json"},
            "body": json.dumps(data).encode("utf-8")
        },
        "schedule_time": timestamp
    }
    task_client.create_task(parent=task_parent, task=task)


def get_handle(user_id: int) -> Optional[str]:
    doc = db.collection("cfbot_handle").document(str(user_id)).get()
    if doc.exists:
        return doc.to_dict()["handle"]


@cached(cache=TTLCache(maxsize=1, ttl=5))
def get_handles() -> list[str]:
    handles = []
    for doc in db.collection("cfbot_handle").stream():
        handles.append(doc.to_dict()["handle"])
    return handles
