"""Fast screening of simple intraday rules on research data (strategy search).

The event engine takes minutes per run; this screens hundreds of rule variants
in seconds, so the search can be broad. It is a filter, not a verdict:

- research data only (it refuses dates past the locked holdout);
- every variant screened is counted, and the luck test (DSR) for any survivor
  counts all of them plus every version tested before;
- a survivor must also make money on the other market (MES);
- survivors are then pre-registered as setups and go through the full engine,
  the prop-firm replay, one holdout look and paper trading.

Fills follow the engine's broker (config.BrokerConfig): market entry at the
next bar's open plus entry slippage; a stop fills at the stop (or the open if
it gaps through) minus stop slippage, and a stop touched on the entry bar
counts; a target needs a one-tick trade-through and can't fill on the entry
bar; stop first when both are touched in one bar; time exit at the open of
the bar after the time-out bar plus slippage; commission on both sides.

Usage: uv run python scripts/research/screen.py [--out data/screen]
"""

from __future__ import annotations

import argparse
import csv
import itertools
import math
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import polars as pl

from moon_ai.backtest.stats import deflated_sharpe, sharpe
from moon_ai.config import load_config
from moon_ai.holdout import HOLDOUT_START

STORE = Path("data/bars/GLBX.MDP3/ohlcv-1m")
START = date(2019, 6, 1)
RTH_MIN = 390  # 09:30-16:00
TIMEOUT_IDX = 385  # the 15:55 bar: the engine's usual time-out
PRIOR_TESTED = 102  # versions tested through the engine before this screen


@dataclass
class Market:
    symbol: str
    days: list[date]
    o: np.ndarray  # (days, 390)
    h: np.ndarray
    lo: np.ndarray
    c: np.ndarray
    prev_close: np.ndarray  # previous day's cash close
    prev_high: np.ndarray
    prev_low: np.ndarray
    on_high: np.ndarray  # overnight 18:00-09:30
    on_low: np.ndarray
    atr: np.ndarray  # 14-day ATR of the cash session, finished days only
    tradable: np.ndarray  # bool: no roll, full session, warm ATR
    tick: float
    point_value: float


