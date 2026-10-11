"""Small helpers shared by every module."""
import hashlib
import json
from datetime import date, datetime, timedelta, timezone

# India has one timezone and no daylight saving.
IST = timezone(timedelta(hours=5, minutes=30))


def today_ist(now: datetime | None = None) -> date:
    now = now or datetime.now(timezone.utc)
    return now.astimezone(IST).date()


def now_iso() -> str:
    return datetime.now(IST).isoformat(timespec="seconds")


def token_hash(token: str) -> str:
    """What logs show instead of a field token."""
    return hashlib.sha256(token.encode()).hexdigest()[:8]


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def loads(text: str):
    return json.loads(text)
