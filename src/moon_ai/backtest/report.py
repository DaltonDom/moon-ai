"""The report card: one self-contained HTML page per backtest run.

Plain language first (the dashboard rules from #12): dollars before R, each
check a tick or a cross with a one-line meaning, the account-growth chart
with its dips, the trade list, and the advanced numbers folded away. The
page is written into the run's folder, so it lives as long as the run.
"""

from __future__ import annotations

import html
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from moon_ai.backtest.evaluate import MIN_TRADES, Evaluation
from moon_ai.backtest.stats import Metrics
from moon_ai.data.news import NEWS_CSV, load_events
from moon_ai.journal import decode_json, read_run
from moon_ai.sessions import to_ny
from moon_ai.setups import load_setup_defaults

HOLDOUT_MONTHS = 6
SKIP_WORDS = {
    "skipped:ml": "low ML confidence",
    "skipped:cap": "already 2 trades that session",
    "skipped:blackout": "during big news",
    "skipped:london_min_stop": "London stop too small",
    "skipped:daily_stop": "daily stop already hit",
    "skipped:session": "holiday, roll or bad-data day",
    "skipped:busy": "a trade was already open",
    "skipped:kill_switch": "kill switch on",
    "skipped:size": "stop too wide for 1 contract",
    "unfilled": "price never reached the entry",
}


def holdout_start(today: date) -> date:
    """Start of the untouched holdout: the most recent 6 months."""
    return today - timedelta(days=round(HOLDOUT_MONTHS * 30.44))


def warnings_for(run: dict[str, Any], today: date, news_csv: Path = NEWS_CSV) -> list[str]:
    out = []
    notes = run.get("notes") or {}
    if notes.get("warning"):
        out.append(
            "Run without the news blackout, so these results are better than live trading would be."
        )
    elif news_csv.exists() and not any(e.event_type == "CPI" for e in load_events(news_csv)):
        out.append(
            "The news calendar doesn't have CPI, jobs-report or PPI times yet, so trades "
            "around those releases weren't blocked. Results are slightly optimistic."
        )
    start = holdout_start(today)
    if run["data_end"].date() > start:
        out.append(
            f"This run uses data from the untouched holdout (from {start}). That data is "
            "for final sign-off only; tune nothing on it."
        )
    return out


def _usd(x: float, sign: bool = True) -> str:
    s = "−" if x < 0 else ("+" if sign and x > 0 else "")
    return f"{s}${abs(x):,.0f}"


def _check(ok: bool | None, title: str, detail: str, meaning: str) -> str:
    mark, cls = {True: ("✓", "ok"), False: ("✕", "no"), None: ("…", "wait")}[ok]
    return (
        f'<div class="chk"><span class="mark {cls}">{mark}</span><div><b>{title}</b>'
        f'<span class="sub">{html.escape(meaning)}</span></div><span class="num">'
        f"{html.escape(detail)}</span></div>"
    )


def _dip_usd(trades: list[dict[str, Any]]) -> float:
    eq = peak = dip = 0.0
    for t in trades:
        eq += t["net_usd"]
        peak = max(peak, eq)
        dip = min(dip, eq - peak)
    return dip


def _chart(trades: list[dict[str, Any]]) -> str:
    if not trades:
        return '<p class="sub">No trades to chart.</p>'
    eq, peak, pts = 0.0, 0.0, [(0.0, 0.0)]
    for t in trades:
        eq += t["net_usd"]
        peak = max(peak, eq)
        pts.append((eq, eq - peak))
    w, h, top, main_h, gap, dd_h, left = 900, 280, 12, 170, 16, 60, 70
    lo, hi = min(0.0, *(p[0] for p in pts)), max(1.0, *(p[0] for p in pts))
    dmin = min(-1.0, *(p[1] for p in pts))
    x = lambda i: left + i / max(1, len(pts) - 1) * (w - left - 10)  # noqa: E731
    y = lambda v: top + (hi - v) / (hi - lo) * main_h  # noqa: E731
    yd = lambda v: top + main_h + gap + v / dmin * dd_h  # noqa: E731
    line = " ".join(f"{'M' if i == 0 else 'L'}{x(i):.1f},{y(p[0]):.1f}" for i, p in enumerate(pts))
    dd = (
        f"M{x(0):.1f},{yd(0):.1f} "
        + " ".join(f"L{x(i):.1f},{yd(p[1]):.1f}" for i, p in enumerate(pts))
        + f" L{x(len(pts) - 1):.1f},{yd(0):.1f} Z"
    )
    far = y(0) - y(hi) > 14  # only label the top when it isn't on top of $0
    hi_label = (
        f'<text x="{left - 8}" y="{y(hi) + 4:.1f}" text-anchor="end">{_usd(hi, False)}</text>'
        if far
        else ""
    )
    return f"""<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="Account growth and dips">
  <line x1="{left}" x2="{w - 10}" y1="{y(0):.1f}" y2="{y(0):.1f}" class="grid"/>
  {hi_label}
  <text x="{left - 8}" y="{y(0) + 4:.1f}" text-anchor="end">$0</text>
  <text x="{left - 8}" y="{y(lo) + 4:.1f}" text-anchor="end">{_usd(lo, False)}</text>
  <path d="{line}" class="eq"/>
  <path d="{dd}" class="dd"/>
  <text x="{left - 8}" y="{yd(dmin) + 4:.1f}" text-anchor="end">{_usd(dmin)}</text>
  <text x="{left}" y="{h - 2}">first trade</text>
  <text x="{w - 10}" y="{h - 2}" text-anchor="end">last trade</text>
</svg>"""


