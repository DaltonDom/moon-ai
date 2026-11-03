"""Causal per-day reference values shared by strategy families."""

from __future__ import annotations

import numpy as np

from moon_ai.lab.data import m


def prev_close(g):
    """Previous trading day's 16:00 close (NaN for the first day)."""
    c = g.C[:, m(16, 0) - 1]
    out = np.full(len(c), np.nan)
    out[1:] = c[:-1]
    return out


def daily_range_atr(g, n=14):
    """ATR-like average of past RTH ranges (09:30-16:00), excluding today."""
    a, b = m(9, 30), m(16, 0)
    rng = np.nanmax(g.H[:, a:b], axis=1) - np.nanmin(g.L[:, a:b], axis=1)
    out = np.full(len(rng), np.nan)
    cs = np.nancumsum(rng)
    for i in range(n, len(rng)):
        out[i] = np.nanmean(rng[i - n:i])
    return out


def first_cross(close_seg, upper, lower):
    """Index of the first minute whose close is above upper (+1) or below lower (-1)."""
    up = close_seg > upper[:, None]
    dn = close_seg < lower[:, None]
    any_up = up.any(1)
    any_dn = dn.any(1)
    iu = np.where(any_up, up.argmax(1), 10**9)
    idn = np.where(any_dn, dn.argmax(1), 10**9)
    side = np.where(iu < idn, 1, np.where(idn < iu, -1, 0))
    idx = np.minimum(iu, idn)
    return side, idx
