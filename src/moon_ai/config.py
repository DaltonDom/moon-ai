"""Typed configuration with the research defaults.

Every parameter that the ICT definitions research marks *param* or UNVERIFIED
lives here with that research's default (docs/research/ict-setup-definitions.md
§1.1, §1.2 and §4 on the `research/ict-setup-definitions` branch). A TOML file
can override any value; unknown keys are rejected so typos don't pass silently.

Times are wall-clock times in America/New_York.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields, replace
from datetime import time
from pathlib import Path
from typing import Any, Literal


class ConfigError(ValueError):
    """Raised for a config file that doesn't match the schema."""


@dataclass(frozen=True)
class Window:
    """A daily window in New York wall-clock time: [start, end).

    `end <= start` means the window crosses midnight (e.g. 20:00-00:00).
    """

    start: time
    end: time


def _w(start: str, end: str) -> Window:
    return Window(time.fromisoformat(start), time.fromisoformat(end))


def _default_windows() -> dict[str, Window]:
    # ict-setup-definitions.md §1.1. All edges are UNVERIFIED-primary except the
    # 10:00 start of the NY AM Silver Bullet.
    return {
        "asian_range": _w("20:00", "00:00"),
        "london_killzone": _w("02:00", "05:00"),
        "ny_am_killzone": _w("07:00", "10:00"),
        # ICT's index "watching hours" (2022 Mentorship ep. 2, tmeCWULSTHc 42:38; #21).
        # Default NY AM window of the OTE pullback and the 2022 model (#16).
        "ny_am_index_hours": _w("08:30", "11:00"),
        "london_close_killzone": _w("10:00", "12:00"),
        "ny_pm_session": _w("13:30", "16:00"),
        "london_silver_bullet": _w("03:00", "04:00"),
        "ny_am_silver_bullet": _w("10:00", "11:00"),
        "ny_pm_silver_bullet": _w("14:00", "15:00"),
        # Off by default: 90 minutes long and overlaps the 08:30 data release.
        "extra_silver_bullet": _w("07:00", "08:30"),
        # Non-ICT batch 1 (#102): where each setup's decision bars close, so the
        # random-entry baseline enters at comparable times.
        "rth_first_hour": _w("09:31", "10:31"),
        "rth_checkpoints": _w("10:00", "15:31"),
        "last_half_hour": _w("15:30", "15:31"),
        "rth_open_90": _w("09:35", "11:01"),
        "rth_first_minute": _w("09:31", "09:32"),
    }


@dataclass(frozen=True)
class SessionConfig:
    windows: dict[str, Window] = field(default_factory=_default_windows)
    enabled_silver_bullets: tuple[str, ...] = (
        "london_silver_bullet",
        "ny_am_silver_bullet",
        "ny_pm_silver_bullet",
    )
    killzones: tuple[str, ...] = (
        "london_killzone",
        "ny_am_killzone",
        "london_close_killzone",
        "ny_pm_session",
    )
    # CME Globex trading day: 18:00 ET (prior calendar day) to 17:00 ET.
    trading_day_start: time = time(18)
    trading_day_end: time = time(17)


@dataclass(frozen=True)
class IctConfig:
    """ICT primitive and setup parameters (ict-setup-definitions.md §1.2, §4)."""

    # Swing = fractal with N bars each side; known at the close of bar i+N.
    swing_n: int = 1
    # Liquidity sweep: trade through a pool, then close back within m bars.
    sweep_close_back_bars: int = 1
    sweep_require_close_back: bool = True
    # Ticks beyond the level a bar must trade. 1 tick == "high > level".
    sweep_min_penetration_ticks: int = 1
    # Relative equal highs/lows tolerance (epsilon, 2-8 ticks on MNQ).
    equal_level_tolerance_ticks: int = 4
    # Displacement: |close - open| >= k * ATR(period), optionally creating an FVG.
    displacement_k: float = 1.5
    displacement_atr_period: int = 14
    displacement_require_fvg: bool = True
    # Market structure shift: "close" beyond the swing, or "wick".
    mss_break: Literal["close", "wick"] = "close"
    # Our own bound (not from the research): how many bars after the sweep an
    # MSS may still confirm.
    mss_max_bars: int = 30
    # FVG
    fvg_min_size_ticks: int = 0
    fvg_entry: Literal["edge", "ce", "far_edge"] = "edge"
    fvg_selection: Literal["first", "first_tethered", "any"] = "first"
    tethered_grid: int = 8
    tethered_tolerance_ticks: int = 0
    # Setup-level parameters, held here so every sweep dimension is in config.
    sb_min_objective_points: float = 10.0
    ote_entry: float = 0.62
    ote_stop: float = 1.0
    # Ticket #8: a London trade whose stop is closer than this is skipped (and
    # logged as skipped), because costs would eat too much of R.
    london_min_stop_ticks: int = 40
    po3_ref_open: time = time(0)
    bias_proxy: Literal[
        "prev_day_range",
        "weekly_expansion",
        "nearest_pool",
        "premium_discount",
        "midnight_open",
        "none",
    ] = "prev_day_range"
    # News blackout (tickets #15, #16; design.md "News blackout"). The blackout
    # blocks entries only; "blocks_setup" is a rescue-pass variant.
    news_handling: Literal["blocks_setup", "blocks_entry"] = "blocks_entry"
    news_blackout_minutes: int = 15  # before and after each blocking event
    # On FOMC statement days the blackout runs from 15 minutes before the
    # statement to this time (end of the press conference).
    fomc_blackout_end: time = time(15, 30)


