"""Fair value gaps (three-candle imbalances)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from moon_ai.bars import Bar


@dataclass(frozen=True)
class FairValueGap:
    direction: Literal["bull", "bear"]
    low: float
    high: float
    ts: datetime  # open stamp of the middle (displacement) candle
    index: int  # position of the middle candle in the input
    known_at: datetime  # close of the third candle
    instrument_id: int

    @property
    def ce(self) -> float:
        """Consequent encroachment: the midpoint of the gap."""
        return (self.low + self.high) / 2


def find_fvgs(bars: Sequence[Bar], tick: float, min_size_ticks: int = 0) -> list[FairValueGap]:
    """Bullish when the third candle's low is above the first candle's high:
    zone [high1, low3]. Bearish mirrors: zone [high3, low1]. The gap exists
    only once the third candle closes, so the earliest fill is the bar after."""
    min_size = max(min_size_ticks, 0) * tick
    gaps: list[FairValueGap] = []
    for i in range(1, len(bars) - 1):
        first, mid, third = bars[i - 1], bars[i], bars[i + 1]
        if not first.instrument_id == mid.instrument_id == third.instrument_id:
            continue
        if third.low > first.high and third.low - first.high >= min_size:
            gaps.append(
                FairValueGap(
                    "bull", first.high, third.low, mid.ts_open, i, third.ts_close, mid.instrument_id
                )
            )
        elif third.high < first.low and first.low - third.high >= min_size:
            gaps.append(
                FairValueGap(
                    "bear", third.high, first.low, mid.ts_open, i, third.ts_close, mid.instrument_id
                )
            )
    return gaps
