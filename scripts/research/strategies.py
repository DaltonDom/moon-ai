"""Non-ICT intraday strategy families (#102) and the fill simulator.

Every family makes at most one trade per day. Each trade is described by
when it enters, the side, the entry fill, a per-minute stop-level series (so a
trailing stop is just a moving series), an optional target and a time exit.
The simulator then walks the bars after entry.

Fills follow the repo's cost model (config.py `CostModel`): market fills
pay 1 tick, stop orders (entries and exits) pay 3 ticks, targets are limit orders
that need a trade one tick through, commission is $1 per side. When a stop and
a target are both inside one bar, the stop is assumed to fill first.

The coin-flip twin of every trade enters at the same minute and price, on the
other side, with the stop series and target mirrored around the entry. Same
timing, same risk, same exit rules: only the direction differs.

No signal uses a bar before it has closed: a decision at minute i uses bars
0..i-1 and fills at the open of bar i (or at a stop level touched inside it).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from sessions import N_MIN, Days

COMMISSION_RT = 2.0  # USD per contract, round trip
ENTRY_SLIP = 1  # ticks
STOP_SLIP = 3
EXIT_I = N_MIN - 1  # flat at the 15:59 open, well before any prop firm cut-off


@dataclass
class Trade:
    day: int
    i: int  # entry bar
    d: int  # +1 long, -1 short
    px: float  # entry fill
    stop: np.ndarray  # stop level per bar (len N_MIN); nan = no stop that bar
    target: float = np.nan
    exit_i: int = EXIT_I
    stop_entry: bool = False  # filled inside bar i by a stop order


@dataclass
class Result:
    day: int
    d: int
    entry_i: int
    exit_i: int
    pnl_pts: float  # per contract, before commission
    risk_pts: float  # initial stop distance
    mae_pts: float  # worst open loss, points per contract
    reason: str


def mirror(t: Trade, tick: float) -> Trade:
    # The twin pays its own entry slippage, so its fill is 2 ticks off ours.
    # A stop entry fills past the level after price has already run through
    # it, so the twin trades at that same fill rather than back at the level
    # (which would hand the original the overshoot). Market entries: the twin
    # pays its own tick of slippage on the other side.
    px = t.px if t.stop_entry else t.px - 2 * ENTRY_SLIP * tick * t.d
    stop = 2 * px - (t.stop + (px - t.px))
    target = 2 * px - (t.target + (px - t.px)) if not np.isnan(t.target) else np.nan
    return Trade(t.day, t.i, -t.d, px, stop, target, t.exit_i, t.stop_entry)


def simulate(days: Days, t: Trade) -> Result:
    k, i, d, tick = t.day, t.i, t.d, days.tick
    o, h, l, c = days.o[k], days.h[k], days.l[k], days.c[k]  # noqa: E741
    j = np.arange(i, t.exit_i)
    st = t.stop[i : t.exit_i]
    risk = abs(t.px - t.stop[i]) if not np.isnan(t.stop[i]) else np.nan
    # adverse extreme, and whether the stop is hit, per bar
    adverse = l[j] if d > 0 else h[j]
    hit = (adverse <= st) if d > 0 else (adverse >= st)
    hit &= ~np.isnan(st)
    if t.stop_entry:  # on the fill bar we only know the close is past the stop
        hit[0] = (c[i] <= st[0]) if d > 0 else (c[i] >= st[0])
    if np.isnan(t.target):
        tgt = np.zeros_like(hit)
    else:
        fav = h[j] if d > 0 else l[j]
        tgt = (fav >= t.target + tick) if d > 0 else (fav <= t.target - tick)
        if t.stop_entry:
            tgt[0] = False
    first_stop = int(np.argmax(hit)) if hit.any() else len(j)
    first_tgt = int(np.argmax(tgt)) if tgt.any() else len(j)
    if first_stop <= first_tgt and first_stop < len(j):
        n = first_stop
        b = j[n]
        level = st[n]
        gap = (o[b] < level) if d > 0 else (o[b] > level)
        base = o[b] if (gap and not (t.stop_entry and n == 0)) else level
        exit_px = base - d * STOP_SLIP * tick
        reason = "stop"
    elif first_tgt < len(j):
        n = first_tgt
        b = j[n]
        gap = (o[b] > t.target) if d > 0 else (o[b] < t.target)
        exit_px = o[b] if gap else t.target
        reason = "target"
    else:
        n = len(j)
        b = t.exit_i
        exit_px = o[b] - d * ENTRY_SLIP * tick
        reason = "time"
    held = j[: n + 1] if n < len(j) else j
    worst = (t.px - l[held].min()) if d > 0 else (h[held].max() - t.px)
    pnl = (exit_px - t.px) * d
    return Result(k, d, i, int(b), pnl, risk, max(worst, -pnl, 0.0), reason)


# ---------------------------------------------------------------- helpers


def _const(level: float) -> np.ndarray:
    return np.full(N_MIN, level)


def _mkt(days: Days, k: int, i: int, d: int) -> float:
    return days.o[k, i] + d * ENTRY_SLIP * days.tick


def _first_touch(days: Days, k: int, start: int, end: int, up: float, dn: float):
    """First bar in [start, end) trading through `up` (long) or `dn` (short)."""
    hi = days.h[k, start:end] >= up
    lo = days.l[k, start:end] <= dn
    a = int(np.argmax(hi)) if hi.any() else 10**9
    b = int(np.argmax(lo)) if lo.any() else 10**9
    if a == b == 10**9 or a == b:  # none, or both in one bar (ambiguous: skip)
        return None
    if a < b:
        i = start + a
        px = max(up, days.o[k, i]) + days.tick * STOP_SLIP
        return i, 1, px
    i = start + b
    px = min(dn, days.o[k, i]) - days.tick * STOP_SLIP
    return i, -1, px


def atr(days: Days, n: int = 14) -> np.ndarray:
    """Mean RTH range of the previous n days (nan until there are n)."""
    rng = days.h.max(1) - days.l.min(1)
    out = np.full(len(days), np.nan)
    cs = np.concatenate([[0], np.cumsum(rng)])
    for k in range(n, len(days)):
        out[k] = (cs[k] - cs[k - n]) / n
    return out


def vwap(days: Days) -> np.ndarray:
    """VWAP through the close of each bar."""
    tp = (days.h + days.l + days.c) / 3
    v = np.maximum(days.v, 0)
    cv = np.cumsum(v, 1)
    out = np.cumsum(tp * v, 1) / np.where(cv > 0, cv, np.nan)
    return np.where(np.isnan(out), days.c, out)


# ---------------------------------------------------------------- families


def orb_candle(days: Days, m: int, target_r: float | None) -> list[Trade]:
    """Zarattini & Aziz (2023): trade the direction of the first m-minute
    candle at the open of minute m, stop at the far side of that range."""
    out = []
    for k in range(len(days)):
        op, cl = days.o[k, 0], days.c[k, m - 1]
        if cl == op:
            continue
        d = 1 if cl > op else -1
        hi, lo = days.h[k, :m].max(), days.l[k, :m].min()
        px = _mkt(days, k, m, d)
        stop = lo if d > 0 else hi
        if (px - stop) * d <= days.tick * 4:
            continue
        tgt = px + d * target_r * abs(px - stop) if target_r else np.nan
        out.append(Trade(k, m, d, px, _const(stop), tgt))
    return out


def orb_break(days: Days, m: int, stop_at: str, last_entry: int = 150) -> list[Trade]:
    """First break of the m-minute opening range by a stop order, before
    12:00. Stop at the other side of the range, or at its midpoint."""
    out = []
    for k in range(len(days)):
        hi, lo = days.h[k, :m].max(), days.l[k, :m].min()
        f = _first_touch(days, k, m, last_entry, hi + days.tick, lo - days.tick)
        if f is None:
            continue
        i, d, px = f
        stop = (lo if d > 0 else hi) if stop_at == "opp" else (hi + lo) / 2
        if (px - stop) * d <= days.tick * 4:
            continue
        out.append(Trade(k, i, d, px, _const(stop), stop_entry=True))
    return out


def noise_area(days: Days, mult: float, lookback: int = 14, step: int = 30) -> list[Trade]:
    """Zarattini, Aziz & Barbon (2024), 'Beat the Market': the noise area is
    the open +/- the average absolute move from the open at that minute over
    the last `lookback` days. A half-hourly close outside it enters; the stop
    trails at the band or VWAP (whichever is tighter), updated every half
    hour, and the trade is flat by the close. One entry per day here."""
    move = np.abs(days.c / days.o[:, :1] - 1)
    vw = vwap(days)
    out = []
    checks = list(range(step, N_MIN - 1, step))  # 10:00, 10:30, ... 15:30
    for k in range(lookback, len(days)):
        if np.isnan(days.prev_close[k]):
            continue
        sigma = mult * move[k - lookback : k].mean(0)
        op = days.o[k, 0]
        up = max(op, days.prev_close[k]) * (1 + sigma)
        dn = min(op, days.prev_close[k]) * (1 - sigma)
        for ci in checks:
            cl = days.c[k, ci - 1]  # the bar that just closed
            d = 1 if cl > up[ci - 1] else (-1 if cl < dn[ci - 1] else 0)
            if d == 0:
                continue
            px = _mkt(days, k, ci, d)
            stop = np.full(N_MIN, np.nan)
            level = np.nan
            for j in range(ci, N_MIN):
                if j == ci or (j % step == 0):
                    band = up[j - 1] if d > 0 else dn[j - 1]
                    new = max(band, vw[k, j - 1]) if d > 0 else min(band, vw[k, j - 1])
                    if new * d < px * d:  # only a stop on the losing side
                        if np.isnan(level):
                            level = new
                        else:
                            level = max(level, new) if d > 0 else min(level, new)
                stop[j] = level
            if np.isnan(stop[ci]):
                break  # no valid stop on entry: skip the day
            out.append(Trade(k, ci, d, px, stop))
            break
    return out


def intraday_momentum(days: Days, signal_end: int, stop_pct: float = 0.004) -> list[Trade]:
    """Gao, Han, Li & Zhou (2018): the return from the prior close to
    `signal_end` predicts the last half hour. Enter 15:30, exit 15:59."""
    out = []
    entry = 360  # 15:30
    for k in range(len(days)):
        pc = days.prev_close[k]
        if np.isnan(pc):
            continue
        r = days.c[k, signal_end - 1] - pc
        if r == 0:
            continue
        d = 1 if r > 0 else -1
        px = _mkt(days, k, entry, d)
        out.append(Trade(k, entry, d, px, _const(px * (1 - d * stop_pct))))
    return out


def gap_fade(days: Days, k_atr: float, exit_i: int = 150) -> list[Trade]:
    """Fade an opening gap bigger than k_atr x ATR toward the prior close.
    Stop one gap-size beyond the open, exit by 12:00."""
    a = atr(days)
    out = []
    for k in range(len(days)):
        pc = days.prev_close[k]
        if np.isnan(pc) or np.isnan(a[k]):
            continue
        gap = days.o[k, 0] - pc
        if abs(gap) < k_atr * a[k]:
            continue
        d = -1 if gap > 0 else 1
        px = _mkt(days, k, 0, d)
        out.append(Trade(k, 0, d, px, _const(px - d * abs(gap)), target=pc, exit_i=exit_i))
    return out


def vwap_revert(days: Days, k_atr: float) -> list[Trade]:
    """From 10:00, fade the first close more than k_atr x ATR from VWAP.
    Target VWAP at entry, stop the same distance beyond."""
    a = atr(days)
    vw = vwap(days)
    out = []
    for k in range(len(days)):
        if np.isnan(a[k]):
            continue
        dev = days.c[k] - vw[k]
        for i in range(30, 360):
            x = dev[i - 1]
            if abs(x) < k_atr * a[k]:
                continue
            d = -1 if x > 0 else 1
            px = _mkt(days, k, i, d)
            dist = abs(px - vw[k, i - 1])
            out.append(Trade(k, i, d, px, _const(px - d * dist), target=vw[k, i - 1]))
            break
    return out


def overnight_break(days: Days, stop_frac: float) -> list[Trade]:
    """First break of the overnight high or low in RTH, before 12:00, with
    a stop `stop_frac` of the overnight range back."""
    out = []
    for k in range(len(days)):
        oh, ol = days.on_high[k], days.on_low[k]
        if np.isnan(oh):
            continue
        op = days.o[k, 0]
        if not (ol < op < oh):
            continue  # opened outside the overnight range
        f = _first_touch(days, k, 0, 150, oh + days.tick, ol - days.tick)
        if f is None:
            continue
        i, d, px = f
        out.append(Trade(k, i, d, px, _const(px - d * stop_frac * (oh - ol)), stop_entry=True))
    return out


@dataclass
class Config:
    family: str
    name: str
    build: object = field(repr=False)


def configs() -> list[Config]:
    """The pre-registered grid: 26 configurations, every one a trial."""
    cs: list[Config] = []
    for m in (5, 15, 30):
        for tr in (None, 2.0):
            cs.append(
                Config(
                    "orb_candle",
                    f"orb_candle_m{m}_{'eod' if tr is None else '2R'}",
                    lambda d, m=m, tr=tr: orb_candle(d, m, tr),
                )
            )
    for m in (15, 30, 60):
        for s in ("opp", "mid"):
            cs.append(
                Config("orb_break", f"orb_break_m{m}_{s}", lambda d, m=m, s=s: orb_break(d, m, s))
            )
    for mult in (1.0, 1.5):
        for step in (30, 15):
            cs.append(
                Config(
                    "noise_area",
                    f"noise_area_x{mult}_{step}m",
                    lambda d, mult=mult, step=step: noise_area(d, mult, step=step),
                )
            )
    for se in (30, 360):
        cs.append(
            Config(
                "intraday_momentum",
                f"intraday_momentum_to{se}",
                lambda d, se=se: intraday_momentum(d, se),
            )
        )
    for ka in (0.15, 0.3):
        cs.append(Config("gap_fade", f"gap_fade_k{ka}", lambda d, ka=ka: gap_fade(d, ka)))
    for ka in (0.25, 0.4):
        cs.append(Config("vwap_revert", f"vwap_revert_k{ka}", lambda d, ka=ka: vwap_revert(d, ka)))
    for sf in (0.25, 0.5):
        cs.append(
            Config(
                "overnight_break", f"overnight_break_s{sf}", lambda d, sf=sf: overnight_break(d, sf)
            )
        )
    return cs


# ------------------------------------------- YouTube group (prop-search 2)
# Rules as extracted from each video by Gemini on 2026-11-09 (notes in
# docs/research/prop-search-youtube.md). Anything the video left open is
# fixed here once, before any result, and noted.


def _daily(days: Days):
    """50-day SMA of RTH closes and 14-day ATR (true range incl. the gap
    from the prior close), both from days before today. Unadjusted
    continuous prices, so a roll adds a small jump."""
    close = days.c[:, -1]
    hi, lo = days.h.max(1), days.l.min(1)
    prev = np.concatenate([[np.nan], close[:-1]])
    tr = np.nanmax(np.stack([hi - lo, np.abs(hi - prev), np.abs(lo - prev)]), 0)
    n = len(days)
    sma, atr14 = np.full(n, np.nan), np.full(n, np.nan)
    for k in range(50, n):
        sma[k] = close[k - 50 : k].mean()
    for k in range(14, n):
        atr14[k] = tr[k - 14 : k].mean()
    return sma, atr14


def opening_range_reversal(days: Days, retrace: float) -> list[Trade]:
    """The Rumers, 8vufTzGZqiI. Daily bias from today's open vs the 50-day
    SMA. The opening move against the bias (open-session extreme to the
    opposite extreme, from 09:30) must exceed 20% of daily ATR. On 5-minute
    bars, after the move's extreme, the first candle closing in the bias
    direction sets the trigger; a stop order one tick past its high (low)
    enters. Stop at the low (high) of day; target `retrace` of the move.
    Fixed here: setups by 10:30, entries by 11:00, flat at 15:59."""
    sma, atr14 = _daily(days)
    out = []
    for k in range(len(days)):
        if np.isnan(sma[k]) or np.isnan(atr14[k]):
            continue
        op = days.o[k, 0]
        d = 1 if op > sma[k] else -1
        o5 = days.o[k, :90].reshape(18, 5)[:, 0]
        h5 = days.h[k, :90].reshape(18, 5).max(1)
        l5 = days.l[k, :90].reshape(18, 5).min(1)
        c5 = days.c[k, :90].reshape(18, 5)[:, -1]
        # running extreme against the bias, through each 5-minute bar (to 10:30)
        for b in range(1, 12):
            ext = l5[: b + 1].min() if d > 0 else h5[: b + 1].max()
            start = (
                h5[: int(np.argmin(l5[: b + 1])) + 1].max()
                if d > 0
                else (l5[: int(np.argmax(h5[: b + 1])) + 1].min())
            )
            move = (start - ext) * d
            at_ext = (l5[b] == ext) if d > 0 else (h5[b] == ext)
            if at_ext or move < 0.2 * atr14[k]:
                continue
            if not ((c5[b] > o5[b]) if d > 0 else (c5[b] < o5[b])):
                continue
            trig = h5[b] + days.tick if d > 0 else l5[b] - days.tick
            f = (
                _first_touch(days, k, 5 * (b + 1), 90, trig, -np.inf)
                if d > 0
                else (_first_touch(days, k, 5 * (b + 1), 90, np.inf, trig))
            )
            if f is None or f[1] != d:
                break
            i, _, px = f
            low_so_far = days.l[k, :i].min() if d > 0 else days.h[k, :i].max()
            if (px - low_so_far) * d <= days.tick * 4:
                break
            tgt = low_so_far + d * retrace * abs(start - low_so_far)
            if (tgt - px) * d <= 0:
                break
            out.append(Trade(k, i, d, px, _const(low_so_far), tgt, stop_entry=True))
            break
    return out


def orb_bracket(days: Days, m: int, target_x: float, stop_x: float) -> list[Trade]:
    """TOS Indicators, MOG-DbgmzzI. First break of the m-minute range by a
    stop order; target and stop are multiples of the range width from the
    entry; flat at the close. Fixed here: entries by 12:00."""
    out = []
    for k in range(len(days)):
        hi, lo = days.h[k, :m].max(), days.l[k, :m].min()
        w = hi - lo
        if w <= days.tick * 4:
            continue
        f = _first_touch(days, k, m, 150, hi + days.tick, lo - days.tick)
        if f is None:
            continue
        i, d, px = f
        out.append(
            Trade(k, i, d, px, _const(px - d * stop_x * w), px + d * target_x * w, stop_entry=True)
        )
    return out


def orb_fvg(days: Days) -> list[Trade]:
    """Jesse Rogers (Casper), mzFXoK2pbNE. 5-minute range 09:30-09:35. The
    first 1-minute close beyond it is the break candle. A fair value gap in
    the break direction on that candle or the next two (candle-3 wick past
    candle-1 wick) enters at the open after candle 3. Stop at the break
    candle's far extreme, target 2R. Fixed here: break by 10:30, no FVG in
    those three candles means no trade."""
    out = []
    h, l, c = days.h, days.l, days.c  # noqa: E741
    for k in range(len(days)):
        hi, lo = h[k, :5].max(), l[k, :5].min()
        brk = None
        for j in range(5, 60):
            if c[k, j] > hi or c[k, j] < lo:
                brk = j
                break
        if brk is None:
            continue
        d = 1 if c[k, brk] > hi else -1
        for j3 in range(max(brk, 7), brk + 3):
            gap = (l[k, j3] > h[k, j3 - 2]) if d > 0 else (h[k, j3] < l[k, j3 - 2])
            if gap:
                i = j3 + 1
                px = _mkt(days, k, i, d)
                stop = l[k, brk] if d > 0 else h[k, brk]
                if (px - stop) * d <= days.tick * 4:
                    break
                out.append(Trade(k, i, d, px, _const(stop), px + 2 * d * abs(px - stop)))
                break
    return out


def youtube_configs() -> list[Config]:
    """Prop-search 2, pre-registered 2026-11-09: 5 configurations."""
    return [
        Config("youtube_orr", "yt_orr_50pct", lambda d: opening_range_reversal(d, 0.5)),
        Config("youtube_orr", "yt_orr_100pct", lambda d: opening_range_reversal(d, 1.0)),
        Config("youtube_orb_bracket", "yt_orb5_full_full", lambda d: orb_bracket(d, 5, 1.0, 1.0)),
        Config("youtube_orb_bracket", "yt_orb5_half_full", lambda d: orb_bracket(d, 5, 0.5, 1.0)),
        Config("youtube_orb_fvg", "yt_orb5_fvg_2R", orb_fvg),
    ]
