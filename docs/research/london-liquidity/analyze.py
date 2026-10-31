# ruff: noqa: E501  (markdown table strings)
"""London (02:00-05:00 ET) vs NY AM (09:30-11:00 ET) liquidity on MNQ.

Reads only the files download.py bought (data/london-liquidity/, git-ignored)
and prints the tables used in docs/research/london-liquidity.md. Makes no
network calls and needs no API key.

Run:  uv run python -I docs/research/london-liquidity/analyze.py
"""

from __future__ import annotations

import sys
from datetime import date, time
from pathlib import Path

import databento as db
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from windows import TICK, TICK_DAYS  # noqa: E402

DATA = HERE.parents[2] / "data" / "london-liquidity"
NYTZ = "America/New_York"
COMMISSION_SIDE = 0.62  # USD per contract per side (config.py placeholder)
TICK_USD = 0.50  # MNQ: 0.25 index points x $2

# name -> (start, end) NY wall clock, [start, end)
WIN = {
    "London 02:00-05:00": (time(2), time(5)),
    "NY AM 09:30-11:00": (time(9, 30), time(11)),
    "Silver Bullet 10:00-11:00": (time(10), time(11)),
}


def load(name: str) -> pd.DataFrame:
    df = db.DBNStore.from_file(DATA / name).to_df()
    return df


def q(s: pd.Series, ps=(0.5, 0.75, 0.9)) -> list[float]:
    s = pd.Series(s).dropna()
    return [float(s.quantile(p)) for p in ps]


def in_win(idx: pd.DatetimeIndex, w: tuple[time, time]) -> np.ndarray:
    t = idx.tz_convert(NYTZ).time
    return np.array([(w[0] <= x < w[1]) for x in t])


def fmt(xs, nd=1) -> str:
    return " / ".join(f"{x:.{nd}f}" for x in xs)


# ---------------------------------------------------------------- 1m bars
def bars() -> pd.DataFrame:
    b = load("ohlcv1m_20260501_20261031.dbn.zst")
    b = b[["instrument_id", "open", "high", "low", "close", "volume"]].copy()
    b.index = b.index.tz_convert(NYTZ)
    b["day"] = b.index.date
    b["t"] = b.index.time
    b["wd"] = b.index.weekday
    return b


def bar_stats(b: pd.DataFrame) -> None:
    print("\n## 1-minute bar statistics (ohlcv-1m, 2026-05-01..2026-10-30)\n")
    print(
        "| window | days | bars present % | volume/min median (p25-p75) | 1m range ticks p50/p75/p90 "
        "| 15m range ticks p50/p75/p90 | window range ticks p50/p75/p90 |"
    )
    print("|---|---:|---:|---:|---:|---:|---:|")
    for name, w in WIN.items():
        m = np.array([(w[0] <= x < w[1]) for x in b["t"]]) & (b["wd"] < 5)
        sub = b[m]
        mins = (
            pd.Timestamp.combine(date.today(), w[1]) - pd.Timestamp.combine(date.today(), w[0])
        ).seconds // 60
        g = sub.groupby("day")
        ok = g.size()[g.size() >= 0.5 * mins].index  # drop holiday/half days
        ok = [d for d in ok if g.get_group(d)["instrument_id"].nunique() == 1]
        sub = sub[sub["day"].isin(ok)]
        present = len(sub) / (len(ok) * mins) * 100
        # volume per minute counting empty minutes as 0
        vol_day = sub.groupby("day")["volume"].sum() / mins
        vpm = sub["volume"].reindex(sub.index)  # per present bar
        full_vpm = pd.concat([vpm, pd.Series(0, index=range(len(ok) * mins - len(sub)))])
        r1 = (sub["high"] - sub["low"]) / TICK
        q15 = sub.index.floor("15min")
        r15 = sub.groupby(q15).agg(h=("high", "max"), l=("low", "min"))
        r15 = (r15.h - r15.l) / TICK
        rw = sub.groupby("day").agg(h=("high", "max"), l=("low", "min"))
        rw = (rw.h - rw.l) / TICK
        print(
            f"| {name} | {len(ok)} | {present:.1f} | {full_vpm.median():.0f} "
            f"({full_vpm.quantile(0.25):.0f}-{full_vpm.quantile(0.75):.0f}); mean {vol_day.mean():.0f} | "
            f"{fmt(q(r1), 0)} | {fmt(q(r15), 0)} | {fmt(q(rw), 0)} |"
        )


