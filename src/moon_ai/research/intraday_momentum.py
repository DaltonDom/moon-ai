"""Intraday momentum ("noise area") backtest for MNQ.

Pre-registered in `config/families/intraday_momentum.toml`; read that file
for the rules and where they come from (Zarattini, Aziz & Barbon 2024).

The strategy doesn't use a fixed stop and target, so it can't run through
the bracket-order engine. This module is a self-contained research backtest
with the engine's conventions:

- a decision uses only the close of the bar that ends at the decision time;
- every order is a market order filled at the open of the next bar, with the
  repo's commission and slippage;
- holidays, half days, roll days and degraded days are skipped, and new
  entries are blocked inside a news blackout;
- the locked holdout is refused unless it's a sign-off.

Run it with `uv run python -m moon_ai.research.intraday_momentum`.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import tomllib
from collections.abc import Sequence
from dataclasses import asdict, dataclass, replace
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

from moon_ai import holdout
from moon_ai.backtest.stats import bootstrap_mean_ci, deflated_sharpe, sharpe
from moon_ai.data.calendar import session_info
from moon_ai.data.news import NEWS_CSV, Blackout, load_events
from moon_ai.data.quality import degraded_sessions, load_degraded_dates
from moon_ai.data.store import BarStore
from moon_ai.sessions import NY

SPEC_PATH = Path(__file__).resolve().parents[3] / "config" / "families" / "intraday_momentum.toml"
SESSION_MINUTES = 390  # 09:30-16:00


def _minute(t: str) -> int:
    """Minutes after 09:30 of a New York "HH:MM"."""
    h, m = map(int, t.split(":"))
    return h * 60 + m - (9 * 60 + 30)


@dataclass(frozen=True)
class Spec:
    lookback_days: int = 14
    band_mult: float = 1.0
    first_decision: int = _minute("10:00")
    last_decision: int = _minute("15:30")
    every: int = 30
    final_exit: int = _minute("15:55")
    equity_usd: float = 50_000.0
    target_daily_vol: float = 0.02
    max_leverage: float = 4.0
    vol_lookback_days: int = 14
    commission: float = 1.00  # per contract per side
    slippage_ticks: float = 1.0  # per market fill
    n_trials: int = 1
    min_trades: int = 100
    dsr_bar: float = 0.95
    symbol: str = "MNQ.v.0"
    tick: float = 0.25
    point_value: float = 2.0  # USD per point per contract
    # Diagnostics only, never a trial: fill this many bars late (0 = next bar).
    fill_delay: int = 0
    # Trial 2 ("prop_v2") risk controls; None/off in the default.
    stop_sigma_mult: float | None = None  # hard stop at this x daily vol x entry price
    daily_stop_risk_mult: float | None = None  # no new entries after this x per-trade risk lost
    stop_slippage_ticks: float = 3.0
    fixed_contracts: int | None = None  # fixed size instead of volatility targeting
    trial: str = "default"
    start: date = date(2019, 6, 3)
    end: date = date(2025, 11, 1)

    @property
    def decisions(self) -> list[int]:
        """Decision minutes: the close of bar k-1 is the decision at minute k."""
        return list(range(self.first_decision, self.last_decision + 1, self.every))


def load_spec(path: Path = SPEC_PATH, trial: str = "default") -> Spec:
    raw = tomllib.loads(Path(path).read_text())
    if trial != "default":
        t = raw.get("trial", {}).get(trial)
        if t is None:
            raise ValueError(f"no pre-registered trial {trial!r} in {path}")
        base = load_spec(path)
        return replace(
            base,
            trial=trial,
            n_trials=base.n_trials + len(raw["trial"]),
            stop_sigma_mult=t["stop_sigma_mult"],
            daily_stop_risk_mult=t["daily_stop_risk_mult"],
            stop_slippage_ticks=t["stop_slippage_ticks"],
            fixed_contracts=1 if t["sizing"] == "fixed_micros" else None,
        )
    r, s, c, smp, bar = raw["rules"], raw["sizing"], raw["costs"], raw["sample"], raw["bar"]
    return Spec(
        lookback_days=r["lookback_days"],
        band_mult=r["band_mult"],
        first_decision=_minute(r["first_decision"]),
        last_decision=_minute(r["last_decision"]),
        every=r["decision_every_minutes"],
        final_exit=_minute(r["final_exit"]),
        equity_usd=s["equity_usd"],
        target_daily_vol=s["target_daily_vol"],
        max_leverage=s["max_leverage"],
        vol_lookback_days=s["vol_lookback_days"],
        commission=c["commission_per_contract_side"],
        slippage_ticks=c["slippage_ticks_per_market_fill"],
        n_trials=raw["family"]["n_trials"],
        symbol=raw["family"]["symbol"],
        min_trades=bar["min_trades"],
        dsr_bar=bar["dsr_bar"],
        start=date.fromisoformat(smp["start"]),
        end=date.fromisoformat(smp["end"]),
    )


# --- data -----------------------------------------------------------------------------


@dataclass
class Day:
    """One regular-hours session on a full 390-minute grid (gaps forward-filled)."""

    day: date
    instrument: int
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray
    bar_count: int  # real bars before filling

    @property
    def session_open(self) -> float:
        return float(self.open[0])

    @property
    def session_close(self) -> float:
        return float(self.close[-1])

    def vwap(self) -> np.ndarray:
        tp = (self.high + self.low + self.close) / 3
        cv = np.cumsum(self.volume)
        out = np.cumsum(tp * self.volume) / np.where(cv > 0, cv, 1)
        return np.where(cv > 0, out, self.close)


def load_days(store: BarStore, symbol: str, start: date, end: date) -> list[Day]:
    """Regular-hours sessions in [start, end), from the 1-minute bar store."""
    paths = [s.path for s in store.files(symbol) if s.start < end and s.end > start]
    if not paths:
        raise FileNotFoundError(f"no {symbol} bars in {store.root} for {start} to {end}")
    frame = (
        pl.concat([pl.read_parquet(p) for p in paths])
        .unique(subset=["ts_event"], keep="last")
        .with_columns(ny=pl.col("ts_event").dt.convert_time_zone("America/New_York"))
        .with_columns(
            d=pl.col("ny").dt.date(),
            k=pl.col("ny").dt.hour().cast(pl.Int32) * 60
            + pl.col("ny").dt.minute().cast(pl.Int32)
            - 570,
        )
        .filter((pl.col("k") >= 0) & (pl.col("k") < SESSION_MINUTES))
        .filter((pl.col("d") >= start) & (pl.col("d") < end))
        .sort("ts_event")
    )
    return [_grid(d, g) for (d,), g in frame.group_by(["d"], maintain_order=True)]


def _grid(d: date, g: pl.DataFrame) -> Day:
    k = g["k"].to_numpy()
    cols = {}
    for name in ("open", "high", "low", "close"):
        a = np.full(SESSION_MINUTES, np.nan)
        a[k] = g[name].to_numpy()
        cols[name] = a
    vol = np.zeros(SESSION_MINUTES)
    vol[k] = g["volume"].to_numpy().astype(float)
    # Forward-fill a missing minute as a flat bar at the last close.
    close = pl.Series(cols["close"]).fill_nan(None).forward_fill().backward_fill().to_numpy()
    for name in ("open", "high", "low"):
        a = cols[name]
        cols[name] = np.where(np.isnan(a), close, a)
    inst = int(g["instrument_id"].mode().sort()[0])
    return Day(d, inst, cols["open"], cols["high"], cols["low"], close, vol, len(k))


# --- the strategy ---------------------------------------------------------------------


@dataclass(frozen=True)
class Trade:
    day: date
    side: int  # +1 long, -1 short
    qty: int
    entry_minute: int  # fill bar, minutes after 09:30
    exit_minute: int
    entry_px: float  # raw fill bar open, before slippage
    exit_px: float
    gross_usd: float
    cost_usd: float
    exit_reason: str
    # Worst open P&L while held (bar lows for longs, highs for shorts), costs included.
    mae_usd: float = 0.0

    @property
    def net_usd(self) -> float:
        return self.gross_usd - self.cost_usd


def noise_sigma(history: Sequence[Day], n: int) -> np.ndarray | None:
    """sigma(t): mean |close(t)/open - 1| over the last `n` sessions."""
    if len(history) < n:
        return None
    moves = np.array([np.abs(h.close / h.session_open - 1) for h in history[-n:]])
    return moves.mean(axis=0)


def daily_vol(history: Sequence[Day], n: int) -> float | None:
    """Std of the last `n` close-to-close returns, skipping pairs across a roll."""
    rets = [
        b.session_close / a.session_close - 1
        for a, b in itertools.pairwise(history)
        if a.instrument == b.instrument
    ]
    if len(rets) < n:
        return None
    return float(np.std(rets[-n:], ddof=1))


def contracts(spec: Spec, price: float, vol: float) -> int:
    lev = spec.max_leverage if vol <= 0 else min(spec.max_leverage, spec.target_daily_vol / vol)
    return max(1, math.floor(spec.equity_usd * lev / (price * spec.point_value)))


def trade_day(
    day: Day,
    sigma: np.ndarray,
    prev_close: float,
    qty: int,
    spec: Spec,
    blocked: Sequence[bool] | None = None,
    slippage_mult: float = 1.0,
    vol: float | None = None,
) -> list[Trade]:
    """Run the noise-area rules over one session.

    `blocked[i]` is True when decision i (spec.decisions order) falls in a
    news blackout; it blocks new entries only. With `spec.stop_sigma_mult`
    set (trial 2), every position also has a hard stop checked on each bar,
    and `spec.daily_stop_risk_mult` ends new entries after a bad session.
    """
    o = day.session_open
    upper = max(o, prev_close) * (1 + spec.band_mult * sigma)
    lower = min(o, prev_close) * (1 - spec.band_mult * sigma)
    vwap = day.vwap()
    slip = spec.slippage_ticks * slippage_mult * spec.tick
    stop_slip = spec.stop_slippage_ticks * slippage_mult * spec.tick
    stops = spec.stop_sigma_mult is not None and vol is not None
    if stops and spec.fill_delay:
        raise ValueError("fill_delay is a diagnostic of the default only")
    dist = spec.stop_sigma_mult * vol * o if stops else None  # stop distance, points
    trades: list[Trade] = []
    pos, entry_k, stop_px, scan_from = 0, -1, 0.0, 0
    realized, halted = 0.0, False
    d, last = spec.fill_delay, SESSION_MINUTES - 1

    def close_out(exit_k: int, reason: str, exit_raw: float | None = None) -> None:
        nonlocal realized, halted
        e = min(entry_k + d, last)
        entry_px = float(day.open[e])
        if exit_raw is None:  # market exit at the open of bar exit_k
            x = min(exit_k + d, last)
            exit_px, exit_slip, held = float(day.open[x]), slip, slice(e, max(x, e + 1))
        else:  # stop exit inside bar exit_k
            exit_px, exit_slip, held = exit_raw, stop_slip, slice(e, exit_k + 1)
        gross = pos * (exit_px - entry_px) * spec.point_value * qty
        cost = qty * (2 * spec.commission + (slip + exit_slip) * spec.point_value)
        if pos == 1:
            adverse = float(day.low[held].min()) - entry_px
        else:
            adverse = entry_px - float(day.high[held].max())
        mae = min(adverse, 0.0) * spec.point_value * qty - cost
        t = Trade(day.day, pos, qty, entry_k, exit_k, entry_px, exit_px, gross, cost, reason, mae)
        trades.append(t)
        realized += t.net_usd
        if stops and spec.daily_stop_risk_mult is not None:
            risk = dist * spec.point_value * qty
            halted = halted or realized <= -spec.daily_stop_risk_mult * risk

    def check_stop(until: int) -> bool:
        """Bars [scan_from, until): close at the hard stop if one is touched."""
        if not (stops and pos):
            return False
        for m in range(scan_from, until):
            if pos == 1 and day.low[m] <= stop_px:
                close_out(m, "stop", min(float(day.open[m]), stop_px))
                return True
            if pos == -1 and day.high[m] >= stop_px:
                close_out(m, "stop", max(float(day.open[m]), stop_px))
                return True
        return False

    for i, k in enumerate(spec.decisions):
        if check_stop(k):
            pos = 0
        scan_from = k
        c = day.close[k - 1]  # the bar ending at minute k
        exited = 0
        if pos == 1 and c < max(upper[k - 1], vwap[k - 1]):
            close_out(k, "trail")
            exited, pos = 1, 0
        elif pos == -1 and c > min(lower[k - 1], vwap[k - 1]):
            close_out(k, "trail")
            exited, pos = -1, 0
        if pos == 0 and not halted and not (blocked is not None and blocked[i]):
            side = 1 if c > upper[k - 1] else -1 if c < lower[k - 1] else 0
            if side and side != exited:
                pos, entry_k = side, k
                if stops:
                    stop_px = float(day.open[k]) - side * dist
    if pos and check_stop(spec.final_exit):
        pos = 0
    if pos:
        close_out(spec.final_exit, "time_out")
    return trades


# --- the backtest ---------------------------------------------------------------------


@dataclass
class Result:
    trades: list[Trade]
    daily: dict[date, float]  # net USD per tradable session (0 when flat)
    qty: dict[date, int]
    skipped: dict[str, int]


def backtest(
    days: Sequence[Day],
    spec: Spec,
    *,
    start: date,
    end: date,
    rolls: frozenset[date] = frozenset(),
    degraded: frozenset[date] = frozenset(),
    blackout: Blackout | None = None,
    slippage_mult: float = 1.0,
) -> Result:
    """Trade the sessions in [start, end); earlier `days` only feed the history."""
    history: list[Day] = []
    trades: list[Trade] = []
    daily: dict[date, float] = {}
    qtys: dict[date, int] = {}
    skipped: dict[str, int] = {}

    def skip(why: str) -> None:
        skipped[why] = skipped.get(why, 0) + 1

    for day in days:
        kind = session_info(day.day).kind
        full = kind == "regular" and day.bar_count >= 300 and day.day not in degraded
        if start <= day.day < end:
            if kind != "regular":
                skip(kind)
            elif day.day in rolls:
                skip("roll")
            elif day.day in degraded:
                skip("degraded")
            elif day.bar_count < 300:
                skip("thin_data")
            else:
                sigma = noise_sigma(history, spec.lookback_days)
                vol = daily_vol(history, spec.vol_lookback_days)
                if sigma is None or vol is None:
                    skip("warm_up")
                else:
                    prev = history[-1]
                    prev_close = (
                        prev.session_close
                        if prev.instrument == day.instrument
                        else day.session_open
                    )
                    qty = spec.fixed_contracts or contracts(spec, day.session_open, vol)
                    blocked = None
                    if blackout is not None:
                        blocked = [blackout.in_blackout(_utc(day.day, k)) for k in spec.decisions]
                    t = trade_day(day, sigma, prev_close, qty, spec, blocked, slippage_mult, vol)
                    trades += t
                    daily[day.day] = sum((x.net_usd for x in t), 0.0)
                    qtys[day.day] = qty
        if full:
            history.append(day)
    return Result(trades, daily, qtys, skipped)


def _utc(d: date, k: int) -> datetime:
    t = datetime.combine(d, time(9, 30), tzinfo=NY) + timedelta(minutes=k)
    return t.astimezone(UTC)


# --- scoring --------------------------------------------------------------------------


def max_drawdown(pnl: Sequence[float]) -> float:
    eq = np.cumsum(np.asarray(pnl, float))
    if len(eq) == 0:
        return 0.0
    peak = np.maximum.accumulate(np.concatenate([[0.0], eq]))[1:]
    return float((peak - eq).max())


def score(res: Result, stress: Result, spec: Spec) -> dict[str, Any]:
    tr = res.trades
    net = np.array([t.net_usd for t in tr])
    gross = np.array([t.gross_usd for t in tr])
    days = sorted(res.daily)
    pnl = np.array([res.daily[d] for d in days])
    rets = pnl / spec.equity_usd
    edge_ci = bootstrap_mean_ci(gross) if len(gross) else (math.nan, math.nan)
    dsr = deflated_sharpe(rets, spec.n_trials, 0.0)
    stress_net = sum(t.net_usd for t in stress.trades)
    reasons = []
    if not edge_ci[0] > 0:
        reasons.append("doesn't clearly beat random entries (95% CI of the edge includes 0)")
    if not dsr > spec.dsr_bar:
        reasons.append(f"not enough evidence it isn't luck (DSR {dsr:.2f} <= {spec.dsr_bar})")
    if not stress_net > 0:
        reasons.append("loses money with double slippage")
    if len(tr) < spec.min_trades:
        verdict = "insufficient"
        reasons.insert(0, f"only {len(tr)} trades; {spec.min_trades} needed")
    else:
        verdict = "go-forward" if not reasons else "fail"

    years: dict[int, dict[str, float]] = {}
    for t in tr:
        y = years.setdefault(t.day.year, {"trades": 0, "net_usd": 0.0, "wins": 0})
        y["trades"] += 1
        y["net_usd"] += t.net_usd
        y["wins"] += t.net_usd > 0
    for y, v in years.items():
        ydays = [res.daily[d] for d in days if d.year == y]
        v["win_rate"] = v.pop("wins") / v["trades"]
        v["sharpe_ann"] = sharpe(ydays) * math.sqrt(252)
        v["max_dd_usd"] = max_drawdown(ydays)

    longs = [t for t in tr if t.side == 1]
    shorts = [t for t in tr if t.side == -1]
    return {
        "verdict": verdict,
        "reasons": reasons,
        "trades": len(tr),
        "sessions": len(days),
        "sessions_traded": len({t.day for t in tr}),
        "net_usd": float(net.sum()),
        "gross_usd": float(gross.sum()),
        "costs_usd": float(sum(t.cost_usd for t in tr)),
        "win_rate": float((net > 0).mean()) if len(net) else 0.0,
        "avg_win_usd": float(net[net > 0].mean()) if (net > 0).any() else 0.0,
        "avg_loss_usd": float(net[net <= 0].mean()) if (net <= 0).any() else 0.0,
        "profit_factor": float(net[net > 0].sum() / -net[net < 0].sum())
        if (net < 0).any()
        else math.inf,
        "mean_net_per_trade_usd": float(net.mean()) if len(net) else 0.0,
        "edge_per_trade_usd": float(gross.mean()) if len(gross) else 0.0,
        "edge_ci_usd": list(edge_ci),
        "sharpe_ann": sharpe(rets) * math.sqrt(252),
        "dsr": dsr,
        "max_dd_usd": max_drawdown(pnl),
        "stress_net_usd": stress_net,
        "avg_contracts": float(np.mean(list(res.qty.values()))) if res.qty else 0.0,
        "long": {"trades": len(longs), "net_usd": sum(t.net_usd for t in longs)},
        "short": {"trades": len(shorts), "net_usd": sum(t.net_usd for t in shorts)},
        "exit_reasons": {
            r: sum(1 for t in tr if t.exit_reason == r) for r in ("trail", "stop", "time_out")
        },
        "skipped_sessions": res.skipped,
        "by_year": dict(sorted(years.items())),
    }


# --- prop-firm replay (illustrative) --------------------------------------------------


@dataclass(frozen=True)
class EvalRules:
    """An evaluation's money rules. Defaults: LucidFlex 25K as listed in
    docs/research/prop-firms-and-order-routing.md (UNVERIFIED secondary listing):
    $1,250 target, $1,000 end-of-day trailing max loss, no daily loss limit,
    no consistency rule, 20 micros max."""

    name: str = "LucidFlex 25K (UNVERIFIED)"
    target_usd: float = 1_250.0
    max_loss_usd: float = 1_000.0
    max_micros: int = 20


def intraday_worst(trades: Sequence[Trade]) -> float:
    """Lowest point of one session's per-contract P&L, from bar extremes (<= 0)."""
    realized, worst = 0.0, 0.0
    for t in sorted(trades, key=lambda t: t.entry_minute):
        worst = min(worst, realized + t.mae_usd / t.qty)
        realized += t.net_usd / t.qty
        worst = min(worst, realized)
    return worst


