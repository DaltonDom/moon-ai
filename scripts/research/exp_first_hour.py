"""Experiments on the best signal so far: first-hour momentum on MNQ (search-plan.md).

Each experiment is a fixed rule; only the prop plan and risk are tuned, per
quarter, in the 12 months before it (as walkforward.py --fixed). Every
experiment is printed, so the full list of what was tried is in the log.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

import screen
import walkforward as wf

from moon_ai.propfirm import load_rules, with_daily_cap


def first_hour(mk: screen.Market, m: int = 60) -> np.ndarray:
    return mk.c[:, m - 1] - mk.o[:, 0]


def aligned(base: screen.Market, others: list[screen.Market], m: int = 60) -> np.ndarray:
    """Per base day: +1 / -1 if every other market's first-hour move has the same
    sign as the base's, else 0 (or 0 when a market has no data that day)."""
    sb = np.sign(first_hour(base, m))
    out = sb.copy()
    for o in others:
        idx = {d: i for i, d in enumerate(o.days)}
        so = np.sign(first_hour(o, m))
        for i, d in enumerate(base.days):
            j = idx.get(d)
            if j is None or so[j] != sb[i]:
                out[i] = 0
    return out


def run(name, mk, side, entry, dist, target, be_r, plans, risks, steady=0.0):
    det = screen.simulate_detail(mk, side, entry, dist, target, be_r=be_r)
    c = wf.Candidate(name, mk.symbol, det, mk.days)
    oos = []
    for q in range(wf.N_QUARTERS):
        lo = wf.add_months(wf.FIRST_TEST, 3 * q)
        hi = wf.add_months(lo, 3)
        tr = wf.add_months(lo, -12)
        months = wf.months_between(tr, lo)
        best = (0.0, None, 0.0)
        for plan in plans.values():
            for risk in risks:
                net_m = wf.monthly(wf.business(wf.day_list([c], tr, lo, plan, risk)), months)
                v = sum(net_m) / len(months) - steady * float(np.std(net_m))
                if v > best[0]:
                    best = (v, plan, risk)
        oos += wf.day_list([c], lo, hi, best[1], best[2])
    led = wf.business(oos, wf.MONTHLY_EVAL_BUDGET / 3)
    months = wf.months_between(wf.FIRST_TEST, wf.add_months(wf.FIRST_TEST, 3 * wf.N_QUARTERS))
    total = [x * 3 for x in wf.monthly(led, months)]
    qn = [sum(total[3 * q : 3 * q + 3]) for q in range(wf.N_QUARTERS)]
    r = det.r[~np.isnan(det.r)]
    win = sum(x > 0 for x in qn)
    print(
        f"{name:<48} trades {len(r):5} mean {r.mean():+.3f}R | "
        f"${sum(total) / len(total):>6,.0f}/mo, "
        f"{win}/8 qtrs | {' '.join(f'{x:+.0f}' for x in qn)}",
        flush=True,
    )


def agree_count(base: screen.Market, others: list[screen.Market], m: int = 60) -> np.ndarray:
    """How many of the other markets' first-hour moves share the base's sign."""
    sb = np.sign(first_hour(base, m))
    cnt = np.zeros(len(base.days))
    for o in others:
        idx = {d: i for i, d in enumerate(o.days)}
        so = np.sign(first_hour(o, m))
        for i, d in enumerate(base.days):
            j = idx.get(d)
            if j is not None and so[j] == sb[i] and sb[i] != 0:
                cnt[i] += 1
    return cnt


def breadth_grid() -> int:
    """Round 2: variations of the breadth rule (all logged)."""
    mnq = screen.load("MNQ.v.0")
    others = [screen.load(f"{r}.v.0", 380 if r == "MES" else 250) for r in ("MES", "M2K", "MYM")]
    plans = {k: with_daily_cap(v, 1000) for k, v in load_rules().items() if v.eval_fee}
    n = len(mnq.days)
    for m in (30, 60, 90):
        base = np.sign(first_hour(mnq, m))
        cnt = agree_count(mnq, others, m)
        for need in (2, 3):
            side = np.where(cnt >= need, base, 0)
            for k in (0.25, 0.5):
                for tgt in (1.5, 2.0, 3.0):
                    run(
                        f"breadth>={need} m={m} k={k} t={tgt}",
                        mnq,
                        side,
                        np.full(n, m),
                        k * mnq.atr,
                        tgt,
                        None,
                        plans,
                        wf.RISKS,
                    )
    return 0


