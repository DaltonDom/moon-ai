"""Prop-firm replay: how a strategy's trades would fare under a firm's rules.

A backtest says whether a strategy makes money. The goal is monthly payouts
from a prop firm, so a strategy is also scored by replaying its trades through
the firm's rules (design.md, "Revision 2026-11-02"):

- an evaluation is started on every trading day in the run, and each one either
  passes, blows the drawdown or daily limit, or runs out of data;
- each pass continues into a funded account that takes payouts by the firm's
  rules until it blows or the data ends.

Trades are re-sized for the account: each trade risks `risk_usd`, rounded down
to whole contracts and capped at the firm's maximum. A trade too wide for one
contract is skipped. Its P&L per contract is net of costs, so re-sizing keeps
the backtest's cost model.

Open losses count. Each trade carries its worst and best open P&L (from the
backtest's excursions), and a drawdown or daily limit is checked against the
worst point. For an intraday trailing drawdown the best point raises the floor
before the worst point is checked, which is the pessimistic order.
"""

from __future__ import annotations

import math
import statistics
import tomllib
from collections import Counter
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

from moon_ai.config import Config, load_config
from moon_ai.journal import decode_json, read_run
from moon_ai.sessions import to_ny

FUNDED_DAYS = 365  # each funded account is followed for at most a year
EVAL_DAYS = 365  # an evaluation not passed within a year counts as failed ("too slow")
RULES_PATH = Path(__file__).resolve().parents[2] / "config" / "prop_firms.toml"
Drawdown = Literal["eod_trailing", "intraday_trailing", "static"]


# --- inputs -------------------------------------------------------------------------------


@dataclass(frozen=True)
class Trade:
    """One backtest trade, per contract, in USD."""

    session: date
    pnl: float  # net of commission and slippage
    risk: float  # entry to stop
    worst: float  # worst open P&L, <= 0
    best: float = 0.0  # best open P&L, >= 0
    exit: datetime | None = None  # orders trades when runs are combined
    entry: datetime | None = None  # with `exit`, finds trades open at the same time


def trades_from_run(folder: Path, config: Config | None = None) -> list[Trade]:
    """A backtest run's closed trades, per contract, in exit order."""
    config = config or load_config()
    cands = {
        c["candidate_id"]: c for c in decode_json(read_run(folder, "candidates"), "candidates")
    }
    qty = {f["fill_id"]: f["qty"] for f in decode_json(read_run(folder, "fills"), "fills")}
    out = []
    rows = decode_json(read_run(folder, "trades"), "trades")
    for t in sorted(rows, key=lambda t: t["exit_time"] or datetime.max):
        if t["net_usd"] is None or t["exit_time"] is None:
            continue
        c = cands[t["candidate_id"]]
        n = qty.get(t["entry_fill_id"]) or 1
        risk = abs(t["entry_price"] - c["stop"]) * config.instrument(c["symbol"]).point_value
        if risk <= 0:
            continue
        out.append(
            Trade(
                session=to_ny(t["entry_time"]).date(),
                pnl=t["net_usd"] / n,
                risk=risk,
                worst=min((t["mae_r"] or 0.0) * risk, 0.0, t["net_usd"] / n),
                best=max((t["mfe_r"] or 0.0) * risk, 0.0, t["net_usd"] / n),
                exit=t["exit_time"],
                entry=t["entry_time"],
            )
        )
    return out


# --- rules --------------------------------------------------------------------------------


@dataclass(frozen=True)
class Phase:
    """The rules of one phase (evaluation or funded), in USD from the start balance."""

    max_loss: float
    drawdown: Drawdown
    profit_target: float | None = None  # evaluation only
    # The trailing floor stops rising once it reaches start + this (e.g. 0 or 100).
    lock_floor_at: float | None = None
    daily_loss: float | None = None
    daily_loss_hard: bool = False  # True: hitting it fails the account; False: done for the day
    consistency_pct: float | None = None  # best day must be <= this % of total profit
    min_days: int = 0  # days with at least one trade
    max_contracts: int = 50  # micros
    # Scaling plan: (profit reached at the end of a day, micros allowed from then on).
    scaling: tuple[tuple[float, int], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "scaling", tuple(tuple(x) for x in self.scaling))


