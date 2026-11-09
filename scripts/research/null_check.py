"""Sanity check: every family on a synthetic random walk should show no edge
over its coin-flip twin (|z| within about 2). Run from the repo root."""

import sys

sys.path.insert(0, "scripts/research")
import numpy as np
from evaluate import r_multiples
from sessions import N_MIN, Days
from strategies import configs, mirror, simulate

rng = np.random.default_rng(1)
n = 800
steps = rng.standard_t(4, (n, N_MIN)) * 4
opens = 20000 + np.cumsum(rng.normal(0, 150, n))
c = np.round((opens[:, None] + np.cumsum(steps, 1)) / 0.25) * 0.25
o = np.concatenate([opens[:, None], c[:, :-1]], 1)
o = np.round(o / 0.25) * 0.25
wick = np.abs(rng.normal(0, 2, (n, N_MIN)))
h = np.round((np.maximum(o, c) + wick) / 0.25) * 0.25
lo = np.round((np.minimum(o, c) - wick) / 0.25) * 0.25
pc = np.concatenate([[np.nan], c[:-1, -1]])
d = Days(
    "MNQ",
    np.arange(n).astype("datetime64[D]"),
    o,
    h,
    lo,
    c,
    rng.integers(1, 100, (n, N_MIN)).astype(float),
    pc,
    np.maximum(o[:, 0], pc) + 30,
    np.minimum(o[:, 0], pc) - 30,
    o[:, 0],
    0.25,
    2.0,
)
for cfg in configs():
    tr = cfg.build(d)
    if len(tr) < 20:
        print(cfg.name, len(tr))
        continue
    r, _, _ = r_multiples([simulate(d, t) for t in tr], [t.px for t in tr], 2.0)
    r2, _, _ = r_multiples([simulate(d, mirror(t, 0.25)) for t in tr], [t.px for t in tr], 2.0)
    e = (r - r2) / 2
    se = e.std() / np.sqrt(len(e))
    print(
        f"{cfg.name:30s} n={len(r):4d} R={r.mean():+.3f} twin={r2.mean():+.3f} "
        f"edge={e.mean():+.3f} z={e.mean() / se:+.2f}"
    )
