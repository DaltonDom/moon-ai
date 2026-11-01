"""The two journal stores: SQLite for paper/shadow/live, Parquet for backtests.

- `SQLiteStore` (`data/journal/journal.sqlite`, WAL) takes rows as they
  happen. Rows are append-only, with the design's two exceptions: a trade's
  exit fields when it closes, and a review's fields when they arrive. Model
  roles change through `set_model_role`.
- `ParquetRun` (`data/runs/<run id>/`) buffers one backtest run and writes it
  once, with a `run.json` manifest. An existing run folder is never rewritten:
  a correction is a new run.

Both refuse rows for a run they don't hold, so run kinds can't mix, and both
read back as Polars frames with the same columns and types.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

from moon_ai.journal.schema import (
    CANDIDATE_STATUSES,
    PARQUET_KINDS,
    PARQUET_TABLES,
    PRIMARY_KEYS,
    SCHEMA_VERSION,
    SQLITE_KINDS,
    TABLES,
    polars_schema,
)

Row = Mapping[str, Any]


class JournalError(ValueError):
    """A row that breaks the journal's rules (unknown column, wrong run, edit, ...)."""


# --- value codecs -------------------------------------------------------------


def _check_row(table: str, row: Row) -> dict[str, Any]:
    cols = TABLES[table]
    unknown = set(row) - set(cols)
    if unknown:
        raise JournalError(f"{table}: unknown columns {sorted(unknown)}")
    if row.get(PRIMARY_KEYS[table]) in (None, ""):
        raise JournalError(f"{table}: missing {PRIMARY_KEYS[table]}")
    if table == "candidates" and row.get("status") not in CANDIDATE_STATUSES:
        raise JournalError(f"candidates: unknown status {row.get('status')!r}")
    full = {c: row.get(c) for c in cols}
    for c, t in cols.items():
        v = full[c]
        if t == "ts" and v is not None:
            if not isinstance(v, datetime) or v.tzinfo is None:
                raise JournalError(f"{table}.{c}: needs a timezone-aware datetime")
            full[c] = v.astimezone(UTC)
        elif t == "json" and v is not None:
            full[c] = json.dumps(v, sort_keys=True, separators=(",", ":"))
    return full


def _to_sql(t: str, v: Any) -> Any:
    if v is None:
        return None
    if t == "ts":
        return v.isoformat()
    if t == "bool":
        return int(v)
    return v


def _from_sql(t: str, v: Any) -> Any:
    if v is None:
        return None
    if t == "ts":
        return datetime.fromisoformat(v).astimezone(UTC)
    if t == "bool":
        return bool(v)
    return v


def _frame(table: str, rows: Iterable[Mapping[str, Any]]) -> pl.DataFrame:
    schema = polars_schema(table)
    data = [[r[c] for c in schema] for r in rows]
    return pl.DataFrame(data, schema=schema, orient="row")


def decode_json(frame: pl.DataFrame, table: str) -> list[dict[str, Any]]:
    """Rows as dicts with JSON columns decoded back to Python values."""
    json_cols = [c for c, t in TABLES[table].items() if t == "json"]
    out = []
    for r in frame.iter_rows(named=True):
        for c in json_cols:
            if r[c] is not None:
                r[c] = json.loads(r[c])
        out.append(r)
    return out


# --- SQLite -------------------------------------------------------------------

_SQL_TYPE = {
    "text": "TEXT",
    "int": "INTEGER",
    "float": "REAL",
    "bool": "INTEGER",
    "ts": "TEXT",
    "json": "TEXT",
}


def _create_sql(table: str) -> str:
    cols = ", ".join(
        f"{c} {_SQL_TYPE[t]}{' PRIMARY KEY' if c == PRIMARY_KEYS[table] else ''}"
        for c, t in TABLES[table].items()
    )
    return f"CREATE TABLE {table} ({cols})"


def _v1(conn: sqlite3.Connection) -> None:
    for table in TABLES:
        conn.execute(_create_sql(table))


# Numbered migrations: index i upgrades version i to i + 1.
MIGRATIONS: list[Callable[[sqlite3.Connection], None]] = [_v1]


