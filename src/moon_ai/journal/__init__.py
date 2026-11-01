"""The journal: every candidate, order, fill, trade, review, model and event.

`Journal` is the seam the engine writes through. `RunJournal` binds one run
to a store (`SQLiteStore` for paper/shadow/live, `ParquetRun` for backtests);
`InMemoryJournal` stays for tests. Storage rules are in `stores.py` and the
schema in `schema.py` (docs/design.md, "Journal storage").
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from moon_ai.journal.schema import SCHEMA_VERSION, TABLES, candidate_id
from moon_ai.journal.stores import (
    JournalError,
    ParquetRun,
    SQLiteStore,
    decode_json,
    read_run,
)

__all__ = [
    "SCHEMA_VERSION",
    "TABLES",
    "InMemoryJournal",
    "Journal",
    "JournalEntry",
    "JournalError",
    "ParquetRun",
    "RunJournal",
    "SQLiteStore",
    "candidate_id",
    "decode_json",
    "read_run",
]


@dataclass(frozen=True)
class JournalEntry:
    ts: datetime  # when the event became known
    kind: str  # e.g. "fill", "roll", "candidate"
    data: dict[str, Any]


class Journal(Protocol):
    def record(self, entry: JournalEntry) -> None: ...


class InMemoryJournal:
    def __init__(self) -> None:
        self.entries: list[JournalEntry] = []

    def record(self, entry: JournalEntry) -> None:
        self.entries.append(entry)

    def of_kind(self, kind: str) -> list[JournalEntry]:
        return [e for e in self.entries if e.kind == kind]


class _Writer(Protocol):
    def insert(self, table: str, row: dict[str, Any]) -> None: ...


class RunJournal:
    """A `Journal` for one run, writing schema rows into a store.

    The trader records candidates and orders explicitly; the engine's fill
    and roll entries arrive through `record`. Order ids are prefixed with the
    run id so they stay unique across runs.
    """

    def __init__(self, store: _Writer, run_id: str, tick_size: Callable[[str], float]):
        self._store = store
        self.run_id = run_id
        self._tick = tick_size
        self._order_candidate: dict[str, str | None] = {}
        self._fill_count: dict[str, int] = {}

    def add_candidate(self, row: dict[str, Any]) -> None:
        self._store.insert("candidates", {**row, "run_id": self.run_id})

    def add_order(
        self,
        broker_order_id: str,
        order: Any,
        submitted_at: datetime,
        candidate_id: str | None = None,
    ) -> str:
        oid = f"{self.run_id}:{broker_order_id}"
        self._order_candidate[oid] = candidate_id
        bracket = order.bracket
        self._store.insert(
            "orders",
            {
                "order_id": oid,
                "run_id": self.run_id,
                "candidate_id": candidate_id,
                "symbol": order.symbol,
                "side": order.side.name.lower(),
                "type": order.type.value,
                "qty": order.qty,
                "price": order.price,
                "stop": bracket.stop if bracket else None,
                "target": bracket.target if bracket else None,
                "submitted_at": submitted_at,
            },
        )
        return oid

    def _candidate_of(self, fill: Any) -> str | None:
        """A bracket exit's order id is `<entry order>-stop|-target` (SimBroker)."""
        oid = f"{self.run_id}:{fill.order_id}"
        if oid not in self._order_candidate and fill.reason in ("stop", "target"):
            oid = oid.removesuffix(f"-{fill.reason}")
        return self._order_candidate.get(oid)

    def add_event(
        self, ts: datetime, step: str, status: str, message: str = "", data: Any = None
    ) -> None:
        self._store.insert(
            "events",
            {
                "event_id": f"{self.run_id}:{step}:{ts.isoformat()}:{message}",
                "run_id": self.run_id,
                "ts": ts,
                "step": step,
                "status": status,
                "message": message,
                "data": data,
            },
        )

    def record(self, entry: JournalEntry) -> None:
        if entry.kind == "fill":
            f = entry.data["fill"]
            oid = f"{self.run_id}:{f.order_id}"
            n = self._fill_count.get(oid, 0) + 1
            self._fill_count[oid] = n
            self._store.insert(
                "fills",
                {
                    "fill_id": f"{oid}:{n}",
                    "run_id": self.run_id,
                    "order_id": oid,
                    "candidate_id": self._candidate_of(f),
                    "symbol": f.symbol,
                    "side": f.side.name.lower(),
                    "qty": f.qty,
                    "price": f.price,
                    "ts": f.ts,
                    "reason": f.reason,
                    "commission": f.commission,
                    "slippage_ticks": f.slippage / self._tick(f.symbol),
                    "pnl": f.pnl,
                    "ambiguous": f.ambiguous,
                    "resolved_by": f.resolved_by,
                },
            )
        elif entry.kind == "roll":
            self.add_event(entry.ts, "roll", "info", entry.data["symbol"], entry.data)
        else:
            self.add_event(entry.ts, entry.kind, "info", "", _plain(entry.data))


def _plain(data: dict[str, Any]) -> dict[str, Any]:
    """Make an arbitrary entry payload JSON-safe for the events table."""
    out: dict[str, Any] = {}
    for k, v in data.items():
        out[k] = (
            v if isinstance(v, str | int | float | bool | type(None) | list | dict) else repr(v)
        )
    return out
