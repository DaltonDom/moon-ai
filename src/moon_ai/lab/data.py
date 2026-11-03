"""Dense per-day minute grids built from the moon-ai-data Parquet bars.

A *day* is a CME trading day: 18:00 New York the evening before up to 17:00.
Minute index 0 is 18:00 ET; index 930 is 09:30 ET; index 1290 is 16:00 ET.
Missing minutes are forward-filled from the last close (volume 0), and minutes
before the first trade of the day carry NaN.

Arrays: O, H, L, C, V with shape (n_days, 1380).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import polars as pl

from moon_ai.data.calendar import session_info
from moon_ai.holdout import HOLDOUT_START

DATA_ROOT = Path(os.environ.get("MOON_AI_DATA", "/home/user/moon-ai-data/data/bars/GLBX.MDP3/ohlcv-1m"))
CACHE = Path(os.environ.get("MOON_AI_LAB_CACHE", "/tmp/moon-ai-lab-cache"))
N_MIN = 1380

POINT_VALUE = {"MNQ": 2.0, "MES": 5.0, "MYM": 0.5, "M2K": 5.0, "MGC": 10.0, "MCL": 100.0, "M6E": 12500.0}
TICK = {"MNQ": 0.25, "MES": 0.25, "MYM": 1.0, "M2K": 0.1, "MGC": 0.1, "MCL": 0.01, "M6E": 0.0001}


def m(hh: int, mm: int = 0) -> int:
    """Minute index of a New York clock time within the trading day."""
    t = hh * 60 + mm - 18 * 60
    return t + 1440 if t < 0 else t


@dataclass
class Grid:
    symbol: str
    days: np.ndarray  # datetime64[D]
    O: np.ndarray
    H: np.ndarray
    L: np.ndarray
    C: np.ndarray
    V: np.ndarray
    tradable: np.ndarray  # bool per day: regular session, not a roll day, not degraded
    point_value: float
    tick: float

    def slice(self, mask: np.ndarray) -> "Grid":
        return Grid(self.symbol, self.days[mask], self.O[mask], self.H[mask], self.L[mask],
                    self.C[mask], self.V[mask], self.tradable[mask], self.point_value, self.tick)


def _degraded() -> set[date]:
    p = Path(__file__).resolve().parents[3] / "data_public" / "degraded_days.csv"
    if not p.exists():
        return set()
    df = pl.read_csv(p)
    return {date.fromisoformat(d) for d in df["date"].to_list()}


def load(symbol: str, include_holdout: bool = False) -> Grid:
    """Load a symbol's grid. The holdout is cut off unless explicitly asked for."""
    tag = "full" if include_holdout else "research"
    cache = CACHE / f"{symbol}_{tag}.npz"
    if cache.exists():
        z = np.load(cache)
        return Grid(symbol, z["days"], z["O"], z["H"], z["L"], z["C"], z["V"], z["tradable"],
                    POINT_VALUE[symbol], TICK[symbol])
    files = sorted((DATA_ROOT / f"{symbol}.v.0").glob("*.parquet"))
    df = pl.concat([pl.read_parquet(f) for f in files]).unique("ts_event").sort("ts_event")
    df = df.with_columns(pl.col("ts_event").dt.convert_time_zone("America/New_York").alias("ny"))
    df = df.with_columns(
        # trading day: bars at/after 18:00 belong to the next calendar day
        pl.when(pl.col("ny").dt.hour() >= 18)
        .then(pl.col("ny").dt.date() + pl.duration(days=1))
        .otherwise(pl.col("ny").dt.date())
        .alias("tday"),
        ((pl.col("ny").dt.hour().cast(pl.Int32) * 60 + pl.col("ny").dt.minute().cast(pl.Int32) - 1080) % 1440)
        .alias("idx"),
    ).filter(pl.col("idx") < N_MIN)
    if not include_holdout:
        df = df.filter(pl.col("tday") < HOLDOUT_START)
    days = df["tday"].unique().sort()
    days = [d for d in days.to_list() if d.weekday() < 5]
    day_pos = {d: i for i, d in enumerate(days)}
    df = df.filter(pl.col("tday").is_in(days))
    n = len(days)
    arrs = {k: np.full((n, N_MIN), np.nan) for k in "OHLC"}
    V = np.zeros((n, N_MIN))
    di = np.array([day_pos[d] for d in df["tday"].to_list()])
    mi = df["idx"].to_numpy()
    for k, col in zip("OHLC", ["open", "high", "low", "close"]):
        arrs[k][di, mi] = df[col].to_numpy()
    V[di, mi] = df["volume"].to_numpy()
    # forward fill within day
    C = arrs["C"]
    for i in range(n):
        row = C[i]
        mask = np.isnan(row)
        if mask.all():
            continue
        idx = np.where(~mask, np.arange(N_MIN), 0)
        np.maximum.accumulate(idx, out=idx)
        filled = row[idx]
        first = np.argmax(~mask)
        filled[:first] = np.nan
        miss = mask & ~np.isnan(filled)
        for k in "OHL":
            arrs[k][i, miss] = filled[miss]
        C[i] = filled
    # tradable days
    inst = df.group_by("tday").agg(pl.col("instrument_id").n_unique().alias("nu"),
                                   pl.col("instrument_id").last().alias("last")).sort("tday")
    inst_map = {r[0]: (r[1], r[2]) for r in inst.iter_rows()}
    degraded = _degraded()
    tradable = np.zeros(n, bool)
    prev_last = None
    for i, d in enumerate(days):
        nu, last = inst_map[d]
        roll = nu > 1 or (prev_last is not None and last != prev_last)
        prev_last = last
        kind = session_info(d).kind
        tradable[i] = (kind == "regular") and not roll and d not in degraded \
            and not np.isnan(C[i, m(9, 30)]) and not np.isnan(C[i, m(16, 0)])
    days_np = np.array(days, dtype="datetime64[D]")
    CACHE.mkdir(parents=True, exist_ok=True)
    np.savez(cache, days=days_np, O=arrs["O"], H=arrs["H"], L=arrs["L"], C=C, V=V, tradable=tradable)
    return Grid(symbol, days_np, arrs["O"], arrs["H"], arrs["L"], C, V, tradable,
                POINT_VALUE[symbol], TICK[symbol])
