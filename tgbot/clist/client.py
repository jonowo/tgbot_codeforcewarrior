import logging
from datetime import timedelta

import requests

from tgbot.clist.models import ClistError, ContestInfo
from tgbot.utils import RESOURCES, hkt_now

logger = logging.getLogger(__name__)


class ClistAPI:
    def __init__(self, api_key: str):
        self.base_url = "https://clist.by/api/v2"
        self.session = requests.Session()
        self.session.headers = {"Authorization": f"ApiKey {api_key}"}

    def _request(self, endpoint, *args, **kwargs):
        resp = self.session.get(f"{self.base_url}/{endpoint}", *args, timeout=5, **kwargs)

        if "application/json" not in resp.headers["Content-Type"]:
            raise ClistError("Clist sent non-JSON response:\n{text}")

        try:
            data = resp.json()
        except Exception as e:
            logger.error("Could not read JSON from response")
            logger.error(resp.text)
            raise e from None

        return data["objects"]

    def get_upcoming_contests(self) -> list[ContestInfo]:
        data = self._request("contest", params={
            "upcoming": "true",
            "resource": ",".join(RESOURCES)
        })
        contests = [ContestInfo(**c) for c in data]
        contests = [c for c in contests if c.start_time <= hkt_now() + timedelta(days=14)]
        contests.sort(key=lambda c: (c.start_time, c.end_time, c.event))
        return contests