# ---------------------------------------------------------------- sweep proxies
def _window(b: pd.DataFrame, day: date, w: tuple[time, time]) -> pd.DataFrame:
    s = b[(b["day"] == day) & (b["t"] >= w[0]) & (b["t"] < w[1])]
    return s


def _scan(sw: pd.DataFrame, hi: float, lo: float, mss_lookback: int = 30, mss_max: int = 30):
    """First sweep of hi or lo in `sw` with a 1-bar close-back. Returns dicts.

    Variant A: enter at the close of the close-back bar; stop 1 tick beyond the
    sweep extreme (max high / min low from sweep bar to entry bar).
    Variant B: after the close-back, enter on the first close beyond the last
    fractal (N=1) swing on the other side formed before the sweep (MSS by
    close, within mss_max bars); stop 1 tick beyond the running sweep extreme.
    The setup is void if price trades beyond the extreme before the MSS.
    """
    H, L, C = sw["high"].to_numpy(), sw["low"].to_numpy(), sw["close"].to_numpy()
    n = len(sw)
    out = []
    for i in range(n):
        for side in ("short", "long"):
            if side == "short" and H[i] >= hi + TICK:
                closes = [j for j in (i, i + 1) if j < n and C[j] < hi]
            elif side == "long" and L[i] <= lo - TICK:
                closes = [j for j in (i, i + 1) if j < n and C[j] > lo]
            else:
                continue
            if not closes:
                continue
            j = closes[0]
            ext = H[i : j + 1].max() if side == "short" else L[i : j + 1].min()
            stop = ext + TICK if side == "short" else ext - TICK
            a = abs(stop - C[j]) / TICK
            rec = {"side": side, "A": a, "sweep_bar": (H[i] - L[i]) / TICK, "B": np.nan}
            # last fractal swing on the other side before the sweep bar
            sw_lvl = None
            for k in range(i - 1, max(0, i - mss_lookback), -1):
                if k - 1 < 0 or k + 1 >= n:
                    continue
                if side == "short" and L[k] < L[k - 1] and L[k] < L[k + 1]:
                    sw_lvl = L[k]
                    break
                if side == "long" and H[k] > H[k - 1] and H[k] > H[k + 1]:
                    sw_lvl = H[k]
                    break
            if sw_lvl is not None:
                for m in range(j, min(n, j + mss_max)):
                    beyond = H[m] > ext if side == "short" else L[m] < ext
                    if beyond and m > j:
                        break
                    if (side == "short" and C[m] < sw_lvl) or (side == "long" and C[m] > sw_lvl):
                        rec["B"] = abs(stop - C[m]) / TICK
                        break
            out.append(rec)
            return out  # first sweep of the window only
    return out


