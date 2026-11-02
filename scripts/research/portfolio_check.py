"""The first test for a pre-registered portfolio of setups (config/defaults.toml, batch 4).

The runs' trades are pooled as one account. All must hold:

1. mean net R per trade > 0, with a session-bootstrap 95% CI above 0;
2. DSR > 0.95 on the pooled daily R, counting EVERY version tested so far
   (`--trials`), because the members were chosen after seeing research results;
3. at least 100 trades;
4. still profitable with double slippage (each member re-run; the sum > 0);
5. net positive in 2022, the bear year.

Usage: uv run python scripts/research/portfolio_check.py RUN_FOLDER... --trials N
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np

from moon_ai.backtest.evaluate import daily_r, stress_test, trading_days
from moon_ai.backtest.stats import deflated_sharpe, sharpe
from moon_ai.config import load_config
from moon_ai.data.store import BarStore
from moon_ai.journal import decode_json, read_run
from moon_ai.sessions import trading_day


def _load(folder: Path):
    run = decode_json(read_run(folder, "runs"), "runs")[0]
    trades = [t for t in decode_json(read_run(folder, "trades"), "trades") if t["r"] is not None]
    return run, trades


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run", type=Path, nargs="+")
    ap.add_argument("--trials", type=int, required=True, help="versions tested so far, all")
    ap.add_argument("--store", type=Path)
    ap.add_argument("--no-stress", action="store_true")
    args = ap.parse_args()
    config = load_config()
    store = BarStore(args.store or config.data.store_root, config.data.dataset)

    runs = []
    for f in args.run:
        run, trades = _load(f)
        if not (run["notes"] or {}).get("stress"):
            runs.append((f, run, trades))
    days: set[date] = set()
    member_sr = []
    for _, run, trades in runs:
        d = trading_days(run, store, run["notes"]["symbol"])
        days |= set(d)
        member_sr.append(sharpe(daily_r(trades, d)))
    all_days = sorted(days)
    trades = [t for _, _, ts in runs for t in ts]
    r = np.array([t["r"] for t in trades])
    daily = daily_r(trades, all_days)

    by_session: dict[date, list[float]] = defaultdict(list)
    for t in trades:
        by_session[trading_day(t["entry_time"])].append(t["r"])
    sessions = list(by_session.values())
    rng = np.random.default_rng(0)
    means = []
    for _ in range(10_000):
        pick = rng.integers(0, len(sessions), len(sessions))
        means.append(np.mean([x for i in pick for x in sessions[i]]))
    lo, hi = np.quantile(means, [0.025, 0.975])
    var_sr = float(np.var(member_sr, ddof=1)) if len(member_sr) > 1 else 0.0
    dsr = deflated_sharpe(daily, args.trials, var_sr)
    years: dict[int, float] = defaultdict(float)
    for t in trades:
        years[t["entry_time"].year] += t["r"]

    stress = 0.0
    if not args.no_stress:
        for f, run, _ in runs:
            n = run["notes"]
            stress += stress_test(
                n["setup"],
                None if n["trial"] == "default" else n["trial"],
                run["data_start"].date(),
                run["data_end"].date(),
                store_root=args.store,
                runs_root=f.parent,
                symbol=n["symbol"],
            ).net_r

    print(f"{len(runs)} member runs, {len(r)} trades, {len(all_days)} days")
    for f, _run, ts in runs:
        print(f"  {f.name}: {len(ts)} trades, {sum(t['r'] for t in ts):+.1f}R")
    print(f"mean {r.mean():+.3f}R per trade, CI {lo:+.3f} to {hi:+.3f}R; net {r.sum():+.1f}R")
    print(f"daily Sharpe x sqrt(252) {sharpe(daily) * np.sqrt(252):.2f}")
    print(f"DSR {dsr:.3f} counting {args.trials} versions (member SR variance {var_sr:.5f})")
    print("by year: " + ", ".join(f"{y} {v:+.1f}R" for y, v in sorted(years.items())))
    checks = [
        ("mean net R > 0 with the 95% CI above 0", bool(lo > 0)),
        (f"DSR > 0.95 counting {args.trials} versions", dsr > 0.95),
        ("at least 100 trades", len(r) >= 100),
        ("profitable with double slippage", args.no_stress or stress > 0),
        ("net positive in 2022", years.get(2022, 0.0) > 0),
    ]
    if not args.no_stress:
        print(f"double slippage: {stress:+.1f}R")
    for name, ok in checks:
        print(f"  {'✓' if ok else '✕'} {name}")
    verdict = all(ok for _, ok in checks)
    print(f"verdict: {'passes' if verdict else 'fails'} the first test")
    return 0 if verdict else 1


if __name__ == "__main__":
    sys.exit(main())
