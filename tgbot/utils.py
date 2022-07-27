from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

HKT = ZoneInfo("Asia/Hong_Kong")

RESOURCES = {
    "codeforces.com": "Codeforces",
    "leetcode.com": "LeetCode",
    "codingcompetitions.withgoogle.com": "Google",
    "facebook.com/hackercup": "Meta",
    "stats.ioinformatics.org": "IOI",
    "icpc.global": "ICPC"
}


def plural(unit: int) -> str:
    return "" if unit == 1 else "s"


def duration(td: timedelta) -> str:
    seconds = int(td.total_seconds())
    days = seconds // (24 * 60 * 60)
    seconds %= 24 * 60 * 60
    hours = seconds // (60 * 60)
    seconds %= 60 * 60
    minutes = seconds // 60
    seconds %= 60

    res = []
    if days:
        res.append(f"{days} day{plural(days)}")
    if hours:
        res.append(f"{hours} hour{plural(hours)}")
    if minutes:
        res.append(f"{minutes} minute{plural(minutes)}")
    if seconds:
        res.append(f"{seconds} second{plural(seconds)}")

    return " ".join(res[:2])


def hkt_now() -> datetime:
    return datetime.now(HKT)


def utc_timestamp_to_hkt(timestamp: int) -> datetime:
    dt = datetime.utcfromtimestamp(timestamp)
    return dt.replace(tzinfo=timezone.utc).astimezone(HKT)
