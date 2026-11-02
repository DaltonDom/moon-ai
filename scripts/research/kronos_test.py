"""Zero-shot test of the Kronos forecasting model on MNQ/MES (pre-registered 2026-11-02).

Kronos (Shi et al., AAAI 2026; github.com/shiyu-coder/Kronos, MIT) is a
foundation model pre-trained on candlestick data from 45 exchanges. Its paper
reports forecasting metrics only; no out-of-sample trading result after costs
exists (docs/research/strategy-search-3.md). This tests it as a trading
signal with no tuning at all, so it adds one version to the luck count per
decision time, not a search.

Rule, fixed before any run:
- Bars: 5-minute OHLCV over the whole Globex session.
- Decision at 10:30 and 13:00 New York on tradable days. Context: the 400
  5-minute bars before the decision (about 33 hours). Forecast 12 bars (60 min),
  5 samples, T=1.0, top_p=0.9, averaged.
- Trade the sign of (forecast close at +60 min) - (last close), at the next
  1-minute bar's open. Stop 0.25 x the 14-day ATR; exit after 60 minutes.
  Costs and fills as screen.simulate (the engine's broker rules).
- Pass bar (per decision time, counting every version tried so far): MNQ mean
  net R > 0 with day-bootstrap 95% CI above 0 and DSR > 0.95; MES mean > 0;
  directional accuracy reported against the 50% coin.

Forecasts are saved to data/kronos/<symbol>.csv, so any later threshold or
sizing idea is a cheap walk-forward on the saved file (and counts as a trial).

Setup (on the Mac; needs huggingface.co):
    git clone https://github.com/shiyu-coder/Kronos ../Kronos
    uv pip install torch einops huggingface_hub safetensors
    uv run python scripts/research/kronos_test.py --kronos-dir ../Kronos [--model small]

Kronos-small on a CPU takes a few hours for both markets; --limit N runs the
first N days only, for a smoke test.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from datetime import time
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl

sys.path.insert(0, str(Path(__file__).parent))

import screen

from moon_ai.backtest.stats import bootstrap_mean_ci, deflated_sharpe, sharpe

DECISIONS = (time(10, 30), time(13, 0))
LOOKBACK, PRED_LEN, SAMPLES = 400, 12, 5
PRIOR_VERSIONS = 314  # through periodicity.py
MODELS = {
    "mini": ("NeoQuasar/Kronos-mini", "NeoQuasar/Kronos-Tokenizer-2k", 2048),
    "small": ("NeoQuasar/Kronos-small", "NeoQuasar/Kronos-Tokenizer-base", 512),
    "base": ("NeoQuasar/Kronos-base", "NeoQuasar/Kronos-Tokenizer-base", 512),
}


def five_minute(symbol: str) -> pd.DataFrame:
    files = sorted((screen.STORE / symbol).glob("*.parquet"))
    df = pl.concat([pl.read_parquet(f) for f in files]).unique("ts_event").sort("ts_event")
    df = df.with_columns(pl.col("ts_event").dt.convert_time_zone("America/New_York").alias("ny"))
    bars = (
        df.group_by_dynamic("ny", every="5m", closed="left", label="left")
        .agg(
            pl.col("open").first(),
            pl.col("high").max(),
            pl.col("low").min(),
            pl.col("close").last(),
            pl.col("volume").sum(),
        )
        .with_columns((pl.col("close") * pl.col("volume")).alias("amount"))
    )
    return bars.to_pandas().set_index("ny")


def forecasts(mk: screen.Market, bars: pd.DataFrame, predictor, limit: int | None):
    """One row per (day, decision): the forecast move in ATR units, or nan."""
    rows = []
    days = mk.days[:limit] if limit else mk.days
    for i, d in enumerate(days):
        if not mk.tradable[i]:
            continue
        for dt in DECISIONS:
            ts = pd.Timestamp.combine(d, dt).tz_localize("America/New_York")
            hist = bars.loc[: ts - pd.Timedelta(minutes=5)].tail(LOOKBACK)
            if len(hist) < LOOKBACK:
                continue
            x_ts = pd.Series(hist.index.tz_localize(None))
            y_ts = pd.Series(pd.date_range(ts.tz_localize(None), periods=PRED_LEN, freq="5min"))
            preds = [
                predictor.predict(
                    df=hist[["open", "high", "low", "close", "volume", "amount"]].reset_index(
                        drop=True
                    ),
                    x_timestamp=x_ts,
                    y_timestamp=y_ts,
                    pred_len=PRED_LEN,
                    T=1.0,
                    top_p=0.9,
                    sample_count=SAMPLES,
                )
            ]
            move = float(preds[0]["close"].iloc[-1] - hist["close"].iloc[-1])
            rows.append((i, dt, move / mk.atr[i]))
        if i % 50 == 0:
            print(f"  {mk.symbol} {d} ({i}/{len(days)})", flush=True)
    return rows


def evaluate(mk: screen.Market, rows, dt: time):
    idx = dt.hour * 60 + dt.minute - 570
    side = np.zeros(len(mk.days), int)
    for i, t, m in rows:
        if t == dt and not math.isnan(m) and m != 0:
            side[i] = int(np.sign(m))
    r = screen.simulate(mk, side, np.full(len(side), idx), 0.25 * mk.atr, None, idx + 59)
    after = np.array(
        [
            mk.c[i, min(idx + 59, screen.RTH_MIN - 1)] - mk.o[i, idx] if side[i] else np.nan
            for i in range(len(side))
        ]
    )
    hit = np.sign(after[side != 0]) == side[side != 0]
    return r, float(hit.mean()) if hit.size else math.nan


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kronos-dir", type=Path, required=True)
    ap.add_argument("--model", choices=sorted(MODELS), default="small")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--out", type=Path, default=Path("data/kronos"))
    args = ap.parse_args()
    sys.path.insert(0, str(args.kronos_dir.resolve()))
    from model import Kronos, KronosPredictor, KronosTokenizer  # type: ignore[import-not-found]

    name, tok, ctx = MODELS[args.model]
    predictor = KronosPredictor(
        Kronos.from_pretrained(name),
        KronosTokenizer.from_pretrained(tok),
        device=args.device,
        max_context=ctx,
    )
    args.out.mkdir(parents=True, exist_ok=True)
    results = {}
    for sym in ("MNQ.v.0", "MES.v.0"):
        mk = screen.load(sym)
        rows = forecasts(mk, five_minute(sym), predictor, args.limit)
        with (args.out / f"{sym}.{args.model}.csv").open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["day", "decision", "forecast_move_atr"])
            w.writerows((mk.days[i], t, m) for i, t, m in rows)
        results[sym] = (mk, rows)
    n_trials = PRIOR_VERSIONS + len(DECISIONS)
    for dt in DECISIONS:
        r1, acc1 = evaluate(*results["MNQ.v.0"], dt)
        r2, acc2 = evaluate(*results["MES.v.0"], dt)
        x1, x2 = r1[~np.isnan(r1)], r2[~np.isnan(r2)]
        d1 = np.nan_to_num(r1, nan=0.0)
        lo, hi = bootstrap_mean_ci(d1)
        dsr = deflated_sharpe(d1, n_trials, 0.002)
        ok = x1.size and x1.mean() > 0 and lo > 0 and dsr > 0.95 and x2.mean() > 0
        print(
            f"{dt:%H:%M}: MNQ {x1.size} trades {x1.mean():+.4f}R, hit {acc1:.1%}, "
            f"daily CI [{lo:+.3f}, {hi:+.3f}], Sharpe/yr {sharpe(d1) * math.sqrt(252):+.2f}, "
            f"DSR {dsr:.3f} | MES {x2.mean():+.4f}R hit {acc2:.1%} -> "
            f"{'PASS' if ok else 'fail'}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