def sweep_stats(b: pd.DataFrame) -> None:
    days = sorted({d for d, wd in zip(b["day"], b["wd"], strict=True) if wd < 5})
    res = {
        "London (sweep of Asian range 20:00-00:00)": [],
        "NY AM 09:30-11:00 (sweep of London 02:00-05:00 range)": [],
        "Silver Bullet 10-11 (sweep of 09:30-10:00 range)": [],
    }
    for d in days:
        prev = d - pd.Timedelta(days=1)
        asian = b[(b["day"] == prev) & (b["t"] >= time(20))]
        lon = _window(b, d, (time(2), time(5)))
        ny = _window(b, d, (time(9, 30), time(11)))
        orng = _window(b, d, (time(9, 30), time(10)))
        sb = _window(b, d, (time(10), time(11)))
        if (
            len(asian) > 100
            and len(lon) > 90
            and asian["instrument_id"].nunique() == 1
            and (lon["instrument_id"] == asian["instrument_id"].iloc[0]).all()
        ):
            res["London (sweep of Asian range 20:00-00:00)"] += _scan(
                lon, asian.high.max(), asian.low.min()
            )
        if (
            len(lon) > 90
            and len(ny) > 45
            and lon["instrument_id"].iloc[0] == ny["instrument_id"].iloc[0]
        ):
            res["NY AM 09:30-11:00 (sweep of London 02:00-05:00 range)"] += _scan(
                ny, lon.high.max(), lon.low.min()
            )
        if len(orng) > 20 and len(sb) > 30:
            res["Silver Bullet 10-11 (sweep of 09:30-10:00 range)"] += _scan(
                sb, orng.high.max(), orng.low.min()
            )
    print("\n## Sweep-and-reverse stop distance (ohlcv-1m proxy, ticks)\n")
    print(
        "| setup proxy | days with a sweep | sweep-bar range p50/p75/p90 | stop A (enter on close-back) p50/p75/p90 "
        "| MSS confirmed | stop B (enter on MSS close) p50/p75/p90 |"
    )
    print("|---|---:|---:|---:|---:|---:|")
    for k, v in res.items():
        df = pd.DataFrame(v)
        print(
            f"| {k} | {len(df)} | {fmt(q(df.sweep_bar), 0)} | {fmt(q(df.A), 0)} | "
            f"{df.B.notna().sum()} | {fmt(q(df.B), 0)} |"
        )
    # Generic, level-free: 1m bar takes out the prior 15-bar high/low by >=1 tick and closes back.
    print(
        "\n### Generic local sweep (prior 15-bar high/low taken by >=1 tick, closes back inside)\n"
    )
    print(
        "| window | events/day | sweep-bar range p50/p75/p90 | stop (close -> extreme+1 tick) p50/p75/p90 |"
    )
    print("|---|---:|---:|---:|")
    for name, w in WIN.items():
        stops, rngs, nd = [], [], 0
        for d in days:
            s = _window(b, d, w)
            if len(s) < 30:
                continue
            nd += 1
            H, L, C = s.high.to_numpy(), s.low.to_numpy(), s.close.to_numpy()
            for i in range(15, len(s)):
                ph, pl = H[i - 15 : i].max(), L[i - 15 : i].min()
                if H[i] >= ph + TICK and C[i] < ph:
                    stops.append((H[i] + TICK - C[i]) / TICK)
                    rngs.append((H[i] - L[i]) / TICK)
                if L[i] <= pl - TICK and C[i] > pl:
                    stops.append((C[i] - L[i] + TICK) / TICK)
                    rngs.append((H[i] - L[i]) / TICK)
        print(f"| {name} | {len(stops) / nd:.1f} | {fmt(q(rngs), 0)} | {fmt(q(stops), 0)} |")
    globals()["SWEEPS"] = res


# ---------------------------------------------------------------- top of book (bbo-1s)
def bbo_stats() -> None:
    frames = []
    for d in TICK_DAYS:
        for w in ("london", "nyam"):
            f = load(f"bbo1s_{w}_{d:%Y%m%d}.dbn.zst")
            frames.append(f[["bid_px_00", "ask_px_00", "bid_sz_00", "ask_sz_00"]])
    df = pd.concat(frames)
    df = df[(df.bid_px_00 > 0) & (df.ask_px_00 > df.bid_px_00)]
    df["spread"] = (df.ask_px_00 - df.bid_px_00) / TICK
    print("\n## Top of book, sampled every second (bbo-1s, 10 days 2026-10-16..29)\n")
    print(
        "| window | seconds | spread ticks p50/p75/p90/p99 | % time spread > 1 tick | mean spread | "
        "bid size p50 (p10) | ask size p50 (p10) | % time touch size < N lots, N=1..5 (bid/ask avg) |"
    )
    print("|---|---:|---:|---:|---:|---:|---:|---|")
    for name, w in WIN.items():
        s = df[in_win(df.index, w)]
        lt = " / ".join(
            f"{((s.ask_sz_00 < n).mean() + (s.bid_sz_00 < n).mean()) * 50:.0f}" for n in range(1, 6)
        )
        print(
            f"| {name} | {len(s)} | {fmt(q(s.spread, (0.5, 0.75, 0.9, 0.99)), 0)} | "
            f"{(s.spread > 1).mean() * 100:.1f} | {s.spread.mean():.2f} | "
            f"{s.bid_sz_00.median():.0f} ({s.bid_sz_00.quantile(0.1):.0f}) | "
            f"{s.ask_sz_00.median():.0f} ({s.ask_sz_00.quantile(0.1):.0f}) | {lt} |"
        )
    print(
        "\n(last column: % of seconds where the touch on a side shows fewer than N lots, N = 1..5, "
        "averaged over bid and ask; N=1 means the side is empty)"
    )