def main() -> int:
    mnq = screen.load("MNQ.v.0")
    others = {r: screen.load(f"{r}.v.0", 380 if r == "MES" else 250) for r in ("MES", "M2K", "MYM")}
    plans = {k: with_daily_cap(v, 1000) for k, v in load_rules().items() if v.eval_fee}
    risks = wf.RISKS
    n = len(mnq.days)
    m = 60
    base = np.sign(first_hour(mnq, m))
    entry = np.full(n, m)
    dist = 0.25 * mnq.atr
    gap = np.sign(mnq.o[:, 0] - mnq.prev_close)
    rng = (mnq.h[:, :m].max(1) - mnq.lo[:, :m].min(1)) / mnq.atr
    exps = {
        "baseline (m60 th0 k.25 t2)": (base, 2.0, None),
        "breakeven at +1R": (base, 2.0, 1.0),
        "breadth: MES, M2K, MYM agree": (aligned(mnq, list(others.values()), m), 2.0, None),
        "breadth: MES agrees": (aligned(mnq, [others["MES"]], m), 2.0, None),
        "gap agrees": (np.where(gap == base, base, 0), 2.0, None),
        "gap disagrees": (np.where(gap == -base, base, 0), 2.0, None),
        "first-hour range > 0.4 ATR": (np.where(rng > 0.4, base, 0), 2.0, None),
        "first-hour range < 0.4 ATR": (np.where(rng < 0.4, base, 0), 2.0, None),
        "breadth all + breakeven": (aligned(mnq, list(others.values()), m), 2.0, 1.0),
        "target 3R": (base, 3.0, None),
        "target 1.5R": (base, 1.5, None),
    }
    for name, (side, tgt, be) in exps.items():
        run(name, mnq, side, entry, dist, tgt, be, plans, risks)
    return 0


def fixed_business() -> int:
    """Round 3: the breadth signal with ONE plan and risk held all 8 quarters
    (no per-quarter re-tuning), to see how stable the outcome is."""
    mnq = screen.load("MNQ.v.0")
    others = [screen.load(f"{r}.v.0", 380 if r == "MES" else 250) for r in ("MES", "M2K", "MYM")]
    rules = {k: with_daily_cap(v, 1000) for k, v in load_rules().items() if v.eval_fee}
    n = len(mnq.days)
    base = np.sign(first_hour(mnq, 60))
    side = np.where(agree_count(mnq, others, 60) >= 3, base, 0)
    months = wf.months_between(wf.FIRST_TEST, wf.add_months(wf.FIRST_TEST, 24))
    lo, hi = wf.FIRST_TEST, wf.add_months(wf.FIRST_TEST, 24)
    for tgt in (1.5, 2.0, 3.0):
        det = screen.simulate_detail(mnq, side, np.full(n, 60), 0.25 * mnq.atr, tgt)
        c = wf.Candidate("b", mnq.symbol, det, mnq.days)
        for plan_name in ("tradeify_growth_50k", "lucidflex_50k", "tradeify_select_daily_50k"):
            for risk in (200.0, 250.0, 300.0, 400.0, 500.0):
                led = wf.business(
                    wf.day_list([c], lo, hi, rules[plan_name], risk), wf.MONTHLY_EVAL_BUDGET / 3
                )
                total = [x * 3 for x in wf.monthly(led, months)]
                qn = [sum(total[3 * q : 3 * q + 3]) for q in range(8)]
                print(
                    f"t={tgt} {plan_name:<26} ${risk:>4.0f}: ${sum(total) / 24:>6,.0f}/mo, "
                    f"{sum(x > 0 for x in qn)}/8 | evals {led.evals} passed {led.passes} "
                    f"blown {led.funded_blown} | {' '.join(f'{x:+.0f}' for x in qn)}",
                    flush=True,
                )
    return 0


if __name__ == "__main__":
    if "--breadth" in sys.argv:
        sys.exit(breadth_grid())
    if "--fixed-business" in sys.argv:
        sys.exit(fixed_business())
    sys.exit(main())