def load(symbol: str) -> Market:
    files = sorted((STORE / symbol).glob("*.parquet"))
    df = pl.concat([pl.read_parquet(f) for f in files]).unique("ts_event").sort("ts_event")
    df = df.with_columns(pl.col("ts_event").dt.convert_time_zone("America/New_York").alias("ny"))
    df = df.with_columns(
        pl.when(pl.col("ny").dt.hour() >= 18)
        .then(pl.col("ny").dt.date() + pl.duration(days=1))
        .otherwise(pl.col("ny").dt.date())
        .alias("tday"),
        (
            pl.col("ny").dt.hour().cast(pl.Int32) * 60
            + pl.col("ny").dt.minute().cast(pl.Int32)
            - 570
        ).alias("m"),
    )
    df = df.filter(pl.col("tday") >= START, pl.col("tday") < HOLDOUT_START)
    cfg = load_config()
    spec = cfg.instrument(symbol)
    rth = df.filter((pl.col("m") >= 0) & (pl.col("m") < RTH_MIN))
    on = df.filter(pl.col("m") < 0)
    on_hl = on.group_by("tday").agg(pl.col("high").max(), pl.col("low").min())
    on_map = {r[0]: (r[1], r[2]) for r in on_hl.iter_rows()}
    days, opens, highs, lows, closes, inst = [], [], [], [], [], []
    for (d,), g in rth.group_by(["tday"], maintain_order=True):
        if g.height < 380:
            continue  # half days and broken sessions
        idx = g["m"].to_numpy()
        arr = {}
        for col in ("open", "high", "low", "close"):
            a = np.full(RTH_MIN, np.nan)
            a[idx] = g[col].to_numpy()
            arr[col] = a
        # forward-fill missing minutes from the last close
        last = arr["open"][0] if not np.isnan(arr["open"][0]) else np.nan
        for i in range(RTH_MIN):
            if np.isnan(arr["open"][i]):
                for col in ("open", "high", "low", "close"):
                    arr[col][i] = last
            last = arr["close"][i]
        if np.isnan(arr["open"]).any():
            continue
        days.append(d)
        opens.append(arr["open"])
        highs.append(arr["high"])
        lows.append(arr["low"])
        closes.append(arr["close"])
        inst.append(g["instrument_id"][0])
    o_, h_, l_, c_ = (np.array(x) for x in (opens, highs, lows, closes))
    n = len(days)
    dh, dl, dc = h_.max(1), l_.min(1), c_[:, -1]
    inst = np.array(inst)
    prev_close = np.r_[np.nan, dc[:-1]]
    prev_high = np.r_[np.nan, dh[:-1]]
    prev_low = np.r_[np.nan, dl[:-1]]
    same = np.r_[False, inst[1:] == inst[:-1]]
    tr = np.where(
        same,
        np.maximum(dh, np.r_[np.nan, dc[:-1]]) - np.minimum(dl, np.r_[np.nan, dc[:-1]]),
        dh - dl,
    )
    atr = np.full(n, np.nan)
    for i in range(15, n):
        atr[i] = np.nanmean(tr[i - 14 : i])  # finished days only
    on_high = np.array([on_map.get(d, (np.nan, np.nan))[0] for d in days])
    on_low = np.array([on_map.get(d, (np.nan, np.nan))[1] for d in days])
    tradable = same & ~np.isnan(atr) & ~np.isnan(prev_close)
    return Market(
        symbol,
        days,
        o_,
        h_,
        l_,
        c_,
        prev_close,
        prev_high,
        prev_low,
        on_high,
        on_low,
        atr,
        tradable,
        spec.tick_size,
        spec.point_value,
    )


def simulate(
    mk: Market,
    side: np.ndarray,  # +1 long, -1 short, 0 none, per day
    entry: np.ndarray,  # bar index whose OPEN is the entry (decision at the bar before)
    stop_dist: np.ndarray,  # points from the raw entry price
    target_r: float | None = None,
    exit_idx: int = TIMEOUT_IDX,
) -> np.ndarray:
    """Net R per day (nan where no trade)."""
    b = load_config().broker
    tick, pv = mk.tick, mk.point_value
    e_slip, s_slip = b.entry_slippage_ticks * tick, b.stop_slippage_ticks * tick
    comm = 2 * b.commission_per_contract
    out = np.full(len(mk.days), np.nan)
    for i in np.nonzero(side)[0]:
        if not mk.tradable[i]:
            continue
        s, e, dist = int(side[i]), int(entry[i]), float(stop_dist[i])
        if not (0 < e <= exit_idx) or not dist > 0:
            continue
        px = mk.o[i, e] + s * e_slip
        risk = dist * pv
        stop = px - s * dist
        tgt = px + s * target_r * dist if target_r else None
        exit_px = None
        for j in range(e, exit_idx + 1):
            o, hi, lo = mk.o[i, j], mk.h[i, j], mk.lo[i, j]
            if s > 0:
                if j > e and o <= stop:
                    exit_px = o - s_slip
                    break
                if lo <= stop:
                    exit_px = stop - s_slip
                    break
                if tgt is not None and j > e and hi >= tgt + tick:
                    exit_px = o if o >= tgt else tgt
                    break
            else:
                if j > e and o >= stop:
                    exit_px = o + s_slip
                    break
                if hi >= stop:
                    exit_px = stop + s_slip
                    break
                if tgt is not None and j > e and lo <= tgt - tick:
                    exit_px = o if o <= tgt else tgt
                    break
        if exit_px is None:
            nxt = min(exit_idx + 1, RTH_MIN - 1)
            exit_px = mk.o[i, nxt] - s * e_slip
        out[i] = (s * (exit_px - px) * pv - comm) / risk
    return out


