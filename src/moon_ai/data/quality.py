"""Databento data-quality flags: days the dataset marks degraded.

The committed list `data_public/degraded_days.csv` comes from
`metadata.get_dataset_condition` (free). Its dates are UTC calendar dates; a
degraded UTC date touches two CME trading days (the one closing that afternoon
and the one opening that evening), and both are skipped.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Protocol

from moon_ai.sessions import trading_day

DEGRADED_CSV = Path(__file__).resolve().parents[3] / "data_public" / "degraded_days.csv"


class _Metadata(Protocol):
    def get_dataset_condition(self, **kwargs: Any) -> list[dict[str, Any]]: ...


class ConditionClient(Protocol):
    metadata: _Metadata


def load_degraded_dates(path: Path = DEGRADED_CSV) -> set[date]:
    """UTC dates Databento marks other than "available"."""
    with path.open(newline="") as fh:
        return {date.fromisoformat(row["date"]) for row in csv.DictReader(fh)}


def fetch_degraded_dates(
    client: ConditionClient, start: date, end: date, dataset: str = "GLBX.MDP3"
) -> set[date]:
    """Ask Databento (free) which dates in [start, end] are not "available"."""
    rows = client.metadata.get_dataset_condition(
        dataset=dataset, start_date=start.isoformat(), end_date=end.isoformat()
    )
    return {date.fromisoformat(r["date"]) for r in rows if r["condition"] != "available"}


def degraded_sessions(utc_dates: Iterable[date]) -> frozenset[date]:
    """CME trading days that overlap any of the degraded UTC dates."""
    days: set[date] = set()
    for d in utc_dates:
        start = datetime.combine(d, time(0), tzinfo=UTC)
        end = start + timedelta(days=1) - timedelta(microseconds=1)
        days.add(trading_day(start))
        days.add(trading_day(end))
    return frozenset(days)
