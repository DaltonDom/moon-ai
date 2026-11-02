"""`moon-ai study`: quick checks of CM's timing and bias claims on MNQ history.

Each study asks one yes/no question of the 1-minute bars and prints the
observed rate next to what chance would give, with a 95% interval, so you can
see which of the mentor's ideas show up on Nasdaq at all before any of them
becomes a trading rule. They're event studies, not trades: no costs and no
entries, except the engineered-candle study, which simulates its scalp with
the bot's costs. Times are New York wall clock (CM's sheet says "UTC-5"; that
matches New York in winter). The last 6 months stay out (the holdout).

Studies (CM's claim in brackets; sources in moon-ai-notes/distilled):
- midnight_open: 09:30 price vs the 00:00 open -> 09:30-11:00 direction
  [buy below the midnight open, sell above it]
- ons_hunt: the 04:00-08:15 overnight range (ONS) -> is a side taken 08:15-09:45,
  and does the first side taken reverse [the liquidity-hunt macro]
- four_hour: outside / inside 4-hour candles (17/21/01/05/09/13 NY) -> the next
  candle's size and direction [outside -> reversal, inside -> expansion]
- prior_high_taker: the candle that takes the prior day's high (up or down)
  -> next day's direction [up candle -> higher, down candle -> deep sell-off]
- offset_turn: is the 09:30-11:00 high or low made in 09:45-10:00 more often
  than time alone predicts [the offset macro]
- engineered_candle: after a 5-minute body closes beyond the ONS range, buy the
  next candle's low (sell its high), target its other end, 20-point stop
  [the engineered-candle scalp]
"""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path

import polars as pl

NY = "America/New_York"
Z = 1.96


def load(store_root: Path, symbol: str, start: date, end: date, dataset: str) -> pl.DataFrame:
    """1-minute bars [start, end) as a frame with New York clock columns.

    Keeps the day's front contract only (the instrument with most bars per
    trading day), so rolls don't create fake gaps.
    """
    folder = Path(store_root) / dataset / "ohlcv-1m" / symbol
    paths = sorted(folder.glob("*.parquet"))
    if not paths:
        return pl.DataFrame()
    df = (
        pl.concat([pl.read_parquet(p) for p in paths], how="diagonal_relaxed")
        .select("ts_event", "open", "high", "low", "close", "instrument_id")
        .unique(subset=["ts_event"], keep="last")
        .sort("ts_event")
    )
    return frame(df, start, end)


def frame(df: pl.DataFrame, start: date, end: date) -> pl.DataFrame:
    ny = pl.col("ts_event").dt.convert_time_zone(NY)
    df = df.with_columns(
        ny=ny,
        nyd=ny.dt.date(),
        hm=ny.dt.hour().cast(pl.Int32) * 60 + ny.dt.minute().cast(pl.Int32),
    ).with_columns(
        # CME trading day: 18:00 New York opens the next day's session.
        tday=pl.when(pl.col("hm") >= 18 * 60)
        .then(pl.col("nyd") + pl.duration(days=1))
        .otherwise(pl.col("nyd"))
    )
    df = df.filter((pl.col("tday") >= start) & (pl.col("tday") < end))
    front = (
        df.group_by("tday", "instrument_id")
        .len()
        .sort("len", descending=True)
        .unique(subset=["tday"], keep="first")
        .select("tday", "instrument_id")
    )
    return df.join(front, on=["tday", "instrument_id"]).sort("ts_event")


def window(df: pl.DataFrame, a: str, b: str) -> pl.DataFrame:
    """Bars opening in [a, b) New York time, e.g. window(df, "04:00", "08:15")."""
    h1, m1 = map(int, a.split(":"))
    h2, m2 = map(int, b.split(":"))
    return df.filter((pl.col("hm") >= h1 * 60 + m1) & (pl.col("hm") < h2 * 60 + m2))


def rate(k: int, n: int) -> str:
    """'k/n = p% (lo-hi%)' with a Wilson 95% interval."""
    if n == 0:
        return "no cases"
    p = k / n
    d = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / d
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return f"{k}/{n} = {p:.0%} ({c - h:.0%}-{c + h:.0%})"


def _per_day(df: pl.DataFrame, a: str, b: str) -> pl.DataFrame:
    """Open, high, low, close of [a, b) per trading day (weekdays with bars)."""
    return (
        window(df, a, b)
        .group_by("tday")
        .agg(
            o=pl.col("open").first(),
            h=pl.col("high").max(),
            l=pl.col("low").min(),
            c=pl.col("close").last(),
            n=pl.len(),
        )
        .sort("tday")
    )


# --- studies -------------------------------------------------------------------------


