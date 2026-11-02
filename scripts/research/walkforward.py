"""Walk-forward strategy search for the business goal (design.md, Revision 2026-11-02b).

Tune on 12 months, trade the next 3 months untouched, roll forward by 3 months,
over Nov 2022 - Oct 2025 (8 untouched quarters, Nov 2023 - Oct 2025). In each
tuning window, using only that window's data:

1. score every rule variant on MNQ and MES (scripts/research/screen.py) by its
   yearly Sharpe; keep the best `--top` with a positive mean and enough trades;
2. pick the prop plan and risk per trade that make the most money a month in a
   business replay of those variants over the tuning window.

The untouched quarter is then traded with those choices fixed. A business
simulation runs across all 8 quarters: buy an evaluation, pass or blow it, trade
the funded account and take payouts by the plan's rules, buy a new evaluation
when an account blows. Income is that, times 3 copy-traded accounts.

A winner (design.md): average total income >= $2,000 a month after fees, money
made in at least 6 of 8 quarters, and evaluation spending <= $500 in every month.

Usage: uv run python scripts/research/walkforward.py [--top 3] [--accounts 3]
"""

from __future__ import annotations

import argparse
import math
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

import screen

from moon_ai.propfirm import Account, Rules, Trade, load_rules

FIRST_TEST = date(2023, 11, 1)
N_QUARTERS = 8
RISKS = (100.0, 150.0, 200.0, 300.0, 400.0, 500.0)
MIN_TRAIN_TRADES = 30
MONTHLY_EVAL_BUDGET = 500.0
TARGET_MONTHLY = 2000.0


def add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, 1)


@dataclass
class Candidate:
    name: str
    symbol: str
    detail: screen.Detail
    days: list[date]


def trades_of(c: Candidate, lo: date, hi: date) -> list[Trade]:
    out = []
    for i, d in enumerate(c.days):
        if not (lo <= d < hi) or np.isnan(c.detail.r[i]):
            continue
        base = datetime.combine(d, datetime.min.time()) + timedelta(hours=9, minutes=30)
        out.append(
            Trade(
                session=d,
                pnl=float(c.detail.pnl[i]),
                risk=float(c.detail.risk[i]),
                worst=float(c.detail.worst[i]),
                best=float(c.detail.best[i]),
                exit=base + timedelta(minutes=float(c.detail.exit_min[i])),
                entry=base + timedelta(minutes=float(c.detail.entry_min[i])),
            )
        )
    return out


def score(c: Candidate, lo: date, hi: date) -> tuple[float, int, float]:
    """(yearly Sharpe of daily R, trades, mean R) over [lo, hi)."""
    mask = np.array([lo <= d < hi for d in c.days])
    r = c.detail.r[mask]
    x = r[~np.isnan(r)]
    daily = np.nan_to_num(r, nan=0.0)
    if len(x) < MIN_TRAIN_TRADES or daily.std(ddof=1) == 0:
        return -math.inf, len(x), float(x.mean()) if len(x) else 0.0
    return float(daily.mean() / daily.std(ddof=1) * math.sqrt(252)), len(x), float(x.mean())


# --- the business simulation --------------------------------------------------------------


@dataclass
class Ledger:
    fees: dict[tuple[int, int], float]
    payouts: dict[tuple[int, int], float]
    evals: int = 0
    passes: int = 0
    funded_blown: int = 0


