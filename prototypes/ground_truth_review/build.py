"""PROTOTYPE (throwaway, ticket #11): build a ground-truth review page.

    uv run python prototypes/ground_truth_review/build.py <bars.parquet> 2026-10-27 2026-10-28 ...

Writes prototypes/ground_truth_review/review.html (double-click to open) with:
- a 1m candle chart of each day's 07:00-11:30 ET window,
- detected "chains" (sweep -> MSS -> displacement FVG), one card each, with
  agree / disagree / unsure buttons and a note,
- click-a-candle to add a setup the detectors missed,
- an Export button (JSON verdicts) and a per-day TradingView Pine overlay.
Nothing is persisted: export before closing the tab.
"""

from __future__ import annotations

import json
import sys
from datetime import time
from pathlib import Path

from load import detect, load_bars

from moon_ai.sessions import to_ny

WIN = (time(7), time(11, 30))
HERE = Path(__file__).parent


def iso(ts) -> str:
    return to_ny(ts).strftime("%Y-%m-%dT%H:%M")


def build_day(bars, d, day: str) -> dict:
    idx = [i for i, b in enumerate(bars)
           if str(to_ny(b.ts_open).date()) == day and WIN[0] <= to_ny(b.ts_open).time() < WIN[1]]
    lo, hi = idx[0], idx[-1]
    first_ts = bars[lo].ts_open
    candles = [dict(t=iso(b.ts_open), o=b.open, h=b.high, l=b.low, c=b.close) for b in bars[lo:hi + 1]]

    # Context pools known before the window opens: the latest of each source.
    pools = []
    for lv in d["levels"]["pool"]:
        if lv.known_at <= first_ts:
            pools.append(lv)
    latest = {}
    for lv in pools:
        key = (lv.source, lv.kind)
        if key not in latest or lv.known_at > latest[key].known_at:
            latest[key] = lv
    context = [dict(name=f"{s} {k}", price=lv.price) for (s, k), lv in sorted(latest.items())]

    # Chains: an MSS with a same-direction displacement between its sweep and 2 bars after.
    # Several sweeps can produce the same MSS bar; merge them into one chain.
    chains: dict[tuple[int, str], dict] = {}
    for m in d["mss"]:
        if not lo <= m.index <= hi:
            continue
        disp = [x for x in d["disp"] if x.direction == m.direction and m.sweep.index <= x.index <= m.index + 2]
        if not disp:
            continue
        x = disp[0]
        gap = next(g for g in d["fvgs"] if g.index == x.index and g.direction == x.direction)
        key = (m.index, m.direction)
        ch = chains.setdefault(key, dict(
            id=f"{day}-{to_ny(m.ts).strftime('%H%M')}-{m.direction}",
            direction=m.direction,
            mss=dict(t=iso(m.ts), price=m.broken_swing.price, swing_t=iso(m.broken_swing.ts)),
            disp=dict(t=iso(x.ts), body=x.body, atr=round(x.atr, 2)),
            fvg=dict(t=iso(gap.ts), low=gap.low, high=gap.high),
            sweeps=[],
        ))
        s = m.sweep
        ch["sweeps"].append(dict(t=iso(bars[s.index].ts_open), level=s.level.price, source=s.level.source, kind=s.kind,
                                 level_t=iso(s.level.known_at), extreme=s.extreme))
    for ch in chains.values():
        ch["sweeps"].sort(key=lambda s: s["t"])

    in_win = lambda i: lo <= i <= hi  # noqa: E731
    counts = dict(
        swing_sweeps=sum(in_win(s.index) for s in d["sweeps"]["swing"]),
        pool_sweeps=sum(in_win(s.index) for s in d["sweeps"]["pool"]),
        mss=sum(in_win(m.index) for m in d["mss"]),
        fvgs=sum(in_win(g.index) for g in d["fvgs"]),
        displacements=sum(in_win(x.index) for x in d["disp"]),
    )
    raw = dict(
        fvgs=[dict(t=iso(g.ts), low=g.low, high=g.high, dir=g.direction) for g in d["fvgs"] if in_win(g.index)],
        sweeps=[dict(t=iso(bars[s.index].ts_open), level=s.level.price, kind=s.kind, source=s.level.source)
                for s in d["sweeps"]["swing"] + d["sweeps"]["pool"] if in_win(s.index)],
    )
    return dict(day=day, candles=candles, context=context,
                chains=sorted(chains.values(), key=lambda c: c["mss"]["t"]), counts=counts, raw=raw)


def pine(day: dict) -> str:
    def ts(t: str) -> str:
        y, mo, rest = t.split("-")
        dd, hm = rest.split("T")
        h, mi = hm.split(":")
        return f'timestamp("America/New_York", {int(y)}, {int(mo)}, {int(dd)}, {int(h)}, {int(mi)})'

    lines = [
        "//@version=5",
        f'indicator("moon-ai detections {day["day"]} (PROTOTYPE)", overlay=true, max_boxes_count=200, max_labels_count=200, max_lines_count=200)',
        "// Paste into the Pine editor on a 1-minute MNQ1! chart (no back-adjustment).",
        "var bool drawn = false",
        "if barstate.islast and not drawn",
        "    drawn := true",
    ]
    for c in day["context"]:
        lines.append(f'    line.new({ts(day["candles"][0]["t"])}, {c["price"]}, {ts(day["candles"][-1]["t"])}, {c["price"]}, xloc=xloc.bar_time, color=color.gray, style=line.style_dotted)')
        lines.append(f'    label.new({ts(day["candles"][0]["t"])}, {c["price"]}, "{c["name"]}", xloc=xloc.bar_time, style=label.style_none, textcolor=color.gray, size=size.small)')
    for n, ch in enumerate(day["chains"], 1):
        col = "color.teal" if ch["direction"] == "bull" else "color.red"
        f = ch["fvg"]
        lines.append(f'    box.new({ts(f["t"])}, {f["high"]}, {ts(f["t"])} + 10 * 60000, {f["low"]}, xloc=xloc.bar_time, bgcolor=color.new({col}, 75), border_color={col})')
        m = ch["mss"]
        lines.append(f'    line.new({ts(m["swing_t"])}, {m["price"]}, {ts(m["t"])}, {m["price"]}, xloc=xloc.bar_time, color={col}, width=2)')
        lines.append(f'    label.new({ts(m["t"])}, {m["price"]}, "#{n} MSS", xloc=xloc.bar_time, color={col}, textcolor=color.white, size=size.small)')
        for s in ch["sweeps"]:
            style = "label.style_label_down" if ch["direction"] == "bear" else "label.style_label_up"
            lines.append(f'    label.new({ts(s["t"])}, {s["extreme"]}, "#{n} sweep {s["level"]}", xloc=xloc.bar_time, style={style}, color=color.orange, textcolor=color.black, size=size.tiny)')
    return "\n".join(lines) + "\n"


def main() -> None:
    path, days = sys.argv[1], sys.argv[2:]
    bars = load_bars(path)
    d = detect(bars)
    data = [build_day(bars, d, day) for day in days]
    for day in data:
        day["pine"] = pine(day)
    html = (HERE / "template.html").read_text().replace("/*DATA*/null", json.dumps(data))
    (HERE / "review.html").write_text(html)
    for day in data:
        print(day["day"], "chains", len(day["chains"]), day["counts"])


if __name__ == "__main__":
    main()