# ---------------------------------------------------------------- trades and stop slippage (tbbo)
def tbbo_stats(b: pd.DataFrame) -> None:
    files = {
        "London 02:00-05:00": [f"tbbo_london_{d:%Y%m%d}.dbn.zst" for d in TICK_DAYS],
        "NY AM 09:30-11:00": ["tbbo_nyam_20261027.dbn.zst", "tbbo_nyam_20261028.dbn.zst"],
    }
    print("\n## Trades and spread at trade time (tbbo)\n")
    print(
        "| window | days | trades/min mean | contracts/min mean | median trade size | "
        "spread before trade p50/p90 ticks | % trades with spread > 1 tick |"
    )
    print("|---|---:|---:|---:|---:|---:|---:|")
    tb = {}
    for name, fs in files.items():
        t = pd.concat([load(f) for f in fs])
        t = t[t.action == "T"]
        tb[name] = t
        mins = len(fs) * (180 if name.startswith("London") else 90)
        sp = (t.ask_px_00 - t.bid_px_00) / TICK
        sp = sp[(t.bid_px_00 > 0) & (t.ask_px_00 > 0)]
        print(
            f"| {name} | {len(fs)} | {len(t) / mins:.0f} | {t['size'].sum() / mins:.0f} | "
            f"{t['size'].median():.0f} | {fmt(q(sp, (0.5, 0.9)), 0)} | {(sp > 1).mean() * 100:.1f} |"
        )
        if name.startswith("NY"):
            sbm = in_win(t.index, (time(10), time(11)))
            ts = t[sbm]
            print(
                f"| Silver Bullet 10:00-11:00 | 2 | {len(ts) / 120:.0f} | {ts['size'].sum() / 120:.0f} | "
                f"{ts['size'].median():.0f} | {fmt(q(sp[sbm], (0.5, 0.9)), 0)} | "
                f"{(sp[sbm] > 1).mean() * 100:.1f} |"
            )

    print("\n## Stop-order slippage when a fresh 15-minute high/low is taken (tbbo)\n")
    print(
        "Event: first trade in a minute at or beyond (prior-15-bar extreme + 1 tick) = a resting "
        "stop at S is elected. Gap = trigger trade price beyond S. Fill for N lots = walk the "
        "post-trigger touch (BBO of the first tbbo record from a later matching event; size beyond the touch assumed 1 tick worse per "
        "touch-size). Slippage = fill - S in ticks.\n"
    )
    print(
        "| window | events | trigger gap ticks p50/p90/max | triggering order runs past S, ticks p50/p90/max | N=1 slip mean / p90 | N=3 slip mean / p90 | "
        "N=5 slip mean / p90 | % events: touch < 5 lots after trigger |"
    )
    print("|---|---:|---:|---:|---:|---:|---:|---:|")
    bars_utc = b.copy()
    bars_utc.index = bars_utc.index.tz_convert("UTC")
    for name, t in tb.items():
        # Keep file order (sequence order); ts_recv ties make sort_index unsafe.
        tev = t.ts_event.to_numpy()
        # index of the first record from a later matching event than record i: the
        # book a just-elected stop order meets once the triggering order is done.
        nxt = np.empty(len(t), dtype=np.int64)
        j = len(t) - 1
        for k in range(len(t) - 1, -1, -1):
            if k == len(t) - 1 or tev[k + 1] != tev[k]:
                j = k + 1
            nxt[k] = min(j, len(t) - 1)
        px, ask, bid = t.price.to_numpy(), t.ask_px_00.to_numpy(), t.bid_px_00.to_numpy()
        asz, bsz = t.ask_sz_00.to_numpy(), t.bid_sz_00.to_numpy()
        minute = t.index.floor("1min")
        hh = bars_utc["high"].rolling(15).max().shift(1)
        ll = bars_utc["low"].rolling(15).min().shift(1)
        lvl_h = hh.reindex(minute).to_numpy()
        lvl_l = ll.reindex(minute).to_numpy()
        gaps, sweeps, slips = [], [], {1: [], 3: [], 5: []}
        thin = 0
        mins_arr = minute.to_numpy()
        seen = set()
        for i in range(len(t) - 1):
            for side in ("buy", "sell"):
                key = (mins_arr[i], side)
                if key in seen:
                    continue
                if side == "buy" and not np.isnan(lvl_h[i]) and px[i] >= lvl_h[i] + TICK:
                    S = lvl_h[i] + TICK
                    gap = (px[i] - S) / TICK
                    top, sz, sgn = ask[nxt[i]], asz[nxt[i]], 1
                elif side == "sell" and not np.isnan(lvl_l[i]) and px[i] <= lvl_l[i] - TICK:
                    S = lvl_l[i] - TICK
                    gap = (S - px[i]) / TICK
                    top, sz, sgn = bid[nxt[i]], bsz[nxt[i]], -1
                else:
                    continue
                seen.add(key)
                gaps.append(gap)
                ev = px[i : max(nxt[i], i + 1)]
                sweeps.append((ev.max() - S) / TICK if sgn > 0 else (S - ev.min()) / TICK)
                thin += sz < 5
                for n in (1, 3, 5):
                    # walk: fill min(n, sz) at top, then each further touch-size chunk 1 tick worse
                    rem, cost, lvl = n, 0.0, 0
                    size = max(int(sz), 1)
                    while rem > 0:
                        f = min(rem, size)
                        cost += f * (top + sgn * lvl * TICK)
                        rem -= f
                        lvl += 1
                    fill = cost / n
                    slips[n].append(sgn * (fill - S) / TICK)
        g = np.array(gaps)
        print(
            f"| {name} | {len(g)} | {np.median(g):.0f} / {np.quantile(g, 0.9):.0f} / {g.max():.0f} | "
            + f"{np.median(sweeps):.0f} / {np.quantile(sweeps, 0.9):.0f} / {np.max(sweeps):.0f} | "
            + " | ".join(
                f"{np.mean(slips[n]):.2f} / {np.quantile(slips[n], 0.9):.0f}" for n in (1, 3, 5)
            )
            + f" | {thin / len(g) * 100:.0f} |"
        )


