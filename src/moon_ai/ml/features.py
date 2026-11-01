"""Feature vector v1 for the ML filter (design.md, "ML filter: features and labels").

Everything is frozen at the candidate's decision time. The builder trims its
inputs itself (`bars` to closes at or before the decision; `daily` to
sessions before the decision's trading day; only scheduled news), so passing
it more data can't leak the future. CI checks that with a truncation test.

Sizes are in ticks or multiples of ATR, never absolute prices.

**Deferred** (needs MES bars beside MNQ in the run): the SMT divergence flag.
The other v1 groups are built:

- context
- bias proxies (previous-day range, weekly expansion, midnight open,
  premium/discount)
- geometry, volatility regime, news, prior sessions and volume
"""

from __future__ import annotations

import bisect
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from moon_ai.bars import Bar
from moon_ai.config import Config, Window
from moon_ai.data.news import NewsEvent
from moon_ai.sessions import NY, in_window, to_ny, trading_day
from moon_ai.setups.base import Candidate
from moon_ai.setups.london import prev_day_range_bias
from moon_ai.setups.model_2022 import weekly_expansion

FEATURE_SET = "v1"
SETUP_CODES = {
    "ny_am_silver_bullet": 0,
    "ny_pm_silver_bullet": 1,
    "london_sweep_and_reverse": 2,
    "ote_pullback": 3,
    "ict_2022_model": 4,
}
EVENT_FLAGS = {"FOMC_STATEMENT": "fomc", "CPI": "cpi", "NFP": "nfp"}


@dataclass(frozen=True)
class Daily:
    """One completed CME session."""

    day: date
    open: float
    high: float
    low: float
    close: float


def daily_from_bars(bars: Sequence[Bar]) -> list[Daily]:
    out: dict[date, list[float]] = {}
    for b in bars:
        d = trading_day(b.ts_close)
        if d not in out:
            out[d] = [b.open, b.high, b.low, b.close]
        else:
            o = out[d]
            o[1], o[2], o[3] = max(o[1], b.high), min(o[2], b.low), b.close
    return [Daily(d, *v) for d, v in sorted(out.items())]


def _atr(
    highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], n: int = 14
) -> float | None:
    if len(highs) < n + 1:
        return None
    trs = [
        max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        for i in range(len(highs) - n, len(highs))
    ]
    return sum(trs) / n


def _align(bias: str | None, side: str) -> int:
    if bias is None:
        return 0
    return 1 if (bias == "bull") == (side == "long") else -1


