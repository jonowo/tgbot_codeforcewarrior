from datetime import datetime, timedelta
from enum import Enum
from string import capwords
from typing import Optional

from pydantic import BaseModel

from tgbot.utils import duration, hkt_now, utc_timestamp_to_hkt


class CodeforcesError(Exception):
    pass


class User(BaseModel):
    handle: str
    rating: Optional[int] = None
    rank: Optional[str] = None
    maxRating: Optional[int] = None
    maxRank: Optional[str] = None

    def __init__(self, **data):
        super().__init__(**data)
        if self.rank:
            self.rank = capwords(self.rank)
            self.maxRank = capwords(self.maxRank)

    @property
    def url(self):
        return f"https://codeforces.com/profile/{self.handle}"

    @property
    def linked_name(self) -> str:
        return f"<a href='{self.url}'>{self.handle}</a>"

    def __str__(self) -> str:
        text = f"Handle: {self.linked_name}\n"
        if self.rating:
            text += f"Rating: {self.rating}, {self.rank}\n"
            text += f"Peak rating: {self.maxRating}, {self.maxRank}"
        else:
            text += "Unrated"
        return text


class Problem(BaseModel):
    contestId: Optional[int]
    index: Optional[str]
    problemsetName: Optional[str]
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

    def __str__(self) -> str:
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
    contestId: Optional[int]
    members: list[User]
    participantType: ParticipantType
    teamId: Optional[int] = None

    def not_team(self) -> bool:
        return self.teamId is None


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

    @property
    def linked_name(self) -> str:
        return f"<a href='{self.url}'>{self.name}</a>"

    def __str__(self) -> str:
        text = self.start_time.strftime("%b {} (%a) %H:%M").format(self.start_time.day)
        text += self.end_time.strftime(" - %H:%M HKT\n")

        text += f"{self.linked_name}\n"

        now = hkt_now()
        if now < self.start_time:
            text += f"Starts in {duration(self.start_time - now)}"
        else:
            text += f"Ends in {duration(self.end_time - now)}"

        return text


class Submission(BaseModel):
    id: int
    contestId: Optional[int]
    creationTimeSeconds: int
    problem: Problem
    author: Party
    programmingLanguage: str
    verdict: Optional[str] = None
    testset: str
    passedTestCount: int

    def __eq__(self, other: "Submission") -> bool:
        return self.id == other.id and self.verdict == other.verdict and self.testset == other.testset

    @property
    def time(self) -> datetime:
        return utc_timestamp_to_hkt(self.creationTimeSeconds)

    def get_author(self) -> Optional[User]:
        if self.author.not_team():
            return self.author.members[0]

    def is_fst(self, contest: Contest) -> bool:
        """Check if the submission failed main tests after passing pretests during contest."""
        return (
                contest.type in (ContestScoring.CF, ContestScoring.IOI)
                and self.author.participantType in (ParticipantType.CONTESTANT, ParticipantType.OUT_OF_COMPETITION)
                and self.testset.startswith("TESTS")
                and self.verdict is not None
                and self.verdict not in ("OK", "TESTING", "CHALLENGED", "SKIPPED", "PARTIAL")
        )

    def should_notify(self, contest: Contest) -> bool:
        """Determine if the submission should be announced in group."""
        if self.verdict == "TESTING":
            return False

        if self.verdict in ("OK", "CHALLENGED"):
            return True

        return self.is_fst(contest)

    def __str__(self) -> str:
        """Group notification for submission update."""
        text = self.get_author().linked_name + " "
        if self.verdict == "OK":
            if self.testset == "PRETESTS":
                text += f"passed all {self.passedTestCount} pretests on {self.problem.linked_name}"
            else:
                text += f"passed all {self.passedTestCount} main tests on {self.problem.linked_name}"
        elif self.verdict == "CHALLENGED":
            text += f"was hacked on {self.problem.linked_name}"
        else:
            text += f"FSTed on {self.problem.linked_name}"

        return text


class RatingChange(BaseModel):
    contestId: int
    contestName: str
    handle: str
    rank: int
    ratingUpdateTimeSeconds: int
    oldRating: int
    newRating: int

    @property
    def delta(self) -> str:
        change = str(self.newRating - self.oldRating)
        if not change.startswith("-"):
            change = f"+{change}"
        return change

    def get_table_row(self) -> tuple[int, str, str]:
        return self.rank, self.handle, self.delta