def business(
    days: list[tuple[date, list[Trade], Rules | None, float]],
    budget: float = math.inf,
) -> Ledger:
    """One account slot over consecutive days; each day carries its trades and the
    plan and risk in force. A new evaluation is bought on the plan in force that day,
    unless it would take this slot's evaluation spending this month over `budget`."""
    led = Ledger(defaultdict(float), defaultdict(float))
    acc: Account | None = None
    rules: Rules | None = None
    phase = "none"
    first_day: date | None = None
    since = 0
    window: list[date] = []
    paid_n = 0
    for d, trades, plan, risk in days:
        if phase == "none":
            if plan is None or not trades:
                continue
            if led.fees[(d.year, d.month)] + (plan.eval_fee or 0.0) > budget + 1e-9:
                continue  # this month's evaluation budget is spent
            rules, phase, first_day = plan, "eval", d
            acc = Account(rules.evaluation)
            led.evals += 1
            led.fees[(d.year, d.month)] += rules.eval_fee or 0.0
        assert acc is not None and rules is not None
        traded = False
        failed = False
        for t in sorted(trades, key=lambda t: t.exit or datetime.max):
            if acc.done_for_day(t.session):
                break
            n = acc.contracts(t, risk)
            if n < 1:
                continue
            traded = True
            if acc.take(t, n):
                failed = True
                break
        acc.end_day()
        if failed:
            if phase == "funded":
                led.funded_blown += 1
            phase = "none"
            continue
        if phase == "eval":
            ph = rules.evaluation
            if first_day and (d - first_day).days >= 365:
                phase = "none"  # too slow: buy a new one
                continue
            if (
                acc.balance >= (ph.profit_target or math.inf)
                and len(acc.days) >= ph.min_days
                and acc.consistent(ph.consistency_pct, acc.balance)
            ):
                led.passes += 1
                led.fees[(d.year, d.month)] += rules.activation_fee
                phase, acc, since, window, paid_n = "funded", Account(rules.funded), 0, [], 0
            continue
        # funded: payout check, as in propfirm._funded
        if not traded:
            continue
        po = rules.payouts
        since += 1
        window.append(d)
        profit_days = sum(acc.day_pnl.get(x, 0.0) >= po.profit_day_usd for x in window)
        cycle = sum(acc.day_pnl.get(x, 0.0) for x in window)
        avail = acc.balance - po.buffer
        cap = po.max_request
        if isinstance(cap, list):
            cap = cap[min(paid_n, len(cap) - 1)]
        if cap is not None:
            avail = min(avail, cap)
        if po.max_pct_of_profit is not None:
            avail = min(avail, acc.balance * po.max_pct_of_profit / 100)
        best = max((acc.day_pnl.get(x, 0.0) for x in window), default=0.0)
        consistent = po.consistency_pct is None or (
            cycle > 0 and best <= cycle * po.consistency_pct / 100
        )
        if (
            since >= po.min_days
            and profit_days >= po.min_profit_days
            and acc.balance >= po.min_balance
            and (po.min_cycle_profit is None or cycle > po.min_cycle_profit)
            and avail >= max(po.min_request, 0.01)
            and consistent
        ):
            acc.balance -= avail
            led.payouts[(d.year, d.month)] += avail * po.split
            paid_n += 1
            if po.floor_after_payout is not None:
                acc.floor = po.floor_after_payout
                acc.peak = acc.floor + rules.funded.max_loss
            since, window = 0, []
    return led


def monthly(led: Ledger, months: list[tuple[int, int]]) -> list[float]:
    return [led.payouts.get(m, 0.0) - led.fees.get(m, 0.0) for m in months]


def day_list(cands: list[Candidate], lo: date, hi: date, plan: Rules | None, risk: float):
    by_day: dict[date, list[Trade]] = defaultdict(list)
    for c in cands:
        for t in trades_of(c, lo, hi):
            by_day[t.session].append(t)
    all_days = sorted({d for c in cands for d in c.days if lo <= d < hi})
    return [(d, by_day.get(d, []), plan, risk) for d in all_days]


