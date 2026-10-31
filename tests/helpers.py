"""Synthetic bar fixtures. Prices are on the 0.25 MNQ tick grid."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from moon_ai.bars import Bar

T0 = datetime(2026, 7, 15, 14, 0, tzinfo=UTC)  # 10:00 New York (EDT)
MINUTE = timedelta(minutes=1)
SECOND = timedelta(seconds=1)


def bar(
    i: int,
    o: float,
    h: float,
    low: float,
    c: float,
    *,
    symbol: str = "MNQ.v.0",
    instrument_id: int = 1,
    interval: timedelta = MINUTE,
    start=T0,
) -> Bar:
    ts_open = start + i * interval
    return Bar(
        symbol=symbol,
        ts_open=ts_open,
        ts_close=ts_open + interval,
        open=o,
        high=h,
        low=low,
        close=c,
        volume=100,
        instrument_id=instrument_id,
    )


def second_bars(minute: int, rows: list[tuple[float, float, float, float]]) -> list[Bar]:
    """1-second bars inside minute `minute` (relative to T0)."""
    start = T0 + minute * MINUTE
    return [bar(i, *row, interval=SECOND, start=start) for i, row in enumerate(rows)]
