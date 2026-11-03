"""Build and cache the full candidate-stream library: every family x params x symbol."""

from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np

from moon_ai.lab import families
from moon_ai.lab.data import CACHE, load

SYMBOLS = ["MNQ", "MES", "MYM", "M2K", "MGC", "MCL", "M6E"]


def build(symbols=SYMBOLS, slip_mult=1.0, refresh=False):
    path = CACHE / f"library_s{slip_mult}.pkl"
    if path.exists() and not refresh:
        return pickle.loads(path.read_bytes())
    # common calendar = union of MNQ days (longest history)
    base = load("MNQ")
    days = base.days
    streams = []
    import moon_ai.lab.engine as E
    for sym in symbols:
        g = load(sym)
        pos = np.searchsorted(days, g.days)
        old_run = families.run
        families.run = lambda *a, **k: E.run(*a, slip_mult=slip_mult, **k)
        for fam in families.ALL:
            for name, params, pnl, mae in fam(g):
                P = np.full(len(days), np.nan)
                M = np.full(len(days), np.nan)
                P[pos] = pnl
                M[pos] = mae
                streams.append({"sym": sym, "fam": name, "params": params,
                                "pnl": P.astype(np.float32), "mae": M.astype(np.float32)})
        families.run = old_run
    lib = {"days": days, "streams": streams}
    path.write_bytes(pickle.dumps(lib))
    return lib