def replay_evals(
    per_contract_daily: Sequence[float],
    micros: int,
    rules: EvalRules,
    per_contract_worst: Sequence[float] | None = None,
) -> dict[str, Any]:
    """Start an evaluation on every session; report pass rate and days to pass.

    The trailing floor (max loss below the highest end-of-day balance, rising
    no higher than the starting balance) is set at each session's end. A
    breach is checked against the session's intraday low when
    `per_contract_worst` is given, and its close otherwise.
    """
    x = np.asarray(per_contract_daily, float) * micros
    w = (
        np.asarray(per_contract_worst, float) * micros
        if per_contract_worst is not None
        else np.minimum(x, 0.0)
    )
    passed, failed, days_to_pass, worst = 0, 0, [], []
    for s in range(len(x)):
        bal, peak, low_room = 0.0, 0.0, rules.max_loss_usd
        for i in range(s, len(x)):
            floor = min(peak - rules.max_loss_usd, 0.0)
            low = bal + w[i]  # the session's lowest balance
            low_room = min(low_room, low - floor)
            bal += x[i]
            if low <= floor or bal <= floor:
                failed += 1
                worst.append(low_room)
                break
            if bal >= rules.target_usd:
                passed += 1
                days_to_pass.append(i - s + 1)
                worst.append(low_room)
                break
            peak = max(peak, bal)
    done = passed + failed
    return {
        "micros": micros,
        "attempts": done,
        "pass_rate": passed / done if done else 0.0,
        "median_days_to_pass": float(np.median(days_to_pass)) if days_to_pass else None,
        "median_closest_to_limit_usd": float(np.median(worst)) if worst else None,
    }


