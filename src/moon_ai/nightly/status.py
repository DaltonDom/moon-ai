"""`moon-ai nightly status`: the last 7 runs and their steps, in plain words."""

from __future__ import annotations

from collections import defaultdict

from moon_ai.journal import SQLiteStore, decode_json
from moon_ai.nightly.job import PAPER_RUN, Paths
from moon_ai.sessions import to_ny

MARKS = {"ok": "✓", "warn": "!", "skipped": "-", "fail": "✕"}


def status_text(paths: Paths, runs: int = 7) -> str:
    if not paths.journal.exists():
        return "No nightly run yet. Install it with `uv run moon-ai nightly install`."
    rows = decode_json(SQLiteStore(paths.journal).read("events", PAPER_RUN), "events")
    by_run: dict[str, list] = defaultdict(list)
    for r in rows:
        if r["data"] and "run" in r["data"]:
            by_run[r["data"]["run"]].append(r)
    if not by_run:
        return "No nightly run yet."
    lines = []
    for stamp in sorted(by_run)[-runs:][::-1]:
        steps = sorted(by_run[stamp], key=lambda r: r["ts"])
        when = to_ny(steps[0]["ts"]).strftime("%a %b %d, %I:%M %p New York")
        worst = "fail" if any(s["status"] == "fail" for s in steps) else "ok"
        lines.append(f"{MARKS[worst]} Run of {when}")
        for s in steps:
            lines.append(f"    {MARKS.get(s['status'], '?')} {s['step']}: {s['message']}")
    return "\n".join(lines)
