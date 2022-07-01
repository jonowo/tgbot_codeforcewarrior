from datetime import datetime, timezone

from pydantic import BaseModel

from .utils import HKT, RESOURCES, duration, hkt_now


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
        return f"<a href='{self.href}'>{self.event}</a>"

    def __str__(self) -> str:
        text = self.start_time.strftime("%b {} (%a) %H:%M").format(self.start_time.day)
        text += self.end_time.strftime(" - %H:%M HKT\n")

        text += f"{RESOURCES[self.resource]}: {self.linked_name}\n"

        now = hkt_now()
        if now < self.start_time:
            text += f"Starts in {duration(self.start_time - now)}"
        else:
            text += f"Ends in {duration(self.end_time - now)}"

        return text