# --- rule templates: each returns (side, entry index, stop distance) per day -------------


def _first_cross(level: np.ndarray, series: np.ndarray, above: bool, start: int, end: int):
    """Index of the first close beyond `level` in [start, end), or -1."""
    seg = series[:, start:end]
    hit = seg > level[:, None] if above else seg < level[:, None]
    first = np.where(hit.any(1), hit.argmax(1) + start, -1)
    return first


def t_time_momentum(mk: Market, m: int, theta: float, k: float):
    """At minute m, trade the direction of the move from the open if it exceeds theta ATR."""
    move = mk.c[:, m - 1] - mk.o[:, 0]
    side = np.where(np.abs(move) > theta * mk.atr, np.sign(move), 0)
    return side, np.full(len(side), m), k * mk.atr


def t_gap_go(mk: Market, theta: float, k: float):
    """Trade in the gap's direction at 09:31 when the gap exceeds theta ATR."""
    gap = mk.o[:, 0] - mk.prev_close
    side = np.where(np.abs(gap) > theta * mk.atr, np.sign(gap), 0)
    return side, np.full(len(side), 1), k * mk.atr


def t_prev_day_breakout(mk: Market, k: float, cutoff: int):
    """First close beyond the previous day's high (long) or low (short) before `cutoff`."""
    up = _first_cross(mk.prev_high, mk.c, True, 0, cutoff)
    dn = _first_cross(mk.prev_low, mk.c, False, 0, cutoff)
    side = np.zeros(len(up))
    entry = np.zeros(len(up), int)
    for i in range(len(up)):
        cands = [(up[i], 1), (dn[i], -1)]
        cands = [x for x in cands if x[0] >= 0]
        if cands:
            j, s = min(cands)
            side[i], entry[i] = s, j + 1
    return side, entry, k * mk.atr


def t_on_breakout(mk: Market, k: float, cutoff: int):
    """First close beyond the overnight high or low before `cutoff` (wider stops)."""
    up = _first_cross(mk.on_high, mk.c, True, 0, cutoff)
    dn = _first_cross(mk.on_low, mk.c, False, 0, cutoff)
    side = np.zeros(len(up))
    entry = np.zeros(len(up), int)
    for i in range(len(up)):
        cands = [x for x in ((up[i], 1), (dn[i], -1)) if x[0] >= 0]
        if cands:
            j, s = min(cands)
            side[i], entry[i] = s, j + 1
    return side, entry, k * mk.atr


def t_range_expansion(mk: Market, first: int, squeeze: float, k: float):
    """If the first `first` minutes' range is under `squeeze` ATR, trade the first
    close beyond that range afterwards (until 14:00)."""
    rng_hi = mk.h[:, :first].max(1)
    rng_lo = mk.lo[:, :first].min(1)
    tight = (rng_hi - rng_lo) < squeeze * mk.atr
    up = _first_cross(rng_hi, mk.c, True, first, 270)
    dn = _first_cross(rng_lo, mk.c, False, first, 270)
    side = np.zeros(len(up))
    entry = np.zeros(len(up), int)
    for i in np.nonzero(tight)[0]:
        cands = [x for x in ((up[i], 1), (dn[i], -1)) if x[0] >= 0]
        if cands:
            j, s = min(cands)
            side[i], entry[i] = s, j + 1
    return side, entry, k * mk.atr


def t_prev_day_trend(mk: Market, theta: float, k: float, follow: bool):
    """At 09:31, trade with (follow) or against yesterday's cash-session move if it
    exceeded theta ATR."""
    prev_open = np.r_[np.nan, mk.o[:-1, 0]]
    move = mk.prev_close - prev_open
    s = np.sign(move) * (1 if follow else -1)
    side = np.where(np.abs(move) > theta * mk.atr, s, 0)
    return side, np.full(len(side), 1), k * mk.atr


