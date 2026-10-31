"""Market structure shift (MSS) after a liquidity sweep."""

from __future__ import annotations

import bisect
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from moon_ai.bars import Bar
from moon_ai.ict.liquidity import Sweep
from moon_ai.ict.swings import Swing


@dataclass(frozen=True)
class MarketStructureShift:
    direction: Literal["bull", "bear"]
    index: int  # the breaking bar
    ts: datetime  # its open stamp
    broken_swing: Swing
    sweep: Sweep
    known_at: datetime  # close of the breaking bar


def find_market_structure_shifts(
    bars: Sequence[Bar],
    swings: Iterable[Swing],
    sweeps: Iterable[Sweep],
    mode: Literal["close", "wick"] = "close",
    max_bars: int = 30,
) -> list[MarketStructureShift]:
    """After a sweep of highs, the first bar within `max_bars` that closes
    (or, in "wick" mode, trades) below the most recent swing low confirmed by
    the time the sweep confirmed. A sweep of lows mirrors this against the
    last swing high. The reference swing is frozen at the sweep's confirmation
    so a later swing can't be picked in hindsight. Confirmed at the breaking
    bar's close; on 1-minute OHLC a wick break can't be timed more finely."""
    swings = list(swings)
    opens = [b.ts_open for b in bars]
    shifts: list[MarketStructureShift] = []
    for sweep in sweeps:
        bearish = sweep.kind == "high"
        want = "low" if bearish else "high"
        candidates = [
            s
            for s in swings
            if s.kind == want
            and s.known_at <= sweep.known_at
            and s.instrument_id == sweep.level.instrument_id
        ]
        if not candidates:
            continue
        ref = max(candidates, key=lambda s: (s.known_at, s.index))
        start = bisect.bisect_left(opens, sweep.known_at)
        for j in range(start, min(start + max_bars, len(bars))):
            b = bars[j]
            if b.instrument_id != ref.instrument_id:
                break
            if bearish:
                broke = (b.close if mode == "close" else b.low) < ref.price
            else:
                broke = (b.close if mode == "close" else b.high) > ref.price
            if broke:
                shifts.append(
                    MarketStructureShift(
                        "bear" if bearish else "bull", j, b.ts_open, ref, sweep, b.ts_close
                    )
                )
                break
    return sorted(shifts, key=lambda s: (s.known_at, s.index))
