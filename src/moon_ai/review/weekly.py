"""The Saturday weekly report and its proposals (docs/design.md, "Weekly report and proposals").

The report is plain Markdown at `reports/weekly/<ISO year>-W<week>.md`, shown
on the dashboard. Code computes every number:

- the week's result, per setup
- who's in charge, and the model in tryout
- review buckets, skipped-candidate totals
- 3-5 instructive trades, and failed reviews

Proposals are the one part Claude writes: from the week's review `follow_up`
ideas and the numbers, at most 3 concrete, testable changes. Each is opened as
a GitHub issue labelled `proposal`, which then needs the user's OK twice.
Without an API key, a GitHub token or room under the monthly cap, the report
is still written, just without proposals.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from moon_ai.journal import SQLiteStore, decode_json
from moon_ai.review.claude import MODEL, MONTHLY_CAP_USD, month_spend
from moon_ai.sessions import trading_day
from moon_ai.setups import load_setup_defaults

MAX_PROPOSALS = 3
EST_PROPOSAL_COST_USD = 0.50
PROPOSAL_PRICE = {"input": 4.0, "output": 20.0}  # Opus 5.5 per 1M tokens, not batched
BUCKET_WORDS = {
    "rule_break": "Rule break or execution error",
    "good_won": "Good setup, won",
    "good_lost": "Good setup, unlucky loss",
    "bad_won": "Bad setup, lucky win",
    "bad_lost": "Bad setup, lost",
}
SKIP_WORDS = {
    "skipped:ml": "low model confidence",
    "skipped:blackout": "news blackout",
    "skipped:cap": "already 2 trades that session",
    "skipped:daily_stop": "daily loss limit",
    "skipped:london_min_stop": "London stop too small",
    "skipped:session": "outside trading hours",
    "skipped:busy": "already in a trade",
    "skipped:kill_switch": "kill switch",
    "skipped:size": "too big to size",
    "unfilled": "price never reached the entry",
}

PROPOSAL_SCHEMA = {
    "type": "object",
    "properties": {
        "proposals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "setup": {"type": "string"},
                    "change": {"type": "string"},
                    "evidence": {"type": "string"},
                    "test": {"type": "string"},
                },
                "required": ["title", "setup", "change", "evidence", "test"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["proposals"],
    "additionalProperties": False,
}

PROPOSAL_SYSTEM = f"""You turn a week of paper-trading results into at most
{MAX_PROPOSALS} proposals for an automated ICT trading bot. Each proposal changes exactly
one parameter or rule of one setup, named as in its pinned rules. Give the evidence
from this week's numbers or reviews, and
the backtest that would decide it (the setup, the one setting changed, and what result would
count as a pass). Propose nothing if nothing is well supported: an empty list is a fine answer.
Write for a non-trader: short, plain sentences."""


def week_bounds(saturday: date) -> tuple[date, date]:
    """Monday to Friday of the week that ends on `saturday`."""
    monday = saturday - timedelta(days=saturday.weekday())
    return monday, monday + timedelta(days=4)


def _usd(x: float) -> str:
    return ("\u2212" if x < 0 else "+" if x > 0 else "") + f"${abs(x):,.0f}"


def gather(db: SQLiteStore, run_id: str, saturday: date) -> dict[str, Any]:
    mon, fri = week_bounds(saturday)
    cands = {c["candidate_id"]: c for c in decode_json(db.read("candidates", run_id), "candidates")}
    trades = [
        t
        for t in decode_json(db.read("trades", run_id), "trades")
        if t["exit_time"] is not None and mon <= trading_day(t["exit_time"]) <= fri
    ]
    reviews = {r["candidate_id"]: r for r in decode_json(db.read("reviews", run_id), "reviews")}
    skipped = [
        c
        for c in cands.values()
        if c["status"] != "taken" and mon <= trading_day(c["decision_time"]) <= fri
    ]
    models = decode_json(db.read("models"), "models")
    return {
        "monday": mon,
        "friday": fri,
        "cands": cands,
        "trades": sorted(trades, key=lambda t: t["exit_time"]),
        "reviews": reviews,
        "skipped": skipped,
        "models": models,
        "events": decode_json(db.read("events", run_id), "events"),
    }


def instructive(d: dict[str, Any], n: int = 5) -> list[tuple[dict[str, Any], str]]:
    """Trades worth a look: rule breaks, lucky wins, bad losses, then the biggest swings."""
    order = {"rule_break": 0, "bad_won": 1, "bad_lost": 2, "good_lost": 3}
    scored = []
    for t in d["trades"]:
        rv = d["reviews"].get(t["candidate_id"])
        bucket = rv["bucket"] if rv and rv["status"] == "done" else None
        scored.append((order.get(bucket, 4), -abs(t["net_usd"] or 0), t, bucket))
    scored.sort(key=lambda x: (x[0], x[1]))
    return [(t, b) for _, _, t, b in scored[:n]]


def render(d: dict[str, Any], proposals: list[dict[str, Any]], iso: str) -> str:
    trades, reviews = d["trades"], d["reviews"]
    net = sum(t["net_usd"] for t in trades)
    wins = sum(t["net_usd"] > 0 for t in trades)
    title = (
        "No trades this week."
        if not trades
        else f"{'Good' if net > 0 else 'Rough' if net < 0 else 'Flat'} week: "
        f"{'up' if net >= 0 else 'down'} ${abs(net):,.0f} "
        f"on {len(trades)} trade{'s' if len(trades) != 1 else ''}."
    )
    titles = {n: d_.title for n, d_ in load_setup_defaults().items()}
    out = [
        f"# {title}",
        "",
        f"{iso} · {d['monday']:%b %d} to {d['friday']:%b %d} · paper account",
        "",
    ]

    out += ["## The week", ""]
    if trades:
        out.append(f"**{_usd(net)}** from {len(trades)} trades, {wins} of them winners.")
        out.append("")
        by: dict[str, list] = defaultdict(list)
        for t in trades:
            by[d["cands"][t["candidate_id"]]["setup"]].append(t)
        for s, ts in sorted(by.items(), key=lambda kv: -sum(t["net_usd"] for t in kv[1])):
            w = sum(t["net_usd"] > 0 for t in ts)
            out.append(
                f"- **{titles.get(s, s)}:** {len(ts)} trades, {w} won, "
                f"{_usd(sum(t['net_usd'] for t in ts))}"
            )
    else:
        out.append("No paper trades closed this week.")
    out.append("")

    sk = d["skipped"]
    out += ["## Skipped setups", ""]
    if sk:
        labelled = [c for c in sk if c["label"] is not None]
        won = sum(c["label"] == 1 for c in labelled)
        reasons = Counter(c["status"] for c in sk)
        out.append(
            f"{len(sk)} setup(s) were skipped: "
            + ", ".join(f"{n} {SKIP_WORDS.get(k, k)}" for k, n in reasons.most_common())
            + "."
        )
        if labelled:
            out.append(f"Of the {len(labelled)} with a known outcome, {won} would have won.")
    else:
        out.append("None.")
    out.append("")

    out += ["## Claude's reviews", ""]
    done = [
        reviews[t["candidate_id"]]
        for t in trades
        if reviews.get(t["candidate_id"], {}).get("status") == "done"
    ]
    if done:
        for b, n in Counter(r["bucket"] for r in done).most_common():
            out.append(f"- {BUCKET_WORDS.get(b, b)}: {n}")
    else:
        out.append("No reviews back yet.")
    failed = [r for r in reviews.values() if r["status"] == "failed"]
    if failed:
        out += ["", f"**{len(failed)} review(s) failed** after 3 tries:"]
        out += [
            f"- `{r['candidate_id']}`: {(r['fields'] or {}).get('last_error', 'no reason')}"
            for r in failed
        ]
    out.append("")

    picks = instructive(d)
    if picks:
        out += ["## Trades worth a look", ""]
        for t, b in picks:
            c = d["cands"][t["candidate_id"]]
            rv = reviews.get(t["candidate_id"])
            why = (rv["fields"] or {}).get("summary", "") if rv and rv["status"] == "done" else ""
            out.append(
                f"- [{titles.get(c['setup'], c['setup'])}, "
                f"{trading_day(t['exit_time']):%a %b %d}](#trade/"
                f"{t['candidate_id']}): {_usd(t['net_usd'])}"
                + (f", rated “{BUCKET_WORDS.get(b, b)}”" if b else "")
                + (f". {why}" if why else "")
            )
        out.append("")

    out += ["## Models", ""]
    champ = next((m for m in d["models"] if m["role"] == "champion"), None)
    tryout = next((m for m in d["models"] if m["role"] == "challenger"), None)
    out.append(
        f"Model {champ['model_id']} is in charge."
        if champ
        else "Rules-only is in charge: no model has been promoted."
    )
    if tryout:
        rec = tryout["records"] or {}
        out.append(
            f"Model {tryout['model_id']} is in tryout: "
            f"{rec.get('disagreements', 0)} trades where they "
            f"disagree so far (150 needed), week {rec.get('weeks', 0)} of 12."
        )
    out.append("")

    out += ["## Proposed changes", ""]
    if proposals:
        for p in proposals:
            link = f" ([#{p['number']}]({p['url']}))" if p.get("number") else ""
            out.append(
                f"- **{p['title']}**{link}: {p['change']} "
                f"*Why:* {p['evidence']} *Test:* {p['test']}"
            )
    else:
        out.append("None this week.")
    out.append("")
    return "\n".join(out)


def ask_for_proposals(client: Any, d: dict[str, Any]) -> tuple[list[dict[str, Any]], float]:
    """One Claude call: the week's numbers and follow-up ideas in, at most 3 proposals out."""
    defaults = load_setup_defaults()
    ideas = [
        {
            "setup": d["cands"][cid]["setup"],
            "bucket": r["bucket"],
            "idea": (r["fields"] or {}).get("follow_up"),
        }
        for cid, r in d["reviews"].items()
        if r["status"] == "done" and (r["fields"] or {}).get("follow_up") and cid in d["cands"]
    ]
    by_setup: dict[str, list[float]] = defaultdict(list)
    for t in d["trades"]:
        by_setup[d["cands"][t["candidate_id"]]["setup"]].append(t["r"])
    payload = {
        "results_r_by_setup": by_setup,
        "follow_up_ideas": ideas,
        "skipped": Counter(c["status"] for c in d["skipped"]),
        "pinned_rules": {
            n: {k: str(v) for k, v in vars(x.params).items()} for n, x in defaults.items()
        },
    }
    msg = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=PROPOSAL_SYSTEM,
        output_config={
            "effort": "high",
            "format": {"type": "json_schema", "schema": PROPOSAL_SCHEMA},
        },
        messages=[{"role": "user", "content": json.dumps(payload, default=str, sort_keys=True)}],
    )
    u = msg.usage
    cost = (
        (u.input_tokens or 0) * PROPOSAL_PRICE["input"]
        + (u.output_tokens or 0) * PROPOSAL_PRICE["output"]
    ) / 1e6
    if msg.stop_reason != "end_turn":
        return [], cost
    text = next((b.text for b in msg.content if b.type == "text"), "")
    try:
        props = json.loads(text)["proposals"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return [], cost
    return [p for p in props if p.get("setup") in defaults][:MAX_PROPOSALS], cost


def proposal_body(p: dict[str, Any], iso: str) -> str:
    return (
        f"**Change:** {p['change']}\n\n**Why:** {p['evidence']}\n\n"
        f"**Test that decides it:** {p['test']}\n\n"
        f"Setup: `{p['setup']}`. From the weekly report {iso}.\n\n"
        "Needs your OK twice: add `approved` (or press *Yes, test it* on the dashboard) to run the "
        "test; the rule changes only if the test passes and you approve the result."
        "\n\n---\n_Written by moon-ai's weekly report with Claude._"
    )


def write_weekly(
    db: SQLiteStore,
    run_id: str,
    saturday: date,
    reports: Path,
    client_factory: Callable[[], Any] | None = None,
    github: Callable[[], Any] | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> tuple[Path, list[str]]:
    """Write the report; returns its path and notes on anything left out."""
    year, week, _ = saturday.isocalendar()
    iso = f"{year}-W{week:02d}"
    d = gather(db, run_id, saturday)
    notes: list[str] = []
    proposals: list[dict[str, Any]] = []
    spent = month_spend(d["events"], now())
    if client_factory is None:
        notes.append("no proposals: no Claude API key")
    elif spent + EST_PROPOSAL_COST_USD > MONTHLY_CAP_USD:
        notes.append(f"no proposals: the ${MONTHLY_CAP_USD:.0f} monthly Claude cap is reached")
    elif d["trades"]:
        try:
            proposals, cost = ask_for_proposals(client_factory(), d)
        except Exception as exc:  # the report must still be written
            notes.append(f"no proposals: Claude call failed ({exc})")
        else:
            t = now()
            db.insert(
                "events",
                {
                    "event_id": f"spend:weekly:{iso}:{t.isoformat()}",
                    "run_id": run_id,
                    "ts": t,
                    "step": "claude_spend",
                    "status": "info",
                    "message": f"${cost:.4f} for the {iso} proposals",
                    "data": {"cost_usd": cost, "week": iso},
                },
            )
    if proposals:
        gh = None
        try:
            gh = github() if github else None
        except Exception as exc:
            notes.append(f"proposals not opened as issues: {exc}")
        for p in proposals:
            if gh is None:
                continue
            issue = gh.create_issue(f"[proposal] {p['title']}", proposal_body(p, iso), ["proposal"])
            p["number"], p["url"] = issue["number"], issue.get("html_url")
    reports.mkdir(parents=True, exist_ok=True)
    path = reports / f"{iso}.md"
    path.write_text(render(d, proposals, iso))
    return path, notes
