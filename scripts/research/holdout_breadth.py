"""The one-look clean check of the breadth first-hour candidate on Nov 2025 - Oct 2026.

Rules and pass test: docs/research/candidate-breadth-first-hour.md (fixed before
this ran). The look is logged in data/holdout_checks.jsonl; a second look is
refused.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

import exp_first_hour as ex
import screen
import walkforward as wf

from moon_ai.holdout import HOLDOUT_END, HOLDOUT_START, sign_off
from moon_ai.propfirm import load_rules, with_daily_cap

WARMUP_FROM = date(2025, 6, 1)  # research data, for the 14-day ATR


def main() -> int:
    sign_off("breadth_first_hour", "candidate-v1", HOLDOUT_START, HOLDOUT_END, symbol="MNQ.v.0")
    kw = {"start": WARMUP_FROM, "end": HOLDOUT_END}
    mnq = screen.load("MNQ.v.0", 380, **kw)
    others = [
        screen.load(f"{r}.v.0", 380 if r == "MES" else 250, **kw) for r in ("MES", "M2K", "MYM")
    ]
    n = len(mnq.days)
    side = np.where(ex.agree_count(mnq, others, 60) >= 3, np.sign(ex.first_hour(mnq, 60)), 0)
    in_year = np.array([HOLDOUT_START <= d < HOLDOUT_END for d in mnq.days])
    side = np.where(in_year, side, 0)
    det = screen.simulate_detail(mnq, side, np.full(n, 60), 0.25 * mnq.atr, 2.0)
    r = det.r[~np.isnan(det.r)]
    print(f"MNQ days in the year: {int(in_year.sum())}; trades {len(r)}")
    print(
        f"mean net R per trade {r.mean():+.3f}; total {r.sum():+.1f}R; "
        f"win rate {(r > 0).mean():.0%}"
    )
    c = wf.Candidate("breadth", mnq.symbol, det, mnq.days)
    rules = with_daily_cap(load_rules()["tradeify_growth_50k"], 1000)
    led = wf.business(
        wf.day_list([c], HOLDOUT_START, HOLDOUT_END, rules, 600.0), wf.MONTHLY_EVAL_BUDGET / 3
    )
    months = wf.months_between(HOLDOUT_START, HOLDOUT_END)
    total = [x * 3 for x in wf.monthly(led, months)]
    qn = [sum(total[3 * q : 3 * q + 3]) for q in range(4)]
    print("month       net (3 accounts)")
    for m, x in zip(months, total, strict=True):
        print(f"  {m[0]}-{m[1]:02d}  {x:>10,.0f}")
    print(
        f"quarters: {' '.join(f'{x:+,.0f}' for x in qn)}; year net {sum(total):+,.0f} "
        f"(${sum(total) / 12:,.0f}/month)"
    )
    print(f"evaluations {led.evals}, passed {led.passes}, funded blown {led.funded_blown}")
    checks = [
        ("mean net R per trade > 0", r.mean() > 0),
        ("business net over the year > 0 after fees", sum(total) > 0),
    ]
    for name, ok in checks:
        print(f"  {'✓' if ok else '✕'} {name}")
    ok = all(x for _, x in checks)
    print(f"verdict: {'PASSES the clean check' if ok else 'FAILS the clean check'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