def midnight_open(df: pl.DataFrame) -> list[str]:
    mid = _per_day(df, "00:00", "00:01").select("tday", mid="o")
    am = _per_day(df, "09:30", "11:00").filter(pl.col("n") >= 80)
    d = am.join(mid, on="tday").with_columns(below=pl.col("o") < pl.col("mid"))
    out = ["CM: buy below the midnight open, sell above it. 09:30-11:00 direction:"]
    for below, side, want in ((True, "below", "up"), (False, "above", "down")):
        g = d.filter(pl.col("below") == below)
        k = g.filter((pl.col("c") > pl.col("o")) if want == "up" else (pl.col("c") < pl.col("o")))
        out.append(f"  09:30 {side} midnight open -> 11:00 {want}: {rate(k.height, g.height)}")
    up_all = d.filter(pl.col("c") > pl.col("o")).height
    out.append(f"  any day -> 11:00 up (base rate): {rate(up_all, d.height)}")
    return out


def ons_hunt(df: pl.DataFrame) -> list[str]:
    ons = _per_day(df, "04:00", "08:15").filter(pl.col("n") >= 200).select("tday", oh="h", ol="l")
    hunt = window(df, "08:15", "09:45").join(ons, on="tday")
    first = (
        hunt.with_columns(up=pl.col("high") > pl.col("oh"), dn=pl.col("low") < pl.col("ol"))
        .filter(pl.col("up") | pl.col("dn"))
        .sort("ts_event")
        .group_by("tday", maintain_order=True)
        .agg(pl.col("up").first(), pl.col("dn").first())
    )
    after = _per_day(df, "09:45", "11:00").select("tday", c11="c")
    mid = ons.with_columns(m=(pl.col("oh") + pl.col("ol")) / 2)
    j = first.join(mid, on="tday").join(after, on="tday")
    n = ons.height
    took = first.height
    out = [
        "CM: 08:15-09:45 runs the overnight (04:00-08:15) highs or lows, then expands.",
        f"  a side of the overnight range taken 08:15-09:45: {rate(took, n)}",
    ]
    hi_first = j.filter(pl.col("up") & ~pl.col("dn"))
    lo_first = j.filter(pl.col("dn") & ~pl.col("up"))
    out.append(
        "  high taken first -> 11:00 close back below the overnight 50%: "
        + rate(hi_first.filter(pl.col("c11") < pl.col("m")).height, hi_first.height)
    )
    out.append(
        "  low taken first -> 11:00 close back above the overnight 50%: "
        + rate(lo_first.filter(pl.col("c11") > pl.col("m")).height, lo_first.height)
    )
    return out


def four_hour(df: pl.DataFrame) -> list[str]:
    anchor = 17 * 60  # CM's 4-hour grid: 17, 21, 01, 05, 09, 13 New York
    k = (
        df.with_columns(
            block=(
                (pl.col("ny").dt.replace_time_zone(None) - pl.duration(minutes=anchor)).dt.truncate(
                    "4h"
                )
            )
        )
        .group_by("block")
        .agg(
            o=pl.col("open").first(),
            h=pl.col("high").max(),
            l=pl.col("low").min(),
            c=pl.col("close").last(),
            n=pl.len(),
        )
        .filter(pl.col("n") >= 180)
        .sort("block")
        .with_columns(
            ph=pl.col("h").shift(1),
            pl_=pl.col("l").shift(1),
            rng=pl.col("h") - pl.col("l"),
            nxt_rng=(pl.col("h") - pl.col("l")).shift(-1),
            dir=pl.col("c") > pl.col("o"),
            nxt_dir=(pl.col("c") > pl.col("o")).shift(-1),
        )
        .drop_nulls()
    )
    med = k["rng"].median()
    outside = k.filter((pl.col("h") > pl.col("ph")) & (pl.col("l") < pl.col("pl_")))
    inside = k.filter((pl.col("h") < pl.col("ph")) & (pl.col("l") > pl.col("pl_")))
    out = ["CM: an outside 4-hour candle -> reversal next; an inside one -> expansion next."]
    rev = outside.filter(pl.col("dir") != pl.col("nxt_dir")).height
    out.append(
        f"  after an outside candle, the next closes the other way: {rate(rev, outside.height)}"
    )
    base = k.filter(pl.col("dir") != pl.col("nxt_dir")).height
    out.append(f"  any candle, the next closes the other way (base rate): {rate(base, k.height)}")
    big_in = inside.filter(pl.col("nxt_rng") > med).height
    out.append(
        "  after an inside candle, the next is bigger than the median: "
        + rate(big_in, inside.height)
    )
    big = k.filter(pl.col("nxt_rng") > med).height
    out.append(
        f"  any candle, the next is bigger than the median (base rate): {rate(big, k.height)}"
    )
    return out


def prior_high_taker(df: pl.DataFrame) -> list[str]:
    d = (
        df.group_by("tday")
        .agg(
            o=pl.col("open").first(),
            h=pl.col("high").max(),
            l=pl.col("low").min(),
            c=pl.col("close").last(),
            n=pl.len(),
        )
        .filter(pl.col("n") >= 800)
        .sort("tday")
        .with_columns(
            ph=pl.col("h").shift(1),
            nxt_up=(pl.col("c") > pl.col("o")).shift(-1),
        )
        .drop_nulls()
    )
    took = d.filter(pl.col("h") > pl.col("ph"))
    up_day = took.filter(pl.col("c") > pl.col("o"))
    dn_day = took.filter(pl.col("c") <= pl.col("o"))
    return [
        "CM: if an up day takes the prior high, expect higher; a down day, a sell-off.",
        "  up day took the prior high -> next day up: "
        + rate(up_day.filter(pl.col("nxt_up")).height, up_day.height),
        "  down day took the prior high -> next day down: "
        + rate(dn_day.filter(~pl.col("nxt_up")).height, dn_day.height),
        "  any day -> next day up (base rate): "
        + rate(d.filter(pl.col("nxt_up")).height, d.height),
    ]


