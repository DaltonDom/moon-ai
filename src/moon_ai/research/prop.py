"""Prop-firm evaluation simulator (design.md, 2026-11-02 revision, step 3).

Replays a strategy's day-by-day trades through one evaluation account's rules
and says whether the account passes, fails or is still open when the data ends.

Rules modelled (prop-firms-and-order-routing.md; rules change often, so check
the firm before trusting a number here):

- **End-of-day trailing max loss.** The floor is the highest end-of-day
  balance minus `max_loss`, and never rises above the start balance. Breaching
  the floor at any moment fails the account, so each trade's worst open loss
  (MAE) is checked, not just its close.
- **Daily loss limit** (optional). A day that loses `daily_loss` is
  liquidated at that loss; the account survives.
- **Profit target** checked at end of day.
- **Consistency** (optional): on the day the target is met, the best day must
  be at most `consistency` of total profit. Until it is, trading continues.
- **Sizing:** contracts = risk_usd / (stop distance x point value + round-trip
  commission), rounded down and capped at `max_contracts`. Zero contracts
  skips the trade.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Account:
    name: str
    start: float
    target: float
    max_loss: float
    max_contracts: int  # micros
    risk_usd: float  # risk per trade, fixed before any result is seen
    daily_loss: float | None = None
    consistency: float | None = None


TOPSTEP_50K = Account("Topstep 50K Combine", 50_000, 3_000, 2_000, 50, 400, 1_000, 0.5)
LUCID_FLEX_25K = Account("LucidFlex 25K", 25_000, 1_250, 1_000, 20, 200)
ACCOUNTS = (TOPSTEP_50K, LUCID_FLEX_25K)


@dataclass(frozen=True)
class DayTrade:
    """One day's trade, per contract."""

    day: int  # index into the trading-day calendar
    pnl_usd: float  # net of commission
    mae_usd: float  # worst open loss, >= 0
    risk_usd: float  # stop distance x point value


@dataclass(frozen=True)
class Outcome:
    status: str  # "pass", "fail", "open"
    days: int  # trading days from start to the verdict (or to the data's end)
    balance: float


def contracts(acct: Account, risk_per_contract: float, commission_rt: float) -> int:
    per = risk_per_contract + commission_rt
    if per <= 0:
        return 0
    return int(min(acct.max_contracts, acct.risk_usd // per))


def day_arrays(
    acct: Account, trades: Sequence[DayTrade], n_days: int, commission_rt: float = 2.0
) -> tuple[list[float], list[float], list[bool]]:
    """Per calendar day: the sized net P&L, the worst moment of the day, and
    whether a trade was taken. Computed once per account and trade list."""
    pnl, worst, traded = [0.0] * n_days, [0.0] * n_days, [False] * n_days
    for t in trades:
        n = contracts(acct, t.risk_usd, commission_rt)
        if not n:
            continue
        w = -t.mae_usd * n - commission_rt * n
        p = t.pnl_usd * n
        if acct.daily_loss is not None and w <= -acct.daily_loss:
            w = max(w, -acct.daily_loss)
            p = max(p, -acct.daily_loss)
        pnl[t.day], worst[t.day], traded[t.day] = p, min(w, p), True
    return pnl, worst, traded


def run(
    acct: Account,
    trades: Sequence[DayTrade],
    start_day: int,
    n_days: int,
    commission_rt: float = 2.0,
    arrays=None,
) -> Outcome:
    """One evaluation that starts on trading day `start_day`."""
    pnl, worst, traded = arrays or day_arrays(acct, trades, n_days, commission_rt)
    bal = hwm = acct.start
    floor = acct.start - acct.max_loss
    best_day = 0.0
    for day in range(start_day, n_days):
        if traded[day]:
            if bal + worst[day] <= floor:
                return Outcome("fail", day - start_day + 1, floor)
            bal += pnl[day]
            best_day = max(best_day, pnl[day])
        hwm = max(hwm, bal)
        floor = min(hwm - acct.max_loss, acct.start)
        profit = bal - acct.start
        if profit >= acct.target and (
            acct.consistency is None or best_day <= acct.consistency * profit
        ):
            return Outcome("pass", day - start_day + 1, bal)
    return Outcome("open", n_days - start_day, bal)


@dataclass(frozen=True)
class Summary:
    starts: int
    passed: int
    failed: int
    open: int
    median_days_to_pass: float

    @property
    def pass_rate(self) -> float:
        """Passed over all starts; an evaluation still open counts as not passed."""
        return self.passed / self.starts if self.starts else 0.0

    @property
    def resolved_pass_rate(self) -> float:
        done = self.passed + self.failed
        return self.passed / done if done else 0.0


def rolling(
    acct: Account, trades: Sequence[DayTrade], n_days: int, commission_rt: float = 2.0
) -> Summary:
    """Start a fresh evaluation on every trading day and tally the verdicts."""
    arrays = day_arrays(acct, trades, n_days, commission_rt)
    outs = [run(acct, trades, s, n_days, commission_rt, arrays) for s in range(n_days)]
    passed = [o.days for o in outs if o.status == "pass"]
    return Summary(
        len(outs),
        len(passed),
        sum(o.status == "fail" for o in outs),
        sum(o.status == "open" for o in outs),
        float(np.median(passed)) if passed else float("nan"),
    )
