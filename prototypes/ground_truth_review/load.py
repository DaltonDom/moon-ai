"""PROTOTYPE (throwaway, ticket #11): load Databento parquet into Bars and run the detectors."""
from __future__ import annotations

from datetime import timedelta

import polars as pl

from moon_ai.bars import Bar, InMemoryBarFeed
from moon_ai.config import load_config
from moon_ai.ict.displacement import find_displacements
from moon_ai.ict.fvg import find_fvgs
from moon_ai.ict.liquidity import find_sweeps, prior_day_levels, swing_levels, window_levels
from moon_ai.ict.structure import find_market_structure_shifts
from moon_ai.ict.swings import find_swings


def load_bars(path: str) -> list[Bar]:
    df = pl.read_parquet(path).sort("ts_event")
    out = []
    for r in df.iter_rows(named=True):
        ts = r["ts_event"]
        out.append(Bar(r["symbol"], ts, ts + timedelta(minutes=1), r["open"], r["high"],
                       r["low"], r["close"], int(r["volume"]), int(r["instrument_id"])))
    return list(InMemoryBarFeed(out))


def detect(bars: list[Bar]):
    cfg = load_config()
    ict, tick = cfg.ict, cfg.instrument("MNQ").tick_size
    w = cfg.sessions.windows
    swings = find_swings(bars, ict.swing_n)
    levels = {
        "swing": swing_levels(swings),
        "pool": prior_day_levels(bars)
        + window_levels(bars, w["asian_range"], "asia")
        + window_levels(bars, w["london_killzone"], "london"),
    }
    sweeps = {k: find_sweeps(bars, v, tick, ict.sweep_close_back_bars, ict.sweep_require_close_back,
                             ict.sweep_min_penetration_ticks) for k, v in levels.items()}
    all_sweeps = sweeps["swing"] + sweeps["pool"]
    mss = find_market_structure_shifts(bars, swings, all_sweeps, ict.mss_break, ict.mss_max_bars)
    fvgs = find_fvgs(bars, tick, ict.fvg_min_size_ticks)
    disp = find_displacements(bars, tick, ict.displacement_k, ict.displacement_atr_period,
                              ict.displacement_require_fvg)
    return dict(swings=swings, levels=levels, sweeps=sweeps, mss=mss, fvgs=fvgs, disp=disp)