@dataclass(frozen=True)
class Payouts:
    min_days: int = 5  # trading days since the start or the last payout
    min_profit_days: int = 0  # of those, days with at least `profit_day_usd` profit
    profit_day_usd: float = 0.0
    buffer: float = 0.0  # profit that must stay in the account above the start balance
    min_request: float = 0.0
    # Cap per request; a list gives the cap for payout 1, 2, 3, ... (the last repeats).
    max_request: float | list[float] | None = None
    max_pct_of_profit: float | None = None  # cap as a % of profit above the start balance
    min_cycle_profit: float | None = None  # profit needed since the last payout
    min_balance: float = 0.0  # profit above the start balance needed to request
    split: float = 0.9  # trader's share
    consistency_pct: float | None = None
    # After a payout the floor is set to start + this (None: unchanged).
    floor_after_payout: float | None = None


@dataclass(frozen=True)
class Rules:
    name: str
    title: str
    evaluation: Phase
    funded: Phase
    payouts: Payouts
    eval_fee: float | None = None  # None: price not confirmed
    activation_fee: float = 0.0
    source: str = ""  # where the numbers came from, and when


def with_daily_cap(rules: Rules, cap: float) -> Rules:
    """Our own soft daily loss cap (design.md: "a daily loss cap set inside the
    firm's limit") on top of the firm's rules, in both phases."""

    def capped(ph: Phase) -> Phase:
        if ph.daily_loss is not None and ph.daily_loss <= cap:
            return ph
        return replace(ph, daily_loss=cap, daily_loss_hard=False)

    return replace(
        rules,
        title=f"{rules.title}, our daily cap ${cap:,.0f}",
        evaluation=capped(rules.evaluation),
        funded=capped(rules.funded),
    )


def load_rules(path: Path = RULES_PATH) -> dict[str, Rules]:
    data = tomllib.loads(path.read_text())
    out = {}
    for name, r in data.get("firms", {}).items():
        out[name] = Rules(
            name=name,
            title=r["title"],
            evaluation=Phase(**r["evaluation"]),
            funded=Phase(**r["funded"]),
            payouts=Payouts(**r.get("payouts", {})),
            eval_fee=r.get("eval_fee"),
            activation_fee=r.get("activation_fee", 0.0),
            source=r.get("source", ""),
        )
    return out


# --- one account --------------------------------------------------------------------------


