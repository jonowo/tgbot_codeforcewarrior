from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional
from zoneinfo import ZoneInfo
from string import capwords

from pydantic import BaseModel

from .utils import duration

HKT = ZoneInfo("Asia/Hong_Kong")


class User(BaseModel):
    handle: str
    rating: Optional[int] = None
    rank: Optional[str] = None
    maxRating: Optional[int] = None
    maxRank: Optional[str] = None
    lastOnlineTimeSeconds: int
    registrationTimeSeconds: int

    @property
    def url(self):
        return f"https://codeforces.com/profile/{self.handle}"

    def __str__(self):
        text = f"Handle: <a href='{self.url}'>{self.handle}</a>\n"
        if self.rating:
            text += f"Rating: {self.rating}, {capwords(self.rank)}\n"
            text += f"Peak rating: {self.maxRating}, {capwords(self.maxRank)}"
        else:
            text += "No rating"
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

    def __str__(self):
        text = f"<a href='{self.url}'>{self.id} - {self.name}</a>\n"
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


class Submission(BaseModel):
    id: int
    contestId: int
    creationTimeSeconds: int
    problem: Problem
    author: Party
    programmingLanguage: str
    verdict: Optional[str] = None

    def get_author(self) -> Optional[User]:
        if len(self.author.members) == 1:
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
        dt = datetime.utcfromtimestamp(self.startTimeSeconds)
        return dt.replace(tzinfo=timezone.utc).astimezone(HKT)

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
