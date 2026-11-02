"""Setup parameters, the pre-registered defaults, `Candidate` and the `Setup` protocol.

docs/design.md, "Setup testing protocol" and "Code layout and commands".

- `config/defaults.toml` holds one locked default per setup plus its rescue
  trials. Its commit is the pre-registration record, and `defaults_hash()`
  ties every backtest run to the exact file it used.
- A setup never places orders. `Setup.scan(ctx)` returns `Candidate`s; the
  trader decides which become orders, and every other one is journaled with
  its skip status.
"""

from __future__ import annotations

import hashlib
import tomllib
from dataclasses import dataclass, field, fields
from datetime import datetime, time
from pathlib import Path
from typing import Any, Literal, Protocol

from moon_ai.config import ConfigError, SessionConfig, _override
from moon_ai.engine import Context
from moon_ai.journal.schema import candidate_id

DEFAULTS_PATH = Path(__file__).resolve().parents[3] / "config" / "defaults.toml"
MAX_RESCUE_TRIALS = 12
MAX_ROUND2_TRIALS = 4

Side = Literal["long", "short"]


@dataclass(frozen=True)
class SetupParams:
    """Every tunable rule of a setup. One instance per setup in defaults.toml."""

    priority: int = 99  # portfolio dedupe: lower wins (AM SB 1 ... 2022 model 5)
    # Setup and entry must fall in this named window (config.SessionConfig.windows).
    window: str = "ny_am_silver_bullet"
    # The sweep may happen from here (it can precede the entry window).
    sweep_from: time | None = None
    timeout: time = time(15, 55)  # a still-open trade is closed at market
    pools: tuple[str, ...] = ()
    # ICT primitives (research §4 dimensions)
    swing_n: int = 1
    sweep_close_back_bars: int = 1
    mss_break: Literal["close", "wick"] = "close"
    displacement_k: float = 1.5
    fvg_entry: Literal["edge", "ce"] = "edge"
    fvg_selection: Literal["first", "first_tethered"] = "first"
    tethered_grid: int = 8
    tethered_tolerance_ticks: int = 0
    stop_offset_ticks: int = 1  # stop = sweep extreme +/- this
    # Minimum move on offer from entry to the draw on liquidity (not a take-profit).
    min_objective_points: float | None = None
    # Round 2 (2026-11-01, after the first results; see docs/research/why-losing.md):
    min_rr: float | None = None  # skip a plan whose reward:risk to the target is below this
    timeframe: int = 1  # minutes per bar the patterns are read from (entries still fill on 1m)
    min_leg_points: float | None = None  # OTE: skip legs shorter than this
    ote_entry: float | None = None
    ote_stop: float | None = None
    require_ote_overlap: bool = False
    bias_proxy: str = "prev_day_range"
    bias_gate: bool = False
    po3_filter: bool = False
    news_handling: Literal["blocks_entry", "blocks_setup"] = "blocks_entry"
    news_day_filter: bool = False
    require_discount_fvg: bool = False
    # Non-ICT intraday setups, batch 1 (#102; setups/intraday.py):
    atr_days: int = 14  # daily ATR of the cash session, over finished days
    noise_days: int = 14  # noise_breakout: days averaged for the noise area
    or_minutes: int = 5  # orb_5m: opening-range length
    checkpoint_minutes: int = 30  # noise_breakout: how often the area is checked
    noise_mult: float = 1.0  # noise_breakout: area width multiplier
    stop_atr: float | None = None  # stop distance as a fraction of the daily ATR
    target_r: float | None = None  # target in R (None: hold to the time-out)
    min_stop_ticks: int = 0  # skip a plan whose stop is closer than this
    entry_time: time | None = None  # intraday_momentum: entry bar close (default 15:30)
    min_move_atr: float | None = None  # intraday_momentum: skip a first half hour smaller than this
    gap_min_atr: float | None = None  # gap_fill: smallest gap traded, in daily ATRs
    gap_max_atr: float | None = None  # gap_fill: largest gap traded
    gap_stop_mult: float = 1.0  # gap_fill: stop distance as a multiple of the gap
    # noise_breakout round 2 (2026-11-02; Zarattini, Aziz & Barbon 2024 as published):
    # "hold": keep the anchor stop to the close; "boundary_vwap": at each checkpoint,
    # exit if the close is back inside the stricter of the noise boundary and VWAP.
    exit_rule: Literal["hold", "boundary_vwap"] = "hold"
    # "simple": one trade a day, held; "paper": the boundary/VWAP exit plus
    # re-entry at later checkpoints (the 2-trades-a-session cap still applies).
    noise_variant: Literal["simple", "paper"] = "simple"
    # Batch 2 (2026-11-02):
    # Trade only when the 14-day ATR is above ("high") or below ("low") its
    # median over the last `regime_days` finished days.
    vol_regime: Literal["any", "high", "low"] = "any"
    regime_days: int = 100
    trend_min_atr: float = 0.5  # vwap_pullback: the day's move from the open that makes a trend
    vwap_dev_atr: float = 0.35  # vwap_reversion: distance from VWAP, in ATRs, that is faded
    dev_stop_mult: float = 1.0  # vwap_reversion: stop distance as a multiple of that distance
    tom_days_before: int = 1  # turn_of_month: trading days before the month end
    tom_days_after: int = 3  # turn_of_month: trading days into the new month


