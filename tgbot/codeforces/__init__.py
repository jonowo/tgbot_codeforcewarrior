import functools

import requests
from cachetools import TTLCache, cached

from .models import Contest, ContestPhase, Problem, User


class CodeforcesError(Exception):
    pass


class CodeforcesAPI:
    def __init__(self):
        self.base_url = "https://codeforces.com/api"
        self.session = requests.Session()

    def _request(self, endpoint, *args, **kwargs):
        resp = self.session.get(f"{self.base_url}/{endpoint}", *args, **kwargs)

        if "Codeforces is temporarily unavailable." in resp.text:
            raise CodeforcesError("Codeforces is temporarily unavailable.")

        data = resp.json()
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

    @cached(cache=TTLCache(maxsize=1, ttl=10 * 60))
    def get_problems(self) -> list[Problem]:
        data = self._request("problemset.problems")["problems"]
        return [Problem(**p) for p in data]

    @cached(cache={})  # Store forever
    def get_available_tags(self) -> set[str]:
        problems = self.get_problems()
        return functools.reduce(lambda t, p: t | set(p.tags), problems, set())

    @cached(cache=TTLCache(maxsize=1, ttl=5 * 60))
    def get_contests(self) -> list[Contest]:
        data = self._request("contest.list", params={"gym": "false"})
        contests = [Contest(**c) for c in data]
        contests = [c for c in contests if c.phase in (ContestPhase.BEFORE, ContestPhase.CODING)]
        contests.sort(key=lambda c: c.startTimeSeconds)
        return contests