def render(
    ev: Evaluation, folder: Path, stress: Metrics | None = None, today: date | None = None
) -> Path:
    folder = Path(folder)
    today = today or date.today()
    run = decode_json(read_run(folder, "runs"), "runs")[0]
    cands = decode_json(read_run(folder, "candidates"), "candidates")
    trades = sorted(
        (t for t in decode_json(read_run(folder, "trades"), "trades") if t["net_usd"] is not None),
        key=lambda t: t["exit_time"],
    )
    by_id = {c["candidate_id"]: c for c in cands}
    m = ev.metrics
    title = load_setup_defaults()[ev.setup].title
    account = run["account_usd"] or 50_000.0
    start, end = run["data_start"].date(), run["data_end"].date() - timedelta(days=1)

    verdict_text = {
        "go-forward": (
            "Passes",
            "win",
            "It passed every check and can go forward to paper trading.",
        ),
        "fail": ("Doesn't pass", "loss", "It failed at least one check below."),
        "insufficient": (
            "Not enough trades yet",
            "amber",
            f"It needs at least {MIN_TRADES} trades before it can be judged.",
        ),
    }[ev.verdict]
    lo, hi = ev.edge_ci
    risk_usd = run["risk_per_trade_usd"] or account / 100
    checks = "".join(
        [
            _check(
                lo > 0 if lo == lo else False,
                "Beats random entries",
                "no trades to compare"
                if lo != lo
                else f"{_usd(lo * risk_usd)} to {_usd(hi * risk_usd)} per trade",
                "Compared with 1,000 sets of random trades in the same window with the same stops "
                "and targets. The whole range must be above $0.",
            ),
            _check(
                ev.dsr > 0.95,
                "Not just luck",
                f"{ev.dsr:.0%} sure (need 95%)",
                f"Allows for all {ev.n_trials} version(s) of this setup tried so far.",
            ),
            _check(
                m.trades >= MIN_TRADES,
                "Enough trades",
                f"{m.trades} of {MIN_TRADES}",
                "Fewer trades than this can't tell skill from chance.",
            ),
            _check(
                None if stress is None else stress.net_r > 0,
                "Still profitable with double costs",
                "not run yet" if stress is None else _usd(stress.net_usd),
                "A re-run with twice the slippage. Only run once the other checks pass.",
            ),
        ]
    )
    dip = _dip_usd(trades)
    pf = "no losses" if m.profit_factor == float("inf") else f"${m.profit_factor:.2f}"
    tiles = "".join(
        f'<div class="tile"><span class="t">{a}</span><b class="{c}">{b}</b>'
        f'<span class="sub">{d}</span></div>'
        for a, b, c, d in [
            (
                "Result",
                _usd(m.net_usd),
                "win" if m.net_usd > 0 else "loss",
                f"on a {_usd(account, False)} account",
            ),
            ("Trades", str(m.trades), "", f"won {m.win_rate:.0%}"),
            (
                "Average per trade",
                _usd(m.net_usd / m.trades) if m.trades else "–",
                "win" if m.expectancy_r > 0 else "loss",
                f"{m.expectancy_r:+.2f}R",
            ),
            ("Won per $1 lost", pf, "", "profit factor; above $1 makes money"),
            ("Biggest dip", _usd(dip), "loss", f"{abs(dip) / account:.1%} of the account"),
        ]
    )
    skipped = Counter(c["status"] for c in cands if c["status"] != "taken")
    skip_rows = "".join(f"<li>{n} × {SKIP_WORDS.get(s, s)}</li>" for s, n in skipped.most_common())
    trade_rows = "".join(
        f"<tr><td>{to_ny(t['entry_time']):%Y-%m-%d %H:%M}</td>"
        f"<td>{by_id.get(t['candidate_id'], {}).get('side', '')}</td>"
        f"<td class=n>{t['entry_price']:,.2f}</td><td class=n>{(t['exit_price'] or 0):,.2f}</td>"
        f"<td>{html.escape(t['exit_reason'] or '')}</td>"
        f"<td class='n {'win' if t['net_usd'] > 0 else 'loss'}'>{_usd(t['net_usd'])}</td>"
        f"<td class=n>{t['r']:+.2f}R</td></tr>"
        for t in reversed(trades)
    )
    warns = "".join(f'<div class="warn">{html.escape(w)}</div>' for w in warnings_for(run, today))
    pbo = "needs 2+ comparable trials" if ev.pbo is None else f"{ev.pbo:.0%} (lower is better)"
    notes = run.get("notes") or {}
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} report card</title><style>{CSS}</style></head><body><main>
<p class="eyebrow">Backtest report card · {start} to {end}</p>
<h1>{html.escape(title)}: <span class="{verdict_text[1]}">{verdict_text[0]}</span></h1>
<p class="lead">{verdict_text[2]} Trial: {html.escape(ev.trial)}.</p>
{warns}
<section class="card"><h2>The four checks</h2>{checks}</section>
<section class="tiles">{tiles}</section>
<section class="card"><h2>Account growth</h2>
<p class="sub">Each trade risks {_usd(risk_usd, False)} (1R). The red band shows dips below the last high.</p>
{_chart(trades)}</section>
<section class="card"><h2>Ideas it didn't trade</h2><ul>{skip_rows or "<li>none</li>"}</ul></section>
<section class="card"><h2>Trades, newest first</h2><div class="scroll"><table>
<tr><th>Entry (New York)</th><th>Side</th><th class=n>Entry</th><th class=n>Exit</th>
<th>Exit reason</th><th class=n>Result</th><th class=n>R</th></tr>{trade_rows}</table></div></section>
<details class="card"><summary>Advanced numbers</summary><dl>
<dt>Random-entry average</dt><dd>{"no trades" if ev.random_mean_r != ev.random_mean_r else f"{ev.random_mean_r:+.3f}R per trade"}</dd>
<dt>Edge vs random (95% CI)</dt><dd>{"no trades" if lo != lo else f"{lo:+.3f}R to {hi:+.3f}R per trade"}</dd>
<dt>Deflated Sharpe (DSR)</dt><dd>{ev.dsr:.3f} over {ev.n_trials} trial(s); the "not just luck" score</dd>
<dt>PBO</dt><dd>{pbo}; chance the best version is overfit</dd>
<dt>Sharpe / Sortino</dt><dd>{m.sharpe:.2f} / {m.sortino:.2f} (yearly, on daily results)</dd>
<dt>Net R</dt><dd>{m.net_r:+.2f}R; average win {m.avg_win_r:+.2f}R, average loss {m.avg_loss_r:+.2f}R</dd>
<dt>Run</dt><dd>{html.escape(run["run_id"])}</dd>
<dt>Code commit</dt><dd>{html.escape(run["code_commit"] or "")}</dd>
<dt>Settings file hash</dt><dd>{html.escape(run["defaults_hash"] or "")}</dd>
<dt>Symbol</dt><dd>{html.escape(str(notes.get("symbol", "")))}</dd>
</dl></details>
<p class="sub">Generated {datetime.now():%Y-%m-%d %H:%M}. Past results don't guarantee future ones.</p>
</main></body></html>"""
    out = folder / "report.html"
    out.write_text(page)
    return out


CSS = """
:root{--bg:#f3f4f8;--card:#fff;--ink:#161a2b;--sub:#5d6378;--line:#e1e4ee;--win:#12a37f;
--loss:#e0533f;--amber:#d99417;--accent:#4b5bd6;--soft:rgba(75,91,214,.1)}
@media (prefers-color-scheme:dark){:root{--bg:#0c0f1d;--card:#151a2e;--ink:#e9ebf5;--sub:#9aa1bd;
--line:#262c47;--win:#35d0a5;--loss:#ff7a66;--amber:#f0b440;--accent:#8d9bff;--soft:rgba(141,155,255,.13)}}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,sans-serif}
main{max-width:1000px;margin:0 auto;padding:24px 16px 48px;display:grid;gap:18px}
h1{margin:0;font-size:clamp(24px,4vw,34px)}h2{margin:0 0 10px;font-size:18px}
.eyebrow{margin:0;font-weight:700;font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--sub)}
.lead{margin:0;color:var(--sub)}.sub{color:var(--sub);font-size:13px;display:block}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px 20px}
.win{color:var(--win)}.loss{color:var(--loss)}.amber{color:var(--amber)}
.warn{background:rgba(217,148,23,.14);border-radius:12px;padding:12px 14px}
.chk{display:grid;grid-template-columns:30px 1fr auto;gap:12px;align-items:center;padding:8px 0;
border-top:1px solid var(--line)}.chk:first-of-type{border-top:0}
.mark{width:28px;height:28px;border-radius:50%;display:grid;place-items:center;font-weight:800}
.mark.ok{background:rgba(18,163,127,.14);color:var(--win)}.mark.no{background:rgba(224,83,63,.14);color:var(--loss)}
.mark.wait{background:rgba(217,148,23,.14);color:var(--amber)}
.num,td.n,th.n{font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px;display:grid;gap:2px}
.tile .t{font-weight:700;font-size:13px}.tile b{font-size:24px}
svg text{font-size:11px;fill:var(--sub)}svg .grid{stroke:var(--line)}
svg .eq{fill:none;stroke:var(--accent);stroke-width:2.5}svg .dd{fill:rgba(224,83,63,.15);stroke:var(--loss)}
.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%}
th,td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left}
th{font-size:12px;color:var(--sub);text-transform:uppercase;letter-spacing:.04em}
summary{cursor:pointer;font-weight:700;color:var(--accent)}dl{display:grid;grid-template-columns:max-content 1fr;gap:6px 16px}
dt{color:var(--sub)}dd{margin:0}
"""