# ---------------------------------------------------------------- depth (mbp-10)
def depth_stats() -> None:
    print(
        "\n## Depth and market-order walk (mbp-10, 2026-10-28, London 03:00-03:15 and NY 10:00-10:05)\n"
    )
    print(
        "| window | seconds | cum. size within 1 / 3 / 5 levels (median, per side) | "
        "market buy N=1/3/5/10/20 slippage vs touch, mean ticks | N=5 / N=20 p90 | vs mid, N=1 / N=5 mean ticks |"
    )
    print("|---|---:|---:|---:|---:|---:|")
    for name, f in (
        ("London 03:00-03:15", "mbp10_london_20261028_0300.dbn.zst"),
        ("NY AM 10:00-10:05", "mbp10_nyam_20261028_1000_5m.dbn.zst"),
    ):
        d = load(f)
        d = d.groupby(d.index.floor("1s")).last()  # book at the end of each second
        ap = d[[f"ask_px_{i:02d}" for i in range(10)]].to_numpy()
        az = d[[f"ask_sz_{i:02d}" for i in range(10)]].to_numpy()
        bp = d[[f"bid_px_{i:02d}" for i in range(10)]].to_numpy()
        bz = d[[f"bid_sz_{i:02d}" for i in range(10)]].to_numpy()
        sp = (ap[:, 0] - bp[:, 0]) / TICK
        print(
            f"<!-- mbp-10 cross-check {name}: spread p50 {np.median(sp):.0f}, % > 1 tick {(sp > 1).mean() * 100:.0f} -->"
        )
        cum = {
            k: np.median(np.concatenate([az[:, :k].sum(1), bz[:, :k].sum(1)])) for k in (1, 3, 5)
        }
        res, vm = {}, {}
        for n in (1, 3, 5, 10, 20):
            sl, slm = [], []
            for r in range(len(d)):
                rem, cost = n, 0.0
                for lv in range(10):
                    f_ = min(rem, az[r, lv])
                    cost += f_ * ap[r, lv]
                    rem -= f_
                    if rem == 0:
                        break
                if rem:
                    continue
                sl.append((cost / n - ap[r, 0]) / TICK)
                slm.append((cost / n - (ap[r, 0] + bp[r, 0]) / 2) / TICK)
            res[n], vm[n] = np.array(sl), np.array(slm)
        print(
            f"| {name} | {len(d)} | {cum[1]:.0f} / {cum[3]:.0f} / {cum[5]:.0f} | "
            + " / ".join(f"{res[n].mean():.2f}" for n in (1, 3, 5, 10, 20))
            + f" | {np.quantile(res[5], 0.9):.2f} / {np.quantile(res[20], 0.9):.2f} | {vm[1].mean():.2f} / {vm[5].mean():.2f} |"
        )


