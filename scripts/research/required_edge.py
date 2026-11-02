"""What edge does the $2k-a-month goal need? (design.md, Revision 2026-11-02b)

Feeds synthetic trade streams of a known edge through the same business
simulation the walk-forward uses (walkforward.business: buy an evaluation,
pass or blow, funded payouts by the plan's rules, replace when blown, eval
spending <= $500 a month across the 3 copy-traded accounts).

Each trading day has `--per-day` independent trades. A trade wins `t` R with
probability p, otherwise loses 1R; p is set so the mean net R per trade equals
the edge being tested. Stop distance is fixed at $50 per micro (25 MNQ points),
so a $500 risk is 10 micros. Worst open P&L is -1R on losers and -0.3R on
winners (they dip first), which is roughly what MNQ momentum trades show.

For each edge, plan and risk, it runs `--paths` independent 24-month paths and
reports the median and 10th percentile of average monthly income (3 accounts,
after fees) and the share of paths that made money in at least 6 of 8 quarters.

No market data is used. It answers "how good must a signal be", not "is there
one".

Usage: uv run python scripts/research/required_edge.py [--paths 400] [--per-day 1]
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from walkforward import MONTHLY_EVAL_BUDGET, business, monthly

from moon_ai.propfirm import Trade, load_rules

STOP_USD = 50.0  # per micro
START = date(2023, 11, 1)
MONTHS = 24
EDGES = (0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4)
RISKS = (200.0, 300.0, 400.0, 600.0, 800.0)
PLANS = ("lucidflex_50k", "tradeify_growth_50k", "tradeify_select_flex_50k")


def trading_days(start: date, months: int) -> list[date]:
    end_m = start.month - 1 + months
    end = date(start.year + end_m // 12, end_m % 12 + 1, 1)
    out, d = [], start
    while d < end:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def path(rng, days, edge, target, per_day):
    p = (edge + 1.0) / (target + 1.0)
    out = []
    for d in days:
        trades = []
        for k in range(per_day):
            win = rng.random() < p
            r = target if win else -1.0
            entry = datetime.combine(d, datetime.min.time()) + timedelta(
                hours=10, minutes=30 + 60 * k
            )
            trades.append(
                Trade(
                    session=d,
                    pnl=r * STOP_USD,
                    risk=STOP_USD,
                    worst=-STOP_USD if not win else -0.3 * STOP_USD,
                    best=max(r, 0.3) * STOP_USD,
                    entry=entry,
                    exit=entry + timedelta(minutes=55),
                )
            )
        out.append(trades)
    return out


def quarters(m: list[float]) -> list[float]:
    return [sum(m[i : i + 3]) for i in range(0, len(m), 3)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--paths", type=int, default=300)
    ap.add_argument("--per-day", type=int, default=1)
    ap.add_argument("--target", type=float, default=2.0)
    ap.add_argument("--accounts", type=int, default=3)
    args = ap.parse_args()

    rules = load_rules()
    days = trading_days(START, MONTHS)
    months = sorted({(d.year, d.month) for d in days})
    budget = MONTHLY_EVAL_BUDGET / args.accounts
    print(
        f"per-day={args.per_day} target={args.target}R paths={args.paths} "
        f"accounts={args.accounts} (income = {args.accounts} x one slot, copy-traded)"
    )
    print(
        f"{'edge R':>6} {'plan':<26} {'risk':>5} {'median $/mo':>12} {'p10 $/mo':>9} "
        f"{'P(>=2k)':>8} {'P(6/8 q)':>9} {'evals/yr':>8}"
    )
    for edge in EDGES:
        best = None
        for plan in PLANS:
            for risk in RISKS:
                rng = np.random.default_rng(12345)  # common random numbers across cells
                incomes, six, evals = [], 0, 0
                for _ in range(args.paths):
                    tr = path(rng, days, edge, args.target, args.per_day)
                    led = business(
                        [(d, t, rules[plan], risk) for d, t in zip(days, tr, strict=False)], budget
                    )
                    m = [x * args.accounts for x in monthly(led, months)]
                    incomes.append(np.mean(m))
                    six += sum(q > 0 for q in quarters(m)) >= 6
                    evals += led.evals
                inc = np.array(incomes)
                row = (
                    np.median(inc),
                    np.percentile(inc, 10),
                    (inc >= 2000).mean(),
                    six / args.paths,
                    evals / args.paths / (MONTHS / 12),
                    plan,
                    risk,
                )
                if best is None or row[0] > best[0]:
                    best = row
        med, p10, p2k, p6, ev, plan, risk = best
        print(
            f"{edge:>6.2f} {plan:<26} {risk:>5.0f} {med:>12,.0f} {p10:>9,.0f} "
            f"{p2k:>8.0%} {p6:>9.0%} {ev:>8.1f}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
