"""Score the pre-registered strategy grid, or sign off finalists on the holdout.

    python scripts/research/evaluate.py research            # 2019-06-01 .. 2025-11-01
    python scripts/research/evaluate.py holdout NAME [...]  # 2025-11-01 .. 2026-11-01, once

For each configuration:

- trades, win rate, mean R net of costs (R = net USD / stop risk, with the
  stop distance floored at 0.05% of price so tiny stops can't inflate R)
- the coin flip: 2,000 runs taking the same trades on a random side; p is the
  share of runs whose mean R is at least the strategy's
- the paired bootstrap 95% CI of (strategy R - its twin's R) / 2, which is
  the edge over the coin flip's expected mean
- DSR, counting every configuration in the grid as a trial
- mean R in each half of the research window
- each prop account's rolling pass rate, and the coin flip's pass rate
  (100 random-side runs; the strategy must beat their 95th percentile)
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "src"))

from sessions import load  # noqa: E402
from strategies import COMMISSION_RT, configs, mirror, simulate  # noqa: E402

from moon_ai import holdout  # noqa: E402
from moon_ai.backtest.stats import deflated_sharpe, sharpe  # noqa: E402
from moon_ai.research.prop import ACCOUNTS, DayTrade, rolling  # noqa: E402

OUT = HERE.parents[1] / "docs" / "research" / "prop-search"
RISK_FLOOR = 0.0005
N_COIN = 2000
N_COIN_PROP = 100


def r_multiples(res, px, pv):
    risk = np.array([max(r.risk_pts, RISK_FLOOR * p) for r, p in zip(res, px, strict=True)])
    pnl = np.array([r.pnl_pts * pv - COMMISSION_RT for r in res])
    return pnl / (risk * pv), pnl, risk


def day_trades(res, pnl_usd, risk_pts, pv):
    return [
        DayTrade(r.day, float(p), float(r.mae_pts * pv), float(k * pv))
        for r, p, k in zip(res, pnl_usd, risk_pts, strict=True)
    ]


def score(days, cfg, n_trials_hint=None, seed=0):
    trades = cfg.build(days)
    if len(trades) < 3:
        return {"name": cfg.name, "family": cfg.family, "trades": len(trades)}, None
    twins = [mirror(t, days.tick) for t in trades]
    res = [simulate(days, t) for t in trades]
    tw = [simulate(days, t) for t in twins]
    px = np.array([t.px for t in trades])
    r, pnl, risk = r_multiples(res, px, days.pv)
    r2, pnl2, risk2 = r_multiples(tw, px, days.pv)

    rng = np.random.default_rng(seed)
    pick = rng.random((N_COIN, len(r))) < 0.5
    coin = np.where(pick, r, r2).mean(1)
    edge = (r - r2) / 2
    boots = edge[rng.integers(0, len(edge), (10_000, len(edge)))].mean(1)

    dates = days.dates[[x.day for x in res]]
    mid = dates[0] + (dates[-1] - dates[0]) / 2
    first, second = r[dates <= mid], r[dates > mid]

    out = {
        "name": cfg.name,
        "family": cfg.family,
        "trades": len(r),
        "win_rate": float((r > 0).mean()),
        "mean_r": float(r.mean()),
        "coin_mean_r": float(coin.mean()),
        "coin_p": float((coin >= r.mean()).mean()),
        "edge": float(edge.mean()),
        "edge_ci": [float(np.quantile(boots, 0.025)), float(np.quantile(boots, 0.975))],
        "sharpe_per_trade": float(sharpe(r)),
        "mean_r_first_half": float(first.mean()),
        "mean_r_second_half": float(second.mean()),
        "usd_per_contract": float(pnl.sum()),
        "exits": {k: int(sum(x.reason == k for x in res)) for k in ("stop", "target", "time")},
    }
    prop = {}
    dt = day_trades(res, pnl, risk, days.pv)
    dt2 = day_trades(tw, pnl2, risk2, days.pv)
    for acct in ACCOUNTS:
        s = rolling(acct, dt, len(days))
        coin_rates = []
        for _ in range(N_COIN_PROP):
            side = rng.random(len(dt)) < 0.5
            mix = [a if c else b for a, b, c in zip(dt, dt2, side, strict=True)]
            coin_rates.append(rolling(acct, mix, len(days)).pass_rate)
        prop[acct.name] = {
            "pass_rate": s.pass_rate,
            "resolved_pass_rate": s.resolved_pass_rate,
            "passed": s.passed,
            "failed": s.failed,
            "open": s.open,
            "median_days_to_pass": s.median_days_to_pass,
            "coin_pass_rate": float(np.mean(coin_rates)),
            "coin_pass_rate_p95": float(np.quantile(coin_rates, 0.95)),
        }
    out["prop"] = prop
    return out, r


def bar(row, n_trials):
    """The go-forward bar (design.md), plus the prop checks."""
    p = row["prop"]
    checks = {
        "100+ trades": row["trades"] >= 100,
        "edge CI excludes 0": row["edge_ci"][0] > 0,
        "DSR > 0.95": row["dsr"] > 0.95,
        "both halves > 0": row["mean_r_first_half"] > 0 and row["mean_r_second_half"] > 0,
    }
    for name, s in p.items():
        checks[f"{name} beats coin"] = s["pass_rate"] > s["coin_pass_rate_p95"]
    return checks


def research(symbol="MNQ"):
    days = load(symbol, date(2019, 6, 1), holdout.HOLDOUT_START)
    cfgs = configs()
    rows, rets = [], []
    for i, cfg in enumerate(cfgs):
        row, r = score(days, cfg, seed=i)
        rows.append(row)
        rets.append(r)
        print(
            f"{cfg.name:32s} n={row['trades']:5d} meanR={row.get('mean_r', 0):+.3f} "
            f"edgeCI={row.get('edge_ci')}",
            flush=True,
        )
    srs = [sharpe(r) for r in rets if r is not None]
    var = float(np.var(srs, ddof=1))
    for row, r in zip(rows, rets, strict=True):
        if r is not None:
            row["dsr"] = float(deflated_sharpe(r, len(cfgs), var))
            row["bar"] = bar(row, len(cfgs))
            row["passes"] = all(row["bar"].values())
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {
        "symbol": symbol,
        "window": ["2019-06-01", str(holdout.HOLDOUT_START)],
        "days": len(days),
        "trials": len(cfgs),
        "var_trial_sharpe": var,
    }
    (OUT / f"research.{symbol}.json").write_text(json.dumps({"meta": meta, "rows": rows}, indent=1))
    return rows


def signoff(names, symbol="MNQ"):
    cfgs = {c.name: c for c in configs()}
    reg = json.loads((OUT / "finalists.json").read_text())
    registered = set(reg["finalists"])
    for n in names:
        if n not in registered:
            raise SystemExit(f"{n} is not a registered finalist")
    days = load(symbol, holdout.HOLDOUT_START, holdout.HOLDOUT_END, holdout_run=True)
    rows = []
    for i, n in enumerate(names):
        holdout.sign_off(
            n,
            "prop-search-1",
            holdout.HOLDOUT_START,
            holdout.HOLDOUT_END,
            ledger=OUT / "holdout_checks.jsonl",
        )
        row, r = score(days, cfgs[n], seed=100 + i)
        row["dsr_vs_zero"] = float(deflated_sharpe(r, 1, 0.0))  # one look: no deflation
        rows.append(row)
        print(json.dumps(row, indent=1))
    (OUT / f"holdout.{symbol}.json").write_text(
        json.dumps(
            {
                "meta": {
                    "symbol": symbol,
                    "days": len(days),
                    "window": [str(holdout.HOLDOUT_START), str(holdout.HOLDOUT_END)],
                },
                "rows": rows,
            },
            indent=1,
        )
    )


if __name__ == "__main__":
    if sys.argv[1] == "research":
        research(sys.argv[2] if len(sys.argv) > 2 else "MNQ")
    elif sys.argv[1] == "holdout":
        signoff(sys.argv[2:])
