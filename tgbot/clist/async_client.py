import logging
from datetime import timedelta
from typing import Any, Optional

from aiohttp import ClientSession

from .models import ContestInfo
from .utils import ClistError, RESOURCES, hkt_now

logger = logging.getLogger(__name__)


class AsyncClistAPI:
    def __init__(self, api_key: str):
        self.base_url = "https://clist.by/api/v2"
        self.session: Optional[ClientSession] = None
        self.api_key = api_key

    async def __aenter__(self) -> "AsyncClistAPI":
        self.session = ClientSession(headers={"Authorization": f"ApiKey {self.api_key}"})
        return self

    async def __aexit__(self, *args) -> None:
        await self.session.close()

    async def _request(self, endpoint, *args, **kwargs) -> Any:
        resp = await self.session.get(f"{self.base_url}/{endpoint}", *args, **kwargs)
        text = await resp.text()

        if resp.content_type != "application/json":
            raise ClistError("Clist sent non-JSON response:\n{text}")

        try:
            data = await resp.json()
        except Exception as e:
            logger.error("Could not read JSON from response:")
            logger.error(text)
            raise e from None

        return data["objects"]

    async def get_upcoming_contests(self) -> list[ContestInfo]:
        data = await self._request("contest", params={
            "upcoming": "true",
            "resource": ",".join(RESOURCES)
        })
        contests = [ContestInfo(**c) for c in data]
        contests = [c for c in contests if c.start_time <= hkt_now() + timedelta(days=14)]
        contests.sort(key=lambda c: (c.start_time, c.end_time))
        return contests
