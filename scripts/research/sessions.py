"""Day x minute matrices of RTH 1-minute bars, for fast strategy research.

Each trading day becomes one row of 390 one-minute bars, 09:30-15:59 New York
time (a bar's label is its open). Minutes with no trade are filled flat at the
previous close. Days are dropped when the session is short (holiday half
days), when a contract roll falls inside the session, or when Databento flags
the day as degraded.

Per day we also keep the overnight (Globex, 18:00 prior evening to 09:29)
high, low and last price, and the prior RTH close on the same contract.

`load(symbol, start, end)` refuses research dates inside the locked holdout
unless `holdout=True` is passed for the single sign-off run.
"""

from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import polars as pl

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from moon_ai import holdout  # noqa: E402

DATA = Path("/home/user/moon-ai-data/data/bars/GLBX.MDP3/ohlcv-1m")
N_MIN = 390  # 09:30 .. 15:59

SPECS = {  # tick size, USD per point
    "MNQ": (0.25, 2.0),
    "MES": (0.25, 5.0),
    "MYM": (1.0, 0.5),
    "M2K": (0.1, 5.0),
}


@dataclass
class Days:
    symbol: str
    dates: np.ndarray  # datetime64[D]
    o: np.ndarray  # (days, 390)
    h: np.ndarray
    l: np.ndarray  # noqa: E741
    c: np.ndarray
    v: np.ndarray
    prev_close: np.ndarray  # prior RTH close, same contract, else nan
    on_high: np.ndarray  # overnight high/low/last, nan if missing
    on_low: np.ndarray
    on_last: np.ndarray
    tick: float
    pv: float

    def __len__(self) -> int:
        return len(self.dates)

    def subset(self, mask: np.ndarray) -> Days:
        f = {k: (v[mask] if isinstance(v, np.ndarray) else v) for k, v in self.__dict__.items()}
        return Days(**f)


def _degraded() -> set[date]:
    path = ROOT / "data_public" / "degraded_days.csv"
    with path.open() as fh:
        return {date.fromisoformat(r["date"]) for r in csv.DictReader(fh)}


def load(symbol: str, start: date, end: date, *, holdout_run: bool = False) -> Days:
    if holdout_run:
        if (start, end) != (holdout.HOLDOUT_START, holdout.HOLDOUT_END):
            raise holdout.HoldoutLocked("a holdout run covers exactly the holdout")
    else:
        holdout.guard(start, end)

    frames = [pl.read_parquet(p) for p in sorted((DATA / f"{symbol}.v.0").glob("*.parquet"))]
    df = (
        pl.concat(frames)
        .unique(subset=["ts_event"], keep="last")
        .with_columns(et=pl.col("ts_event").dt.convert_time_zone("America/New_York"))
        .with_columns(
            mod=pl.col("et").dt.hour().cast(pl.Int32) * 60
            + pl.col("et").dt.minute().cast(pl.Int32),
            cal=pl.col("et").dt.date(),
        )
        # Globex session date: bars from 18:00 on belong to the next day.
        .with_columns(
            sess=pl.when(pl.col("mod") >= 18 * 60)
            .then(pl.col("cal") + pl.duration(days=1))
            .otherwise(pl.col("cal"))
        )
        .filter((pl.col("sess") >= start) & (pl.col("sess") < end))
        .sort("ts_event")
    )
    if not holdout_run and df.height and df["sess"].max() >= holdout.HOLDOUT_START:
        raise holdout.HoldoutLocked("research data reaches into the holdout")

    rth = df.filter((pl.col("mod") >= 570) & (pl.col("mod") < 960))
    on = df.filter((pl.col("mod") >= 18 * 60) | (pl.col("mod") < 570))
    on_stats = on.group_by("sess").agg(
        on_high=pl.col("high").max(),
        on_low=pl.col("low").min(),
        on_last=pl.col("close").last(),
        on_ids=pl.col("instrument_id").n_unique(),
    )

    bad = _degraded()
    tick, pv = SPECS[symbol]
    rows = []
    for (sess,), g in rth.group_by(["sess"], maintain_order=True):
        if sess in bad or g["instrument_id"].n_unique() != 1:
            continue
        if g["mod"].max() < 955 or g["mod"].min() > 575 or g.height < 300:
            continue  # half day or badly gapped session
        idx = (g["mod"].to_numpy() - 570).astype(int)
        arr = np.full((5, N_MIN), np.nan)
        for k, col in enumerate(("open", "high", "low", "close", "volume")):
            arr[k, idx] = g[col].to_numpy()
        # forward-fill missing minutes flat at the last close
        c = arr[3]
        last = np.nan
        for i in range(N_MIN):
            if np.isnan(c[i]):
                arr[0, i] = arr[1, i] = arr[2, i] = arr[3, i] = last
                arr[4, i] = 0
            else:
                last = c[i]
        if np.isnan(arr[0, 0]):  # back-fill a missing first minute
            first = int(np.argmax(~np.isnan(arr[3])))
            arr[:4, :first] = arr[0, first]
            arr[4, :first] = 0
        rows.append((sess, int(g["instrument_id"][0]), arr))

    on_map = {r["sess"]: r for r in on_stats.iter_rows(named=True)}
    dates, o, h, l, c, v, pc, onh, onl, onc = ([] for _ in range(10))  # noqa: E741
    prev = None
    for sess, iid, arr in rows:
        dates.append(np.datetime64(sess, "D"))
        for lst, row in zip((o, h, l, c, v), arr, strict=True):
            lst.append(row)
        pc.append(prev[2][3, -1] if prev is not None and prev[1] == iid else np.nan)
        s = on_map.get(sess)
        ok = s is not None and s["on_ids"] == 1
        onh.append(s["on_high"] if ok else np.nan)
        onl.append(s["on_low"] if ok else np.nan)
        onc.append(s["on_last"] if ok else np.nan)
        prev = (sess, iid, arr)

    A = np.array
    return Days(symbol, A(dates), A(o), A(h), A(l), A(c), A(v), A(pc),
                A(onh), A(onl), A(onc), tick, pv)