def variants():
    for m, theta, k in itertools.product(
        (15, 30, 60, 120, 180), (0.0, 0.25, 0.5), (0.25, 0.5, 1.0)
    ):
        for tr in (None, 2.0):
            yield f"time_mom m={m} th={theta} k={k} t={tr}", (t_time_momentum, (m, theta, k)), tr
    for theta, k in itertools.product((0.1, 0.25, 0.5), (0.25, 0.5, 1.0)):
        for tr in (None, 2.0):
            yield f"gap_go th={theta} k={k} t={tr}", (t_gap_go, (theta, k)), tr
    for k, cut in itertools.product((0.25, 0.5, 1.0), (60, 150, 270)):
        for tr in (None, 2.0):
            yield f"pdh_pdl k={k} cut={cut} t={tr}", (t_prev_day_breakout, (k, cut)), tr
            yield f"on_break k={k} cut={cut} t={tr}", (t_on_breakout, (k, cut)), tr
    for first, sq, k in itertools.product((30, 60), (0.3, 0.5), (0.25, 0.5)):
        for tr in (None, 2.0):
            yield (
                f"range_exp first={first} sq={sq} k={k} t={tr}",
                (t_range_expansion, (first, sq, k)),
                tr,
            )
    for theta, k, follow in itertools.product((0.0, 0.5), (0.25, 0.5, 1.0), (True, False)):
        yield (
            f"prev_trend th={theta} k={k} follow={follow}",
            (t_prev_day_trend, (theta, k, follow)),
            None,
        )


