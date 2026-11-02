"""The locked research holdout (design.md, "Verifiability").

The last 12 months of data, 2025-11-01 up to 2026-11-01, are fixed here and
never used for research: no backtest, funnel or review page may touch them.
The dates are constants, not "the last 12 months from today", so the window
can't creep forward and quietly hand already-studied data back to research.

A finalist strategy gets exactly one look, a sign-off run over the holdout
alone. Each look is written to a ledger and counts as a trial, so a second
look at the same setup and trial is refused.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

HOLDOUT_START = date(2025, 11, 1)
HOLDOUT_END = date(2026, 11, 1)  # exclusive
LEDGER = Path("data/holdout_checks.jsonl")


class HoldoutLocked(ValueError):
    """A research run asked for dates inside the locked holdout."""


def touches(start: date, end: date) -> bool:
    """Whether the trading days [start, end) overlap the holdout."""
    return start < HOLDOUT_END and end > HOLDOUT_START


def guard(start: date, end: date) -> None:
    """Refuse a research run whose dates reach into the holdout."""
    if touches(start, end):
        raise HoldoutLocked(
            f"{start} to {end} reaches into the locked holdout ({HOLDOUT_START} to "
            f"{HOLDOUT_END}). Research must end by {HOLDOUT_START}; a finalist checks "
            "the holdout once with --holdout-signoff."
        )


@dataclass(frozen=True)
class Signoff:
    setup: str
    trial: str
    at: str


def checks(ledger: Path = LEDGER) -> list[Signoff]:
    if not ledger.exists():
        return []
    return [Signoff(**json.loads(line)) for line in ledger.read_text().splitlines() if line]


def sign_off(setup: str, trial: str, start: date, end: date, ledger: Path = LEDGER) -> Signoff:
    """Record a finalist's one allowed look at the holdout, or refuse it.

    The run must cover the holdout and nothing else, so research data and
    sign-off data never mix in one result.
    """
    if (start, end) != (HOLDOUT_START, HOLDOUT_END):
        raise HoldoutLocked(
            f"a sign-off run covers exactly the holdout: --from {HOLDOUT_START} --to {HOLDOUT_END}"
        )
    if any(c.setup == setup and c.trial == trial for c in checks(ledger)):
        raise HoldoutLocked(f"{setup} ({trial}) already had its one look at the holdout")
    s = Signoff(setup, trial, datetime.now(UTC).isoformat(timespec="seconds"))
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a") as f:
        f.write(json.dumps(s.__dict__) + "\n")
    return s