class SQLiteStore:
    def __init__(
        self, path: Path, migrations: list[Callable[[sqlite3.Connection], None]] | None = None
    ):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self.migrate(MIGRATIONS if migrations is None else migrations)

    # schema versions
    def version(self) -> int:
        self._conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
        row = self._conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
        return row[0] or 0

    def migrate(self, migrations: list[Callable[[sqlite3.Connection], None]]) -> None:
        current = self.version()
        if current > len(migrations):
            raise JournalError(
                f"{self.path} is at schema {current}, newer than this code ({len(migrations)}); "
                "update the code before opening it"
            )
        for i in range(current, len(migrations)):
            with self.transaction():
                migrations[i](self._conn)
                self._conn.execute("INSERT INTO schema_version VALUES (?)", (i + 1,))

    def transaction(self) -> sqlite3.Connection:
        """`with store.transaction(): ...` commits on success and rolls back on error."""
        return _Tx(self._conn)  # type: ignore[return-value]

    def close(self) -> None:
        self._conn.close()

    # writes
    def start_run(self, row: Row) -> str:
        if row.get("kind") not in SQLITE_KINDS:
            raise JournalError(f"{row.get('kind')!r} runs belong in a Parquet run, not SQLite")
        full = {"schema_version": SCHEMA_VERSION, **row}
        self._insert("runs", full)
        return str(full["run_id"])

    def insert(self, table: str, row: Row) -> None:
        if table == "runs":
            raise JournalError("use start_run for runs")
        runless_ok = table == "models" or (table == "events" and row.get("run_id") is None)
        if not runless_ok and not self._has_run(row.get("run_id")):
            raise JournalError(f"{table}: run {row.get('run_id')!r} is not in this journal")
        self._insert(table, row)

    def close_trade(self, candidate_id: str, **exit_fields: Any) -> None:
        allowed = {
            "exit_fill_id",
            "exit_time",
            "exit_price",
            "exit_reason",
            "mae_r",
            "mfe_r",
            "r",
            "net_usd",
            "chart_path",
        }
        self._update("trades", candidate_id, exit_fields, allowed)

    def set_review(self, candidate_id: str, **fields: Any) -> None:
        """Insert or update a trade's review (the other mutable record)."""
        exists = self._conn.execute(
            "SELECT 1 FROM reviews WHERE candidate_id = ?", (candidate_id,)
        ).fetchone()
        if exists:
            self._update(
                "reviews", candidate_id, fields, set(TABLES["reviews"]) - {"candidate_id", "run_id"}
            )
        else:
            self.insert("reviews", {"candidate_id": candidate_id, **fields})

    def set_model_role(
        self, model_id: str, role: str, records: Any = None, holdout_checks: int | None = None
    ) -> None:
        fields: dict[str, Any] = {"role": role}
        if records is not None:
            fields["records"] = records
        if holdout_checks is not None:
            fields["holdout_checks"] = holdout_checks
        self._update("models", model_id, fields, {"role", "records", "holdout_checks"})

    # reads
    def read(self, table: str, run_id: str | None = None) -> pl.DataFrame:
        cols = TABLES[table]
        sql = f"SELECT {', '.join(cols)} FROM {table}"
        args: tuple[Any, ...] = ()
        if run_id is not None and "run_id" in cols:
            sql += " WHERE run_id = ?"
            args = (run_id,)
        rows = [
            {c: _from_sql(t, v) for (c, t), v in zip(cols.items(), r, strict=True)}
            for r in self._conn.execute(sql + f" ORDER BY {PRIMARY_KEYS[table]}", args)
        ]
        return _frame(table, rows)

    # internals
    def _has_run(self, run_id: Any) -> bool:
        return run_id is not None and bool(
            self._conn.execute("SELECT 1 FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        )

    def _insert(self, table: str, row: Row) -> None:
        full = _check_row(table, row)
        cols = TABLES[table]
        try:
            self._conn.execute(
                f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                [_to_sql(cols[c], full[c]) for c in cols],
            )
        except sqlite3.IntegrityError as exc:
            raise JournalError(
                f"{table}: {PRIMARY_KEYS[table]} {full[PRIMARY_KEYS[table]]!r} "
                "already written; rows are append-only"
            ) from exc

    def _update(self, table: str, key: str, fields: Mapping[str, Any], allowed: set[str]) -> None:
        bad = set(fields) - allowed
        if bad:
            raise JournalError(f"{table}: {sorted(bad)} can't be changed after writing")
        cols = TABLES[table]
        current = self._conn.execute(
            f"SELECT {', '.join(cols)} FROM {table} WHERE {PRIMARY_KEYS[table]} = ?", (key,)
        ).fetchone()
        if current is None:
            raise JournalError(f"{table}: no row {key!r}")
        merged = {c: _from_sql(t, v) for (c, t), v in zip(cols.items(), current, strict=True)}
        json_cols = {c for c, t in cols.items() if t == "json"}
        merged = {
            c: (json.loads(v) if c in json_cols and v is not None else v) for c, v in merged.items()
        }
        merged.update(fields)
        full = _check_row(table, merged)
        sets = ", ".join(f"{c} = ?" for c in fields)
        self._conn.execute(
            f"UPDATE {table} SET {sets} WHERE {PRIMARY_KEYS[table]} = ?",
            [_to_sql(cols[c], full[c]) for c in fields] + [key],
        )


class _Tx:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def __enter__(self) -> sqlite3.Connection:
        self._conn.execute("BEGIN")
        return self._conn

    def __exit__(self, exc_type, exc, tb) -> None:
        self._conn.execute("ROLLBACK" if exc_type else "COMMIT")


# --- Parquet ------------------------------------------------------------------


class ParquetRun:
    """One immutable backtest run: buffer rows, then `write()` once."""

    def __init__(self, root: Path, run: Row):
        if run.get("kind") not in PARQUET_KINDS:
            raise JournalError(f"{run.get('kind')!r} runs belong in the SQLite journal")
        self.run_id = str(run["run_id"])
        self.folder = Path(root) / self.run_id
        if self.folder.exists():
            raise JournalError(f"run {self.run_id} already exists; a correction is a new run")
        self._rows: dict[str, list[dict[str, Any]]] = {t: [] for t in PARQUET_TABLES}
        self._rows["runs"].append(_check_row("runs", {"schema_version": SCHEMA_VERSION, **run}))
        self._keys: dict[str, set[Any]] = {t: set() for t in PARQUET_TABLES}
        self._written = False

    def insert(self, table: str, row: Row) -> None:
        if table not in PARQUET_TABLES or table == "runs":
            raise JournalError(f"a backtest run can't hold {table!r} rows")
        if row.get("run_id") != self.run_id:
            raise JournalError(f"{table}: row for run {row.get('run_id')!r} in run {self.run_id!r}")
        if self._written:
            raise JournalError(f"run {self.run_id} is already written")
        full = _check_row(table, row)
        key = full[PRIMARY_KEYS[table]]
        if key in self._keys[table]:
            raise JournalError(f"{table}: {key!r} already written; rows are append-only")
        self._keys[table].add(key)
        self._rows[table].append(full)

    def write(self) -> Path:
        self.folder.mkdir(parents=True)
        for table, rows in self._rows.items():
            _frame(table, rows).write_parquet(self.folder / f"{table}.parquet")
        manifest = {
            "run_id": self.run_id,
            "schema_version": SCHEMA_VERSION,
            "tables": {t: len(r) for t, r in self._rows.items()},
        }
        (self.folder / "run.json").write_text(json.dumps(manifest, indent=2) + "\n")
        self._written = True
        return self.folder


def read_run(folder: Path, table: str) -> pl.DataFrame:
    """Read one table of a written Parquet run, checking its schema version."""
    manifest = json.loads((Path(folder) / "run.json").read_text())
    if manifest["schema_version"] > SCHEMA_VERSION:
        raise JournalError(
            f"run {manifest['run_id']} has schema {manifest['schema_version']}, "
            f"newer than this code ({SCHEMA_VERSION})"
        )
    frame = pl.read_parquet(Path(folder) / f"{table}.parquet")
    return frame.select([pl.col(c).cast(t) for c, t in polars_schema(table).items()])
