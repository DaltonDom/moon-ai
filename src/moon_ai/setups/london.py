"""London sweep-and-reverse (ict-setup-definitions.md §2.3; config/defaults.toml).

The London killzone (02:00-05:00 New York) Judas swing: price raids one side
of the Asian range (20:00-00:00) against the day's bias, shifts structure the
other way and is traded back toward the opposite side of the Asian range.
It reuses the Silver Bullet machinery with three additions:

- **Bias** (previous-day-range rule, research §1.4): if the last completed
  session closed above the session before's high, the bias is bullish, so
  only a sweep of the Asian *low* followed by a long counts (bearish
  mirrors). An inside close gives no bias, and either side qualifies. The
  `bias_gate = false` rescue trial drops the rule.
- **Power of 3** (`po3_filter`): a long's sweep must go below the 00:00 New
  York open, and a short's above it.
- **Prior-day pools** (rescue trial `also_prior_day_pools`): the last
  completed session's high and low join the Asian range.

The trader skips London stops under 40 ticks (#8), and the time-out is 09:30.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime, time
from typing import Literal

from moon_ai.bars import Bar
from moon_ai.ict.liquidity import Level
from moon_ai.ict.structure import MarketStructureShift
from moon_ai.sessions import NY, trading_day
from moon_ai.setups.base import register
from moon_ai.setups.silver_bullet import SilverBullet

Bias = Literal["bull", "bear"] | None


def session_ohlc(bars: Sequence[Bar]) -> dict[date, tuple[float, float, float, float]]:
    """(open, high, low, close) per CME trading day, from 1-minute bars."""
    out: dict[date, list[float]] = {}
    for b in bars:
        d = trading_day(b.ts_close)
        if d not in out:
            out[d] = [b.open, b.high, b.low, b.close]
        else:
            o = out[d]
            o[1], o[2], o[3] = max(o[1], b.high), min(o[2], b.low), b.close
    return {d: (v[0], v[1], v[2], v[3]) for d, v in out.items()}


def prev_day_range_bias(sessions: dict[date, tuple[float, float, float, float]], day: date) -> Bias:
    """Bias for `day` from the two completed sessions before it."""
    before = sorted(d for d in sessions if d < day)
    if len(before) < 2:
        return None
    _, h2, l2, _ = sessions[before[-2]]
    _, _, _, c1 = sessions[before[-1]]
    if c1 > h2:
        return "bull"
    if c1 < l2:
        return "bear"
    return None


@register("london_sweep_and_reverse")
class LondonSweepAndReverse(SilverBullet):
    supports_bias = True
    extra_pools = frozenset({"prior_day"})
    history_bars = 3 * 1440  # two prior sessions for the bias, plus today

    def _prepare(self, history: Sequence[Bar], bars: Sequence[Bar], day: date) -> None:
        if getattr(self, "_prepared_day", None) == day:
            return
        sessions = session_ohlc([b for b in history if b.instrument_id == bars[-1].instrument_id])
        self._prepared_day = day
        self._bias: Bias = prev_day_range_bias(sessions, day)
        self._midnight: float | None = _midnight_open(bars, day)
        prior = [d for d in sorted(sessions) if d < day]
        self._prior: list[Level] = []
        if "prior_day" in self.params.pools and prior:
            _, h, lo, _ = sessions[prior[-1]]
            start = bars[0].ts_open
            inst = bars[-1].instrument_id
            self._prior = [
                Level("high", h, start, "prior_day", inst),
                Level("low", lo, start, "prior_day", inst),
            ]

    def _accept(self, mss: MarketStructureShift, bars: Sequence[Bar]) -> bool:
        long = mss.direction == "bull"
        if self.params.bias_gate and self._bias is not None and self._bias != mss.direction:
            return False
        if self.params.po3_filter:
            if self._midnight is None:
                return False
            extreme = mss.sweep.extreme
            if (extreme >= self._midnight) if long else (extreme <= self._midnight):
                return False
        return True

    def _extra_levels(self) -> list[Level]:
        return list(self._prior)


def _midnight_open(bars: Sequence[Bar], day: date) -> float | None:
    """Open of the 00:00 New York bar of the calendar date `day` (the "true day open")."""
    target = datetime.combine(day, time(0), tzinfo=NY).astimezone(UTC)
    for b in bars:
        if b.ts_open == target:
            return b.open
        if b.ts_open > target:
            return b.open  # first bar after midnight if the 00:00 bar is missing
    return None
