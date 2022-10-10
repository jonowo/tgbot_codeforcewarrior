from datetime import datetime, timedelta, timezone

from pydantic import BaseModel

from tgbot.utils import HKT, RESOURCES, duration, hkt_now


class ClistError(Exception):
    pass


class ContestInfo(BaseModel):
    event: str
    href: str
    resource: str
    start: str
    end: str

    @property
    def start_time(self) -> datetime:
        dt = datetime.strptime(self.start, "%Y-%m-%dT%H:%M:%S")
        return dt.replace(tzinfo=timezone.utc).astimezone(HKT)

    @property
    def end_time(self) -> datetime:
        dt = datetime.strptime(self.end, "%Y-%m-%dT%H:%M:%S")
        return dt.replace(tzinfo=timezone.utc).astimezone(HKT)

    @property
    def linked_name(self) -> str:
        return f"{RESOURCES[self.resource]}: <a href='{self.href}'>{self.event}</a>"

    def __str__(self) -> str:
        text = self.start_time.strftime("%b {} (%a) %H:%M - ").format(self.start_time.day)
        if self.end_time - self.start_time >= timedelta(days=1):
            text += self.end_time.strftime("%b {} (%a) %H:%M").format(self.end_time.day)
        else:
            text += self.end_time.strftime("%H:%M")
        text += " HKT\n"

        text += f"{self.linked_name}\n"

        now = hkt_now()
        if now < self.start_time:
            text += f"Starts in {duration(self.start_time - now)}"
        else:
            text += f"Ends in {duration(self.end_time - now)}"

        return text

    def can_join(self, other: "ContestInfo") -> bool:
        return (
                self.resource == other.resource
                and self.start_time == other.start_time
                and self.end_time == other.end_time
        )

    def join_str(self, other: "ContestInfo") -> str:
        text = self.start_time.strftime("%b {} (%a) %H:%M - ").format(self.start_time.day)
        if self.end_time - self.start_time >= timedelta(days=1):
            text += self.end_time.strftime("%b {} (%a) %H:%M").format(self.end_time.day)
        else:
            text += self.end_time.strftime("%H:%M")
        text += " HKT\n"

        text += f"{self.linked_name}\n"
        text += f"{other.linked_name}\n"

        now = hkt_now()
        if now < self.start_time:
            text += f"Starts in {duration(self.start_time - now)}"
        else:
            text += f"Ends in {duration(self.end_time - now)}"

        return text
