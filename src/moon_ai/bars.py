"""The `Bar` record and the `BarFeed` interface.

A Databento OHLCV bar is stamped at its open (`ts_open`, Databento's
`ts_event`). Its high, low and close are only knowable when it closes, so each
bar carries `ts_close = ts_open + interval`, and a `BarFeed` hands bars to the
engine in `ts_close` order. Nothing downstream may see a bar before its close.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Bar:
    symbol: str
    ts_open: datetime  # UTC, inclusive start of the interval (Databento ts_event)
    ts_close: datetime  # UTC, exclusive end: the moment the bar becomes known
    open: float
    high: float
    low: float
    close: float
    volume: int
    instrument_id: int
    roll: bool = False  # first bar of a new contract in a continuous series

    @property
    def known_at(self) -> datetime:
        return self.ts_close


class BarFeed(Protocol):
    """Closed bars in non-decreasing `ts_close` order (ties by symbol)."""

    def __iter__(self) -> Iterator[Bar]: ...


class InMemoryBarFeed:
    """A `BarFeed` over bars already in memory (fixtures, replays, tests)."""

    def __init__(self, bars: Iterable[Bar]):
        ordered = sorted(bars, key=lambda b: (b.ts_close, b.symbol))
        validate(ordered)
        self._bars = list(mark_rolls(ordered))

    def __iter__(self) -> Iterator[Bar]:
        return iter(self._bars)


def mark_rolls(bars: Iterable[Bar], last_id: dict[str, int] | None = None) -> Iterator[Bar]:
    """Flag the first bar after each `instrument_id` change, per symbol.

    Databento continuous symbols are not back-adjusted, so a contract change
    is a price discontinuity. Detectors must not span it. Pass the same
    `last_id` dict across consecutive chunks of one series to catch a roll on
    a chunk boundary.
    """
    last_id = {} if last_id is None else last_id
    for b in bars:
        prev = last_id.get(b.symbol)
        last_id[b.symbol] = b.instrument_id
        rolled = prev is not None and prev != b.instrument_id
        yield replace(b, roll=rolled) if rolled != b.roll else b


def validate(bars: list[Bar]) -> None:
    seen: set[tuple[str, datetime]] = set()
    for b in bars:
        key = (b.symbol, b.ts_open)
        if key in seen:
            raise ValueError(f"duplicate bar {b.symbol} at {b.ts_open.isoformat()}")
        seen.add(key)
        if not (b.low <= min(b.open, b.close) and b.high >= max(b.open, b.close)):
            raise ValueError(f"bar {b.symbol} at {b.ts_open.isoformat()}: high/low don't bound it")
        if b.ts_close <= b.ts_open:
            raise ValueError(f"bar {b.symbol} at {b.ts_open.isoformat()}: close before open")