@dataclass(frozen=True)
class RescueTrial:
    name: str
    changes: dict[str, Any]


@dataclass(frozen=True)
class SetupDefaults:
    name: str
    title: str
    params: SetupParams
    rescue: tuple[RescueTrial, ...] = ()
    # Round 2, registered 2026-11-01 after every setup failed (docs/research/why-losing.md).
    round2: tuple[RescueTrial, ...] = ()

    @property
    def all_trials(self) -> tuple[RescueTrial, ...]:
        """Every pre-registered trial: the rescue list, then round 2."""
        return (*self.rescue, *self.round2)

    def trial(self, name: str) -> RescueTrial:
        """A pre-registered trial by name, from either list."""
        for t in self.all_trials:
            if t.name == name:
                return t
        raise ValueError(f"{self.name} has no pre-registered trial {name!r}")

    def trial_params(self, trial: RescueTrial) -> SetupParams:
        return _apply(self.params, trial.changes, f"setups.{self.name}.rescue.{trial.name}")


# Fields whose default is None, so the generic coercion can't infer their type.
_OPTIONAL_TIMES = {"sweep_from", "entry_time"}
_OPTIONAL_FLOATS = {
    "min_objective_points",
    "ote_entry",
    "ote_stop",
    "min_rr",
    "min_leg_points",
    "stop_atr",
    "target_r",
    "min_move_atr",
    "gap_min_atr",
    "gap_max_atr",
}


def _apply(params: SetupParams, values: dict[str, Any], section: str) -> SetupParams:
    coerced = dict(values)
    for k, v in values.items():
        if k in _OPTIONAL_TIMES and isinstance(v, str):
            coerced[k] = time.fromisoformat(v)
        elif k in _OPTIONAL_FLOATS and isinstance(v, int | float):
            coerced[k] = float(v)
    return _override(params, coerced, section)


def load_setup_defaults(path: Path = DEFAULTS_PATH) -> dict[str, SetupDefaults]:
    """Read and check defaults.toml. Unknown keys, combined or no-op rescue
    trials and more than 12 rescue (4 round-2) trials per setup are all errors."""
    with Path(path).open("rb") as fh:
        raw = tomllib.load(fh)
    unknown = set(raw) - {"setups"}
    if unknown:
        raise ConfigError(f"unknown sections in {path}: {sorted(unknown)}")
    out: dict[str, SetupDefaults] = {}
    for name, sec in raw.get("setups", {}).items():
        sec = dict(sec)
        title = sec.pop("title", name)
        trials_raw = sec.pop("rescue", [])
        round2_raw = sec.pop("round2", [])
        params = _apply(SetupParams(), sec, f"setups.{name}")
        _check_window(params, f"setups.{name}")
        if len(trials_raw) > MAX_RESCUE_TRIALS:
            raise ConfigError(
                f"setups.{name}: {len(trials_raw)} rescue trials, max {MAX_RESCUE_TRIALS}"
            )
        if len(round2_raw) > MAX_ROUND2_TRIALS:
            raise ConfigError(
                f"setups.{name}: {len(round2_raw)} round-2 trials, max {MAX_ROUND2_TRIALS}"
            )
        d = SetupDefaults(name, title, params)
        trials = [_trial(d, t) for t in trials_raw]
        round2 = [_trial(d, t) for t in round2_raw]
        names = [t.name for t in trials + round2]
        if len(set(names)) != len(names):
            raise ConfigError(f"setups.{name}: duplicate rescue trial names")
        out[name] = SetupDefaults(name, title, params, tuple(trials), tuple(round2))
    return out


