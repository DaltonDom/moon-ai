"""The `Journal` interface and a minimal in-memory implementation.

The full journal schema (feature vectors, rule results, ML probability, chart
snapshots, reviews) is still open on the map; this only fixes the seam.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


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