@dataclass(frozen=True)
class LucidRules:
    """LucidFlex 50K, from secondary sources (UNVERIFIED; checked 2026-11-03):
    $3,000 target, $2,000 end-of-day trailing max loss whose floor stops rising
    at start + $100, 40% consistency in the evaluation (best day <= 40% of the
    profit at the pass), no daily loss limit, 40 micros max; the funded account
    keeps the trailing max loss and drops the consistency rule."""

    name: str = "LucidFlex 50K (UNVERIFIED)"
    target_usd: float = 3_000.0
    max_loss_usd: float = 2_000.0
    floor_lock_usd: float = 100.0
    consistency: float = 0.40
    min_days: int = 2
    max_micros: int = 40


def _account(x: np.ndarray, w: np.ndarray, s: int, rules: LucidRules, funded: bool):
    """Walk one account from session s. Returns (outcome, sessions used, balance, best day)."""
    bal, peak, best = 0.0, 0.0, 0.0
    for i in range(s, len(x)):
        floor = min(peak - rules.max_loss_usd, rules.floor_lock_usd)
        if bal + w[i] <= floor or bal + x[i] <= floor:
            return "bust", i - s + 1, bal + x[i], best
        bal += x[i]
        best = max(best, x[i])
        peak = max(peak, bal)
        enough = bal >= rules.target_usd and i - s + 1 >= rules.min_days
        if not funded and enough and best <= rules.consistency * bal:
            return "pass", i - s + 1, bal, best
    return "open", len(x) - s, bal, best