def offset_turn(df: pl.DataFrame) -> list[str]:
    am = window(df, "09:30", "11:00")
    ext = (
        am.group_by("tday")
        .agg(
            hi_t=pl.col("hm").sort_by("high", descending=True).first(),
            lo_t=pl.col("hm").sort_by("low").first(),
            n=pl.len(),
        )
        .filter(pl.col("n") >= 80)
    )

    def share(a: int, b: int) -> int:
        return ext.filter(
            pl.col("hi_t").is_between(a, b, closed="left")
            | pl.col("lo_t").is_between(a, b, closed="left")
        ).height

    return [
        "CM: the 09:45-10:00 offset macro makes a turn (a high or low of 09:30-11:00).",
        "  09:30-11:00 high or low made 09:45-10:00: " + rate(share(585, 600), ext.height),
        "  same-length comparison slot 10:15-10:30: " + rate(share(615, 630), ext.height),
    ]


def engineered_candle(
    df: pl.DataFrame, stop_pts: float = 20.0, min_target: float = 20.0, cost_pts: float = 1.75
) -> list[str]:
    """Simulated scalp. cost_pts: $1/side commission (1 pt round trip on MNQ at $2/pt)
    plus 3 ticks of stop slippage on losers, rounded to 1.75 pts per trade."""
    ons = _per_day(df, "04:00", "08:15").filter(pl.col("n") >= 200).select("tday", oh="h", ol="l")
    rs: list[float] = []
    skipped = 0
    for _day, g in window(df, "08:15", "11:00").join(ons, on="tday").group_by("tday"):
        g = g.sort("ts_event")
        five = (
            g.with_columns(b=pl.col("ts_event").dt.truncate("5m"))
            .group_by("b", maintain_order=True)
            .agg(
                o=pl.col("open").first(),
                h=pl.col("high").max(),
                l=pl.col("low").min(),
                c=pl.col("close").last(),
                oh=pl.col("oh").first(),
                ol=pl.col("ol").first(),
            )
        )
        rows = five.rows(named=True)
        for i in range(len(rows) - 1):
            r = rows[i]
            bull, bear = r["c"] > r["oh"], r["c"] < r["ol"]  # a body close beyond the range
            if not (bull or bear):
                continue
            eo = rows[i + 1]
            entry, target = (eo["l"], eo["h"]) if bull else (eo["h"], eo["l"])
            if abs(target - entry) < min_target:
                skipped += 1
                break
            stop = entry - stop_pts if bull else entry + stop_pts
            later = g.filter(pl.col("ts_event") >= eo["b"] + timedelta(minutes=5))
            r_ = _walk(later, bull, entry, stop, target)
            if r_ is not None:
                rs.append((r_ * stop_pts - cost_pts) / stop_pts)
            break  # one per day
    n = len(rs)
    if not n:
        return ["Engineered-candle scalp: no trades."]
    wins = sum(r > 0 for r in rs)
    return [
        f"CM: after a 5-minute body closes beyond the overnight range, fade to the next "
        f"candle's other end ({stop_pts:.0f}-pt stop, skip targets under {min_target:.0f} pts).",
        f"  trades {n} (skipped {skipped} as too small) | win rate {rate(wins, n)}",
        f"  average {sum(rs) / n:+.3f}R per trade after about {cost_pts} pts of costs",
    ]


def _walk(bars: pl.DataFrame, bull: bool, entry: float, stop: float, target: float) -> float | None:
    """R of one limit trade on 1-minute bars: fill at entry, then stop or target
    (a bar touching both counts as the stop). None if never filled."""
    filled = False
    for h, lo in bars.select("high", "low").iter_rows():
        if not filled:
            if (lo <= entry) if bull else (h >= entry):
                filled = True
            else:
                continue
        hit_stop = (lo <= stop) if bull else (h >= stop)
        hit_tgt = (h >= target) if bull else (lo <= target)
        if hit_stop:
            return -1.0
        if hit_tgt:
            return abs(target - entry) / abs(entry - stop)
    if not filled:
        return None
    last = bars["close"][-1]
    return ((last - entry) if bull else (entry - last)) / abs(entry - stop)


STUDIES: dict[str, Callable[[pl.DataFrame], list[str]]] = {
    "midnight_open": midnight_open,
    "ons_hunt": ons_hunt,
    "four_hour": four_hour,
    "prior_high_taker": prior_high_taker,
    "offset_turn": offset_turn,
    "engineered_candle": engineered_candle,
}
