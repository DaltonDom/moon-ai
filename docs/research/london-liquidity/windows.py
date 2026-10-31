"""Sample definition shared by the download and analysis scripts."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
DATASET = "GLBX.MDP3"
SYMBOL = "MNQ.v.0"
TICK = 0.25

# Windows in New York wall-clock time, [start, end).
WINDOWS = {
    "london": (time(2, 0), time(5, 0)),
    "nyam": (time(9, 30), time(11, 0)),  # NY AM open; contains the 10-11 Silver Bullet
}
SILVER_BULLET = (time(10, 0), time(11, 0))

# Ten recent trading days, all in EDT (US DST ends 2026-11-01), clear of the
# September (MNQU6 -> MNQZ6) and December roll weeks.
TICK_DAYS = [date(2026, 10, d) for d in (16, 19, 20, 21, 22, 23, 26, 27, 28, 29)]


def window_utc(day: date, name: str) -> tuple[datetime, datetime]:
    s, e = WINDOWS[name]
    a = datetime.combine(day, s, tzinfo=NY).astimezone(UTC)
    b = datetime.combine(day, e, tzinfo=NY).astimezone(UTC)
    return a, b


def sample_days() -> list[date]:
    return list(TICK_DAYS)


def _check() -> None:
    assert window_utc(date(2026, 10, 28), "london")[0].hour == 6
    assert window_utc(date(2026, 1, 28), "london")[0].hour == 7
    assert (
        window_utc(date(2026, 10, 28), "nyam")[1] - window_utc(date(2026, 10, 28), "nyam")[0]
    ) == timedelta(minutes=90)


_check()
