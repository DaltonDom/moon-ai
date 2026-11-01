"""The news calendar and the blackout windows built from it.

docs/design.md, "News blackout" (#15); sources and file format from the
news-calendar research (#5). One versioned file, `data_public/news_events.csv`,
is read by backtests, paper replay and live trading alike.

Rows hold the time a release **actually** came out (cancelled releases have
no row). Columns:

    event_id, event_type, publisher, local_time_et, utc_time, scheduled,
    source_url, verified_by

- **Blocking** event types get a window of +-`news_blackout_minutes`. On an
  FOMC statement day the window runs from 15 minutes before the statement to
  `fomc_blackout_end` (15:30 ET), through the press conference.
- **Recorded** event types never block. They are ML features and the 2022
  model's "news inside the killzone" trigger.
- **Unscheduled** events (`scheduled=false`, e.g. the March 2020 emergency
  cuts) don't block: live trading couldn't have known 15 minutes ahead.

The blackout blocks entries only. `starts_between` tells the trader when to
cancel unfilled entry orders.
"""

from __future__ import annotations

import bisect
import csv
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from moon_ai.config import IctConfig
from moon_ai.sessions import NY, to_ny

NEWS_CSV = Path(__file__).resolve().parents[3] / "data_public" / "news_events.csv"

BLOCKING = frozenset(
    {
        "CPI",
        "NFP",
        "PPI",
        "GDP",
        "PCE",
        "FOMC_STATEMENT",
        "FOMC_MINUTES",
        "FOMC_PRESSER",
        "FED_CHAIR_TESTIMONY",
        "JACKSON_HOLE",
    }
)
RECORDED = frozenset(
    {
        "FED_CHAIR_SPEECH",
        "ISM_MANUFACTURING",
        "ISM_SERVICES",
        "RETAIL_SALES",
        "JOBLESS_CLAIMS",
        "JOLTS",
        "CONSUMER_SENTIMENT",
    }
)
COLUMNS = (
    "event_id",
    "event_type",
    "publisher",
    "local_time_et",
    "utc_time",
    "scheduled",
    "source_url",
    "verified_by",
)


class NewsCalendarError(ValueError):
    """A row in the news calendar that breaks its format."""


@dataclass(frozen=True)
class NewsEvent:
    event_id: str
    event_type: str
    publisher: str
    at: datetime  # UTC
    scheduled: bool
    source_url: str
    verified_by: str = ""

    @property
    def blocking(self) -> bool:
        return self.event_type in BLOCKING and self.scheduled


def load_events(path: Path = NEWS_CSV) -> list[NewsEvent]:
    """Read and check the calendar, oldest first."""
    events: list[NewsEvent] = []
    seen: set[str] = set()
    with Path(path).open(newline="") as fh:
        reader = csv.DictReader(fh)
        if tuple(reader.fieldnames or ()) != COLUMNS:
            raise NewsCalendarError(f"{path}: columns must be {', '.join(COLUMNS)}")
        for n, row in enumerate(reader, start=2):
            where = f"{path}:{n}"
            kind = row["event_type"]
            if kind not in BLOCKING | RECORDED:
                raise NewsCalendarError(f"{where}: unknown event_type {kind!r}")
            if row["event_id"] in seen:
                raise NewsCalendarError(f"{where}: duplicate event_id {row['event_id']!r}")
            seen.add(row["event_id"])
            local = datetime.fromisoformat(row["local_time_et"])
            if local.tzinfo is not None:
                raise NewsCalendarError(f"{where}: local_time_et is New York wall-clock, no offset")
            at = local.replace(tzinfo=NY).astimezone(UTC)
            stated = datetime.fromisoformat(row["utc_time"].replace("Z", "+00:00"))
            if stated != at:
                raise NewsCalendarError(
                    f"{where}: utc_time {row['utc_time']} doesn't match "
                    f"{row['local_time_et']} New York"
                )
            if row["scheduled"] not in ("true", "false"):
                raise NewsCalendarError(f"{where}: scheduled must be true or false")
            events.append(
                NewsEvent(
                    row["event_id"],
                    kind,
                    row["publisher"],
                    at,
                    row["scheduled"] == "true",
                    row["source_url"],
                    row["verified_by"],
                )
            )
    return sorted(events, key=lambda e: (e.at, e.event_id))


@dataclass(frozen=True)
class Window:
    start: datetime  # UTC, inclusive
    end: datetime  # UTC, exclusive
    events: tuple[str, ...]  # event ids that caused it


class Blackout:
    """Merged blackout windows, queried by UTC time."""

    def __init__(self, events: Iterable[NewsEvent], cfg: IctConfig | None = None):
        cfg = cfg or IctConfig()
        pad = timedelta(minutes=cfg.news_blackout_minutes)
        self._events = sorted(events, key=lambda e: e.at)
        self._times = [e.at for e in self._events]
        raw: list[Window] = []
        for e in self._events:
            if not e.blocking:
                continue
            end = e.at + pad
            if e.event_type == "FOMC_STATEMENT":
                day_end = datetime.combine(to_ny(e.at).date(), cfg.fomc_blackout_end, tzinfo=NY)
                end = max(end, day_end.astimezone(UTC))
            raw.append(Window(e.at - pad, end, (e.event_id,)))
        raw.sort(key=lambda w: w.start)
        merged: list[Window] = []
        for w in raw:
            if merged and w.start <= merged[-1].end:
                last = merged[-1]
                merged[-1] = Window(last.start, max(last.end, w.end), last.events + w.events)
            else:
                merged.append(w)
        self.windows = merged
        self._starts = [w.start for w in merged]
        self._fomc_days = {
            to_ny(e.at).date()
            for e in self._events
            if e.event_type == "FOMC_STATEMENT" and e.scheduled
        }

    def window_at(self, ts: datetime) -> Window | None:
        i = bisect.bisect_right(self._starts, ts) - 1
        if i >= 0 and self.windows[i].start <= ts < self.windows[i].end:
            return self.windows[i]
        return None

    def in_blackout(self, ts: datetime) -> bool:
        return self.window_at(ts) is not None

    def starts_between(self, after: datetime, until: datetime) -> list[Window]:
        """Windows starting in (after, until]: unfilled entries are cancelled at each start."""
        lo = bisect.bisect_right(self._starts, after)
        hi = bisect.bisect_right(self._starts, until)
        return self.windows[lo:hi]

    def events_near(
        self, ts: datetime, before: timedelta, after: timedelta, include_recorded: bool = True
    ) -> list[NewsEvent]:
        """Events in [ts - before, ts + after], blocking or recorded (for features).

        Only scheduled events may be looked up ahead of `ts`; an unscheduled
        event is known only once it happens.
        """
        lo = bisect.bisect_left(self._times, ts - before)
        hi = bisect.bisect_right(self._times, ts + after)
        return [
            e
            for e in self._events[lo:hi]
            if (include_recorded or e.event_type in BLOCKING) and (e.scheduled or e.at <= ts)
        ]

    def is_fomc_day(self, day: date) -> bool:
        """New York date with a scheduled FOMC statement (no NY PM Silver Bullet)."""
        return day in self._fomc_days
