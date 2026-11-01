"""The local bar store: Databento Parquet files -> `Bar`s.

Files are laid out by the downloader as
`<root>/<dataset>/<schema>/<symbol>/<start>_<end>.parquet` (end exclusive),
with `ts_event` stamped at each bar's open. Overlapping files are allowed (a
re-pull, a nightly top-up); the same bar is kept once.

`ParquetBarFeed` serves the backtest and the nightly replay alike. It reads
one calendar month at a time so seven years of 1-minute bars never sit in
memory at once, and marks contract rolls across month boundaries.
`SecondBarLookup` answers the simulated broker's question "what did the
1-second bars of this minute do?" for same-bar stop/target ambiguity.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import polars as pl

from moon_ai.bars import Bar, mark_rolls, validate

INTERVALS = {
    "ohlcv-1s": timedelta(seconds=1),
    "ohlcv-1m": timedelta(minutes=1),
    "ohlcv-1h": timedelta(hours=1),
    "ohlcv-1d": timedelta(days=1),
}


def _utc(x: date | datetime) -> datetime:
    if isinstance(x, datetime):
        if x.tzinfo is None:
            raise ValueError("datetimes must be timezone-aware")
        return x.astimezone(UTC)
    return datetime.combine(x, time(0), tzinfo=UTC)


@dataclass(frozen=True)
class FileSpan:
    path: Path
    start: date
    end: date  # exclusive


class BarStore:
    def __init__(self, root: Path, dataset: str = "GLBX.MDP3"):
        self.root = Path(root)
        self.dataset = dataset

    def files(self, symbol: str, schema: str = "ohlcv-1m") -> list[FileSpan]:
        """Files for `symbol`, ordered by start date then name (later wins on overlap)."""
        folder = self.root / self.dataset / schema / symbol
        spans = []
        for path in sorted(folder.glob("*.parquet")):
            try:
                a, b = path.stem.split("_")
                spans.append(FileSpan(path, date.fromisoformat(a), date.fromisoformat(b)))
            except ValueError:
                continue  # not a downloader file
        return sorted(spans, key=lambda s: (s.start, s.path.name))

    def covers(self, symbol: str, day: date, schema: str = "ohlcv-1m") -> bool:
        return any(s.start <= day < s.end for s in self.files(symbol, schema))

    def load(
        self,
        symbol: str,
        start: date | datetime,
        end: date | datetime,
        schema: str = "ohlcv-1m",
    ) -> list[Bar]:
        """Bars of `symbol` opening in [start, end), oldest first, rolls not yet marked."""
        lo, hi = _utc(start), _utc(end)
        paths = [
            s.path
            for s in self.files(symbol, schema)
            if s.start < hi.date() + timedelta(days=1) and s.end > lo.date()
        ]
        if not paths:
            return []
        interval = INTERVALS[schema]
        frame = (
            pl.concat([pl.read_parquet(p) for p in paths], how="diagonal_relaxed")
            .filter((pl.col("ts_event") >= lo) & (pl.col("ts_event") < hi))
            .unique(subset=["ts_event"], keep="last", maintain_order=True)
            .sort("ts_event")
        )
        return [
            Bar(
                symbol=symbol,
                ts_open=ts,
                ts_close=ts + interval,
                open=o,
                high=h,
                low=lo_,
                close=c,
                volume=int(v),
                instrument_id=int(i),
            )
            for ts, o, h, lo_, c, v, i in frame.select(
                "ts_event", "open", "high", "low", "close", "volume", "instrument_id"
            ).iter_rows()
        ]


def _month_starts(start: datetime, end: datetime) -> Iterator[tuple[datetime, datetime]]:
    cur = start
    while cur < end:
        nxt = datetime(cur.year + (cur.month == 12), cur.month % 12 + 1, 1, tzinfo=UTC)
        yield cur, min(nxt, end)
        cur = nxt


class ParquetBarFeed:
    """A `BarFeed` over the store: closed bars in `ts_close` order, rolls marked."""

    def __init__(
        self,
        store: BarStore,
        symbols: Sequence[str],
        start: date | datetime,
        end: date | datetime,
        schema: str = "ohlcv-1m",
    ):
        self._store = store
        self._symbols = tuple(symbols)
        self._start, self._end = _utc(start), _utc(end)
        self._schema = schema

    def __iter__(self) -> Iterator[Bar]:
        last_id: dict[str, int] = {}
        for lo, hi in _month_starts(self._start, self._end):
            chunk = [b for s in self._symbols for b in self._store.load(s, lo, hi, self._schema)]
            chunk.sort(key=lambda b: (b.ts_close, b.symbol))
            validate(chunk)
            yield from mark_rolls(chunk, last_id)


class SecondBarLookup:
    """`SecondBarSource` for `SimBroker`: a minute's 1-second bars, or None.

    None means the store has no 1-second file covering that minute, so the
    broker keeps its pessimistic stop-first assumption. One UTC day of a
    symbol is read at a time and cached.
    """

    def __init__(self, store: BarStore, schema: str = "ohlcv-1s"):
        self._store = store
        self._schema = schema
        self._cache: dict[tuple[str, date], dict[datetime, list[Bar]] | None] = {}

    def __call__(self, symbol: str, minute_open: datetime) -> list[Bar] | None:
        minute_open = _utc(minute_open)
        key = (symbol, minute_open.date())
        if key not in self._cache:
            self._cache[key] = self._load_day(symbol, minute_open.date())
        by_minute = self._cache[key]
        if by_minute is None:
            return None
        return by_minute.get(minute_open.replace(second=0, microsecond=0), [])

    def _load_day(self, symbol: str, day: date) -> dict[datetime, list[Bar]] | None:
        if not self._store.covers(symbol, day, self._schema):
            return None
        by_minute: dict[datetime, list[Bar]] = {}
        for b in self._store.load(symbol, day, day + timedelta(days=1), self._schema):
            by_minute.setdefault(b.ts_open.replace(second=0, microsecond=0), []).append(b)
        return by_minute