def entry_stats(b: pd.DataFrame) -> None:
    """Market entry at a 1m bar close: what the touch looks like at that instant.

    Uses the bbo-1s record stamped exactly at the minute boundary (BBO at the
    close of the bar that just ended) and the bar's close / next bar's open.
    Buy cost = ask - reference; sell cost = reference - bid, pooled.
    """
    frames = []
    for d in TICK_DAYS:
        for w in ("london", "nyam"):
            frames.append(load(f"bbo1s_{w}_{d:%Y%m%d}.dbn.zst"))
    q1 = pd.concat(frames)
    q1 = q1[q1.index.second == 0]
    q1.index = q1.index.tz_convert(NYTZ)
    close = b["close"].shift(1).reindex(q1.index)  # bar that ended at this boundary
    nxt_open = b["open"].reindex(q1.index)  # bar that starts at this boundary
    print("\n## Market entry at a bar close (bbo-1s at minute boundaries, 10 days)\n")
    print(
        "(Pooled over buys and sells the mean equals the half-spread by construction; the p90 is the "
        "one-sided cost a single fill can see.)\n"
    )
    print(
        "| window | boundaries | half-spread ticks mean | buy at ask vs bar close, mean / p90 ticks | "
        "buy at ask vs next bar open, mean / p90 ticks |"
    )
    print("|---|---:|---:|---:|---:|")
    for name, w in WIN.items():
        m = in_win(q1.index, w)
        s = q1[m]
        c, o = close[m], nxt_open[m]
        buy_c = (s.ask_px_00 - c) / TICK
        sell_c = (c - s.bid_px_00) / TICK
        buy_o = (s.ask_px_00 - o) / TICK
        sell_o = (o - s.bid_px_00) / TICK
        vc = pd.concat([buy_c, sell_c]).dropna()
        vo = pd.concat([buy_o, sell_o]).dropna()
        hs = ((s.ask_px_00 - s.bid_px_00) / TICK / 2).mean()
        print(
            f"| {name} | {len(s)} | {hs:.2f} | {vc.mean():.2f} / {vc.quantile(0.9):.0f} | "
            f"{vo.mean():.2f} / {vo.quantile(0.9):.0f} |"
        )


def costs() -> None:
    rt_comm = 2 * COMMISSION_SIDE / TICK_USD
    print(
        f"\nRound-trip commission: 2 x ${COMMISSION_SIDE} = ${2 * COMMISSION_SIDE:.2f} = {rt_comm:.2f} ticks per contract"
    )


if __name__ == "__main__":
    pd.set_option("display.width", 200)
    b = bars()
    bar_stats(b)
    sweep_stats(b)
    bbo_stats()
    tbbo_stats(b)
    entry_stats(b)
    depth_stats()
    costs()
