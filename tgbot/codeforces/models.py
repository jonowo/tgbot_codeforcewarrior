from datetime import datetime, timedelta, timezone
from enum import Enum
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from .utils import duration

HKT = ZoneInfo("Asia/Hong_Kong")


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
    def start_time(self):
        dt = datetime.utcfromtimestamp(self.startTimeSeconds)
        return dt.replace(tzinfo=timezone.utc).astimezone(HKT)

    @property
    def end_time(self):
        return self.start_time + timedelta(seconds=self.durationSeconds)

    def __str__(self):
        text = self.start_time.strftime("%b {} (%a) %H:%M").format(
            self.start_time.day)
        text += self.end_time.strftime(" - %H:%M\n")
        now = datetime.now(HKT)
        if now < self.start_time:
            text += f"Starts in {duration(self.start_time - now)}\n"
        else:
            text += f"Ends in {duration(self.end_time - now)}\n"
        text += f"<a href='https://codeforces.com/contests/{self.id}'>{self.name}</a>"
        return text
