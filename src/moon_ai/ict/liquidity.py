"""Liquidity levels (pools) and sweeps of them.

Levels: confirmed swing highs/lows, session-window highs/lows (e.g. the Asian
range) and prior trading-day highs/lows. A sweep is a bar trading through a
level, followed by a close back on the original side within m bars.

`find_sweeps` scans forward from each level, so it costs O(levels x bars) in
the worst case. It's meant for session-sized inputs; a vectorized version for
full-history sweeps is follow-up work.
"""

from __future__ import annotations

import bisect
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Literal

from moon_ai.bars import Bar
from moon_ai.config import Window
from moon_ai.ict.swings import Swing
from moon_ai.sessions import to_ny, window_bounds

TRADING_DAY = Window(time(18), time(17))


@dataclass(frozen=True)
class Level:
    kind: Literal["high", "low"]  # high = buy-side liquidity above, low = sell-side below
    price: float
    known_at: datetime
    source: str  # "swing", "asia", "day", ...
    instrument_id: int


@dataclass(frozen=True)
class Sweep:
    level: Level
    index: int  # bar that first traded through the level
    extreme: float  # furthest price reached beyond the level before the close back
    known_at: datetime  # close of the close-back bar (or of the trade-through bar)

    @property
    def kind(self) -> Literal["high", "low"]:
        return self.level.kind


def swing_levels(swings: Iterable[Swing]) -> list[Level]:
    return [Level(s.kind, s.price, s.known_at, "swing", s.instrument_id) for s in swings]


def window_levels(bars: Sequence[Bar], window: Window, source: str) -> list[Level]:
    """High and low of each completed occurrence of `window` (New York time).

    A bar counts if its whole interval lies inside the window. The levels are
    known when the window ends, and only windows that ended by the last bar's
    close are reported. A window that spans a contract roll is skipped.
    """
    if not bars:
        return []
    groups: dict[tuple[datetime, datetime], list[Bar]] = defaultdict(list)
    for b in bars:
        bounds = _window_of(b, window)
        if bounds is not None:
            groups[bounds].append(b)

    last_close = bars[-1].ts_close
    levels: list[Level] = []
    for (_, end), members in sorted(groups.items()):
        if end > last_close or len({b.instrument_id for b in members}) != 1:
            continue
        inst = members[0].instrument_id
        levels.append(Level("high", max(b.high for b in members), end, source, inst))
        levels.append(Level("low", min(b.low for b in members), end, source, inst))
    return levels


def prior_day_levels(bars: Sequence[Bar]) -> list[Level]:
    """High and low of each completed CME trading day (18:00-17:00 New York)."""
    return window_levels(bars, TRADING_DAY, "day")


def _window_of(b: Bar, window: Window) -> tuple[datetime, datetime] | None:
    day: date = to_ny(b.ts_open).date()
    for d in (day, day - timedelta(days=1)):
        start, end = window_bounds(d, window)
        if start <= b.ts_open and b.ts_close <= end:
            return start, end
    return None


def find_sweeps(
    bars: Sequence[Bar],
    levels: Iterable[Level],
    tick: float,
    close_back_bars: int = 1,
    require_close_back: bool = True,
    min_penetration_ticks: int = 1,
) -> list[Sweep]:
    """First trade-through of each level by a bar that opened after the level
    was known, by at least `min_penetration_ticks`. With `require_close_back`,
    one of that bar and the next `close_back_bars - 1` bars must close back on
    the level's original side; otherwise it was a breakout. Either way the
    level is spent after its first trade-through. A level dies at a roll."""
    opens = [b.ts_open for b in bars]
    pen = min_penetration_ticks * tick
    sweeps: list[Sweep] = []
    for level in levels:
        sign = 1 if level.kind == "high" else -1
        start = bisect.bisect_left(opens, level.known_at)
        for j in range(start, len(bars)):
            b = bars[j]
            if b.instrument_id != level.instrument_id:
                break
            beyond = b.high if sign > 0 else b.low
            if sign * (beyond - level.price) < pen:
                continue
            sweep = _confirm(bars, j, level, sign, close_back_bars, require_close_back)
            if sweep is not None:
                sweeps.append(sweep)
            break
    return sorted(sweeps, key=lambda s: (s.known_at, s.index))


def _confirm(
    bars: Sequence[Bar], j: int, level: Level, sign: int, m: int, require_close_back: bool
) -> Sweep | None:
    if not require_close_back:
        extreme = bars[j].high if sign > 0 else bars[j].low
        return Sweep(level, j, extreme, bars[j].ts_close)
    extreme = level.price
    for k in range(j, min(j + max(m, 1), len(bars))):
        b = bars[k]
        if b.instrument_id != level.instrument_id:
            return None
        extreme = max(extreme, b.high) if sign > 0 else min(extreme, b.low)
        if sign * (b.close - level.price) < 0:
            return Sweep(level, j, extreme, b.ts_close)
    return None
