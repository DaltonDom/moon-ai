from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest

from moon_ai.data.store import BarStore, ParquetBarFeed, SecondBarLookup


def write(root: Path, symbol: str, name: str, rows: list[tuple], schema: str = "ohlcv-1m") -> None:
    """Rows of (ts_event, open, high, low, close, instrument_id), in Databento's column layout."""
    folder = root / "GLBX.MDP3" / schema / symbol
    folder.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(
        {
            "rtype": [33] * len(rows),
            "publisher_id": [1] * len(rows),
            "instrument_id": [r[5] for r in rows],
            "open": [r[1] for r in rows],
            "high": [r[2] for r in rows],
            "low": [r[3] for r in rows],
            "close": [r[4] for r in rows],
            "volume": [10] * len(rows),
            "symbol": [symbol] * len(rows),
            "ts_event": pl.Series([r[0] for r in rows], dtype=pl.Datetime("ns", "UTC")),
        }
    ).write_parquet(folder / f"{name}.parquet")


def ts(*a):
    return datetime(*a, tzinfo=UTC)


def row(t, px, inst=1):
    return (t, px, px + 1, px - 1, px + 0.5, inst)


def test_load_filters_dedupes_and_stamps_the_close(tmp_path):
    t0 = ts(2026, 10, 27, 14, 0)
    write(
        tmp_path,
        "MNQ.v.0",
        "2026-10-27_2026-10-28",
        [row(t0, 100), row(t0 + timedelta(minutes=1), 101)],
    )
    # An overlapping re-pull: the later file wins for the shared bar.
    write(tmp_path, "MNQ.v.0", "2026-10-27_2026-10-29", [row(t0 + timedelta(minutes=1), 201)])
    bars = BarStore(tmp_path).load("MNQ.v.0", date(2026, 10, 27), date(2026, 10, 29))
    assert [b.open for b in bars] == [100, 201]
    assert bars[0].ts_close == t0 + timedelta(minutes=1)
    assert (
        BarStore(tmp_path).load("MNQ.v.0", t0 + timedelta(minutes=1), date(2026, 10, 29))[0].open
        == 201
    )


def test_feed_orders_symbols_by_close_and_marks_a_roll_across_months(tmp_path):
    a = ts(2026, 8, 31, 20, 59)
    b = ts(2026, 9, 1, 13, 30)
    write(tmp_path, "MNQ.v.0", "2026-08-31_2026-09-02", [row(a, 100, 1), row(b, 300, 2)])
    write(tmp_path, "MES.v.0", "2026-08-31_2026-09-02", [row(a, 50, 7), row(b, 51, 7)])
    feed = list(
        ParquetBarFeed(
            BarStore(tmp_path), ["MNQ.v.0", "MES.v.0"], date(2026, 8, 1), date(2026, 10, 1)
        )
    )
    assert [(x.symbol, x.ts_open) for x in feed] == [
        ("MES.v.0", a),
        ("MNQ.v.0", a),
        ("MES.v.0", b),
        ("MNQ.v.0", b),
    ]
    assert [x.roll for x in feed] == [False, False, False, True]


def test_feed_rejects_bad_bars(tmp_path):
    write(
        tmp_path, "MNQ.v.0", "2026-10-27_2026-10-28", [(ts(2026, 10, 27, 14), 100, 99, 98, 100, 1)]
    )
    with pytest.raises(ValueError, match="high/low"):
        list(
            ParquetBarFeed(BarStore(tmp_path), ["MNQ.v.0"], date(2026, 10, 27), date(2026, 10, 28))
        )


def test_second_bar_lookup(tmp_path):
    m = ts(2026, 10, 27, 14, 5)
    write(
        tmp_path,
        "MNQ.v.0",
        "2026-10-27_2026-10-28",
        [row(m, 100), row(m + timedelta(seconds=1), 101), row(m + timedelta(minutes=1), 102)],
        schema="ohlcv-1s",
    )
    look = SecondBarLookup(BarStore(tmp_path))
    got = look("MNQ.v.0", m)
    assert [b.open for b in got] == [100, 101]
    assert got[0].ts_close == m + timedelta(seconds=1)
    assert look("MNQ.v.0", m + timedelta(minutes=5)) == []  # covered day, no trades that minute
    assert look("MNQ.v.0", ts(2026, 10, 28, 14, 5)) is None  # no 1-second file for that day
