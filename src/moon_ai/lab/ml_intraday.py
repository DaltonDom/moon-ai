"""Intraday ML: predict the forward return at fixed decision minutes.

Decision at minute t uses only bars that closed before t (index <= t-1); the
trade fills at the open of minute t. Walk-forward by calendar year: the model
for year Y is trained only on years before Y.
"""

from __future__ import annotations

import numpy as np

from moon_ai.lab.data import m


def _ret(C, t, k):
    return np.log(C[:, t - 1] / C[:, t - 1 - k])


def build(grids, main: str, times, horizon, atr):
    """Feature matrix for every (day, decision time). Returns X, y, day_idx, t_idx, names."""
    g = grids[main]
    n = len(g.days)
    a930 = m(9, 30)
    rows, ys, di, ti = [], [], [], []
    names = None
    # previous day's RTH stats
    c_close = g.C[:, m(16, 0) - 1]
    prev_c = np.r_[np.nan, c_close[:-1]]
    for t in times:
        f = {}
        for sym, gg in grids.items():
            C = gg.C
            for k in (1, 5, 15, 30, 60, 120):
                if t - 1 - k >= 0:
                    f[f"{sym}_r{k}"] = _ret(C, t, k) * 1e4
            if t > a930:
                f[f"{sym}_r_open"] = np.log(C[:, t - 1] / gg.O[:, a930]) * 1e4
            pcs = np.r_[np.nan, gg.C[:-1, m(16, 0) - 1]]
            f[f"{sym}_r_prevclose"] = np.log(C[:, t - 1] / pcs) * 1e4
        C, H, L, V = g.C, g.H, g.L, g.V
        start = a930 if t > a930 + 5 else 0
        hi = np.nanmax(H[:, start:t], 1)
        lo = np.nanmin(L[:, start:t], 1)
        f["pos_in_range"] = (C[:, t - 1] - lo) / np.maximum(hi - lo, 1e-9)
        f["range_atr"] = (hi - lo) / atr
        vw = np.nansum(C[:, start:t] * V[:, start:t], 1) / np.maximum(np.nansum(V[:, start:t], 1), 1)
        f["vwap_dist"] = (C[:, t - 1] - vw) / atr
        f["vol30"] = np.nanstd(np.diff(np.log(C[:, max(t - 31, 0):t]), axis=1), 1) * 1e4
        f["volu30"] = np.nansum(V[:, max(t - 30, 0):t], 1)
        f["on_ret"] = np.log(C[:, a930 - 1] / prev_c) * 1e4 if t > a930 else np.full(n, np.nan)
        f["atr_pct"] = atr / C[:, t - 1] * 1e4
        f["tod"] = np.full(n, t)
        f["dow"] = g.days.astype("datetime64[D]").view("int64") % 7
        X = np.column_stack(list(f.values()))
        if names is None:
            names = list(f.keys())
        y = np.log(g.O[:, min(t + horizon, g.O.shape[1] - 1)] / g.O[:, t]) * 1e4
        rows.append(X); ys.append(y); di.append(np.arange(n)); ti.append(np.full(n, t))
    X = np.vstack(rows); y = np.concatenate(ys); di = np.concatenate(di); ti = np.concatenate(ti)
    # normalise volume feature per time-of-day by trailing mean (causal: use rolling over days)
    return X, y, di, ti, names
