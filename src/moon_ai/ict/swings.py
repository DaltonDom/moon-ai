"""Swing highs and lows (N-bar fractals)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from moon_ai.bars import Bar


@dataclass(frozen=True)
class Swing:
    kind: Literal["high", "low"]
    price: float
    ts: datetime  # open stamp of the pivot bar
    index: int  # position of the pivot bar in the input
    known_at: datetime  # close of the bar N bars after the pivot
    instrument_id: int


def find_swings(bars: Sequence[Bar], n: int = 1) -> list[Swing]:
    """Bar i is a swing high if its high is strictly above the highs of the
    N bars on each side (swing low mirrors). It is known at the close of bar
    i+N, so the last N bars of the input can never be swings yet."""
    swings: list[Swing] = []
    for i in range(n, len(bars) - n):
        window = bars[i - n : i + n + 1]
        pivot = bars[i]
        if any(b.instrument_id != pivot.instrument_id for b in window):
            continue
        others = [b for j, b in enumerate(window) if j != n]
        known_at = bars[i + n].ts_close
        if all(pivot.high > b.high for b in others):
            swings.append(
                Swing("high", pivot.high, pivot.ts_open, i, known_at, pivot.instrument_id)
            )
        if all(pivot.low < b.low for b in others):
            swings.append(Swing("low", pivot.low, pivot.ts_open, i, known_at, pivot.instrument_id))
    return swings
