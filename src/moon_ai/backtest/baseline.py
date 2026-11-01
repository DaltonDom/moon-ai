"""The random-entry baseline (docs/design.md, "Setup testing protocol").

Each baseline run takes as many random trades as the setup took. Each random
trade:

- is a market entry on a random allowed trading day, after a random bar
  closing inside the setup's window;
- borrows the side, stop distance and target distance of one of the setup's
  real trades, so the direction mix and the stops and targets match.

It is simulated with the backtest's own rules:
- the market entry fills at the next bar's open, plus entry slippage;
- the stop exit pays stop slippage;
- the target is a limit that needs a 1-tick trade-through and can't fill on
  the entry bar;
- when the stop and target are both touched in one bar, the stop fills first;
- an unfinished trade is closed at the time-out bar's close, minus entry slippage;
- commission is charged on both sides.

The setup must beat the mean R of these runs. Only that comparison matters,
so the simulator is small and vectorised rather than a second engine.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time

import numpy as np

from moon_ai.bars import Bar
from moon_ai.config import Config, Window
from moon_ai.sessions import NY, in_window, to_ny, trading_day


@dataclass(frozen=True)
class TradeShape:
    side: int  # +1 long, -1 short
    stop_points: float
    target_points: float


@dataclass
class _Day:
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    london: np.ndarray  # bar opens inside the London slippage window
    entry_idx: np.ndarray  # bars whose close is inside the setup window
    last_idx: int  # last bar closing at or before the time-out


def prepare_days(
    bars: Sequence[Bar], days: set[date], window: Window, timeout: time, config: Config
) -> list[_Day]:
    by_day: dict[date, list[Bar]] = {}
    for b in bars:
        d = trading_day(b.ts_close)
        if d in days:
            by_day.setdefault(d, []).append(b)
    b_cfg = config.broker
    london = Window(b_cfg.london_slippage_start, b_cfg.london_slippage_end)
    out = []
    for d, bs in sorted(by_day.items()):
        cutoff = datetime.combine(d, timeout, tzinfo=NY)
        closes = [b.ts_close for b in bs]
        last = max((i for i, t in enumerate(closes) if t <= cutoff), default=-1)
        entries = [i for i, t in enumerate(closes) if in_window(t, window) and i + 1 < last]
        if last < 1 or not entries:
            continue
        out.append(
            _Day(
                np.array([b.open for b in bs]),
                np.array([b.high for b in bs]),
                np.array([b.low for b in bs]),
                np.array([b.close for b in bs]),
                np.array([in_window(to_ny(b.ts_open), london) for b in bs]),
                np.array(entries),
                last,
            )
        )
    return out


def simulate(day: _Day, i: int, shape: TradeShape, symbol: str, config: Config) -> float:
    """Net R of a market entry after bar `i` closes."""
    spec = config.instrument(symbol)
    tick, b = spec.tick_size, config.broker
    m = b.slippage_multiplier

    def slip(j: int, stop: bool) -> float:
        if day.london[j]:
            ticks = b.london_stop_slippage_ticks if stop else b.london_entry_slippage_ticks
        else:
            ticks = b.stop_slippage_ticks if stop else b.entry_slippage_ticks
        return ticks * m * tick

    s = shape.side
    e = i + 1
    entry = day.open[e] + s * slip(e, False)
    stop = entry - s * shape.stop_points
    target = entry + s * shape.target_points
    lo, hi = day.low[e : day.last_idx + 1], day.high[e : day.last_idx + 1]
    stop_hit = (lo <= stop) if s > 0 else (hi >= stop)
    tgt_hit = (hi >= target + tick) if s > 0 else (lo <= target - tick)
    tgt_hit[0] = False  # a touched target doesn't count on the entry bar
    j_stop = int(np.argmax(stop_hit)) if stop_hit.any() else None
    j_tgt = int(np.argmax(tgt_hit)) if tgt_hit.any() else None
    if j_stop is not None and (j_tgt is None or j_stop <= j_tgt):
        bar = e + j_stop
        gap = day.open[bar]
        fill = min(gap, stop) if s > 0 else max(gap, stop)  # gaps through the stop fill worse
        exit_px = fill - s * slip(bar, True)
    elif j_tgt is not None:
        exit_px = target
    else:
        exit_px = day.close[day.last_idx] - s * slip(day.last_idx, False)
    commission_points = 2 * b.commission_per_contract / spec.point_value
    return (s * (exit_px - entry) - commission_points) / shape.stop_points


def random_entry_means(
    days: list[_Day],
    shapes: Sequence[TradeShape],
    symbol: str,
    config: Config,
    n_runs: int = 1000,
    seed: int = 0,
) -> np.ndarray:
    """Mean net R of each of `n_runs` random-entry runs, `len(shapes)` trades each."""
    if not days or not shapes:
        return np.array([])
    rng = np.random.default_rng(seed)
    means = np.empty(n_runs)
    for k in range(n_runs):
        total = 0.0
        for _ in range(len(shapes)):
            day = days[rng.integers(len(days))]
            i = int(day.entry_idx[rng.integers(len(day.entry_idx))])
            total += simulate(day, i, shapes[rng.integers(len(shapes))], symbol, config)
        means[k] = total / len(shapes)
    return means
