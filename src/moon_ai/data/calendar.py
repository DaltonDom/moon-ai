"""CME equity-index session calendar: holidays, early closes and skip rules.

Design rule (docs/design.md, "Backtest realism"): no new trades on CME holiday
sessions, early-close sessions, or the session in which the continuous `.v.0`
contract rolls. Degraded Databento days are skipped too (`quality.py`).

Dates here are CME **trading days** (`sessions.trading_day`): the session that
opens at 18:00 New York the evening before and closes at 17:00 on that date.

The holiday set follows the NYSE calendar, which CME equity-index futures
follow with a trading halt or a full close:

- **closed:** New Year's Day, Good Friday, Christmas.
- **holiday halt** (trading halts at 12:00 CT / 13:00 ET): MLK Day, Presidents'
  Day, Memorial Day, Juneteenth (from 2022), Independence Day, Labor Day,
  Thanksgiving.
- **early close** (12:15 CT / 13:15 ET): the day after Thanksgiving, July 3
  and December 24 when they fall Monday-Thursday.

Weekend holidays move to Friday (Saturday) or Monday (Sunday), except a
Saturday New Year's Day, which is not observed on December 31. Whichever kind
a holiday is, it's a no-new-trades session, so a wrong halt time can't let a
trade through.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, time, timedelta
from typing import Literal

from moon_ai.bars import Bar
from moon_ai.sessions import trading_day

SessionKind = Literal["regular", "weekend", "closed", "holiday_halt", "early_close"]
SkipReason = Literal["weekend", "closed", "holiday_halt", "early_close", "roll", "degraded"]

HOLIDAY_HALT_NY = time(13)
EARLY_CLOSE_NY = time(13, 15)

# One-off closures announced at short notice.
_SPECIAL: dict[date, tuple[SessionKind, str, time | None]] = {
    # NYSE closed; CME equity futures halted early. The exact CME halt time is
    # UNVERIFIED; the session is skipped either way.
    date(2025, 1, 9): ("holiday_halt", "National Day of Mourning (President Carter)", time(9, 30)),
}


@dataclass(frozen=True)
class SessionInfo:
    day: date
    kind: SessionKind
    name: str | None = None
    halt_ny: time | None = None  # when trading halts early, New York time


def easter(year: int) -> date:
    """Gregorian Easter Sunday (anonymous Gregorian algorithm)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    m = (32 + 2 * e + 2 * i - h - k) % 7
    n = (a + 11 * h + 22 * m) // 451
    month, day = divmod(h + m - 7 * n + 114, 31)
    return date(year, month, day + 1)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The n-th `weekday` (Mon=0) of the month; n=-1 for the last one."""
    if n > 0:
        first = date(year, month, 1)
        return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))
    nxt = date(year + (month == 12), month % 12 + 1, 1)
    last = nxt - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _observed(d: date) -> date:
    if d.weekday() == 5:
        return d - timedelta(days=1)
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


def holidays(year: int) -> dict[date, SessionInfo]:
    """Every non-regular weekday session of `year`."""
    out: dict[date, SessionInfo] = {}

    def add(d: date, kind: SessionKind, name: str, halt: time | None = None) -> None:
        if d.year == year and d.weekday() < 5:
            out[d] = SessionInfo(d, kind, name, halt)

    new_year = date(year, 1, 1)
    if new_year.weekday() != 5:  # a Saturday New Year's Day is not observed
        add(_observed(new_year), "closed", "New Year's Day")
    # Next year's New Year's Day observed on this year's Dec 31 never happens (see above).
    add(_nth_weekday(year, 1, 0, 3), "holiday_halt", "Martin Luther King Jr. Day", HOLIDAY_HALT_NY)
    add(_nth_weekday(year, 2, 0, 3), "holiday_halt", "Presidents' Day", HOLIDAY_HALT_NY)
    add(easter(year) - timedelta(days=2), "closed", "Good Friday")
    add(_nth_weekday(year, 5, 0, -1), "holiday_halt", "Memorial Day", HOLIDAY_HALT_NY)
    if year >= 2022:
        add(_observed(date(year, 6, 19)), "holiday_halt", "Juneteenth", HOLIDAY_HALT_NY)
    july4 = _observed(date(year, 7, 4))
    add(july4, "holiday_halt", "Independence Day", HOLIDAY_HALT_NY)
    july3 = date(year, 7, 3)
    if july3.weekday() < 4 and july3 != july4:
        add(july3, "early_close", "Day before Independence Day", EARLY_CLOSE_NY)
    add(_nth_weekday(year, 9, 0, 1), "holiday_halt", "Labor Day", HOLIDAY_HALT_NY)
    thanksgiving = _nth_weekday(year, 11, 3, 4)
    add(thanksgiving, "holiday_halt", "Thanksgiving", HOLIDAY_HALT_NY)
    add(thanksgiving + timedelta(days=1), "early_close", "Day after Thanksgiving", EARLY_CLOSE_NY)
    christmas = _observed(date(year, 12, 25))
    add(christmas, "closed", "Christmas")
    dec24 = date(year, 12, 24)
    if dec24.weekday() < 4 and dec24 != christmas:
        add(dec24, "early_close", "Christmas Eve", EARLY_CLOSE_NY)
    for d, (kind, name, halt) in _SPECIAL.items():
        add(d, kind, name, halt)
    return out


def session_info(day: date) -> SessionInfo:
    """What kind of CME equity-index session `day` is."""
    if day.weekday() >= 5:
        return SessionInfo(day, "weekend")
    return holidays(day.year).get(day, SessionInfo(day, "regular"))


def roll_days(bars: Iterable[Bar]) -> set[date]:
    """Trading days in which a continuous contract rolled (a `roll`-flagged bar)."""
    return {trading_day(b.ts_close) for b in bars if b.roll}


@dataclass(frozen=True)
class SessionCalendar:
    """Answers "may new trades open in this session?" for the trader."""

    rolls: frozenset[date] = frozenset()
    degraded: frozenset[date] = frozenset()

    def skip_reason(self, day: date) -> SkipReason | None:
        kind = session_info(day).kind
        if kind != "regular":
            return kind
        if day in self.rolls:
            return "roll"
        if day in self.degraded:
            return "degraded"
        return None

    def no_new_trades(self, day: date) -> bool:
        return self.skip_reason(day) is not None
