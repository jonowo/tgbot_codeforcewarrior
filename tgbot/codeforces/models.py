from datetime import datetime, timedelta
from enum import Enum
from string import capwords
from typing import Optional

from pydantic import BaseModel

from .utils import HKT, duration, utc_timestamp_to_hkt


class User(BaseModel):
    handle: str
    rating: Optional[int] = None
    rank: Optional[str] = None
    maxRating: Optional[int] = None
    maxRank: Optional[str] = None

    @property
    def url(self):
        return f"https://codeforces.com/profile/{self.handle}"

    def __str__(self):
        text = f"Handle: <a href='{self.url}'>{self.handle}</a>\n"
        if self.rating:
            text += f"Rating: {self.rating}, {capwords(self.rank)}\n"
            text += f"Peak rating: {self.maxRating}, {capwords(self.maxRank)}"
        else:
            text += "Unrated"
        return text


class Problem(BaseModel):
    contestId: int
    index: str
    name: str
    rating: Optional[int] = None
    tags: list[str]

    @property
    def id(self) -> str:
        return f"{self.contestId}{self.index}"

    @property
    def url(self) -> str:
        return f"https://codeforces.com/problemset/problem/{self.contestId}/{self.index}"

    @property
    def linked_name(self) -> str:
        return f"<a href='{self.url}'>{self.id} - {self.name}</a>"

    def __str__(self):
        text = self.linked_name + "\n"
        text += f"Tags: {', '.join(self.tags)}\n"
        text += f"Rating: {self.rating}"
        return text


class ParticipantType(str, Enum):
    CONTESTANT = "CONTESTANT"
    PRACTICE = "PRACTICE"
    VIRTUAL = "VIRTUAL"
    MANAGER = "MANAGER"
    OUT_OF_COMPETITION = "OUT_OF_COMPETITION"


class Party(BaseModel):
    contestId: int
    members: list[User]
    participantType: ParticipantType
    teamId: Optional[int] = None

    def not_team(self) -> bool:
        return self.teamId is None


class Submission(BaseModel):
    id: int
    contestId: int
    creationTimeSeconds: int
    problem: Problem
    author: Party
    programmingLanguage: str
    verdict: Optional[str] = None
    testset: str
    passedTestCount: int

    @property
    def time(self) -> datetime:
        return utc_timestamp_to_hkt(self.creationTimeSeconds)

    def get_author(self) -> Optional[User]:
        if self.author.not_team():
            return self.author.members[0]


class ContestScoring(str, Enum):
    CF = "CF"
    IOI = "IOI"
    ICPC = "ICPC"


class ContestPhase(str, Enum):
    BEFORE = "BEFORE"
    CODING = "CODING"
    PENDING_SYSTEM_TEST = "PENDING_SYSTEM_TEST"
    SYSTEM_TEST = "SYSTEM_TEST"
    FINISHED = "FINISHED"


class Contest(BaseModel):
    id: int
    name: str
    type: ContestScoring
    phase: ContestPhase
    durationSeconds: int
    startTimeSeconds: int

    @property
    def start_time(self) -> datetime:
        return utc_timestamp_to_hkt(self.startTimeSeconds)

    @property
    def end_time(self) -> datetime:
        return self.start_time + timedelta(seconds=self.durationSeconds)

    @property
    def url(self) -> str:
        return f"https://codeforces.com/contests/{self.id}"

    def __str__(self):
        text = self.start_time.strftime("%b {} (%a) %H:%M").format(
            self.start_time.day)
        text += self.end_time.strftime(" - %H:%M\n")

        now = datetime.now(HKT)
        if now < self.start_time:
            text += f"Starts in {duration(self.start_time - now)}\n"
        else:
            text += f"Ends in {duration(self.end_time - now)}\n"

        text += f"<a href='{self.url}'>{self.name}</a>"
        return text
