import requests

from .models import Contest, ContestPhase


class CodeforcesError(Exception):
    pass


class CodeforcesAPI:
    def __init__(self):
        self.base_url = "https://codeforces.com/api"
        self.session = requests.Session()

    def _request(self, endpoint, *args, **kwargs):
        resp = self.session.get(f"{self.base_url}/{endpoint}", *args, **kwargs)
        resp.raise_for_status()
        if "Codeforces is temporarily unavailable." in resp.text:
            raise CodeforcesError("Codeforces is temporarily unavailable.")

        data = resp.json()
        if data["status"] == "FAILED":
            raise CodeforcesError(data["comment"])
        return data["result"]

    def get_contests(self):
        data = self._request("contest.list", params={"gym": "false"})
        contests = [Contest(**c) for c in data]
        contests = [c for c in contests if c.phase in (ContestPhase.BEFORE, ContestPhase.CODING)]
        contests.sort(key=lambda c: c.startTimeSeconds)
        return contests
