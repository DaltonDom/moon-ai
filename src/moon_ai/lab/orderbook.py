"""Order-book feasibility tests on Databento bbo-1s (top of book sampled each second).

Signals use the snapshot at second t; a market order then fills at the *next*
second's ask (buy) or bid (sell), i.e. it pays the spread and one second of
latency. Exits also cross the spread. NQ mini: $20/point, commission assumed
$5.00 a round trip (conservative).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

NQ_PV = 20.0
COMM_RT = 5.0


def load_bbo(path: str) -> pd.DataFrame:
    import databento as db
    df = db.DBNStore.from_file(path).to_df()
    df = df[["bid_px_00", "ask_px_00", "bid_sz_00", "ask_sz_00", "price", "size", "side"]]
    df.index = df.index.tz_convert("America/New_York")
    df = df[(df.bid_px_00 > 0) & (df.ask_px_00 > df.bid_px_00)]
    return df


def imbalance_test(df: pd.DataFrame, horizons=(5, 15, 60, 300), thresholds=(0.5, 0.7, 0.9),
                   rth_only=True) -> pd.DataFrame:
    if rth_only:
        t = df.index.hour * 60 + df.index.minute
        df = df[(t >= 9 * 60 + 30) & (t < 16 * 60)]
    bid = df.bid_px_00.to_numpy(); ask = df.ask_px_00.to_numpy()
    bs = df.bid_sz_00.to_numpy().astype(float); az = df.ask_sz_00.to_numpy().astype(float)
    imb = (bs - az) / (bs + az)
    mid = (bid + ask) / 2
    rows = []
    for h in horizons:
        if len(mid) <= h + 1:
            continue
        fwd = mid[1 + h:] - mid[1:-h]  # from the next second's mid, h seconds on
        x = imb[: len(fwd)]
        ic = np.corrcoef(x, fwd)[0, 1]
        for th in thresholds:
            longs = x > th
            shorts = x < -th
            # buy at next ask, sell at bid h seconds later (and mirror for shorts)
            pl_long = bid[1 + h:][longs] - ask[1:-h][longs]
            pl_short = bid[1:-h][shorts] - ask[1 + h:][shorts]
            pts = np.r_[pl_long, pl_short]
            rows.append({"h_s": h, "thr": th, "ic": ic, "n": len(pts),
                         "gross_pts": float(np.mean(np.r_[fwd[longs], -fwd[shorts]])) if len(pts) else np.nan,
                         "net_$": float(np.mean(pts) * NQ_PV - COMM_RT) if len(pts) else np.nan})
    return pd.DataFrame(rows)
