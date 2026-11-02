"""The first test for time-of-day setups (config/defaults.toml, batch 3).

The random-entry baseline can't judge a setup that always enters at one fixed
minute: random entries in that minute are the setup itself. These setups are
judged instead on (all must hold):

1. mean net R per trade > 0, with a session-bootstrap 95% CI above 0;
2. DSR > 0.95 (every logged trial of the setup counts) and at least 100 trades;
3. still profitable with double slippage;
4. net positive in 2022, the bear year, so the result isn't only market beta.

Usage: uv run python scripts/research/time_effect_check.py RUN_FOLDER [--store DIR]
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np

from moon_ai.backtest.evaluate import evaluate, stress_test
from moon_ai.journal import decode_json, read_run
from moon_ai.sessions import trading_day


def check(folder: Path, store: Path | None = None, n_boot: int = 10_000) -> list[tuple[str, bool]]:
    run = decode_json(read_run(folder, "runs"), "runs")[0]
    trades = [t for t in decode_json(read_run(folder, "trades"), "trades") if t["r"] is not None]
    r = np.array([t["r"] for t in trades])
    by_session: dict[date, list[float]] = defaultdict(list)
    for t in trades:
        by_session[trading_day(t["entry_time"])].append(t["r"])
    sessions = list(by_session.values())
    rng = np.random.default_rng(0)
    means = []
    for _ in range(n_boot):
        pick = rng.integers(0, len(sessions), len(sessions))
        xs = [x for i in pick for x in sessions[i]]
        means.append(np.mean(xs))
    lo, hi = np.quantile(means, [0.025, 0.975])
    ev = evaluate(folder, store_root=store, n_random=50)
    notes = run["notes"]
    trial = None if notes["trial"] == "default" else notes["trial"]
    stress = stress_test(
        notes["setup"],
        trial,
        run["data_start"].date(),
        run["data_end"].date(),
        store_root=store,
        runs_root=folder.parent,
        symbol=notes["symbol"],
    )
    years: dict[int, float] = defaultdict(float)
    for t in trades:
        years[t["entry_time"].year] += t["r"]
    print(f"{folder.name}: {len(r)} trades, mean {r.mean():+.3f}R, CI {lo:+.3f} to {hi:+.3f}R")
    print(f"  DSR {ev.dsr:.3f} over {ev.n_trials} trial(s); double slippage {stress.net_r:+.1f}R")
    print("  by year: " + ", ".join(f"{y} {v:+.1f}R" for y, v in sorted(years.items())))
    return [
        ("mean net R > 0 with the 95% CI above 0", bool(lo > 0)),
        ("DSR > 0.95", ev.dsr > 0.95),
        ("at least 100 trades", len(r) >= 100),
        ("profitable with double slippage", stress.net_r > 0),
        ("net positive in 2022", years.get(2022, 0.0) > 0),
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run", type=Path, nargs="+")
    ap.add_argument("--store", type=Path)
    args = ap.parse_args()
    ok_all = True
    for folder in args.run:
        notes = decode_json(read_run(folder, "runs"), "runs")[0]["notes"] or {}
        if notes.get("stress"):
            continue
        results = check(folder, args.store)
        for name, ok in results:
            print(f"  {'✓' if ok else '✕'} {name}")
        verdict = all(ok for _, ok in results)
        ok_all &= verdict
        print(f"  verdict: {'passes' if verdict else 'fails'} the first test\n")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
