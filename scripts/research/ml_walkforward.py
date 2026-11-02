"""Machine-learning walk-forward search (design.md, Revision 2026-11-02b).

A gradient-boosted model (scikit-learn HistGradientBoostingClassifier) learns,
from features known at a decision time, whether MNQ / MES will be higher at
15:55 than at the next bar's open. The bot trades the first decision time of
the day where the model is confident, in that direction, with a stop of k ATR,
out at 15:55.

Walk-forward over Nov 2022 - Oct 2025, 8 untouched quarters (Nov 2023 - Oct 2025):
for each quarter, inside the 12 tuning months before it,
  - train on the first 9 months; on the last 3 (validation) pick the
    confidence threshold, the stop, the prop plan and the risk per trade by
    business income;
  - retrain on all 12 months; trade the untouched quarter with those choices.
The business simulation and the winner bar are walkforward.py's.

Usage: uv run python scripts/research/ml_walkforward.py [--horizon close]
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier

sys.path.insert(0, str(Path(__file__).parent))

import screen
import walkforward as wf

from moon_ai.propfirm import load_rules

DECISIONS = (30, 60, 90, 120, 180, 240)  # minutes after 09:30
DELTAS = (0.04, 0.08, 0.12, 0.16)
STOPS = (0.25, 0.5)


def features(mk: screen.Market, other: screen.Market) -> tuple[np.ndarray, np.ndarray, list]:
    """Rows (day, decision) with features known at the decision; label: up at 15:55."""
    o_idx = {d: i for i, d in enumerate(other.days)}
    rows, labels, keys = [], [], []
    atr60 = np.array([np.nanmean(mk.atr[max(0, i - 60) : i + 1]) for i in range(len(mk.days))])
    for i, d in enumerate(mk.days):
        if not mk.tradable[i]:
            continue
        a = mk.atr[i]
        o0 = mk.o[i, 0]
        j = o_idx.get(d)
        for m in DECISIONS:
            c = mk.c[i, m - 1]
            hi, lo = mk.h[i, :m].max(), mk.lo[i, :m].min()
            f = [
                (c - o0) / a,
                (c - mk.c[i, max(m - 16, 0)]) / a,
                (c - mk.c[i, max(m - 31, 0)]) / a,
                (hi - lo) / a,
                (c - lo) / (hi - lo) if hi > lo else 0.5,
                (o0 - mk.prev_close[i]) / a,
                (mk.prev_close[i] - mk.o[i - 1, 0]) / a if i > 0 else 0.0,
                (mk.on_high[i] - mk.on_low[i]) / a,
                (o0 - mk.on_high[i]) / a,
                (o0 - mk.on_low[i]) / a,
                a / atr60[i] if atr60[i] else 1.0,
                d.weekday(),
                m,
            ]
            if j is not None and other.tradable[j]:
                a2 = other.atr[j]
                f += [
                    (other.c[j, m - 1] - other.o[j, 0]) / a2,
                    (other.c[j, m - 1] - other.c[j, max(m - 16, 0)]) / a2,
                ]
            else:
                f += [np.nan, np.nan]
            rows.append(f)
            labels.append(1 if mk.c[i, screen.TIMEOUT_IDX] > mk.o[i, m] else 0)
            keys.append((i, m))
    return np.array(rows, float), np.array(labels), keys


class MarketML:
    def __init__(self, mk: screen.Market, other: screen.Market):
        self.mk = mk
        self.X, self.y, self.keys = features(mk, other)
        self.day_of = np.array([mk.days[i] for i, _ in self.keys])

    def fit(self, lo: date, hi: date) -> HistGradientBoostingClassifier:
        mask = (self.day_of >= lo) & (self.day_of < hi)
        model = HistGradientBoostingClassifier(
            max_iter=200, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=40
        )
        model.fit(self.X[mask], self.y[mask])
        return model

    def signals(self, model, lo: date, hi: date, delta: float, k: float):
        """side / entry / stop distance per day: the first confident decision time."""
        mk = self.mk
        n = len(mk.days)
        side, entry, dist = np.zeros(n), np.zeros(n, int), np.zeros(n)
        mask = (self.day_of >= lo) & (self.day_of < hi)
        if not mask.any():
            return side, entry, dist
        p = model.predict_proba(self.X[mask])[:, 1]
        for (i, m), pi in zip(
            [k_ for k_, ok in zip(self.keys, mask, strict=False) if ok], p, strict=True
        ):
            if side[i] != 0:
                continue
            if pi > 0.5 + delta:
                side[i], entry[i], dist[i] = 1, m, k * mk.atr[i]
            elif pi < 0.5 - delta:
                side[i], entry[i], dist[i] = -1, m, k * mk.atr[i]
        return side, entry, dist


def candidates(mls, models, lo, hi, delta, k):
    out = []
    for ml, model in zip(mls, models, strict=True):
        s, e, dist = ml.signals(model, lo, hi, delta, k)
        det = screen.simulate_detail(ml.mk, s, e, dist, None)
        out.append(wf.Candidate(f"ml d={delta} k={k}", ml.mk.symbol, det, ml.mk.days))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--accounts", type=int, default=3)
    ap.add_argument("--markets", default="both", choices=["both", "MNQ", "MES"])
    args = ap.parse_args()
    plans = {k: v for k, v in load_rules().items() if v.eval_fee is not None}
    mnq, mes = screen.load("MNQ.v.0"), screen.load("MES.v.0")
    mls = [MarketML(mnq, mes), MarketML(mes, mnq)]
    if args.markets != "both":
        mls = [m for m in mls if m.mk.symbol.startswith(args.markets)]
    print(f"rows: {', '.join(f'{m.mk.symbol} {len(m.y)}' for m in mls)}")

    oos = []
    for q in range(wf.N_QUARTERS):
        test_lo = wf.add_months(wf.FIRST_TEST, 3 * q)
        test_hi = wf.add_months(test_lo, 3)
        train_lo = wf.add_months(test_lo, -12)
        val_lo = wf.add_months(test_lo, -3)
        inner = [ml.fit(train_lo, val_lo) for ml in mls]
        val_months = wf.months_between(val_lo, test_lo)
        best = (0.0, None, 0.0, None, None)
        for delta in DELTAS:
            for k in STOPS:
                cands = candidates(mls, inner, val_lo, test_lo, delta, k)
                for plan in plans.values():
                    for risk in wf.RISKS:
                        led = wf.business(wf.day_list(cands, val_lo, test_lo, plan, risk))
                        net = sum(wf.monthly(led, val_months)) / len(val_months)
                        if net > best[0]:
                            best = (net, plan, risk, delta, k)
        net, plan, risk, delta, k = best
        if plan is None:
            print(f"Q{q + 1} {test_lo}: sit out (nothing made money in validation)")
            oos += wf.day_list([], test_lo, test_hi, None, 0.0)
            continue
        full = [ml.fit(train_lo, test_lo) for ml in mls]
        cands = candidates(mls, full, test_lo, test_hi, delta, k)
        oos += wf.day_list(cands, test_lo, test_hi, plan, risk)
        n_tr = sum(
            int((~np.isnan(c.detail.r[[test_lo <= d < test_hi for d in c.days]])).sum())
            for c in cands
        )
        print(
            f"Q{q + 1} {test_lo}: {plan.name} @ ${risk:.0f}, confidence +{delta}, stop {k} ATR "
            f"(validation ${net:,.0f}/mo per account); {n_tr} trades"
        )

    led = wf.business(oos, wf.MONTHLY_EVAL_BUDGET / args.accounts)
    months = wf.months_between(wf.FIRST_TEST, wf.add_months(wf.FIRST_TEST, 3 * wf.N_QUARTERS))
    per = wf.monthly(led, months)
    total = [x * args.accounts for x in per]
    fees = [led.fees.get(m, 0.0) * args.accounts for m in months]
    q_net = [sum(total[3 * q : 3 * q + 3]) for q in range(wf.N_QUARTERS)]
    avg = sum(total) / len(total)
    print(
        f"\nuntouched quarters, {args.accounts} accounts: {', '.join(f'{x:+,.0f}' for x in q_net)}"
    )
    print(f"  evaluations {led.evals}, passed {led.passes}, funded blown {led.funded_blown}")
    checks = [
        (f"average >= $2,000/month (got ${avg:,.0f})", avg >= wf.TARGET_MONTHLY),
        (f"6 of 8 quarters (got {sum(x > 0 for x in q_net)})", sum(x > 0 for x in q_net) >= 6),
        (f"eval spend <= $500/month (max ${max(fees):,.0f})", max(fees) <= wf.MONTHLY_EVAL_BUDGET),
    ]
    for name, ok in checks:
        print(f"  {'✓' if ok else '✕'} {name}")
    winner = all(ok for _, ok in checks)
    print(f"verdict: {'WINNER' if winner else 'not a winner'}")
    return 0 if winner else 1


if __name__ == "__main__":
    sys.exit(main())