def months_between(lo: date, hi: date) -> list[tuple[int, int]]:
    out, d = [], date(lo.year, lo.month, 1)
    while d < hi:
        out.append((d.year, d.month))
        d = add_months(d, 1)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--accounts", type=int, default=3)
    ap.add_argument("--daily-cap", type=float, help="our own soft daily loss cap, USD")
    ap.add_argument(
        "--objective",
        choices=["sharpe", "business"],
        default="sharpe",
        help="rank variants by Sharpe, or by business income in the tuning year",
    )
    ap.add_argument("--prefilter", type=int, default=40, help="business: Sharpe pre-filter")
    ap.add_argument(
        "--markets",
        default="MNQ,MES",
        help="comma-separated roots, e.g. MNQ,MES,M2K,MYM,MGC,MCL,M6E",
    )
    ap.add_argument(
        "--per-market",
        type=int,
        default=0,
        help="instead of a global top N, keep the best N variants of each market",
    )
    args = ap.parse_args()
    plans = {k: v for k, v in load_rules().items() if v.eval_fee is not None}
    if args.daily_cap:
        from moon_ai.propfirm import with_daily_cap

        plans = {k: with_daily_cap(v, args.daily_cap) for k, v in plans.items()}
    roots = args.markets.split(",")
    markets = [screen.load(f"{r}.v.0", min_bars=380 if r in ("MNQ", "MES") else 250) for r in roots]
    cands: list[Candidate] = []
    for name, (fn, params), tr in screen.variants():
        for mk in markets:
            side, entry, dist = fn(mk, *params)
            cands.append(
                Candidate(
                    name, mk.symbol, screen.simulate_detail(mk, side, entry, dist, tr), mk.days
                )
            )
    print(f"{len(cands)} candidates (variant x market); plans: {', '.join(plans)}")

    oos: list[tuple[date, list[Trade], Rules | None, float]] = []
    quarters = []
    for q in range(N_QUARTERS):
        test_lo = add_months(FIRST_TEST, 3 * q)
        test_hi = add_months(test_lo, 3)
        train_lo = add_months(test_lo, -12)
        scored = sorted(((score(c, train_lo, test_lo), c) for c in cands), key=lambda x: -x[0][0])
        chosen = [c for (s, n, m), c in scored if s > 0 and m > 0][: args.top]
        if args.per_market:
            chosen = []
            for mk in markets:
                mine = [c for (s, n, m), c in scored if c.symbol == mk.symbol and s > 0 and m > 0]
                chosen += mine[: args.per_market]
        train_months = months_between(train_lo, test_lo)
        if args.objective == "business":
            pool = [c for (s, n, m), c in scored if s > 0 and m > 0][: args.prefilter]
            ranked = []
            for c in pool:
                best = max(
                    sum(monthly(business(day_list([c], train_lo, test_lo, p, r)), train_months))
                    for p in plans.values()
                    for r in RISKS
                )
                ranked.append((best, c))
            ranked.sort(key=lambda x: -x[0])
            chosen = [c for v, c in ranked if v > 0][: args.top]
        best_plan, best_risk, best_net = None, 0.0, 0.0
        for plan in plans.values():
            for risk in RISKS:
                led = business(day_list(chosen, train_lo, test_lo, plan, risk))
                net = sum(monthly(led, train_months)) / len(train_months)
                if net > best_net:
                    best_plan, best_risk, best_net = plan, risk, net
        quarters.append((test_lo, test_hi, chosen, best_plan, best_risk, best_net, scored[:3]))
        oos += day_list(chosen, test_lo, test_hi, best_plan, best_risk)
        names = "; ".join(f"{c.name} [{c.symbol[:3]}]" for c in chosen) or "none"
        plan_name = best_plan.name if best_plan else "sit out"
        print(
            f"Q{q + 1} {test_lo}..{test_hi}: {plan_name} @ ${best_risk:.0f}/trade "
            f"(tuning-year net ${best_net:,.0f}/mo per account)\n    {names}"
        )

    led = business(oos, MONTHLY_EVAL_BUDGET / args.accounts)
    months = months_between(FIRST_TEST, add_months(FIRST_TEST, 3 * N_QUARTERS))
    per_acct = monthly(led, months)
    total = [x * args.accounts for x in per_acct]
    fees_total = [led.fees.get(m, 0.0) * args.accounts for m in months]
    q_net = [sum(total[3 * q : 3 * q + 3]) for q in range(N_QUARTERS)]
    avg = sum(total) / len(total)
    print(f"\nuntouched quarters, {args.accounts} copy-traded accounts:")
    print("  month       net total   eval fees")
    for m, x, f in zip(months, total, fees_total, strict=True):
        print(f"  {m[0]}-{m[1]:02d}  {x:>11,.0f}  {f:>10,.0f}")
    print(f"  quarters: {', '.join(f'{x:+,.0f}' for x in q_net)}")
    print(
        f"  evaluations bought {led.evals}, passed {led.passes}, "
        f"funded accounts blown {led.funded_blown} (per account slot)"
    )
    checks = [
        (f"average >= ${TARGET_MONTHLY:,.0f}/month total (got ${avg:,.0f})", avg >= TARGET_MONTHLY),
        (
            f"money made in >= 6 of 8 quarters (got {sum(x > 0 for x in q_net)})",
            sum(x > 0 for x in q_net) >= 6,
        ),
        (
            f"eval spending <= ${MONTHLY_EVAL_BUDGET:,.0f} every month "
            f"(max ${max(fees_total):,.0f})",
            max(fees_total) <= MONTHLY_EVAL_BUDGET,
        ),
    ]
    for name, ok in checks:
        print(f"  {'✓' if ok else '✕'} {name}")
    winner = all(ok for _, ok in checks)
    print(f"verdict: {'WINNER' if winner else 'not a winner'}")
    return 0 if winner else 1


if __name__ == "__main__":
    sys.exit(main())
