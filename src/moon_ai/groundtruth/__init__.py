"""Ground truth: the user's own reading of sampled days, and the check against it.

Decided in the ground-truth workflow ticket (#11): the unit of review is a
setup's whole chain (sweep, MSS, displacement FVG). The user marks each
detection agree / disagree / unsure and adds any setup the bot missed. CI then
holds the setups to those verdicts both ways:

- every detection must be one the user agreed with (or was unsure about)
- every agreed or user-added setup must be detected

"Unsure" is left out of both directions.

Files:
- `tests/fixtures/ground_truth/<setup>/verdicts.json`: the exported verdicts
- `tests/fixtures/ground_truth/<setup>/bars/`: the reviewed days' bars, in
  the store layout. They're committed because the repo is private.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import polars as pl

from moon_ai.bars import InMemoryBarFeed
from moon_ai.broker import SimBroker
from moon_ai.config import Config, load_config
from moon_ai.data.calendar import SessionCalendar
from moon_ai.data.store import BarStore
from moon_ai.engine import run
from moon_ai.journal import InMemoryJournal
from moon_ai.sessions import NY, to_ny
from moon_ai.setups import REGISTRY, defaults_hash, load_setup_defaults
from moon_ai.setups.base import Candidate

REPO = Path(__file__).resolve().parents[3]
FIXTURES = REPO / "tests" / "fixtures" / "ground_truth"
MATCH_MINUTES = 5  # a user-added setup matches a detection within this many minutes


def key(c: Candidate) -> str:
    """How a detection is named in a verdict file: New York decision time and side."""
    return f"{to_ny(c.decision_time):%Y-%m-%dT%H:%M}:{c.side}"


def session_bounds(day: date) -> tuple[datetime, datetime]:
    """CME trading day `day`: 18:00 New York the evening before to 17:00."""
    return (
        datetime.combine(day - timedelta(days=1), time(18), tzinfo=NY),
        datetime.combine(day, time(17), tzinfo=NY),
    )


def detect(
    setup: str, store: BarStore, day: date, config: Config | None = None, symbol: str = "MNQ.v.0"
) -> tuple[list[Candidate], list]:
    """The setup's detections on one trading day (with up to two weeks of
    lead-in for setups that read bias from earlier sessions)."""
    config = config or load_config()
    params = load_setup_defaults()[setup].params
    start, end = session_bounds(day)
    bars = store.load(symbol, start - timedelta(days=14), end)
    feed = InMemoryBarFeed(bars)
    s = REGISTRY[setup](params, config, symbol)
    found: list[Candidate] = []
    lo = start.astimezone(UTC)

    class Collect:
        def on_bar(self, bar, ctx):
            hits = s.scan(ctx)
            found.extend(h for h in hits if h.decision_time > lo)

    run(feed, SimBroker(config.broker, config.instrument), Collect(), InMemoryJournal())
    return found, [b for b in bars if b.ts_open >= lo]


def sample_days(
    store: BarStore, start: date, end: date, n: int, seed: int = 7, symbol: str = "MNQ.v.0"
) -> list[date]:
    cal = SessionCalendar()
    covered = [s for s in store.files(symbol)]
    days = []
    d = start
    while d < end:
        if not cal.no_new_trades(d) and any(s.start <= d < s.end for s in covered):
            days.append(d)
        d += timedelta(days=1)
    return sorted(random.Random(seed).sample(days, min(n, len(days))))


# --- the CI check -------------------------------------------------------------------


@dataclass(frozen=True)
class Problem:
    day: str
    message: str


def check(setup: str, root: Path = FIXTURES, config: Config | None = None) -> list[Problem]:
    """Compare the setup's detections with the committed verdicts, both ways."""
    folder = root / setup
    data = json.loads((folder / "verdicts.json").read_text())
    store = BarStore(folder / "bars")
    problems = []
    for day_s, v in sorted(data["days"].items()):
        found, _ = detect(setup, store, date.fromisoformat(day_s), config)
        got = {key(c) for c in found}
        verdicts: dict[str, str] = v.get("verdicts", {})
        for k in sorted(got):
            if k not in verdicts:
                problems.append(Problem(day_s, f"new detection {k} that wasn't reviewed"))
            elif verdicts[k] == "disagree":
                problems.append(Problem(day_s, f"detects {k}, which the review rejected"))
        for k, verdict in sorted(verdicts.items()):
            if verdict == "agree" and k not in got:
                problems.append(
                    Problem(day_s, f"no longer detects {k}, which the review agreed with")
                )
        for m in v.get("missed", []):
            t = datetime.fromisoformat(m["t"])  # New York wall-clock, as the page exports it
            t = t.replace(tzinfo=NY) if t.tzinfo is None else t
            near = [
                c
                for c in found
                if abs(to_ny(c.decision_time) - t) <= timedelta(minutes=MATCH_MINUTES)
                and (not m.get("side") or c.side == m["side"])
            ]
            if not near:
                problems.append(
                    Problem(
                        day_s,
                        f"misses the setup the review added at {m['t']}"
                        + (f" ({m['side']})" if m.get("side") else ""),
                    )
                )
    return problems


def import_verdicts(path: Path, store: BarStore, root: Path = FIXTURES) -> Path:
    """Save an exported verdict file as a fixture, with its days' bars."""
    data = json.loads(Path(path).read_text())
    setup = data["setup"]
    folder = root / setup
    (folder / "bars").mkdir(parents=True, exist_ok=True)
    frames = []
    for day_s in data["days"]:
        day = date.fromisoformat(day_s)
        start, end = session_bounds(day)
        for span in store.files(data.get("symbol", "MNQ.v.0")):
            if span.start <= day < span.end + timedelta(days=1):
                frames.append(
                    pl.read_parquet(span.path).filter(
                        (pl.col("ts_event") >= (start - timedelta(days=14)).astimezone(UTC))
                        & (pl.col("ts_event") < end.astimezone(UTC))
                    )
                )
    if frames:
        bars = pl.concat(frames).unique(subset=["ts_event"], keep="last").sort("ts_event")
        first = bars["ts_event"].min().date()
        last = bars["ts_event"].max().date() + timedelta(days=1)
        out = folder / "bars" / store.dataset / "ohlcv-1m" / data.get("symbol", "MNQ.v.0")
        out.mkdir(parents=True, exist_ok=True)
        bars.write_parquet(out / f"{first}_{last}.parquet")
    (folder / "verdicts.json").write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
    return folder


def export_template(setup: str, days: dict[str, list[Candidate]]) -> dict[str, Any]:
    return {
        "setup": setup,
        "symbol": "MNQ.v.0",
        "defaults_hash": defaults_hash(),
        "days": {d: {"verdicts": {key(c): "" for c in cs}, "missed": []} for d, cs in days.items()},
    }
