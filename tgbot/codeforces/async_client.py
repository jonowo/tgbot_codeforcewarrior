import logging
from typing import Any, Optional

from aiocache import cached
from aiohttp import ClientSession

from .models import Contest, ContestPhase, RatingChange, Submission, User
from .utils import CodeforcesError

logger = logging.getLogger(__name__)


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

        text = await resp.text()

        if "Codeforces is temporarily unavailable." in text:
            raise CodeforcesError("Codeforces is temporarily unavailable.")
        if "504 Gateway Time-out" in text and resp.content_type == "text/html":
            raise CodeforcesError("504 Gateway Timeout")
        if resp.content_type != "application/json":
            raise CodeforcesError("Codeforces sent non-JSON response:\n{text}")

        try:
            data = await resp.json()
        except Exception as e:
            logger.error("Could not read JSON from response:")
            logger.error(text)
            raise e from None

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
        status = [Submission(**s) for s in data]
        status = [s for s in status if s.author.not_team() and s.problem.problemsetName is None]
        return status

    @cached(ttl=5 * 60)
    async def get_contest(self, contest_id: int) -> Contest:
        # Assumes contest has already started
        data = await self._request(
            "contest.standings",
            params={"contestId": contest_id, "handles": "jonowo"}  # dummy handle
        )
        return Contest(**data["contest"])

    @cached(ttl=5 * 60)
    async def get_contests(
            self,
            phases: tuple[ContestPhase] = (ContestPhase.BEFORE, ContestPhase.CODING)
    ) -> list[Contest]:
        data = await self._request("contest.list", params={"gym": "false"})
        contests = [Contest(**c) for c in data]
        if phases:
            contests = [c for c in contests if c.phase in phases]
        contests.sort(key=lambda c: c.startTimeSeconds)
        return contests

    # @cached(ttl=30)
    # async def get_standings(self, contest_id: int) -> list[RanklistRow]:
    #     data = await self._request(
    #         "contest.standings",
    #         params={"contestId": contest_id, "showUnofficial": "false"}
    #     )
    #     return [RanklistRow(**r) for r in data["rows"]]

    @cached(ttl=60 * 60)
    async def get_rating_changes(self, contest_id: int) -> dict[str, RatingChange]:
        data = await self._request("contest.ratingChanges", params={"contestId": contest_id})
        rating_changes = [RatingChange(**rc) for rc in data]
        rc_dict = {rc.handle: rc for rc in rating_changes}
        return rc_dict
