"""Walk-forward selection of a portfolio of streams, year by year.

For out-of-sample year Y, everything (which streams, their weights) is decided
from data before 1 January Y only; the year's P&L is then recorded. Chaining the
years gives an out-of-sample daily P&L stream a live trader could have had.
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np


def years_of(days):
    return days.astype("datetime64[Y]").astype(int) + 1970


def select(streams, days, Y, min_days=250, top_per_group=1, min_t=2.5, lookback_years=None,
           group_key=("sym", "fam")):
    yrs = years_of(days)
    is_mask = yrs < Y
    if lookback_years:
        is_mask &= yrs >= Y - lookback_years
    groups = defaultdict(list)
    for i, s in enumerate(streams):
        p = s["pnl"][is_mask]
        p = p[~np.isnan(p)]
        if len(p) < min_days:
            continue
        sd = p.std()
        if sd == 0:
            continue
        sh = p.mean() / sd
        t = sh * np.sqrt(len(p))
        if t < min_t:
            continue
        groups[tuple(s[k] for k in group_key)].append((sh, i, sd))
    chosen = []
    for k, lst in groups.items():
        lst.sort(reverse=True)
        chosen.extend(lst[:top_per_group])
    return chosen


def walk_forward(lib, years=range(2021, 2026), **kw):
    days = lib["days"]
    streams = lib["streams"]
    yrs = years_of(days)
    out_pnl = np.zeros(len(days))
    out_low = np.zeros(len(days))
    oos = np.zeros(len(days), bool)
    picks = {}
    for Y in years:
        ch = select(streams, days, Y, **kw)
        picks[Y] = [(streams[i]["sym"], streams[i]["fam"], streams[i]["params"], round(sh, 3))
                    for sh, i, sd in ch]
        te = yrs == Y
        oos |= te
        if not ch:
            continue
        # equal risk weights: each stream scaled to $1 daily sd in-sample, then the
        # portfolio is normalised later by the sizing rule.
        for sh, i, sd in ch:
            p = np.nan_to_num(streams[i]["pnl"][te]) / sd
            lo = np.nan_to_num(streams[i]["mae"][te]) / sd
            out_pnl[te] += p / len(ch)
            out_low[te] += np.minimum(lo, 0) / len(ch)
    return out_pnl, out_low, oos, picks
