"""The journal schema, shared by the SQLite store and the Parquet run store.

docs/design.md "Journal storage". One table definition drives both stores and
the Polars reader, so the same columns come back whichever store wrote them.

Column types:
- `text`, `int`, `float`, `bool`
- `ts`: a timezone-aware UTC datetime
- `json`: any JSON-serialisable value (feature vectors, rule results, tags,
  review fields). Stored as canonical JSON text in both stores, so a
  round-trip is exact; the reader can decode it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

import polars as pl

SCHEMA_VERSION = 1

ColType = Literal["text", "int", "float", "bool", "ts", "json"]

TABLES: dict[str, dict[str, ColType]] = {
    "runs": {
        "run_id": "text",
        "kind": "text",
        "created_at": "ts",
        "code_commit": "text",
        "defaults_hash": "text",
        "model_id": "text",
        "data_start": "ts",
        "data_end": "ts",
        "account_usd": "float",
        "risk_per_trade_usd": "float",
        "schema_version": "int",
        "notes": "json",
    },
    "candidates": {
        "candidate_id": "text",
        "run_id": "text",
        "setup": "text",
        "symbol": "text",
        "side": "text",  # "long" | "short"
        "decision_time": "ts",
        "entry_type": "text",  # "market" | "limit" | "stop"
        "entry": "float",
        "stop": "float",
        "target": "float",
        "timeout": "ts",
        "rule_results": "json",
        "features": "json",
        "feature_set": "text",
        "ml_p": "float",
        "ml_threshold": "float",
        "status": "text",
        "label": "int",
        "tags": "json",
    },
    "orders": {
        "order_id": "text",
        "run_id": "text",
        "candidate_id": "text",
        "symbol": "text",
        "side": "text",
        "type": "text",
        "qty": "int",
        "price": "float",
        "stop": "float",
        "target": "float",
        "submitted_at": "ts",
    },
    "fills": {
        "fill_id": "text",
        "run_id": "text",
        "order_id": "text",
        "candidate_id": "text",
        "symbol": "text",
        "side": "text",
        "qty": "int",
        "price": "float",
        "ts": "ts",
        "reason": "text",
        "commission": "float",
        "slippage_ticks": "float",
        "pnl": "float",
        "ambiguous": "bool",
        "resolved_by": "text",
    },
    "trades": {
        "candidate_id": "text",
        "run_id": "text",
        "entry_fill_id": "text",
        "exit_fill_id": "text",
        "entry_time": "ts",
        "exit_time": "ts",
        "entry_price": "float",
        "exit_price": "float",
        "exit_reason": "text",
        "mae_r": "float",
        "mfe_r": "float",
        "r": "float",
        "net_usd": "float",
        "chart_path": "text",
    },
    "reviews": {
        "candidate_id": "text",
        "run_id": "text",
        "status": "text",  # pending | done | failed
        "attempts": "int",
        "bucket": "text",
        "fields": "json",
        "model": "text",
        "cost_usd": "float",
        "updated_at": "ts",
    },
    "models": {
        "model_id": "text",
        "created_at": "ts",
        "recipe": "json",
        "train_start": "ts",
        "train_end": "ts",
        "role": "text",  # champion | challenger | retired
        "records": "json",
        "holdout_checks": "int",
    },
    "events": {
        "event_id": "text",
        "run_id": "text",
        "ts": "ts",
        "step": "text",
        "status": "text",  # ok | fail | skipped | alarm | info
        "message": "text",
        "data": "json",
    },
}

PRIMARY_KEYS = {
    "runs": "run_id",
    "candidates": "candidate_id",
    "orders": "order_id",
    "fills": "fill_id",
    "trades": "candidate_id",
    "reviews": "candidate_id",
    "models": "model_id",
    "events": "event_id",
}

# Which run kinds live in which store. Kinds are never mixed.
PARQUET_KINDS = frozenset({"backtest", "baseline_random", "baseline_rules"})
SQLITE_KINDS = frozenset({"paper", "shadow", "live"})
# Tables a Parquet (backtest) run writes; reviews and models exist only for live-like runs.
PARQUET_TABLES = ("runs", "candidates", "orders", "fills", "trades", "events")

CANDIDATE_STATUSES = frozenset(
    {
        "taken",
        "skipped:ml",
        "skipped:cap",
        "skipped:blackout",
        "skipped:london_min_stop",
        "skipped:daily_stop",
        "skipped:session",
        "unfilled",
    }
)

_POLARS: dict[ColType, pl.DataType] = {
    "text": pl.String(),
    "int": pl.Int64(),
    "float": pl.Float64(),
    "bool": pl.Boolean(),
    "ts": pl.Datetime("us", "UTC"),
    "json": pl.String(),
}


def polars_schema(table: str) -> dict[str, pl.DataType]:
    return {c: _POLARS[t] for c, t in TABLES[table].items()}


def candidate_id(run_id: str, setup: str, decision_time: datetime, side: str) -> str:
    """Deterministic id: two runs of the same code compare row by row."""
    if decision_time.tzinfo is None:
        raise ValueError("decision_time must be timezone-aware")
    return f"{run_id}:{setup}:{decision_time.isoformat()}:{side}"
