"""LucidFlex 50K evaluation + funded simulator, run from every start day.

Rules (see docs/research/strategy-search.md, "Rules simulated"; checked 2026-11-03
against secondary sources because Lucid's own help pages are not reachable from
the research container -- where sources disagree the stricter number is used):

Evaluation
- start balance $50,000; profit target $3,000 (pass at end of day once the
  balance is >= $53,000, the consistency rule holds and >= 2 trading days).
- Max loss limit $2,000, trailing on end-of-day balance highs, locking at the
  start balance. Breached if equity at any moment <= the MLL.
- Consistency: largest winning day <= 50% of total profit at the moment of pass.
- No daily loss limit. Max size 4 minis / 40 micros.
- Our own bar: must pass within 21 trading days (one month).

Funded (LucidFlex)
- Same $2,000 EOD trailing MLL locking at the start balance (some sources say
  $2,500; the stricter $2,000 is used). No consistency rule, no daily limit.
- Size cap 20 micros until the balance reaches $52,000, then 40 (scaling plan
  tiers UNVERIFIED; this is a conservative guess).
- Payout cycle: >= 5 days each with >= $150 profit since the last payout, and a
  positive cycle. Request up to 50% of profit above the start balance, capped at
  $2,000, minimum $500. Trader keeps 90%.
- Our bar: >= $1,000 net (after the split) withdrawn in each of the first six
  21-trading-day months.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numba import njit

START = 50_000.0
TARGET = 3_000.0
MLL = 2_000.0
EVAL_DAYS = 21
MONTH = 21
FUNDED_MONTHS = 6
NET_PER_MONTH = 1_000.0
SPLIT = 0.9


@njit(cache=True)
def _units(cushion, to_target, unit_risk, risk_frac, cap, coast):
    """Contracts (micro units) for the day: risk a fraction of the cushion above
    the MLL, never more than needed to reach the target (when coast > 0)."""
    if unit_risk <= 0:
        return 0
    u = np.floor(risk_frac * cushion / unit_risk)
    if coast > 0 and to_target > 0:
        u2 = np.ceil(coast * to_target / unit_risk)
        if u2 < u:
            u = u2
    if u > cap:
        u = cap
    if u < 0:
        u = 0
    return u


@njit(cache=True)
def run_eval(pnl, low, unit_risk, s, risk_frac, coast, max_days):
    """Evaluation from day s. Returns (status, days_used, end_day).
    status 1 = passed, 0 = failed (MLL), 2 = timed out, 3 = ran out of data."""
    bal = START
    mll = START - MLL
    hi = START
    best_day = 0.0
    n = pnl.shape[0]
    days = 0
    d = s
    while d < n and days < max_days:
        cushion = bal - mll
        u = _units(cushion, START + TARGET - bal, unit_risk[d], risk_frac, 40.0, coast)
        days += 1
        if bal + u * low[d] <= mll:
            return 0, days, d
        p = u * pnl[d]
        bal += p
        if p > best_day:
            best_day = p
        if bal > hi:
            hi = bal
            nm = hi - MLL
            if nm > START:
                nm = START
            if nm > mll:
                mll = nm
        prof = bal - START
        if prof >= TARGET and days >= 2 and best_day <= 0.5 * prof:
            return 1, days, d
        d += 1
    if days >= max_days:
        return 2, days, d - 1
    return 3, days, d - 1


@njit(cache=True)
def run_funded(pnl, low, unit_risk, s, risk_frac, months, withdraw_frac):
    """Funded account from day s. Returns (blown_day_or_-1, net per month array)."""
    bal = START
    mll = START - MLL
    hi = START
    net = np.zeros(months)
    n = pnl.shape[0]
    good_days = 0
    cycle_start_bal = bal
    total_days = months * MONTH
    for k in range(total_days):
        d = s + k
        if d >= n:
            return -2, net
        cap = 20.0 if bal < START + 2000 else 40.0
        u = _units(bal - mll, 0.0, unit_risk[d], risk_frac, cap, 0.0)
        if bal + u * low[d] <= mll:
            return k, net
        p = u * pnl[d]
        bal += p
        if p >= 150:
            good_days += 1
        if bal > hi:
            hi = bal
            nm = hi - MLL
            if nm > START:
                nm = START
            if nm > mll:
                mll = nm
        if good_days >= 5 and bal > cycle_start_bal:
            amt = withdraw_frac * 0.5 * (bal - START)
            if amt > 2000.0:
                amt = 2000.0
            if amt >= 500.0:
                bal -= amt
                net[k // MONTH] += amt * SPLIT
                good_days = 0
                cycle_start_bal = bal
                hi = bal  # payouts do not raise the trail; keep the trail at its level
    return -1, net


@njit(cache=True)
def sweep(pnl, low, unit_risk, starts, risk_frac, coast, f_risk_frac, withdraw_frac):
    m = starts.shape[0]
    status = np.zeros(m, np.int64)
    days = np.zeros(m, np.int64)
    full = np.zeros(m, np.int64)  # 1 = passed eval and >= $1k net in each of 6 months
    funded_ok = np.zeros(m, np.int64)  # -1 not evaluated (no data)
    for i in range(m):
        st, du, end = run_eval(pnl, low, unit_risk, starts[i], risk_frac, coast, EVAL_DAYS)
        status[i] = st
        days[i] = du
        funded_ok[i] = -1
        if st == 1:
            blown, net = run_funded(pnl, low, unit_risk, end + 1, f_risk_frac, FUNDED_MONTHS,
                                    withdraw_frac)
            if blown == -2:
                continue
            ok = 1
            for j in range(FUNDED_MONTHS):
                if net[j] < NET_PER_MONTH:
                    ok = 0
            funded_ok[i] = ok
            full[i] = ok
    return status, days, full, funded_ok


@dataclass
class PropResult:
    pass_rate: float  # eval passed within 21 trading days
    fail_rate: float  # MLL breached
    median_days: float
    full_rate: float  # passed AND >= $1k net each of 6 funded months (over starts with data)
    funded_rate: float  # given passed, 6 good months
    n_starts: int
    n_full: int

    def __str__(self) -> str:
        return (f"pass {self.pass_rate:5.1%} bust {self.fail_rate:5.1%} med {self.median_days:4.1f}d "
                f"| full {self.full_rate:5.1%} (funded|pass {self.funded_rate:5.1%}) n={self.n_starts}")


def evaluate(pnl, low, unit_risk, risk_frac=0.25, coast=0.0, f_risk_frac=None,
             withdraw_frac=1.0, starts=None) -> PropResult:
    """Run an eval (and, if passed, a funded account) from every start day."""
    pnl = np.ascontiguousarray(pnl, dtype=np.float64)
    low = np.ascontiguousarray(np.minimum(low, 0.0), dtype=np.float64)
    unit_risk = np.ascontiguousarray(unit_risk, dtype=np.float64)
    n = len(pnl)
    if starts is None:
        starts = np.arange(max(n - EVAL_DAYS + 1, 0))
    starts = np.asarray(starts, dtype=np.int64)
    if f_risk_frac is None:
        f_risk_frac = risk_frac
    st, du, full, fok = sweep(pnl, low, unit_risk, starts, risk_frac, coast, f_risk_frac, withdraw_frac)
    valid = st != 3
    passed = st[valid] == 1
    have_full = (fok >= 0) | ((st != 1) & valid)
    # full-run rate over starts whose whole horizon fits in the data
    horizon_ok = starts + EVAL_DAYS + FUNDED_MONTHS * MONTH <= n
    fr_mask = horizon_ok & valid
    full_rate = float(full[fr_mask].mean()) if fr_mask.any() else float("nan")
    pm = (st == 1) & (fok >= 0)
    funded_rate = float(fok[pm].mean()) if pm.any() else float("nan")
    return PropResult(
        pass_rate=float(passed.mean()) if valid.any() else float("nan"),
        fail_rate=float((st[valid] == 0).mean()) if valid.any() else float("nan"),
        median_days=float(np.median(du[valid][passed])) if passed.any() else float("nan"),
        full_rate=full_rate,
        funded_rate=funded_rate,
        n_starts=int(valid.sum()),
        n_full=int(fr_mask.sum()),
    )