def replay_lucid(
    per_contract_daily: Sequence[float],
    per_contract_worst: Sequence[float],
    micros: int,
    rules: LucidRules | None = None,
    funded_sessions: int = 126,
) -> dict[str, Any]:
    """An evaluation started on every session, then (on a pass) a funded account
    from the next session for `funded_sessions` sessions (126 = about 6 months).
    Payouts aren't modelled: the funded figure is the account's profit before
    withdrawals and the 90/10 split."""
    rules = rules or LucidRules()
    if micros > rules.max_micros:
        raise ValueError(f"{micros} micros is above the {rules.max_micros} allowed")
    x = np.asarray(per_contract_daily, float) * micros
    w = np.asarray(per_contract_worst, float) * micros
    passed, busted, days, funded_bust, funded_pnl = 0, 0, [], 0, []
    for s in range(len(x)):
        out, n, _, _ = _account(x, w, s, rules, funded=False)
        if out == "bust":
            busted += 1
        elif out == "pass":
            passed += 1
            days.append(n)
            f0 = s + n
            if f0 + funded_sessions <= len(x):
                xs, ws = x[f0 : f0 + funded_sessions], w[f0 : f0 + funded_sessions]
                fout, _, fbal, _ = _account(xs, ws, 0, rules, funded=True)
                funded_bust += fout == "bust"
                funded_pnl.append(fbal)
    done = passed + busted
    nf = len(funded_pnl)
    return {
        "micros": micros,
        "evaluations": done,
        "pass_rate": passed / done if done else 0.0,
        "median_sessions_to_pass": float(np.median(days)) if days else None,
        "funded_bust_within_6m": funded_bust / nf if nf else None,
        "funded_median_6m_profit_usd": float(np.median(funded_pnl)) if nf else None,
    }


