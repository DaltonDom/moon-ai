"""New York session time: window membership, window bounds and the CME trading day.

All session logic runs in America/New_York wall-clock time; timestamps
elsewhere in the system are timezone-aware UTC. `zoneinfo` handles DST, so a
window such as 10:00-11:00 stays at 10:00-11:00 New York time all year.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from moon_ai.config import Window

NY = ZoneInfo("America/New_York")
TRADING_DAY_START = time(18)


def to_ny(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware (UTC); got a naive datetime")
    return ts.astimezone(NY)


def in_window(ts: datetime, window: Window) -> bool:
    """True if `ts` falls in [window.start, window.end) New York time.

    For anything confirmed on a bar's close, pass the bar's close time: a bar
    stamped 10:59 closes at 11:00, which is outside 10:00-11:00.
    """
    t = to_ny(ts).time()
    if window.start < window.end:
        return window.start <= t < window.end
    # Crosses midnight (or spans the full day when start == end).
    return t >= window.start or t < window.end


def window_bounds(day: date, window: Window) -> tuple[datetime, datetime]:
    """UTC [start, end) of `window` starting on New York calendar date `day`.

    A window whose end is not after its start ends on the next calendar day.
    On the spring-forward date a wall time inside the skipped hour resolves
    with the pre-transition offset (zoneinfo's fold=0 rule).
    """
    start = datetime.combine(day, window.start, tzinfo=NY)
    end_day = day if window.start < window.end else day + timedelta(days=1)
    end = datetime.combine(end_day, window.end, tzinfo=NY)
    return start.astimezone(UTC), end.astimezone(UTC)


def trading_day(ts: datetime) -> date:
    """CME Globex trading date: a session opens at 18:00 New York the day before."""
    ny = to_ny(ts)
    if ny.time() >= TRADING_DAY_START:
        return ny.date() + timedelta(days=1)
    return ny.date()
