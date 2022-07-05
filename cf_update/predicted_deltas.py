from html.parser import HTMLParser
from typing import Optional

from aiocache import cached
from aiohttp import web


class Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parsing = False
        self.data = {}
        self.row = []
        self.content = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        if tag == "tbody":
            self.parsing = True
        elif tag == "tr":
            self.row = []
        elif tag == "td":
            self.content = ""

    def handle_data(self, data: str) -> None:
        if self.parsing:
            self.content += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self.parsing:
            self.row.append(self.content.strip())
        elif tag == "tr" and self.parsing:
            change = self.row[2]
            if not change.startswith("-"):
                change = f"+{change}"
            self.data[self.row[1]] = (int(self.row[0]), self.row[1], change)
        elif tag == "tbody":
            self.parsing = False


@cached(ttl=60)
async def get_predicted_deltas(app: web.Application, contest_id: int) -> dict[str, tuple[int, str, int]]:
    parser = Parser()
    resp = await app["session"].get(
        "https://cf-predictor-frontend.herokuapp.com/roundResults.jsp",
        params={"contestId": contest_id}
    )
    async for data in resp.content.iter_chunked(32768):
        parser.feed(data.decode())

    return parser.data