def build(
    cand: Candidate,
    bars: Sequence[Bar],
    daily: Sequence[Daily],
    news: Sequence[NewsEvent],
    config: Config,
    window: Window,
) -> dict[str, Any]:
    t = cand.decision_time
    day = trading_day(t)
    bars = [b for b in bars if b.ts_close <= t and b.symbol == cand.symbol]
    past = [d for d in daily if d.day < day]
    tick = config.instrument(cand.symbol).tick_size
    ny = to_ny(t)
    sign = 1 if cand.side == "long" else -1
    entry = cand.entry if cand.entry is not None else (bars[-1].close if bars else cand.stop)
    f: dict[str, Any] = {}

    # Context
    f["setup"] = SETUP_CODES.get(cand.setup, -1)
    f["minute_of_day"] = ny.hour * 60 + ny.minute
    f["day_of_week"] = ny.weekday()
    start = datetime.combine(ny.date(), window.start, tzinfo=NY)
    if start > t:
        start -= timedelta(days=1)
    f["minutes_into_window"] = (t - start).total_seconds() / 60

    # Volatility
    today = [b for b in bars if trading_day(b.ts_close) == day]
    atr1 = _atr(
        [b.high for b in bars[-15:]], [b.low for b in bars[-15:]], [b.close for b in bars[-15:]]
    )
    f["atr1m_ticks"] = atr1 / tick if atr1 else None
    f["atr1m_vs_20d_same_time"] = _atr_vs_history(bars, t, atr1)
    d_atr = _atr([d.high for d in past], [d.low for d in past], [d.close for d in past])
    f["prior_day_range_atr"] = (past[-1].high - past[-1].low) / d_atr if past and d_atr else None
    f["daily_atr_pct_252"] = _atr_percentile(past)

    # Geometry
    stop_d, tgt_d = abs(entry - cand.stop), abs(cand.target - entry)
    f["stop_ticks"] = stop_d / tick
    f["target_ticks"] = tgt_d / tick
    f["stop_atr"] = stop_d / atr1 if atr1 else None
    f["target_atr"] = tgt_d / atr1 if atr1 else None
    f["planned_rr"] = tgt_d / stop_d if stop_d else None
    for k, v in cand.features.items():
        if isinstance(v, int | float):
            f[f"setup_{k}"] = v

    # Bias proxies: +1 aligned with the trade, -1 against, 0 none
    sessions = {d.day: (d.open, d.high, d.low, d.close) for d in past}
    week_bars = [b for b in bars if trading_day(b.ts_close) > day - timedelta(days=14)]
    midnight = next(
        (
            b.open
            for b in today
            if to_ny(b.ts_open).time() >= time(0) and to_ny(b.ts_open).date() == ny.date()
        ),
        None,
    )
    rng20 = past[-20:]
    pd_mid = (max(d.high for d in rng20) + min(d.low for d in rng20)) / 2 if rng20 else None
    biases = {
        "bias_prev_day_range": prev_day_range_bias(sessions, day),
        "bias_weekly_expansion": weekly_expansion(week_bars, day),
        "bias_midnight_open": None
        if midnight is None or not bars
        else (
            "bull" if bars[-1].close > midnight else "bear" if bars[-1].close < midnight else None
        ),
        "bias_premium_discount": None
        if pd_mid is None
        else ("bull" if entry < pd_mid else "bear" if entry > pd_mid else None),
    }
    for k, b in biases.items():
        f[k] = _align(b, cand.side)
    f["bias_agree_count"] = sum(1 for k in biases if f[k] == 1)

    # Prior sessions
    if past and d_atr:
        prev = past[-1]
        f["prior_day_pos_pct"] = (
            (entry - prev.low) / (prev.high - prev.low) if prev.high > prev.low else None
        )
        for name, w, end in (
            ("asia", Window(time(20), time(0)), time(0)),
            ("london", Window(time(2), time(5)), time(5)),
        ):
            # Only a window that has closed: a still-forming range is the current
            # session's range, which is banned.
            closed = datetime.combine(ny.date(), end, tzinfo=NY) <= t
            rb = [b for b in today if in_window(b.ts_close, w)] if closed else []
            f[f"{name}_range_atr"] = (
                (max(b.high for b in rb) - min(b.low for b in rb)) / d_atr if rb else None
            )
        f["dist_prior_day_opposing_atr"] = (
            (prev.high - entry) if sign > 0 else (entry - prev.low)
        ) / d_atr
    else:
        f.update(
            prior_day_pos_pct=None,
            asia_range_atr=None,
            london_range_atr=None,
            dist_prior_day_opposing_atr=None,
        )

    # News (scheduled only; unscheduled events can't be known in advance)
    sched = sorted(e.at for e in news if e.scheduled)
    i = bisect.bisect_right(sched, t)
    f["min_to_next_event"] = (sched[i] - t).total_seconds() / 60 if i < len(sched) else None
    f["min_since_last_event"] = (t - sched[i - 1]).total_seconds() / 60 if i > 0 else None
    todays = {e.event_type for e in news if e.scheduled and to_ny(e.at).date() == ny.date()}
    for ev, name in EVENT_FLAGS.items():
        f[f"event_day_{name}"] = int(ev in todays)
    f["event_day_other"] = int(bool(todays - set(EVENT_FLAGS)))

    # Volume: the decision bar vs the 20-session median for that minute
    f["volume_vs_20d_same_minute"] = _volume_vs_history(bars, t)
    return f


def _same_minute(bars: Sequence[Bar], t: datetime) -> list[Bar]:
    ny = to_ny(t)
    hm = (ny.hour, ny.minute)
    return [
        b
        for b in bars
        if trading_day(b.ts_close) < trading_day(t)
        and (to_ny(b.ts_close).hour, to_ny(b.ts_close).minute) == hm
    ][-20:]


def _volume_vs_history(bars: Sequence[Bar], t: datetime) -> float | None:
    hist = _same_minute(bars, t)
    if not hist or not bars:
        return None
    med = statistics.median(b.volume for b in hist)
    return bars[-1].volume / med if med else None


def _atr_vs_history(bars: Sequence[Bar], t: datetime, atr1: float | None) -> float | None:
    if atr1 is None:
        return None
    idx = {b.ts_close: i for i, b in enumerate(bars)}
    vals = []
    for b in _same_minute(bars, t):
        i = idx[b.ts_close]
        if i >= 15:
            w = bars[i - 14 : i + 1]
            a = _atr([x.high for x in w], [x.low for x in w], [x.close for x in w])
            if a:
                vals.append(a)
    return atr1 / statistics.median(vals) if vals else None


def _atr_percentile(past: Sequence[Daily]) -> float | None:
    if len(past) < 30:
        return None
    atrs = []
    for k in range(15, len(past) + 1):
        w = past[k - 15 : k]
        atrs.append(_atr([d.high for d in w], [d.low for d in w], [d.close for d in w]))
    atrs = [a for a in atrs if a is not None][-252:]
    cur = atrs[-1]
    return sum(1 for a in atrs if a <= cur) / len(atrs)
