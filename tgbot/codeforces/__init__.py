import requests

from .models import Contest, ContestPhase


class CodeforcesAPI:
    def __init__(self):
        self.base_url = "https://codeforces.com/api"
        self.session = requests.Session()

    def get_contests(self):
        resp = self.session.get(f"{self.base_url}/contest.list?gym=false")
        resp.raise_for_status()
        data = resp.json()["result"]
        contests = [Contest(**c) for c in data]
        contests = [c for c in contests if c.phase in (ContestPhase.BEFORE, ContestPhase.CODING)]
        contests.sort(key=lambda c: c.startTimeSeconds)
        return contests