@dataclass
class Account:
    """Balance and floor, relative to the start balance (start = 0)."""

    phase: Phase
    balance: float = 0.0
    peak: float = 0.0  # what the floor trails
    floor: float = 0.0
    min_buffer: float = math.inf  # closest approach to the floor
    days: list[date] = field(default_factory=list)
    day_pnl: dict[date, float] = field(default_factory=dict)
    size_cap: int = 0  # micros allowed today (scaling plan)
    # Today's earlier trades: (exit time, how much worse than its result it got, in USD).
    _open: list[tuple[datetime | None, float]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.floor = -self.phase.max_loss
        self._scale()

    def _scale(self) -> None:
        """Micros allowed from the next day: the highest scaling tier reached."""
        tiers = self.phase.scaling
        cap = tiers[0][1] if tiers else self.phase.max_contracts
        for level, n in tiers:
            if self.balance >= level:
                cap = n
        self.size_cap = min(cap, self.phase.max_contracts)

    def _raise_floor(self, level: float) -> None:
        if self.phase.drawdown == "static":
            return
        self.peak = max(self.peak, level)
        target = self.peak - self.phase.max_loss
        if self.phase.lock_floor_at is not None:
            target = min(target, self.phase.lock_floor_at)
        self.floor = max(self.floor, target)

    def end_day(self) -> None:
        if self.phase.drawdown == "eod_trailing":
            self._raise_floor(self.balance)
        self._scale()

    def contracts(self, t: Trade, risk_usd: float) -> int:
        return min(self.size_cap, math.floor(risk_usd / t.risk))

    def take(self, t: Trade, n: int) -> str | None:
        """Book one trade of `n` contracts. Returns why the account failed, if it did."""
        if not self.days or self.days[-1] != t.session:
            self.days.append(t.session)
            self._open = []
        day = self.day_pnl.get(t.session, 0.0)
        if self.phase.drawdown == "intraday_trailing":
            self._raise_floor(self.balance + t.best * n)
        before = self.balance
        # Trades still open when this one opened may be at their worst at the same
        # moment (pessimistic): their already-booked results get that much worse.
        overlap = sum(
            extra
            for ex, extra in self._open
            if ex is not None and t.entry is not None and ex > t.entry
        )
        self._open.append((t.exit, (t.worst - t.pnl) * n))
        worst = before + t.worst * n + overlap
        self.min_buffer = min(self.min_buffer, worst - self.floor)
        if worst <= self.floor:
            self.balance = self.floor
            self.day_pnl[t.session] = day + self.floor - before
            return "max loss"
        pnl = t.pnl * n
        limit = self.phase.daily_loss
        if limit is not None and day + t.worst * n + overlap <= -limit:
            if self.phase.daily_loss_hard:
                self.balance += -limit - day
                self.day_pnl[t.session] = -limit
                return "daily loss limit"
            pnl = -limit - day  # closed at the limit; done for the day
        self.balance += pnl
        self.day_pnl[t.session] = day + pnl
        if self.phase.drawdown == "intraday_trailing":
            self._raise_floor(self.balance)
        return None

    def done_for_day(self, session: date) -> bool:
        limit = self.phase.daily_loss
        return limit is not None and self.day_pnl.get(session, 0.0) <= -limit + 1e-9

    def consistent(self, pct: float | None, profit: float) -> bool:
        if pct is None or profit <= 0:
            return True
        best = max(self.day_pnl.values(), default=0.0)
        return best <= profit * pct / 100


# --- replay -------------------------------------------------------------------------------


@dataclass(frozen=True)
class Attempt:
    start: date
    outcome: Literal["passed", "failed", "ran out"]
    reason: str  # why it failed, or ""
    end: date | None
    trading_days: int
    min_buffer: float
    payouts: tuple[tuple[date, float], ...] = ()  # (day, trader's share) while funded
    funded_outcome: str = ""  # "failed: max loss", "still running", ...
    funded_days: int = 0  # calendar days funded


def combine(*runs: list[Trade]) -> list[Trade]:
    """Several runs' trades as one account's, in exit order (e.g. MNQ and MES)."""
    return sorted(
        (t for r in runs for t in r),
        key=lambda t: (t.session, t.exit or datetime.max.replace(tzinfo=None)),
    )


def _days(trades: list[Trade]) -> list[list[Trade]]:
    out: list[list[Trade]] = []
    for t in trades:
        if out and out[-1][0].session == t.session:
            out[-1].append(t)
        else:
            out.append([t])
    return out


def _evaluate(days: list[list[Trade]], i: int, rules: Rules, risk_usd: float):
    ph = rules.evaluation
    acc = Account(ph)
    first = days[i][0].session
    for k in range(i, len(days)):
        if (days[k][0].session - first).days >= EVAL_DAYS:
            return "failed", "too slow", k - 1, acc
        for t in days[k]:
            if acc.done_for_day(t.session):
                break
            n = acc.contracts(t, risk_usd)
            if n < 1:
                continue
            why = acc.take(t, n)
            if why:
                return "failed", why, k, acc
        acc.end_day()
        if (
            ph.profit_target is not None
            and acc.balance >= ph.profit_target
            and len(acc.days) >= ph.min_days
            and acc.consistent(ph.consistency_pct, acc.balance)
        ):
            return "passed", "", k, acc
    return "ran out", "", len(days) - 1, acc


def _funded(days: list[list[Trade]], i: int, rules: Rules, risk_usd: float):
    ph, po = rules.funded, rules.payouts
    acc = Account(ph)
    paid: list[tuple[date, float]] = []
    since = 0  # trading days since the start or the last payout
    window_start = 0  # index into acc.days where the payout window began
    first = days[i][0].session
    for k in range(i, len(days)):
        if (days[k][0].session - first).days >= FUNDED_DAYS:
            return paid, "survived a year", k - 1
        traded = False
        for t in days[k]:
            if acc.done_for_day(t.session):
                break
            n = acc.contracts(t, risk_usd)
            if n < 1:
                continue
            traded = True
            why = acc.take(t, n)
            if why:
                return paid, f"failed: {why}", k
        acc.end_day()
        if not traded:
            continue
        since += 1
        window = acc.days[window_start:]
        profit_days = sum(acc.day_pnl[d] >= po.profit_day_usd for d in window)
        available = acc.balance - po.buffer
        cap = po.max_request
        if isinstance(cap, list):
            cap = cap[min(len(paid), len(cap) - 1)]
        if cap is not None:
            available = min(available, cap)
        if po.max_pct_of_profit is not None:
            available = min(available, acc.balance * po.max_pct_of_profit / 100)
        window_profit = sum(acc.day_pnl[d] for d in window)
        best = max((acc.day_pnl[d] for d in window), default=0.0)
        consistent = po.consistency_pct is None or (
            window_profit > 0 and best <= window_profit * po.consistency_pct / 100
        )
        if (
            since >= po.min_days
            and profit_days >= po.min_profit_days
            and acc.balance >= po.min_balance
            and (po.min_cycle_profit is None or window_profit > po.min_cycle_profit)
            and available >= max(po.min_request, 0.01)
            and consistent
        ):
            acc.balance -= available
            paid.append((days[k][0].session, available * po.split))
            if po.floor_after_payout is not None:
                acc.floor = po.floor_after_payout
                acc.peak = acc.floor + ph.max_loss
            since = 0
            window_start = len(acc.days)
    return paid, "still running", len(days) - 1


def replay(trades: list[Trade], rules: Rules, risk_usd: float) -> list[Attempt]:
    """Start an evaluation on every trading day; carry each pass into a funded account."""
    days = _days(trades)
    out = []
    for i in range(len(days)):
        outcome, why, k, acc = _evaluate(days, i, rules, risk_usd)
        paid: list[tuple[date, float]] = []
        funded_outcome, funded_days = "", 0
        if outcome == "passed" and k + 1 < len(days):
            paid, funded_outcome, j = _funded(days, k + 1, rules, risk_usd)
            funded_days = (days[j][0].session - days[k + 1][0].session).days + 1
        out.append(
            Attempt(
                start=days[i][0].session,
                outcome=outcome,
                reason=why,
                end=days[k][0].session,
                trading_days=len(acc.days),
                min_buffer=min(acc.min_buffer, rules.evaluation.max_loss),
                payouts=tuple(paid),
                funded_outcome=funded_outcome,
                funded_days=funded_days,
            )
        )
    return out


# --- summary ------------------------------------------------------------------------------


@dataclass(frozen=True)
class Summary:
    rules: str
    risk_usd: float
    attempts: int  # evaluations that ended (passed or failed)
    pass_rate: float
    median_days_to_pass: float | None  # calendar days
    fail_reasons: dict[str, int]
    payout_per_month: float  # trader's share, averaged over all funded time
    funded_failed_rate: float | None  # blew within a year; None if no funded account to judge
    median_payouts_before_fail: float | None
    cost_per_funded: float | None  # evaluation fees spent per pass, on average
    # Payouts minus the evaluation fees needed to replace blown accounts, per funded month.
    net_per_month: float | None
    median_min_buffer: float | None  # closest approach to the floor in evaluations


def summarise(attempts: list[Attempt], rules: Rules, risk_usd: float) -> Summary:
    ended = [a for a in attempts if a.outcome != "ran out"]
    passed = [a for a in ended if a.outcome == "passed"]
    rate = len(passed) / len(ended) if ended else 0.0
    to_pass = [(a.end - a.start).days + 1 for a in passed if a.end]
    funded = [a for a in passed if a.funded_days > 0]
    months = sum(a.funded_days for a in funded) / 30.44
    paid = sum(x for a in funded for _, x in a.payouts)
    blown = [a for a in funded if a.funded_outcome.startswith("failed")]
    # Accounts the data cut short (neither blown nor a full year old) say nothing about blowing.
    judged = blown + [a for a in funded if a.funded_outcome == "survived a year"]
    cost = rules.eval_fee / rate if rate and rules.eval_fee is not None else None
    return Summary(
        rules=rules.name,
        risk_usd=risk_usd,
        attempts=len(ended),
        pass_rate=rate,
        median_days_to_pass=statistics.median(to_pass) if to_pass else None,
        fail_reasons=dict(Counter(a.reason for a in ended if a.outcome == "failed")),
        payout_per_month=paid / months if months else 0.0,
        funded_failed_rate=len(blown) / len(judged) if judged else None,
        median_payouts_before_fail=(
            statistics.median(len(a.payouts) for a in blown) if blown else None
        ),
        cost_per_funded=cost,
        net_per_month=(
            (paid - len(blown) * cost) / months if months and cost is not None else None
        ),
        median_min_buffer=statistics.median(a.min_buffer for a in ended) if ended else None,
    )


def score(
    trades: list[Trade], rules: Rules, risks: tuple[float, ...] = (100, 200, 300, 400, 500)
) -> list[Summary]:
    return [summarise(replay(trades, rules, r), rules, r) for r in risks]


def lines(summaries: list[Summary], rules: Rules) -> list[str]:
    """Plain-language table, one line per risk level."""
    out = [
        f"{rules.title}: an evaluation started on every trading day, each pass carried into a "
        "funded account",
        f"  {'risk/trade':>10}  {'passed':>7}  {'days to pass':>12}  {'payout/month':>12}  "
        f"{'blown in 1yr':>12}  {'fees per pass':>13}  {'net/month':>10}",
    ]
    for s in summaries:
        days = f"{s.median_days_to_pass:.0f}" if s.median_days_to_pass is not None else "—"
        fee = f"${s.cost_per_funded:,.0f}" if s.cost_per_funded is not None else "—"
        net = _usd(s.net_per_month) if s.net_per_month is not None else "—"
        blown = "—" if s.funded_failed_rate is None else f"{s.funded_failed_rate:.0%}"
        out.append(
            f"  {'$' + format(s.risk_usd, ',.0f'):>10}  {s.pass_rate:>7.0%}  {days:>12}  "
            f"{'$' + format(s.payout_per_month, ',.0f'):>12}  {blown:>12}  "
            f"{fee:>13}  {net:>10}"
        )
    out += [
        "  passed: share of evaluations that hit the target within a year without breaking a rule",
        "  payout/month: your share, averaged over all the time accounts were funded",
        "  blown in 1yr: share of funded accounts that broke a rule within their first year",
        "  fees per pass: evaluation fees spent, on average, to get one funded account",
        "  net/month: payouts minus the fees to replace blown accounts, per funded month",
    ]
    if rules.source:
        out.append(f"  rules: {rules.source}")
    return out


def _usd(x: float) -> str:
    return f"{'-' if x < 0 else ''}${abs(x):,.0f}"


def as_dict(s: Summary) -> dict[str, Any]:
    return s.__dict__.copy()