def daily_series(r: np.ndarray) -> np.ndarray:
    return np.nan_to_num(r, nan=0.0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("data/screen"))
    args = ap.parse_args()
    mnq, mes = load("MNQ.v.0"), load("MES.v.0")
    print(f"MNQ {len(mnq.days)} days, MES {len(mes.days)} days ({mnq.days[0]} to {mnq.days[-1]})")
    rows = []
    for name, (fn, params), tr in variants():
        res = {}
        for mk in (mnq, mes):
            side, entry, dist = fn(mk, *params)
            r = simulate(mk, side, entry, dist, tr)
            x = r[~np.isnan(r)]
            d = daily_series(r)
            res[mk.symbol] = (len(x), float(x.mean()) if len(x) else math.nan, sharpe(d), d, x)
        rows.append((name, res))
    n_trials = len(rows) + PRIOR_TESTED
    srs = [res["MNQ.v.0"][2] for _, res in rows]
    var_sr = float(np.var(srs, ddof=1))
    args.out.mkdir(parents=True, exist_ok=True)
    out = []
    for name, res in rows:
        n, mean, sr, d, x = res["MNQ.v.0"]
        n2, mean2, sr2, _, _ = res["MES.v.0"]
        dsr = deflated_sharpe(d, n_trials, var_sr)
        out.append(
            {
                "variant": name,
                "mnq_trades": n,
                "mnq_mean_r": round(mean, 4),
                "mnq_sharpe_yr": round(sr * math.sqrt(252), 2),
                "mnq_dsr": round(dsr, 3),
                "mes_trades": n2,
                "mes_mean_r": round(mean2, 4),
                "mes_sharpe_yr": round(sr2 * math.sqrt(252), 2),
            }
        )
    out.sort(key=lambda r: -r["mnq_dsr"])
    with (args.out / "screen.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print(
        f"{len(rows)} variants screened; DSR counts {n_trials} versions (SR variance {var_sr:.5f})"
    )
    print("top 15 by MNQ DSR:")
    for r in out[:15]:
        print(
            f"  {r['variant']:<42} MNQ {r['mnq_trades']:5} {r['mnq_mean_r']:+.3f}R "
            f"S={r['mnq_sharpe_yr']:+.2f} DSR={r['mnq_dsr']:.3f} | MES {r['mes_trades']:5} "
            f"{r['mes_mean_r']:+.3f}R S={r['mes_sharpe_yr']:+.2f}"
        )
    surv = [r for r in out if r["mnq_dsr"] > 0.95 and r["mes_mean_r"] > 0]
    print(f"survivors (MNQ DSR > 0.95 and MES mean > 0): {len(surv)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())


@dataclass
class Detail:
    """Per day (nan where no trade), per contract, in USD unless noted."""

    r: np.ndarray
    pnl: np.ndarray  # net of commission and slippage
    risk: np.ndarray  # entry fill to stop
    worst: np.ndarray  # worst open P&L (net of commission), <= 0
    best: np.ndarray
    entry_min: np.ndarray  # minutes after 09:30
    exit_min: np.ndarray


def simulate_detail(
    mk: Market,
    side: np.ndarray,
    entry: np.ndarray,
    stop_dist: np.ndarray,
    target_r: float | None = None,
    exit_idx: int = TIMEOUT_IDX,
) -> Detail:
    """`simulate`, keeping each trade's dollars and open-P&L extremes for the prop replay."""
    b = load_config().broker
    tick, pv = mk.tick, mk.point_value
    e_slip, s_slip = b.entry_slippage_ticks * tick, b.stop_slippage_ticks * tick
    comm = 2 * b.commission_per_contract
    n = len(mk.days)
    d = Detail(*(np.full(n, np.nan) for _ in range(7)))
    for i in np.nonzero(side)[0]:
        if not mk.tradable[i]:
            continue
        s, e, dist = int(side[i]), int(entry[i]), float(stop_dist[i])
        if not (0 < e <= exit_idx) or not dist > 0:
            continue
        px = mk.o[i, e] + s * e_slip
        stop = px - s * dist
        tgt = px + s * target_r * dist if target_r else None
        exit_px, j_exit = None, exit_idx + 1
        lo_seen, hi_seen = px, px
        for j in range(e, exit_idx + 1):
            o, hi, lo = mk.o[i, j], mk.h[i, j], mk.lo[i, j]
            if s > 0:
                if j > e and o <= stop:
                    exit_px, j_exit = o - s_slip, j
                    lo_seen = min(lo_seen, o)
                    break
                if lo <= stop:
                    exit_px, j_exit = stop - s_slip, j
                    lo_seen = min(lo_seen, stop)
                    break
                if tgt is not None and j > e and hi >= tgt + tick:
                    exit_px, j_exit = (o if o >= tgt else tgt), j
                    hi_seen = max(hi_seen, tgt)
                    break
            else:
                if j > e and o >= stop:
                    exit_px, j_exit = o + s_slip, j
                    hi_seen = max(hi_seen, o)
                    break
                if hi >= stop:
                    exit_px, j_exit = stop + s_slip, j
                    hi_seen = max(hi_seen, stop)
                    break
                if tgt is not None and j > e and lo <= tgt - tick:
                    exit_px, j_exit = (o if o <= tgt else tgt), j
                    lo_seen = min(lo_seen, tgt)
                    break
            lo_seen, hi_seen = min(lo_seen, lo), max(hi_seen, hi)
        if exit_px is None:
            nxt = min(exit_idx + 1, RTH_MIN - 1)
            exit_px = mk.o[i, nxt] - s * e_slip
        pnl = s * (exit_px - px) * pv - comm
        adverse = (lo_seen - px) if s > 0 else (px - hi_seen)
        favour = (hi_seen - px) if s > 0 else (px - lo_seen)
        d.r[i] = pnl / (dist * pv)
        d.pnl[i] = pnl
        d.risk[i] = dist * pv
        d.worst[i] = min(adverse * pv - comm, pnl, 0.0)
        d.best[i] = max(favour * pv - comm, pnl, 0.0)
        d.entry_min[i], d.exit_min[i] = e, j_exit
    return d