def _trial(d: SetupDefaults, t: dict[str, Any]) -> RescueTrial:
    """One pre-registered trial: exactly one parameter changed, and it must change it."""
    t = dict(t)
    changes = {k: v for k, v in t.items() if k != "name"}
    if len(changes) != 1:
        raise ConfigError(
            f"setups.{d.name} rescue {t.get('name')!r}: change exactly one parameter, "
            f"not {sorted(changes)}"
        )
    trial = RescueTrial(str(t.get("name", next(iter(changes)))), changes)
    _check_window(d.trial_params(trial), f"setups.{d.name} rescue {trial.name!r}")
    if d.trial_params(trial) == d.params:
        raise ConfigError(f"setups.{d.name} rescue {trial.name!r} changes nothing")
    return trial


def _check_window(params: SetupParams, where: str) -> None:
    windows = SessionConfig().windows
    if params.window not in windows:
        raise ConfigError(f"{where}: unknown window {params.window!r}; known: {sorted(windows)}")


def defaults_hash(path: Path = DEFAULTS_PATH) -> str:
    """sha256 of the defaults file: recorded on every run (`runs.defaults_hash`)."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@dataclass(frozen=True)
class Candidate:
    """One trade a setup proposes, frozen at its decision time.

    `decision_time` is the close of the bar that completed the setup; nothing
    in `features` or `rule_results` may be known later than that.
    """

    setup: str
    symbol: str
    side: Side
    decision_time: datetime
    entry_type: Literal["market", "limit", "stop"]
    entry: float | None  # None for market entries
    stop: float
    target: float
    timeout: datetime
    # An entry not filled by this time is cancelled (e.g. the Silver Bullet window end).
    entry_deadline: datetime | None = None
    rule_results: dict[str, Any] = field(default_factory=dict)
    features: dict[str, Any] = field(default_factory=dict)
    feature_set: str = ""
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.decision_time.tzinfo is None or self.timeout.tzinfo is None:
            raise ValueError("candidate times must be timezone-aware")
        if self.entry_type != "market" and self.entry is None:
            raise ValueError(f"a {self.entry_type} entry needs a price")
        ref = self.entry if self.entry is not None else (self.stop + self.target) / 2
        sign = 1 if self.side == "long" else -1
        if not sign * (self.stop - ref) < 0 < sign * (self.target - ref):
            raise ValueError(
                f"{self.side} candidate needs stop and target on opposite sides of entry"
            )

    def id(self, run_id: str) -> str:
        return candidate_id(run_id, self.setup, self.decision_time, self.side)

    def journal_row(self, run_id: str, status: str, **extra: Any) -> dict[str, Any]:
        """The `candidates` table row; `extra` sets ml_p, ml_threshold, label, ..."""
        row = {
            "candidate_id": self.id(run_id),
            "run_id": run_id,
            "setup": self.setup,
            "symbol": self.symbol,
            "side": self.side,
            "decision_time": self.decision_time,
            "entry_type": self.entry_type,
            "entry": self.entry,
            "stop": self.stop,
            "target": self.target,
            "timeout": self.timeout,
            "rule_results": self.rule_results,
            "features": self.features,
            "feature_set": self.feature_set,
            "status": status,
            "tags": list(self.tags),
        }
        return {**row, **extra}


class Setup(Protocol):
    name: str
    params: SetupParams

    def scan(self, ctx: Context) -> list[Candidate]:
        """Candidates completed by the bar that just closed (`ctx.now`)."""
        ...


REGISTRY: dict[str, Any] = {}


def register(name: str):
    """Class decorator: make a setup available to the backtest runner by name."""

    def deco(cls):
        if name in REGISTRY:
            raise ValueError(f"setup {name!r} registered twice")
        cls.name = name
        REGISTRY[name] = cls
        return cls

    return deco


def param_names() -> set[str]:
    return {f.name for f in fields(SetupParams)}


__all__ = [
    "DEFAULTS_PATH",
    "MAX_RESCUE_TRIALS",
    "REGISTRY",
    "Candidate",
    "RescueTrial",
    "Setup",
    "SetupDefaults",
    "SetupParams",
    "defaults_hash",
    "load_setup_defaults",
    "param_names",
    "register",
]
