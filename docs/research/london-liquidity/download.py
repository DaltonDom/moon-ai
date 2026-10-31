"""Price every request with the free get_cost, enforce the budget, then download.

Usage: python download.py [--dry-run]
Reads DATABENTO_API_KEY from the environment (databento.Historical() default);
never prints or stores it. Files go to data/london-liquidity/ (git-ignored) and
are never fetched twice: an existing file is skipped. Each paid request is
appended to ledger.csv next to this script.
"""

from __future__ import annotations

import csv
import sys
from datetime import UTC, date, datetime, time
from pathlib import Path

import databento as db

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from windows import DATASET, NY, SYMBOL, TICK_DAYS, window_utc  # noqa: E402

OUT = HERE.parents[2] / "data" / "london-liquidity"
LEDGER = HERE / "ledger.csv"
BUDGET = 5.00

NYAM_TBBO_DAYS = [date(2026, 10, d) for d in (27, 28)]


def ny(day: date, hh: int, mm: int) -> datetime:
    return datetime.combine(day, time(hh, mm), tzinfo=NY).astimezone(UTC)


def requests() -> list[tuple[str, str, object, object]]:
    """(name, schema, start, end)."""
    reqs: list[tuple[str, str, object, object]] = [
        ("ohlcv1m_20260501_20261031", "ohlcv-1m", "2026-05-01", "2026-10-31"),
    ]
    for d in TICK_DAYS:
        for w in ("london", "nyam"):
            a, b = window_utc(d, w)
            reqs.append((f"bbo1s_{w}_{d:%Y%m%d}", "bbo-1s", a, b))
    for d in TICK_DAYS:
        a, b = window_utc(d, "london")
        reqs.append((f"tbbo_london_{d:%Y%m%d}", "tbbo", a, b))
    for d in NYAM_TBBO_DAYS:
        a, b = window_utc(d, "nyam")
        reqs.append((f"tbbo_nyam_{d:%Y%m%d}", "tbbo", a, b))
    # Tiny mbp-10 depth sample, one day: 15 min of London, 5 min of NY AM.
    d = date(2026, 10, 28)
    reqs.append(("mbp10_london_20261028_0300", "mbp-10", ny(d, 3, 0), ny(d, 3, 15)))
    reqs.append(("mbp10_nyam_20261028_1000_5m", "mbp-10", ny(d, 10, 0), ny(d, 10, 5)))
    return reqs


def main(dry: bool) -> None:
    client = db.Historical()
    plan = []
    for name, schema, a, b in requests():
        kw = dict(
            dataset=DATASET, symbols=[SYMBOL], stype_in="continuous", schema=schema, start=a, end=b
        )
        c = client.metadata.get_cost(**kw)
        plan.append((name, kw, c))
        print(f"{name:34s} {schema:9s} ${c:.4f}")
    spent = 0.0
    if LEDGER.exists():
        with LEDGER.open() as fh:
            spent = sum(float(r["get_cost_usd"]) for r in csv.DictReader(fh))
    todo = [(n, kw, c) for n, kw, c in plan if not (OUT / f"{n}.dbn.zst").exists()]
    need = sum(c for _, _, c in todo)
    print(f"already spent ${spent:.4f}; to buy ${need:.4f}; total ${spent + need:.4f}")
    if spent + need > BUDGET:
        sys.exit(f"over budget ${BUDGET:.2f}: refusing")
    if dry:
        return
    OUT.mkdir(parents=True, exist_ok=True)
    new = not LEDGER.exists()
    with LEDGER.open("a", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["name", "schema", "symbol", "start_utc", "end_utc", "get_cost_usd"])
        for n, kw, c in todo:
            path = OUT / f"{n}.dbn.zst"
            client.timeseries.get_range(**kw, path=str(path))
            w.writerow([n, kw["schema"], SYMBOL, str(kw["start"]), str(kw["end"]), f"{c:.6f}"])
            fh.flush()
            print("downloaded", path.name, path.stat().st_size)


if __name__ == "__main__":
    main("--dry-run" in sys.argv)
