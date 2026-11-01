"""Run one setup over a date range: bar store -> engine -> SimBroker -> Parquet run.

Every run records what it was made from (code commit, defaults hash, data
range, account and risk) so a report card can always be traced back, and is
deterministic: the same code, data and defaults give the same candidates and
trades.

The news calendar is required by default. A run without it is allowed only
with `news=False`, and says so in its notes, because skipping the blackout
makes results look better than live trading could.
"""

from __future__ import annotations

import subprocess
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import polars as pl

from moon_ai.broker import SimBroker
from moon_ai.config import Config, load_config
from moon_ai.data.calendar import SessionCalendar
from moon_ai.data.news import NEWS_CSV, Blackout, load_events
from moon_ai.data.quality import degraded_sessions, load_degraded_dates
from moon_ai.data.store import BarStore, ParquetBarFeed, SecondBarLookup
from moon_ai.engine import run
from moon_ai.journal import ParquetRun, RunJournal, decode_json, read_run
from moon_ai.sessions import NY, trading_day
from moon_ai.setups import REGISTRY, defaults_hash, load_setup_defaults
from moon_ai.setups.base import DEFAULTS_PATH
from moon_ai.trader import Trader

REPO = Path(__file__).resolve().parents[3]


class NewsCalendarMissing(RuntimeError):
    """The news calendar file isn't there and the run didn't opt out of it."""


@dataclass(frozen=True)
class BacktestResult:
    run_id: str
    folder: Path
    summary: dict[str, Any]

    def line(self) -> str:
        s = self.summary
        return (
            f"{self.run_id}: {s['trades']} trades, net ${s['net_usd']:,.0f}, "
            f"win rate {s['win_rate']:.0%}, {s['net_r']:+.2f}R; candidates {s['statuses']}"
        )


def code_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def roll_days_in_store(store: BarStore, symbol: str, start: date, end: date) -> frozenset[date]:
    """Trading days where the continuous contract changes, without loading every bar."""
    paths = [s.path for s in store.files(symbol) if s.start < end and s.end > start]
    if not paths:
        return frozenset()
    frame = (
        pl.concat([pl.read_parquet(p, columns=["ts_event", "instrument_id"]) for p in paths])
        .unique(subset=["ts_event"], keep="last")
        .sort("ts_event")
    )
    prev = pl.col("instrument_id").shift(1)
    changes = frame.filter(prev.is_not_null() & (pl.col("instrument_id") != prev))
    return frozenset(trading_day(ts + timedelta(minutes=1)) for ts in changes["ts_event"].to_list())


def run_backtest(
    setup: str,
    start: date,
    end: date,
    *,
    trial: str | None = None,
    store_root: Path | None = None,
    runs_root: Path = Path("data/runs"),
    config: Config | None = None,
    symbol: str = "MNQ.v.0",
    news: bool = True,
    news_csv: Path = NEWS_CSV,
    defaults_path: Path = DEFAULTS_PATH,
    run_id: str | None = None,
    extra_notes: dict[str, Any] | None = None,
    second_bars: bool = True,
) -> BacktestResult:
    """Backtest `setup` (its default, or one pre-registered rescue `trial`) over
    the trading days [start, end)."""
    config = config or load_config()
    defaults = load_setup_defaults(defaults_path)[setup]
    params = defaults.params
    if trial is not None:
        match = [t for t in defaults.rescue if t.name == trial]
        if not match:
            raise ValueError(f"{setup} has no pre-registered rescue trial {trial!r}")
        params = defaults.trial_params(match[0])
    store = BarStore(store_root or config.data.store_root, config.data.dataset)

    notes: dict[str, Any] = {
        "setup": setup,
        "trial": trial or "default",
        "symbol": symbol,
        **(extra_notes or {}),
    }
    blackout = None
    if news:
        if not Path(news_csv).exists():
            raise NewsCalendarMissing(
                f"{news_csv} is missing; build it first, or pass news=False (--no-news) "
                "to run without the news blackout"
            )
        blackout = Blackout(load_events(news_csv), config.ict)
    else:
        notes["warning"] = "run without the news blackout: results are optimistic"

    calendar = SessionCalendar(
        rolls=roll_days_in_store(store, symbol, start - timedelta(days=1), end),
        degraded=degraded_sessions(load_degraded_dates()),
    )
    stamp = datetime.now(UTC)
    run_id = run_id or f"{setup}.{trial or 'default'}.{start}_{end}.{stamp:%Y%m%dT%H%M%S}"
    parquet = ParquetRun(
        runs_root,
        {
            "run_id": run_id,
            "kind": "backtest",
            "created_at": stamp,
            "code_commit": code_commit(),
            "defaults_hash": defaults_hash(defaults_path),
            "model_id": None,
            "data_start": datetime.combine(start, datetime.min.time(), tzinfo=UTC),
            "data_end": datetime.combine(end, datetime.min.time(), tzinfo=UTC),
            "account_usd": config.risk.account_usd,
            "risk_per_trade_usd": config.risk.account_usd * config.risk.risk_per_trade_pct / 100,
            "notes": notes,
        },
    )
    journal = RunJournal(parquet, run_id, lambda s: config.instrument(s).tick_size)
    trader = Trader(
        [REGISTRY[setup](params, config, symbol)],
        journal,
        config,
        calendar=calendar,
        blackout=blackout,
    )
    # Trading day D runs 18:00 New York on D-1 to 17:00 on D.
    session_open = time(18)
    feed = ParquetBarFeed(
        store,
        [symbol],
        datetime.combine(start - timedelta(days=1), session_open, tzinfo=NY),
        datetime.combine(end - timedelta(days=1), session_open, tzinfo=NY),
    )
    lookup = SecondBarLookup(store) if second_bars else None
    broker = SimBroker(config.broker, config.instrument, lookup)
    run(feed, broker, trader, trader.tap(journal))
    trader.finish()
    folder = parquet.write()
    return BacktestResult(run_id, folder, summarize(folder))


def summarize(folder: Path) -> dict[str, Any]:
    cands = decode_json(read_run(folder, "candidates"), "candidates")
    trades = [t for t in decode_json(read_run(folder, "trades"), "trades") if t["r"] is not None]
    wins = sum(1 for t in trades if t["net_usd"] > 0)
    return {
        "statuses": dict(sorted(Counter(c["status"] for c in cands).items())),
        "trades": len(trades),
        "net_usd": sum(t["net_usd"] for t in trades),
        "net_r": sum(t["r"] for t in trades),
        "win_rate": wins / len(trades) if trades else 0.0,
    }
