"""Order-book imbalance on MNQ/MES (pre-registered 2026-11-02, before any bbo data was bought).

The first test in this project that uses information the 1-minute bars don't
have: how many contracts sit at the best bid vs the best offer. Data is
Databento `bbo-1m` (top of book sampled once a minute), about $3 per symbol for
2019-06 to 2025-10. Microstructure work (Cont, Kukanov & Stoikov 2014, "The
price impact of order book events") finds top-of-book imbalance predicts the
next price moves; whether anything survives at a 15-minute horizon after
micro-contract costs is the open question.

Rule, fixed here:
- Imbalance at a snapshot: (bid size - ask size) / (bid size + ask size).
- Signal at a decision: the mean of the last 5 snapshots stamped at or before
  the decision bar's open.
- Decisions every 15 minutes, 09:45 to 15:30 New York (24 a day). Long if the
  signal is above the 80th percentile of the signal at decision times over the
  previous 60 tradable days, short if below the 20th; else no trade.
- Enter at the decision bar's open; exit at the open 15 minutes later; stop
  0.25 x the 14-day ATR. Fills and costs as screen.simulate (engine rules).
- Two versions:
    1. "deep": the full-size contract's book (NQ for MNQ, ES for MES), which
       carries most of the resting liquidity;
    2. "own": the micro's own book (MNQ for MNQ, MES for MES).

Pass (each version, counting every version tried so far): MNQ mean net R > 0,
day-bootstrap 95% CI of daily R above 0, DSR > 0.95; MES mean net R > 0 with the
matching book. A pass then needs the business bar in strategy-search-3.md.

Also printed: the raw correlation of the signal with the next 15-minute move,
so "no information" can be told from "costs ate it".

Data (on the Mac, then push to moon-ai-data as before):
    uv run moon-ai download --schema bbo-1m --symbols NQ.v.0 MNQ.v.0 ES.v.0 MES.v.0 \
        --start 2019-05-06 --end 2025-11-01 --dry-run    # then without --dry-run
Usage: uv run python scripts/research/book_imbalance.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).parent))

import screen

from moon_ai.backtest.stats import bootstrap_mean_ci, deflated_sharpe, sharpe

BBO = Path("data/bars/GLBX.MDP3/bbo-1m")
DECISIONS = list(range(15, 361, 15))  # minutes after 09:30: 09:45 ... 15:30
HOLD = 15
SNAPS = 5
WINDOW = 60  # tradable days for the percentile cut
LO_Q, HI_Q = 20, 80
PRIOR_VERSIONS = 314  # through periodicity.py
VERSIONS = {
    "deep": {"MNQ.v.0": "NQ.v.0", "MES.v.0": "ES.v.0"},
    "own": {"MNQ.v.0": "MNQ.v.0", "MES.v.0": "MES.v.0"},
}


def book_signal(book_symbol: str, mk: screen.Market) -> np.ndarray:
    """(days, len(DECISIONS)) mean imbalance of the last SNAPS snapshots at or
    before each decision bar's open; nan where there are too few."""
    files = sorted((BBO / book_symbol).glob("*.parquet"))
    if not files:
        raise SystemExit(f"no bbo-1m data for {book_symbol} under {BBO}")
    df = pl.concat([pl.read_parquet(f) for f in files])
    ts = "ts_recv" if "ts_recv" in df.columns else "ts_event"
    df = (
        df.unique(ts)
        .sort(ts)
        .with_columns(pl.col(ts).dt.convert_time_zone("America/New_York").alias("ny"))
        .with_columns(
            pl.col("ny").dt.date().alias("d"),
            # a snapshot stamped exactly at hh:mm is usable for the bar opening at hh:mm
            (
                pl.col("ny").dt.hour().cast(pl.Int32) * 60
                + pl.col("ny").dt.minute().cast(pl.Int32)
                - 570
                + (pl.col("ny").dt.second() + pl.col("ny").dt.nanosecond() > 0).cast(pl.Int32)
            ).alias("m"),
            (
                (pl.col("bid_sz_00") - pl.col("ask_sz_00"))
                / (pl.col("bid_sz_00") + pl.col("ask_sz_00"))
            ).alias("imb"),
        )
        .filter(pl.col("m").is_between(0, screen.RTH_MIN))
    )
    by_day = {
        d: (g["m"].to_numpy(), g["imb"].to_numpy())
        for (d,), g in df.group_by(["d"], maintain_order=True)
    }
    out = np.full((len(mk.days), len(DECISIONS)), np.nan)
    for i, d in enumerate(mk.days):
        if d not in by_day:
            continue
        m, imb = by_day[d]
        for j, dec in enumerate(DECISIONS):
            k = np.searchsorted(m, dec, side="right")  # snapshots with m <= dec
            if k >= SNAPS:
                x = imb[k - SNAPS : k]
                if np.isfinite(x).all():
                    out[i, j] = x.mean()
    return out


