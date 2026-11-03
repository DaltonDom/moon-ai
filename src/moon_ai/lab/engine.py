"""Fast bracket-trade simulation on day grids (numba).

One trade per day per call. A trade enters at the *open* of minute `ent` (the
signal must use only bars that closed before `ent`), with a protective stop and
a target given as point distances from the fill, and a time exit at the open of
minute `ext`. Costs follow design.md "Backtest realism".

Returns per-day $ P&L for one micro contract and the worst open P&L ($, <= 0)
seen during the trade, both net of costs.
"""

from __future__ import annotations

import numpy as np
from numba import njit

COMM_RT = 2.0  # $ per micro round trip


@njit(cache=True)
def bracket(O, H, L, C, ent, side, stop_d, tgt_d, ext, tick, pv, slip_in, slip_stop, slip_out):
    n = O.shape[0]
    pnl = np.zeros(n)
    mae = np.zeros(n)
    exit_min = np.full(n, -1, np.int64)
    for d in range(n):
        e = ent[d]
        if e < 0 or side[d] == 0:
            continue
        s = side[d]
        px = O[d, e]
        if np.isnan(px):
            continue
        fill = px + s * slip_in * tick
        stop = fill - s * stop_d[d] if stop_d[d] > 0 else np.nan
        tgt = fill + s * tgt_d[d] if tgt_d[d] > 0 else np.nan
        x = ext[d]
        out = np.nan
        worst = 0.0
        for t in range(e, x):
            h = H[d, t]
            lo = L[d, t]
            if np.isnan(h):
                continue
            adverse = (lo - fill) if s > 0 else (fill - h)
            if adverse < worst:
                worst = adverse
            if not np.isnan(stop):
                if (s > 0 and lo <= stop) or (s < 0 and h >= stop):
                    # gap through the stop fills at the open
                    o = O[d, t]
                    base = stop
                    if (s > 0 and o < stop) or (s < 0 and o > stop):
                        base = o
                    out = base - s * slip_stop * tick
                    exit_min[d] = t
                    break
            if not np.isnan(tgt) and t > e:
                if (s > 0 and h >= tgt + tick) or (s < 0 and lo <= tgt - tick):
                    out = tgt
                    exit_min[d] = t
                    break
        if np.isnan(out):
            px2 = O[d, x] if x < O.shape[1] else C[d, x - 1]
            if np.isnan(px2):
                px2 = C[d, x - 1]
            out = px2 - s * slip_out * tick
            exit_min[d] = x
        r = s * (out - fill)
        pnl[d] = r * pv - COMM_RT
        w = worst * pv - COMM_RT - slip_stop * tick * pv
        mae[d] = w if w < pnl[d] else pnl[d]
    return pnl, mae, exit_min


def run(g, ent, side, stop_d, tgt_d, ext, slip_mult=1.0):
    ent = np.asarray(ent, np.int64)
    ent = np.where(g.tradable, ent, -1)
    n = len(g.days)
    def arr(x, dt):
        a = np.asarray(x, dt)
        return np.full(n, a) if a.ndim == 0 else a
    return bracket(g.O, g.H, g.L, g.C, ent, arr(side, np.int64), arr(stop_d, np.float64),
                   arr(tgt_d, np.float64), arr(ext, np.int64), g.tick, g.point_value,
                   1.0 * slip_mult, 3.0 * slip_mult, 1.0 * slip_mult)


def sharpe(x):
    x = np.asarray(x)
    sd = x.std()
    return x.mean() / sd if sd > 0 else 0.0
