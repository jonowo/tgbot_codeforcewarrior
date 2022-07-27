import functools
import logging
from typing import Optional

import requests
from cachetools import TTLCache, cached

from tgbot.codeforces.models import CodeforcesError, Contest, ContestPhase, Problem, Submission, User

logger = logging.getLogger(__name__)


class CodeforcesAPI:
    def __init__(self):
        self.base_url = "https://codeforces.com/api"
        self.session = requests.Session()

    def _request(self, endpoint, *args, **kwargs):
        resp = self.session.get(f"{self.base_url}/{endpoint}", *args, timeout=10, **kwargs)
        content_type = resp.headers["Content-Type"]

        if "Codeforces is temporarily unavailable." in resp.text:
            raise CodeforcesError("Codeforces is temporarily unavailable.")
        if "504 Gateway Time-out" in resp.text and "text/html" in content_type:
            raise CodeforcesError("504 Gateway Timeout")
        if "application/json" not in content_type:
            raise CodeforcesError("Codeforces sent non-JSON response:\n{text}")

        try:
            data = resp.json()
        except Exception as e:
            logger.error("Could not read JSON from response")
            logger.error(resp.text)
            raise e from None

        if data["status"] == "FAILED":
            if "not found" in data["comment"].lower():
                raise CodeforcesError("Not found")
            else:
                raise CodeforcesError(data["comment"])
        return data["result"]

    def get_user(self, handle: str) -> User:
        return self.get_users(handle)[0]

    @cached(cache=TTLCache(maxsize=1024, ttl=60))
    def get_users(self, *handles: str) -> list[User]:
        data = self._request("user.info", params={"handles": ";".join(handles)})
        return [User(**u) for u in data]

    def get_status(self, handle: str, count: Optional[int] = None) -> list[Submission]:
        params = {"handle": handle}
        if count is not None:
            params["count"] = count
        data = self._request("user.status", params=params)
        status = [Submission(**s) for s in data]
        status = [s for s in status if s.author.not_team() and s.problem.problemsetName is None]
        return status

    @cached(cache=TTLCache(maxsize=1, ttl=10 * 60))
    def get_problems(self) -> list[Problem]:
        data = self._request("problemset.problems")["problems"]
        problems = [Problem(**p) for p in data]
        problems = [p for p in problems if p.problemsetName is None]  # codeforces problems only
        return problems

    @cached(cache={})  # Store forever
    def get_available_tags(self) -> set[str]:
        problems = self.get_problems()
        return functools.reduce(lambda t, p: t | set(p.tags), problems, set())

    @cached(cache=TTLCache(maxsize=1, ttl=5 * 60))
    def get_contests(self, phases: tuple[ContestPhase] = (ContestPhase.BEFORE, ContestPhase.CODING)) -> list[Contest]:
        data = self._request("contest.list", params={"gym": "false"})
        contests = [Contest(**c) for c in data]
        if phases:
            contests = [c for c in contests if c.phase in phases]
        contests.sort(key=lambda c: c.startTimeSeconds)
        return contests