def sides(sig: np.ndarray, tradable: np.ndarray) -> np.ndarray:
    """+1/-1/0 from rolling percentiles of earlier days only."""
    out = np.zeros(sig.shape, int)
    rows = [i for i in range(len(sig)) if tradable[i]]
    for n, i in enumerate(rows):
        if n < WINDOW:
            continue
        past = sig[rows[n - WINDOW : n]].ravel()
        past = past[np.isfinite(past)]
        if past.size < WINDOW * len(DECISIONS) // 2:
            continue
        lo, hi = np.percentile(past, [LO_Q, HI_Q])
        s = sig[i]
        out[i] = np.where(np.isfinite(s) & (s > hi), 1, np.where(np.isfinite(s) & (s < lo), -1, 0))
    return out


def run(mk: screen.Market, book_symbol: str):
    sig = book_signal(book_symbol, mk)
    side = sides(sig, mk.tradable)
    fwd = np.full(sig.shape, np.nan)
    for j, dec in enumerate(DECISIONS):
        fwd[:, j] = (mk.o[:, min(dec + HOLD, screen.RTH_MIN - 1)] - mk.o[:, dec]) / mk.atr
    ok = np.isfinite(sig) & np.isfinite(fwd) & mk.tradable[:, None]
    corr = float(np.corrcoef(sig[ok], fwd[ok])[0, 1]) if ok.sum() > 2 else math.nan
    daily = np.zeros(len(mk.days))
    trades = []
    for j, dec in enumerate(DECISIONS):
        r = screen.simulate(
            mk, side[:, j], np.full(len(mk.days), dec), 0.25 * mk.atr, None, dec + HOLD - 1
        )
        trades.append(r[~np.isnan(r)])
        daily += np.nan_to_num(r, nan=0.0)
    return corr, int(ok.sum()), np.concatenate(trades), daily


def main() -> int:
    mnq, mes = screen.load("MNQ.v.0"), screen.load("MES.v.0")
    print(f"MNQ {len(mnq.days)} days ({mnq.days[0]} to {mnq.days[-1]}), MES {len(mes.days)} days")
    n_trials = PRIOR_VERSIONS + len(VERSIONS)
    res = {v: (run(mnq, b["MNQ.v.0"]), run(mes, b["MES.v.0"])) for v, b in VERSIONS.items()}
    srs = [sharpe(r[0][3]) for r in res.values()]
    var_sr = max(float(np.var(srs)), 1e-4)
    for v, ((c1, k1, x1, d1), (c2, _, x2, _)) in res.items():
        lo, hi = bootstrap_mean_ci(d1)
        dsr = deflated_sharpe(d1, n_trials, var_sr)
        ok = x1.size and x1.mean() > 0 and lo > 0 and dsr > 0.95 and x2.size and x2.mean() > 0
        print(
            f"{v}: corr MNQ {c1:+.4f} (n={k1}) MES {c2:+.4f} | MNQ {x1.size} trades "
            f"{x1.mean():+.4f}R/trade, daily-R CI [{lo:+.3f}, {hi:+.3f}], "
            f"Sharpe/yr {sharpe(d1) * math.sqrt(252):+.2f}, DSR {dsr:.3f} | "
            f"MES {x2.size} trades {x2.mean():+.4f}R/trade -> {'PASS' if ok else 'fail'}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
