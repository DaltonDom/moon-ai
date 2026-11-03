"""Rule-based strategy families. Each yields (family, params, pnl, mae) per day
for one micro contract, net of costs. All signals use bars closed before entry.
"""

from __future__ import annotations

import itertools

import numpy as np

from moon_ai.lab.data import m
from moon_ai.lab.engine import run
from moon_ai.lab.features import daily_range_atr, first_cross, prev_close

TIMES = {
    "on": (m(18, 0), m(9, 30)),
    "eu": (m(2, 0), m(9, 30)),
    "o30": (m(9, 30), m(10, 0)),
    "o60": (m(9, 30), m(10, 30)),
    "am": (m(9, 30), m(12, 0)),
    "mid": (m(12, 0), m(14, 0)),
    "pm": (m(14, 0), m(15, 30)),
    "l30": (m(15, 30), m(15, 59)),
    "aft": (m(12, 0), m(15, 59)),
    "rest": (m(10, 0), m(15, 59)),
    "rest60": (m(10, 30), m(15, 59)),
}
SIG_WINDOWS = ["on", "eu", "o30", "o60", "am", "mid", "prev"]


def _win_ret(g, w, pc):
    if w == "prev":
        c = g.C[:, m(16, 0) - 1]
        o = g.O[:, m(9, 30)]
        r = np.log(c / o)
        return np.r_[np.nan, r[:-1]]
    a, b = TIMES[w]
    if w == "on":
        return np.log(g.C[:, b - 1] / pc)
    return np.log(g.C[:, b - 1] / g.O[:, a])


def window_momentum(g):
    """Sign of a signal window's return -> trade a later window (mom or rev),
    optionally only when |signal| exceeds k x its trailing median."""
    pc = prev_close(g)
    atr = daily_range_atr(g)
    for sw in SIG_WINDOWS:
        r = _win_ret(g, sw, pc)
        sig_end = TIMES[sw][1] if sw != "prev" else 0
        ar = np.abs(r)
        med = np.full(len(r), np.nan)
        for i in range(60, len(r)):
            med[i] = np.nanmedian(ar[i - 60:i])
        for tw, (a, b) in TIMES.items():
            if a < sig_end or tw in ("on",) and sw != "prev":
                continue
            if sw == "prev" and False:
                pass
            for k in (0.0, 1.0, 2.0):
                strong = (ar > k * med) & ~np.isnan(med)
                for sign in (1, -1):
                    for stop in (0.0, 0.5):
                        side = np.where(strong, sign * np.sign(r), 0).astype(int)
                        side = np.nan_to_num(side).astype(int)
                        sd = np.nan_to_num(atr * stop) if stop else 0.0
                        pnl, mae, _ = run(g, np.full(len(r), a), side, sd, 0.0, b)
                        yield "winmom", (sw, tw, k, sign, stop), pnl, mae


def orb(g):
    for k, stopf, tgt, exh in itertools.product([5, 15, 30, 60], [0.5, 1.0], [0, 1, 2],
                                                 ["12", "1555"]):
        a = m(9, 30)
        b = a + k
        hi = np.nanmax(g.H[:, a:b], 1)
        lo = np.nanmin(g.L[:, a:b], 1)
        r = hi - lo
        ext = m(12, 0) if exh == "12" else m(15, 55)
        side, idx = first_cross(g.C[:, b:ext - 5], hi, lo)
        for fade in (1, -1):
            ent = np.where(side != 0, b + idx + 1, -1)
            sd = np.maximum(r * stopf, 4 * g.tick)
            pnl, mae, _ = run(g, ent, side * fade, sd, sd * tgt, ext)
            yield "orb", (k, stopf, tgt, exh, fade), pnl, mae


