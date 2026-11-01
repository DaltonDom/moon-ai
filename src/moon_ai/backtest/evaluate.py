"""Judge a backtest run against the go-forward bar (docs/design.md, "Setup testing protocol").

A setup goes forward only if all three hold:

1. its mean R per trade beats the random-entry baseline, with the bootstrap
   95% CI of the difference above zero;
2. DSR > 0.95, counting every trial logged for that setup (every backtest run
   of it in the runs folder, stress re-runs excluded);
3. at least 100 trades. Fewer is "insufficient", not "fail".

A setup that passes must also survive a re-run with double slippage
(`stress_test`), still profitable.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import numpy as np

from moon_ai.backtest.baseline import TradeShape, prepare_days, random_entry_means
from moon_ai.backtest.runner import roll_days_in_store, run_backtest
from moon_ai.backtest.stats import Metrics, deflated_sharpe, metrics, pbo, sharpe
from moon_ai.config import Config, load_config
from moon_ai.data.calendar import SessionCalendar
from moon_ai.data.quality import degraded_sessions, load_degraded_dates
from moon_ai.data.store import BarStore
from moon_ai.journal import decode_json, read_run
from moon_ai.sessions import NY, trading_day
from moon_ai.setups import load_setup_defaults

MIN_TRADES = 100
DSR_BAR = 0.95
Verdict = Literal["go-forward", "fail", "insufficient"]


@dataclass(frozen=True)
class Evaluation:
    run_id: str
    setup: str
    trial: str
    metrics: Metrics
    random_mean_r: float
    edge_ci: tuple[float, float]  # 95% CI of (setup mean R - random mean R)
    dsr: float
    n_trials: int
    pbo: float | None  # None until there are 2+ comparable trials
    verdict: Verdict
    reasons: list[str]


def decide(trades: int, edge_ci_low: float, dsr: float) -> tuple[Verdict, list[str]]:
    reasons = []
    if edge_ci_low <= 0:
        reasons.append("doesn't clearly beat random entries (95% CI of the edge includes 0)")
    if dsr <= DSR_BAR:
        reasons.append(f"not enough evidence it isn't luck (DSR {dsr:.2f} <= {DSR_BAR})")
    if trades < MIN_TRADES:
        return "insufficient", [f"only {trades} trades; {MIN_TRADES} needed", *reasons]
    return ("go-forward", []) if not reasons else ("fail", reasons)


def _run(folder: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    run = decode_json(read_run(folder, "runs"), "runs")[0]
    trades = [t for t in decode_json(read_run(folder, "trades"), "trades") if t["r"] is not None]
    return run, sorted(trades, key=lambda t: t["exit_time"])


def trading_days(run: dict[str, Any], store: BarStore, symbol: str) -> list[date]:
    start, end = run["data_start"].date(), run["data_end"].date()
    cal = SessionCalendar(
        rolls=roll_days_in_store(store, symbol, start - timedelta(days=1), end),
        degraded=degraded_sessions(load_degraded_dates()),
    )
    days, d = [], start
    while d < end:
        if not cal.no_new_trades(d):
            days.append(d)
        d += timedelta(days=1)
    return days


def daily_r(trades: list[dict[str, Any]], days: list[date]) -> np.ndarray:
    idx = {d: i for i, d in enumerate(days)}
    out = np.zeros(len(days))
    for t in trades:
        i = idx.get(trading_day(t["exit_time"]))
        if i is not None:
            out[i] += t["r"]
    return out


def evaluate(
    folder: Path,
    *,
    store_root: Path | None = None,
    config: Config | None = None,
    n_random: int = 1000,
    seed: int = 0,
) -> Evaluation:
    config = config or load_config()
    folder = Path(folder)
    run, trades = _run(folder)
    notes = run["notes"]
    setup, trial, symbol = notes["setup"], notes["trial"], notes["symbol"]
    store = BarStore(store_root or config.data.store_root, config.data.dataset)
    days = trading_days(run, store, symbol)
    m = metrics([t["r"] for t in trades], [t["net_usd"] for t in trades], daily_r(trades, days))

    # Random-entry baseline over the same allowed days, window and time-out.
    defaults = load_setup_defaults()[setup]
    params = defaults.params
    if trial != "default":
        params = defaults.trial_params(defaults.trial(trial))
    cands = {
        c["candidate_id"]: c for c in decode_json(read_run(folder, "candidates"), "candidates")
    }
    shapes = []
    for t in trades:
        c = cands[t["candidate_id"]]
        shapes.append(
            TradeShape(
                1 if c["side"] == "long" else -1,
                abs(t["entry_price"] - c["stop"]),
                abs(c["target"] - t["entry_price"]),
            )
        )
    bars = (
        store.load(
            symbol,
            datetime.combine(days[0] - timedelta(days=1), datetime.min.time(), tzinfo=NY),
            run["data_end"],
        )
        if days
        else []
    )
    prepared = prepare_days(
        bars, set(days), config.sessions.windows[params.window], params.timeout, config
    )
    rand = random_entry_means(prepared, shapes, symbol, config, n_random, seed)
    rng = np.random.default_rng(seed + 1)
    real = np.asarray([t["r"] for t in trades])
    if len(real) and len(rand):
        boot = real[rng.integers(0, len(real), size=(len(rand), len(real)))].mean(axis=1)
        diff = boot - rand
        edge_ci = (float(np.quantile(diff, 0.025)), float(np.quantile(diff, 0.975)))
        random_mean = float(rand.mean())
    else:
        edge_ci, random_mean = (float("nan"), float("nan")), float("nan")

    # Every logged trial of this setup counts for the DSR and PBO.
    trial_series = _trial_series(folder.parent, setup, store, symbol)
    n_trials = max(len(trial_series), 1)
    srs = [sharpe(s) for s in trial_series.values()]
    var_sr = float(np.var(srs, ddof=1)) if len(srs) > 1 else 0.0
    dsr = deflated_sharpe(daily_r(trades, days), n_trials, var_sr)
    same_len = [s for s in trial_series.values() if len(s) == len(days)]
    pbo_value = pbo(np.column_stack(same_len)) if len(same_len) >= 2 and len(days) >= 16 else None

    verdict, reasons = decide(m.trades, edge_ci[0] if edge_ci[0] == edge_ci[0] else -1.0, dsr)
    return Evaluation(
        run["run_id"],
        setup,
        trial,
        m,
        random_mean,
        edge_ci,
        dsr,
        n_trials,
        pbo_value,
        verdict,
        reasons,
    )


def _trial_series(
    runs_root: Path, setup: str, store: BarStore, symbol: str
) -> dict[str, np.ndarray]:
    out = {}
    for f in sorted(runs_root.iterdir()):
        if not (f / "run.json").exists():
            continue
        run, trades = _run(f)
        notes = run["notes"] or {}
        if run["kind"] != "backtest" or notes.get("setup") != setup or notes.get("stress"):
            continue
        out[run["run_id"]] = daily_r(trades, trading_days(run, store, symbol))
    return out


def stress_test(setup: str, trial: str | None, start: date, end: date, **kw: Any) -> Metrics:
    """Re-run with double slippage; a passing setup must stay profitable. Not a trial."""
    config: Config = kw.pop("config", None) or load_config()
    stressed = replace(config, broker=replace(config.broker, slippage_multiplier=2.0))
    result = run_backtest(
        setup, start, end, trial=trial, config=stressed, extra_notes={"stress": "2x slippage"}, **kw
    )
    _, trades = _run(result.folder)
    return metrics([t["r"] for t in trades], [t["net_usd"] for t in trades], [])