# --- entry point ----------------------------------------------------------------------


def run(
    spec: Spec,
    store_root: Path,
    out: Path,
    *,
    signoff: bool = False,
) -> dict[str, Any]:
    start, end = spec.start, spec.end
    if signoff:
        holdout.sign_off("intraday_momentum", spec.trial, start, end)
    else:
        holdout.guard(start, end)
    store = BarStore(store_root)
    symbol = spec.symbol
    days = load_days(store, symbol, start - timedelta(days=45), end)
    from moon_ai.backtest.runner import roll_days_in_store

    rolls = roll_days_in_store(store, symbol, start - timedelta(days=1), end)
    degraded = degraded_sessions(load_degraded_dates())
    blackout = Blackout(load_events(NEWS_CSV))
    kw = dict(start=start, end=end, rolls=rolls, degraded=degraded, blackout=blackout)
    res = backtest(days, spec, **kw)
    stress = backtest(days, spec, slippage_mult=2.0, **kw)
    summary = score(res, stress, spec)

    # Prop replay on 1-contract P&L, so size can be chosen separately.
    sessions = sorted(res.daily)
    per_contract, worst = [], []
    for d in sessions:
        day_trades = [t for t in res.trades if t.day == d]
        per_contract.append(sum((t.net_usd / t.qty for t in day_trades), 0.0))
        worst.append(intraday_worst(day_trades))
    summary["one_contract"] = {
        "net_usd": float(sum(per_contract)),
        "max_dd_usd": max_drawdown(per_contract),
        "sharpe_ann": sharpe(per_contract) * math.sqrt(252),
    }
    rules = EvalRules()
    summary["prop_replay"] = {
        "rules": asdict(rules),
        "by_size": [replay_evals(per_contract, m, rules, worst) for m in (1, 2, 3, 5)],
        "lucid_50k": {
            "rules": asdict(LucidRules()),
            "by_size": [replay_lucid(per_contract, worst, m) for m in (1, 2, 3, 4, 5, 6, 8)],
        },
        "by_size_close_only": [replay_evals(per_contract, m, rules) for m in (1, 2, 3, 5)],
    }
    summary["spec"] = {k: str(v) for k, v in asdict(spec).items()}

    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    pl.DataFrame([{**asdict(t), "net_usd": t.net_usd} for t in res.trades]).write_csv(
        out / "trades.csv"
    )
    pl.DataFrame(
        {
            "day": sessions,
            "net_usd": [float(res.daily[d]) for d in sessions],
            "one_contract_usd": per_contract,
        }
    ).write_csv(out / "daily.csv")
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--store", type=Path, default=Path("data/bars"))
    p.add_argument("--out", type=Path, default=Path("data/runs/intraday_momentum"))
    p.add_argument("--holdout-signoff", action="store_true")
    p.add_argument("--trial", default="default", help="a pre-registered trial, e.g. prop_v2")
    p.add_argument("--symbol", help="cross-check on another market (diagnostics only)")
    p.add_argument("--fill-delay", type=int, default=0, help="diagnostics only")
    args = p.parse_args(argv)
    spec = load_spec(trial=args.trial)
    if args.holdout_signoff:
        spec = replace(spec, start=holdout.HOLDOUT_START, end=holdout.HOLDOUT_END)
    if args.symbol:
        from moon_ai.config import load_config

        inst = load_config().instrument(args.symbol)
        spec = replace(spec, symbol=args.symbol, tick=inst.tick_size, point_value=inst.point_value)
    if args.fill_delay:
        spec = replace(spec, fill_delay=args.fill_delay)
    diag = args.symbol or args.fill_delay
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    tag = "holdout" if args.holdout_signoff else "diagnostic" if diag else spec.trial
    if args.holdout_signoff and diag:
        p.error("a sign-off runs the pre-registered default only")
    s = run(spec, args.store, args.out / f"{tag}.{stamp}", signoff=args.holdout_signoff)
    print(json.dumps({k: v for k, v in s.items() if k != "spec"}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