def gap(g):
    pc = prev_close(g)
    atr = daily_range_atr(g)
    o = g.O[:, m(9, 30)]
    gp = (o - pc) / atr
    for th, ex, fade, stop in itertools.product([0.1, 0.2, 0.4], ["1030", "12", "1555"],
                                                [1, -1], [0.0, 0.3]):
        side = np.where(np.abs(gp) > th, -fade * np.sign(gp), 0)
        side = np.nan_to_num(side).astype(int)
        ext = {"1030": m(10, 30), "12": m(12, 0), "1555": m(15, 55)}[ex]
        sd = np.nan_to_num(atr * stop) if stop else 0.0
        # gap fade target = previous close
        pnl, mae, _ = run(g, m(9, 30), side, sd, 0.0, ext)
        yield "gap", (th, ex, fade, stop), pnl, mae


def vwap_rev(g):
    """At a check time, fade (or follow) price that is far from the session VWAP."""
    atr = daily_range_atr(g)
    a = m(9, 30)
    for ct, th, ex, sign in itertools.product([m(10, 30), m(11, 30), m(13, 0), m(14, 30)],
                                              [0.15, 0.3, 0.5], ["+60", "1555"], [1, -1]):
        C, V = g.C, g.V
        vw = np.nansum(C[:, a:ct] * V[:, a:ct], 1) / np.maximum(np.nansum(V[:, a:ct], 1), 1)
        dist = (C[:, ct - 1] - vw) / atr
        side = np.where(np.abs(dist) > th, -sign * np.sign(dist), 0)
        side = np.nan_to_num(side).astype(int)
        ext = ct + 60 if ex == "+60" else m(15, 55)
        pnl, mae, _ = run(g, ct, side, 0.0, 0.0, ext)
        yield "vwap", (ct, th, ex, sign), pnl, mae


def calendar(g):
    """Long/short in a window on given weekdays or turn-of-month days."""
    d = g.days.astype("datetime64[D]")
    dow = (d.view("int64") + 3) % 7  # 0 = Monday
    month = d.astype("datetime64[M]")
    # trading-day-of-month from start and from end
    tdom = np.zeros(len(d), int)
    tdom_end = np.zeros(len(d), int)
    for mo in np.unique(month):
        idx = np.where(month == mo)[0]
        tdom[idx] = np.arange(len(idx))
        tdom_end[idx] = np.arange(len(idx))[::-1]
    for wname in ("on", "am", "aft", "rest"):
        a, b = TIMES[wname]
        for wd in range(5):
            for sign in (1, -1):
                side = np.where(dow == wd, sign, 0)
                pnl, mae, _ = run(g, a, side, 0.0, 0.0, b)
                yield "cal_dow", (wname, wd, sign), pnl, mae
        tom = (tdom <= 2) | (tdom_end == 0)
        for sign in (1, -1):
            side = np.where(tom, sign, 0)
            pnl, mae, _ = run(g, a, side, 0.0, 0.0, b)
            yield "cal_tom", (wname, sign), pnl, mae


def prevday_levels(g):
    """Break of yesterday's RTH high/low: follow or fade, stop at x ATR."""
    atr = daily_range_atr(g)
    a, b = m(9, 30), m(16, 0)
    ph = np.r_[np.nan, np.nanmax(g.H[:-1, a:b], 1)]
    pl = np.r_[np.nan, np.nanmin(g.L[:-1, a:b], 1)]
    for start, stop, sign, ex in itertools.product([m(9, 35), m(10, 30)], [0.2, 0.4], [1, -1],
                                                   ["12", "1555"]):
        ext = m(12, 0) if ex == "12" else m(15, 55)
        side, idx = first_cross(g.C[:, start:ext - 5], ph, pl)
        ent = np.where(side != 0, start + idx + 1, -1)
        sd = np.nan_to_num(atr * stop)
        pnl, mae, _ = run(g, ent, side * sign, sd, 0.0, ext)
        yield "pdl", (start, stop, sign, ex), pnl, mae


ALL = [window_momentum, orb, gap, vwap_rev, calendar, prevday_levels]
