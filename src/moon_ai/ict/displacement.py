"""ATR and displacement candles."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from moon_ai.bars import Bar
from moon_ai.ict.fvg import find_fvgs


@dataclass(frozen=True)
class Displacement:
    direction: Literal["bull", "bear"]
    index: int  # position of the displacement candle in the input
    ts: datetime  # its open stamp
    body: float  # |close - open|
    atr: float  # the ATR it was measured against (as of the previous bar)
    known_at: datetime


def atr(bars: Sequence[Bar], period: int = 14) -> list[float | None]:
    """Simple mean of the last `period` true ranges, known at each bar's close.

    The previous close only counts within one contract; the ATR restarts after
    a roll and is None until `period` bars of the new contract exist.
    """
    out: list[float | None] = []
    trs: list[float] = []
    for i, b in enumerate(bars):
        prev = bars[i - 1] if i > 0 else None
        if prev is None or prev.instrument_id != b.instrument_id:
            trs = []
            tr = b.high - b.low
        else:
            tr = max(b.high - b.low, abs(b.high - prev.close), abs(b.low - prev.close))
        trs.append(tr)
        out.append(sum(trs[-period:]) / period if len(trs) >= period else None)
    return out


def find_displacements(
    bars: Sequence[Bar],
    tick: float,
    k: float = 1.5,
    atr_period: int = 14,
    require_fvg: bool = True,
) -> list[Displacement]:
    """A candle whose body is at least `k` x the ATR as of the previous bar.

    With `require_fvg`, the candle must also be the middle candle of a fair
    value gap in its own direction, so it is known only at the next bar's close.
    """
    atrs = atr(bars, atr_period)
    gaps = {(g.index, g.direction): g for g in find_fvgs(bars, tick)} if require_fvg else {}
    found: list[Displacement] = []
    for i in range(1, len(bars)):
        b, ref = bars[i], atrs[i - 1]
        if ref is None or bars[i - 1].instrument_id != b.instrument_id:
            continue
        body = abs(b.close - b.open)
        if body == 0 or body < k * ref:
            continue
        direction: Literal["bull", "bear"] = "bull" if b.close > b.open else "bear"
        if require_fvg:
            gap = gaps.get((i, direction))
            if gap is None:
                continue
            known_at = gap.known_at
        else:
            known_at = b.ts_close
        found.append(Displacement(direction, i, b.ts_open, body, ref, known_at))
    return found
