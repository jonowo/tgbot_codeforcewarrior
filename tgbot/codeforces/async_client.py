from typing import Any, Optional

from aiocache import cached
from aiohttp import ClientSession

from .models import Contest, ContestPhase, Submission, User
from .utils import CodeforcesError


class AsyncCodeforcesAPI:
    def __init__(self):
        self.base_url = "https://codeforces.com/api"
        self.session: Optional[ClientSession] = None

    async def __aenter__(self) -> "AsyncCodeforcesAPI":
        self.session = ClientSession()
        return self

    async def __aexit__(self, *args) -> None:
        await self.session.close()

    async def _request(self, endpoint, *args, **kwargs) -> Any:
        resp = await self.session.get(f"{self.base_url}/{endpoint}", *args, **kwargs)

        if "Codeforces is temporarily unavailable." in await resp.text():
            raise CodeforcesError("Codeforces is temporarily unavailable.")

        data = await resp.json()
        if data["status"] == "FAILED":
            if "not found" in data["comment"].lower():
                raise CodeforcesError("Not found")
            else:
                raise CodeforcesError(data["comment"])
        return data["result"]

    async def get_user(self, handle: str) -> User:
        users = await self.get_users(handle)
        return users[0]

    @cached(ttl=60)
    async def get_users(self, *handles: str) -> list[User]:
        data = await self._request("user.info", params={"handles": ";".join(handles)})
        return [User(**u) for u in data]

    async def get_status(self, handle: str, count: Optional[int] = None) -> list[Submission]:
        params = {"handle": handle}
        if count is not None:
            params["count"] = count
        data = await self._request("user.status", params=params)
        return [Submission(**s) for s in data]

    @cached(ttl=5 * 60)
    async def get_contests(self) -> list[Contest]:
        data = await self._request("contest.list", params={"gym": "false"})
        contests = [Contest(**c) for c in data]
        contests = [c for c in contests if c.phase in (ContestPhase.BEFORE, ContestPhase.CODING)]
        contests.sort(key=lambda c: c.startTimeSeconds)
        return contests
