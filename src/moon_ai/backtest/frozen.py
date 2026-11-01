"""The frozen replay (docs/design.md, "Verifiability" and "Code layout").

A fixed four-week window of real MNQ bars (2026-09-28 to 2026-10-23, committed
under tests/fixtures/frozen/bars because the repo is private) is replayed
through every setup. Every candidate and trade must match
tests/frozen/expected.json exactly. An intentional change updates that file in
the same commit (`moon-ai verify --update-frozen`), so the diff shows what moved.

1-second bars are left out, so the result doesn't depend on which minutes
happen to have them on a given machine.
"""

from __future__ import annotations

import json
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

from moon_ai.backtest.runner import run_backtest
from moon_ai.journal import decode_json, read_run
from moon_ai.setups import load_setup_defaults

REPO = Path(__file__).resolve().parents[3]
FIXTURE_STORE = REPO / "tests" / "fixtures" / "frozen" / "bars"
EXPECTED = REPO / "tests" / "frozen" / "expected.json"
START, END = date(2026, 9, 28), date(2026, 10, 24)


def _row(r: dict[str, Any], run_id: str, keys: tuple[str, ...]) -> dict[str, Any]:
    out = {}
    for k in keys:
        v = r[k]
        if isinstance(v, str):
            v = v.removeprefix(f"{run_id}:")
        elif hasattr(v, "isoformat"):
            v = v.isoformat()
        elif isinstance(v, float):
            v = round(v, 6)
        out[k] = v
    return out


def replay(store_root: Path = FIXTURE_STORE) -> dict[str, Any]:
    """Run every pre-registered setup's default over the frozen window."""
    result: dict[str, Any] = {"window": [START.isoformat(), END.isoformat()], "setups": {}}
    with tempfile.TemporaryDirectory() as tmp:
        for setup in sorted(load_setup_defaults()):
            run = run_backtest(
                setup,
                START,
                END,
                store_root=store_root,
                runs_root=Path(tmp),
                run_id=f"frozen-{setup}",
                second_bars=False,
            )
            rid = run.run_id
            cands = decode_json(read_run(run.folder, "candidates"), "candidates")
            trades = decode_json(read_run(run.folder, "trades"), "trades")
            result["setups"][setup] = {
                "candidates": sorted(
                    (
                        _row(c, rid, ("candidate_id", "status", "entry", "stop", "target", "tags"))
                        for c in cands
                    ),
                    key=lambda c: c["candidate_id"],
                ),
                "trades": sorted(
                    (
                        _row(
                            t,
                            rid,
                            (
                                "candidate_id",
                                "entry_time",
                                "entry_price",
                                "exit_time",
                                "exit_price",
                                "exit_reason",
                                "net_usd",
                                "r",
                            ),
                        )
                        for t in trades
                    ),
                    key=lambda t: t["candidate_id"],
                ),
            }
    return result


def diff(expected: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    """Plain-language differences, empty when they match."""
    out = []
    for setup in sorted(set(expected["setups"]) | set(actual["setups"])):
        e = expected["setups"].get(setup, {"candidates": [], "trades": []})
        a = actual["setups"].get(setup, {"candidates": [], "trades": []})
        for table in ("candidates", "trades"):
            ek = {r["candidate_id"]: r for r in e[table]}
            ak = {r["candidate_id"]: r for r in a[table]}
            for k in sorted(set(ek) - set(ak)):
                out.append(f"{setup}: {table[:-1]} {k} disappeared")
            for k in sorted(set(ak) - set(ek)):
                out.append(f"{setup}: new {table[:-1]} {k}")
            for k in sorted(set(ek) & set(ak)):
                changed = [f for f in ek[k] if ek[k][f] != ak[k].get(f)]
                if changed:
                    out.append(f"{setup}: {table[:-1]} {k} changed {', '.join(changed)}")
    return out


def load_expected(path: Path = EXPECTED) -> dict[str, Any]:
    return json.loads(path.read_text())


def write_expected(result: dict[str, Any], path: Path = EXPECTED) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
