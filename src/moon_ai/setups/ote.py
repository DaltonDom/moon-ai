"""OTE pullback (ict-setup-definitions.md §2.4; config/defaults.toml).

At each bar close inside the window (08:30-11:00 New York by default), on the
current CME session's bars:

1. **Leg:** a displacement candle (body >= k x ATR, with its FVG) whose close
   breaks the latest swing on the other side (BOS/MSS). The leg's origin is the
   extreme from the last opposite swing before the displacement up to it. The
   leg's end is the first swing confirmed after the displacement. The anchors
   are frozen when that swing is confirmed, which is the decision time.
2. **Plan** (long; short mirrors):
   - entry: a limit at `high - ote_entry x (high - low)`, 62% by default
   - stop: `high - ote_stop x (high - low)` minus `stop_offset_ticks` (the
     leg's origin at 100%)
   - target: the leg's high (0%)
3. **Skips:** price already back at the entry by the decision time, or, with
   `require_ote_overlap`, no FVG of the leg overlapping the 62-79% zone. With
   the `bias_gate` rescue trial, a leg against the previous-day-range bias is
   skipped too.

At most one candidate per day; the entry must fill before the window ends.
The OTE levels are still UNVERIFIED against ICT's own material (#28), so
they are logged sweep parameters.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime

from moon_ai.bars import Bar
from moon_ai.config import Config
from moon_ai.engine import Context
from moon_ai.ict.displacement import find_displacements
from moon_ai.ict.fvg import find_fvgs
from moon_ai.ict.swings import find_swings
from moon_ai.sessions import NY, in_window, to_ny, trading_day, window_bounds
from moon_ai.setups.base import Candidate, SetupParams, register
from moon_ai.setups.london import prev_day_range_bias, session_ohlc

FEATURE_SET = "ote-v0"
OTE_ZONE_DEEP = 0.79


@register("ote_pullback")
class OtePullback:
    def __init__(self, params: SetupParams, config: Config, symbol: str = "MNQ.v.0"):
        if params.ote_entry is None or params.ote_stop is None:
            raise ValueError("ote_pullback needs ote_entry and ote_stop")
        self.params = params
        self.config = config
        self.symbol = symbol
        self.window = config.sessions.windows[params.window]
        self.tick = config.instrument(symbol).tick_size
        self._done: set[date] = set()
        self._bias_day: date | None = None
        self._bias: str | None = None

    def scan(self, ctx: Context) -> list[Candidate]:
        now = ctx.now
        if now is None or not in_window(now, self.window):
            return []
        day = trading_day(now)
        if day in self._done:
            return []
        history = ctx.history(self.symbol, 3 * 1440 if self.params.bias_gate else 1600)
        bars = [b for b in history if trading_day(b.ts_close) == day]
        if len(bars) < 3 or bars[-1].ts_close != now:
            return []
        if self.params.bias_gate and self._bias_day != day:
            sessions = session_ohlc(
                [b for b in history if b.instrument_id == bars[-1].instrument_id]
            )
            self._bias_day, self._bias = day, prev_day_range_bias(sessions, day)
        cand = self._find(bars, now, day)
        if cand is None:
            return []
        self._done.add(day)
        return [cand]

    def _find(self, bars: Sequence[Bar], now: datetime, day: date) -> Candidate | None:
        p, ict = self.params, self.config.ict
        swings = find_swings(bars, p.swing_n)
        disps = find_displacements(
            bars,
            self.tick,
            p.displacement_k,
            ict.displacement_atr_period,
            ict.displacement_require_fvg,
        )
        fvgs = find_fvgs(bars, self.tick, ict.fvg_min_size_ticks)
        for d in disps:
            long = d.direction == "bull"
            if p.bias_gate and self._bias is not None and self._bias != d.direction:
                continue
            want = "high" if long else "low"  # the swing the displacement must break
            before = [s for s in swings if s.kind == want and s.known_at <= bars[d.index].ts_open]
            if not before:
                continue
            broken = before[-1]
            close = bars[d.index].close
            if (close <= broken.price) if long else (close >= broken.price):
                continue
            # The leg's end: the first swing confirmed after the displacement, known now.
            end = next(
                (s for s in swings if s.kind == want and s.index >= d.index and s.known_at <= now),
                None,
            )
            if end is None or end.known_at != now:
                continue
            other = "low" if long else "high"
            origins = [s for s in swings if s.kind == other and s.index < d.index]
            start = origins[-1].index if origins else 0
            seg = bars[start : d.index + 1]
            origin = min(b.low for b in seg) if long else max(b.high for b in seg)
            hi, lo = (end.price, origin) if long else (origin, end.price)
            rng = hi - lo
            if rng <= 0 or (p.min_leg_points is not None and rng < p.min_leg_points):
                continue
            sign = 1 if long else -1
            far = hi if long else lo  # the leg's end (0%)
            entry = _round(far - sign * p.ote_entry * rng, self.tick)
            stop = (
                _round(far - sign * p.ote_stop * rng, self.tick)
                - sign * p.stop_offset_ticks * self.tick
            )
            after = bars[end.index + 1 :]
            if any((b.low <= entry) if long else (b.high >= entry) for b in after):
                continue  # already back at the entry when the leg was confirmed
            if p.require_ote_overlap and not _overlap(
                fvgs, d.direction, far, sign, rng, p.ote_entry
            ):
                continue
            ny_date = to_ny(now).date()
            _, window_end = window_bounds(ny_date, self.window)
            return Candidate(
                setup=self.name,
                symbol=self.symbol,
                side="long" if long else "short",
                decision_time=now,
                entry_type="limit",
                entry=entry,
                stop=stop,
                target=far,
                timeout=datetime.combine(ny_date, p.timeout, tzinfo=NY),
                entry_deadline=window_end,
                rule_results={"broke": broken.price, "leg": [lo, hi], "ote": p.ote_entry},
                features={
                    "leg_points": rng,
                    "displacement_atr_mult": d.body / d.atr,
                    "risk_ticks": round(abs(entry - stop) / self.tick),
                    "minutes_into_window": (
                        to_ny(now) - datetime.combine(ny_date, self.window.start, tzinfo=NY)
                    ).total_seconds()
                    / 60,
                },
                feature_set=FEATURE_SET,
            )
        return None

    name = "ote_pullback"


def _overlap(fvgs, direction: str, far: float, sign: int, rng: float, ote: float) -> bool:
    shallow = far - sign * ote * rng
    deep = far - sign * OTE_ZONE_DEEP * rng
    zlo, zhi = min(shallow, deep), max(shallow, deep)
    return any(g.direction == direction and g.low <= zhi and g.high >= zlo for g in fvgs)


def _round(price: float, tick: float) -> float:
    return round(price / tick) * tick