@dataclass(frozen=True)
class BrokerConfig:
    """Simulated broker costs and fill policy (ticket #8, design.md "Backtest realism").

    Slippage is in ticks against us. "Entry" slippage applies to market and
    stop-entry orders (and market exits); "stop" slippage applies to bracket
    stop exits. Limit orders and targets never slip. Values come from the
    London liquidity research (docs/research/london-liquidity.md on the
    `research/london-liquidity` branch): NY AM was measured, and every window
    other than London uses it.
    """

    # Generic default until a prop firm is chosen; then use that firm's rate.
    commission_per_contract: float = 1.00  # per side, USD
    entry_slippage_ticks: int = 1
    stop_slippage_ticks: int = 3
    # London override, by the time the fill's bar opens (New York time).
    london_slippage_start: time = time(2)
    london_slippage_end: time = time(5)
    london_entry_slippage_ticks: int = 2
    london_stop_slippage_ticks: int = 2
    # Above this many contracts, London fills walk the book: both become this.
    london_large_qty: int = 10
    london_large_slippage_ticks: int = 3
    # 2.0 for the double-slippage stress test every passing setup must survive.
    slippage_multiplier: float = 1.0
    limit_fill: Literal["trade_through", "touch"] = "trade_through"


@dataclass(frozen=True)
class InstrumentSpec:
    tick_size: float
    point_value: float  # USD per 1.0 point per contract


def _default_instruments() -> dict[str, InstrumentSpec]:
    return {
        "MNQ": InstrumentSpec(tick_size=0.25, point_value=2.0),
        "MES": InstrumentSpec(tick_size=0.25, point_value=5.0),
        "NQ": InstrumentSpec(tick_size=0.25, point_value=20.0),
        "ES": InstrumentSpec(tick_size=0.25, point_value=50.0),
    }


@dataclass(frozen=True)
class DataConfig:
    dataset: str = "GLBX.MDP3"
    schema: str = "ohlcv-1m"
    stype_in: str = "continuous"
    symbols: tuple[str, ...] = ("MNQ.v.0", "MES.v.0", "NQ.v.0", "ES.v.0")
    store_root: Path = Path("data/bars")
    # The downloader refuses any request whose get_cost estimate exceeds this,
    # unless explicitly confirmed.
    max_cost_usd: float = 15.0


@dataclass(frozen=True)
class RiskConfig:
    """Hard risk rules the ML can't override (docs/design.md, "Hard risk rules")."""

    account_usd: float = 50_000.0
    risk_per_trade_pct: float = 1.0
    max_trades_per_session: int = 2
    daily_stop_pct: float = 2.0  # of the session's starting equity
    kill_switch_drawdown_pct: float = 10.0  # from the equity peak; stops new trades for good
    flat_by: time = time(16)  # New York; positions are closed at market before this


@dataclass(frozen=True)
class Config:
    sessions: SessionConfig = field(default_factory=SessionConfig)
    ict: IctConfig = field(default_factory=IctConfig)
    broker: BrokerConfig = field(default_factory=BrokerConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    instruments: dict[str, InstrumentSpec] = field(default_factory=_default_instruments)
    data: DataConfig = field(default_factory=DataConfig)

    def instrument(self, symbol: str) -> InstrumentSpec:
        """Spec for a root ("MNQ") or a continuous symbol ("MNQ.v.0")."""
        root = symbol.split(".", 1)[0]
        try:
            return self.instruments[root]
        except KeyError:
            raise ConfigError(f"no instrument spec for {symbol!r}") from None


def load_config(path: Path | None = None) -> Config:
    """Defaults, overridden by the TOML file at `path` if given."""
    cfg = Config()
    if path is None:
        return cfg
    with Path(path).open("rb") as fh:
        raw = tomllib.load(fh)
    return _apply(cfg, raw)


def _apply(cfg: Config, raw: dict[str, Any]) -> Config:
    unknown = set(raw) - {"sessions", "ict", "broker", "risk", "instruments", "data"}
    if unknown:
        raise ConfigError(f"unknown config sections: {sorted(unknown)}")

    sessions = cfg.sessions
    if "sessions" in raw:
        sec = dict(raw["sessions"])
        windows = dict(sessions.windows)
        for name, pair in sec.pop("windows", {}).items():
            windows[name] = _w(*pair)
        sessions = replace(_override(sessions, sec, "sessions"), windows=windows)

    instruments = dict(cfg.instruments)
    for root, spec in raw.get("instruments", {}).items():
        instruments[root] = InstrumentSpec(**spec)

    return replace(
        cfg,
        sessions=sessions,
        ict=_override(cfg.ict, raw.get("ict", {}), "ict"),
        broker=_override(cfg.broker, raw.get("broker", {}), "broker"),
        data=_override(cfg.data, raw.get("data", {}), "data"),
        risk=_override(cfg.risk, raw.get("risk", {}), "risk"),
        instruments=instruments,
    )


def _override[T](obj: T, values: dict[str, Any], section: str) -> T:
    known = {f.name: f for f in fields(obj)}  # type: ignore[arg-type]
    unknown = set(values) - set(known)
    if unknown:
        raise ConfigError(f"unknown keys in [{section}]: {sorted(unknown)}")
    coerced: dict[str, Any] = {}
    for key, value in values.items():
        current = getattr(obj, key)
        if isinstance(current, time):
            value = time.fromisoformat(value)
        elif isinstance(current, tuple):
            value = tuple(value)
        elif isinstance(current, Path):
            value = Path(value)
        elif isinstance(current, float) and isinstance(value, int):
            value = float(value)
        coerced[key] = value
    return replace(obj, **coerced)  # type: ignore[type-var]
