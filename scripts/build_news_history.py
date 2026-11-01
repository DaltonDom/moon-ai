"""Build `data_public/news_events.csv` from official publishers only.

Usage:  uv run python scripts/build_news_history.py [--until YYYY-MM-DD] [--refresh]

Rows hold the time each release **actually** came out (docs/design.md, "News
blackout"; sources from docs/research/news-calendar.md). Only these hosts are
fetched: www.bls.gov, www.bea.gov, apps.bea.gov and www.federalreserve.gov.
Requests carry a plain User-Agent, run at most about one per second, and every
raw page is cached under the gitignored `data/cache/news/`. Release pages never
change, so they are fetched once; `--refresh` re-fetches the index pages and
feeds that grow over time.

Sources, per event type:

- GDP, PCE (BEA): the news-release archive and current-releases listings name
  every actual release; each row's time is the "EMBARGOED UNTIL RELEASE AT ..."
  line of that release's own page (`source_url`).
- FOMC_STATEMENT, FOMC_MINUTES (Fed Board): the press-release feed lists each
  release; each row's time is the "For release at ..." line of the press
  release itself. Statements from unscheduled meetings and notation votes
  (from the per-year historical pages) get `scheduled=false`.
- FOMC_PRESSER (Fed Board): one per meeting with a press-conference page. The
  Board states the start time only on some calendars (Jan 2019, Sep 2025
  onward); elsewhere the row uses the standing 2:30 p.m. start and is marked
  `verified_by=builder-time-assumed`.
- FED_CHAIR_TESTIMONY, JACKSON_HOLE, FED_CHAIR_SPEECH (Fed Board): the Board's
  monthly calendars (HTML pages and calendar.json) give date and start time.
  Testimony is the semiannual Monetary Policy Report hearings (Humphrey-
  Hawkins); when the prepared text was posted before the hearing started, a
  second "-text" row records the posting time from the testimony feed. Other
  Chair testimony and all other Chair speeches are FED_CHAIR_SPEECH (recorded).
- CPI, NFP, PPI, JOLTS (BLS): parsed from the BLS release archives. www.bls.gov
  refuses automated clients that carry no owner contact, so when it answers 403
  the builder keeps whatever BLS rows the existing file already holds and says so.

Not built (no allowed official source): ISM manufacturing and services (ISM),
consumer sentiment (University of Michigan), retail sales (Census) and jobless
claims (Department of Labor).
"""

from __future__ import annotations

import argparse
import calendar
import csv
import hashlib
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache" / "news"
OUT = ROOT / "data_public" / "news_events.csv"
USER_AGENT = "moon-ai-calendar-builder/0.1"
ALLOWED_HOSTS = ("www.bls.gov", "www.bea.gov", "apps.bea.gov", "www.federalreserve.gov")
MIN_INTERVAL = 1.1  # seconds between live requests
START = date(2019, 1, 1)
NY = ZoneInfo("America/New_York")
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
FRB = "https://www.federalreserve.gov"
BEA = "https://www.bea.gov"
BLS = "https://www.bls.gov"


# --------------------------------------------------------------------------- fetch


class FetchError(RuntimeError):
    def __init__(self, url: str, status: int | None, msg: str):
        super().__init__(f"{url}: {msg}")
        self.url = url
        self.status = status


_last_request = 0.0
_refresh = False


def cache_path(url: str) -> Path:
    host = url.split("/")[2]
    digest = hashlib.sha1(url.encode()).hexdigest()[:16]
    tail = re.sub(r"[^\w.-]", "_", url.rstrip("/").split("/")[-1].split("?")[0])[:60]
    return CACHE / host / f"{tail or 'index'}.{digest}"


def fetch(url: str, index: bool = False) -> bytes:
    """GET an allowed official URL through the cache.

    `index` marks a listing or feed that grows over time: `--refresh` re-fetches
    those. Release pages are immutable and stay cached. 404s are cached too.
    """
    global _last_request
    host = url.split("/")[2]
    if host not in ALLOWED_HOSTS:
        raise FetchError(url, None, f"{host} is not an allowed official publisher")
    path = cache_path(url)
    missing = path.with_name(path.name + ".404")
    if not (index and _refresh):
        if path.exists():
            return path.read_bytes()
        if missing.exists():
            raise FetchError(url, 404, "HTTP 404 (cached)")
    wait = MIN_INTERVAL - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            missing.parent.mkdir(parents=True, exist_ok=True)
            missing.touch()
        raise FetchError(url, exc.code, f"HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise FetchError(url, None, str(exc.reason)) from exc
    finally:
        _last_request = time.monotonic()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    missing.unlink(missing_ok=True)
    return body


def page_text(raw: bytes) -> str:
    """Visible text of an HTML page, whitespace collapsed."""
    t = raw.decode("utf-8", "replace")
    t = re.sub(r"<(script|style)\b.*?</\1>", " ", t, flags=re.S | re.I)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    return re.sub(r"\s+", " ", t)


def load_json(raw: bytes):
    return json.loads(raw.decode("utf-8-sig"))


# --------------------------------------------------------------------------- rows


@dataclass
class Row:
    event_id: str
    event_type: str
    publisher: str
    local: datetime  # New York wall clock, naive
    scheduled: bool
    source_url: str
    verified_by: str = "builder"

    def csv(self) -> dict[str, str]:
        utc = self.local.replace(tzinfo=NY).astimezone(UTC)
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "publisher": self.publisher,
            "local_time_et": self.local.strftime("%Y-%m-%dT%H:%M"),
            "utc_time": utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "scheduled": "true" if self.scheduled else "false",
            "source_url": self.source_url,
            "verified_by": self.verified_by,
        }


def clock(h: str, m: str, ampm: str) -> tuple[int, int]:
    hour = int(h) % 12 + (12 if ampm.lower().startswith("p") else 0)
    return hour, int(m)


def parse_day(s: str) -> datetime:
    """'July 30, 2026', 'Sept. 26, 2019' or 'SEPTEMBER 26,2019' -> midnight that day."""
    m = re.match(r"([A-Za-z]+)\.?\s+(\d{1,2}),\s*(\d{4})", s.strip())
    if not m:
        raise ValueError(f"not a date: {s!r}")
    month = next(
        i for i in range(1, 13) if calendar.month_name[i].lower().startswith(m.group(1).lower()[:3])
    )
    return datetime(int(m.group(3)), month, int(m.group(2)))


TIME_RE = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*([ap])\.?\s*m\b\.?", re.I)


def parse_clock(s: str) -> tuple[int, int] | None:
    m = TIME_RE.search(s)
    if not m:
        return None
    return clock(m.group(1), m.group(2) or "00", m.group(3))


# --------------------------------------------------------------------------- BEA

BEA_LISTINGS = (
    BEA + "/news/archive?field_related_product_target_id=All&created_1=All&title=",
    BEA + "/news/current-releases",
)
GDP_TITLE = re.compile(r"^(GDP|Gross Domestic Product)\b", re.I)
GDP_NOT = re.compile(
    r"^(GDP|Gross Domestic Product)\s+(by|for)\s|Puerto Rico|Territor|by County|"
    r"by State and|by Metropolitan",
    re.I,
)
# "Personal Income and Outlays, ..." or, after the 2019 shutdown, "Personal Income, Feb 2019;
# Personal Outlays, Jan 2019".
PIO_TITLE = re.compile(r"^Personal Income\b.*\bOutlays\b", re.I)
EMBARGO_RE = re.compile(
    r"EMBARGOED\s+UNTIL\s+RELEASE\s+AT\s+(\d{1,2}):(\d{2})\s*([ap])\.?\s*m\.?"
    r"\s*(?:\(?E[DS]T\)?)?,?\s*(?:[A-Za-z]+,\s*)?([A-Za-z]+\.?\s+\d{1,2},\s*\d{4})",
    re.I,
)


def _bea_listing(url: str) -> list[tuple[str, str, datetime | None]]:
    """(path, title, listed datetime) for each release on a BEA listing page."""
    raw = fetch(url, index=True).decode("utf-8", "replace")
    out = []
    for m in re.finditer(
        r'<a href="(?:/index\.php)?(/news/(?:19|20)\d\d/[^"#?]+)"[^>]*>(.*?)</a>(?=(.{0,600}))',
        raw,
        flags=re.S,
    ):
        title = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", m.group(2)))).strip()
        when = None
        t = re.search(r'<time datetime="([^"]+)"', m.group(3))
        if t:
            when = datetime.fromisoformat(t.group(1)).astimezone(NY).replace(tzinfo=None)
        else:
            d = re.search(r"([A-Z][a-z]+ \d{1,2}, \d{4})", page_text(m.group(3).encode()))
            if d:
                when = datetime.strptime(d.group(1), "%B %d, %Y")
        out.append((m.group(1), title, when))
    return out


def bea_releases(until: date) -> list[tuple[str, str, datetime | None]]:
    seen: dict[str, tuple[str, str, datetime | None]] = {}
    base, current = BEA_LISTINGS
    page = 0
    while True:
        url = base + (f"&page={page}" if page else "")
        items = _bea_listing(url)
        if not items:
            break
        for item in items:
            seen.setdefault(item[0], item)
        dated = [w for _, _, w in items if w]
        if dated and min(dated).date() < START:
            break
        page += 1
        if page > 80:
            raise RuntimeError("BEA archive pagination ran away")
    for item in _bea_listing(current):
        seen.setdefault(item[0], item)
    return list(seen.values())


def bea_events(until: date, log: list[str]) -> list[Row]:
    rows: list[Row] = []
    for path, title, listed in sorted(bea_releases(until), key=lambda x: x[0]):
        if PIO_TITLE.search(title):
            kind = "PCE"
        elif GDP_TITLE.search(title) and not GDP_NOT.search(title):
            kind = "GDP"
        else:
            continue
        if listed and not (START <= listed.date() <= until + timedelta(days=1)):
            continue
        url = BEA + path
        text = page_text(fetch(url))
        m = EMBARGO_RE.search(text)
        if m:
            day = parse_day(m.group(4))
            hh, mm = clock(m.group(1), m.group(2), m.group(3))
            local = day.replace(hour=hh, minute=mm)
            if listed and listed.date() != local.date():
                log.append(
                    f"BEA {path}: listing date {listed:%Y-%m-%d} != embargo {local:%Y-%m-%d}"
                )
        elif listed and (listed.hour, listed.minute) != (0, 0):
            local = listed
            log.append(f"BEA {path}: no embargo line, using listing time {listed:%Y-%m-%d %H:%M}")
        else:
            log.append(f"BEA {path}: no release time found, skipped ({title})")
            continue
        if not (START <= local.date() <= until):
            continue
        rows.append(Row("", kind, "BEA", local, True, url))
    return rows


# --------------------------------------------------------------------------- Fed

FED_FEEDS = {
    "press": FRB + "/json/ne-press.json",
    "testimony": FRB + "/json/ne-testimony.json",
    "calendar": FRB + "/json/calendar.json",
}
RELEASE_AT = re.compile(r"For release at\s+(\d{1,2}):(\d{2})\s*([ap])\.m\.", re.I)
CHAIR = re.compile(r"(?<!Vice )\bChair(?:man)?(?: Pro Tempore)?\s+(?:Jerome|Kevin|Janet)\b")


def feed_time(s: str) -> datetime | None:
    try:
        return datetime.strptime(s.strip(), "%m/%d/%Y %I:%M:%S %p")
    except ValueError:
        return None


def press_release_time(url: str) -> datetime | None:
    """The 'For release at h:mm' time on a Board press release, on its own date."""
    text = page_text(fetch(url))
    m = RELEASE_AT.search(text)
    d = re.search(r"/(?:monetary|other)(\d{8})[a-z]\d*\.htm$", url)
    if not m or not d:
        return None
    hh, mm = clock(m.group(1), m.group(2), m.group(3))
    return datetime.strptime(d.group(1), "%Y%m%d").replace(hour=hh, minute=mm)


def fomc_meeting_pages(until: date) -> list[tuple[str, str]]:
    """(heading, block html) for each FOMC meeting block, 2019 onward."""
    blocks: list[tuple[str, str]] = []
    for year in range(START.year, until.year + 1):
        try:
            raw = fetch(f"{FRB}/monetarypolicy/fomchistorical{year}.htm").decode("utf-8", "replace")
        except FetchError as exc:
            if exc.status != 404:
                raise
            continue
        parts = re.split(r"<h5[^>]*panel-heading[^>]*>(.*?)</h5>", raw, flags=re.S)
        for head, body in zip(parts[1::2], parts[2::2], strict=True):
            blocks.append((page_text(head.encode()).strip(), body))
    raw = fetch(FRB + "/monetarypolicy/fomccalendars.htm", index=True).decode("utf-8", "replace")
    years = re.split(r"<h4><a[^>]*>(\d{4}) FOMC Meetings</a></h4>", raw)
    for year, body in zip(years[1::2], years[2::2], strict=True):
        months = re.split(r"fomc-meeting__month[^>]*><strong>([\w/]+)</strong>", body)
        for month, mbody in zip(months[1::2], months[2::2], strict=True):
            d = re.search(r"fomc-meeting__date[^>]*>([^<]*)<", mbody)
            blocks.append((f"{month} {d.group(1).strip() if d else ''} - {year}", mbody))
    return blocks


def fed_events(until: date, log: list[str]) -> list[Row]:
    rows: list[Row] = []
    press = [x for x in load_json(fetch(FED_FEEDS["press"], index=True)) if "d" in x]
    blocks = fomc_meeting_pages(until)

    # Statements: the feed's "FOMC statement" releases, plus the statements of
    # unscheduled meetings and notation votes (e.g. 2019-10-11 for the Oct 4 meeting).
    unscheduled_urls: set[str] = set()
    presser_urls: dict[date, str] = {}
    for head, body in blocks:
        for m in re.finditer(
            r'href="(?:https://www\.federalreserve\.gov)?(/monetarypolicy/fomcpres+conf(\d{8})\.htm)"',
            body,
        ):
            presser_urls[datetime.strptime(m.group(2), "%Y%m%d").date()] = FRB + m.group(1)
        if re.search(r"unscheduled|notation vote", head, re.I):
            for m in re.finditer(
                r'href="(/newsevents/pressreleases/monetary\d{8}a\.htm)"[^>]*>\s*(Statement|HTML)\s*<',
                body,
            ):
                unscheduled_urls.add(FRB + m.group(1))
    statement_urls = {
        FRB + x["l"]
        for x in press
        if x.get("pt") == "Monetary Policy"
        and x["t"].strip() == "Federal Reserve issues FOMC statement"
    } | unscheduled_urls
    minutes_urls = {
        FRB + x["l"]
        for x in press
        if x.get("pt") == "Monetary Policy"
        and "Minutes of the Federal Open Market Committee" in x["t"]
    }
    feed_at = {FRB + x["l"]: feed_time(x["d"]) for x in press}

    cal = calendar_events(until, log)
    scheduled_days = {
        e.day for e in cal if e.section.startswith("FOMC") and re.search(r"FOMC Meeting", e.title)
    }

    statement_days: dict[date, bool] = {}
    for kind, urls in (("FOMC_STATEMENT", statement_urls), ("FOMC_MINUTES", minutes_urls)):
        for url in sorted(urls):
            listed = feed_at.get(url)
            if listed and not (START <= listed.date() <= until):
                continue
            at = press_release_time(url)
            if at is None:
                if listed is None:
                    log.append(f"FRB {url}: no release time, skipped")
                    continue
                at = listed
                log.append(f"FRB {url}: no 'For release at' line, using feed time")
            elif listed and listed != at:
                log.append(f"FRB {url}: feed time {listed} != page time {at}")
            if not (START <= at.date() <= until):
                continue
            scheduled = True
            if kind == "FOMC_STATEMENT":
                scheduled = url not in unscheduled_urls and at.date() in scheduled_days
                statement_days[at.date()] = scheduled
            rows.append(Row("", kind, "FRB", at, scheduled, url))

    # Press conferences: start time where the Board states it, else the standing 2:30 p.m.
    stated = {
        e.day: e for e in cal if e.section.startswith("FOMC") and "Press Conference" in e.title
    }
    stated.update(announced_presser_times(cal))
    for day, url in sorted(presser_urls.items()):
        if not (START <= day <= until):
            continue
        if not statement_days.get(day, False):
            log.append(f"FRB presser {day}: unscheduled meeting, start time not published; no row")
            continue
        if day in stated and stated[day].clock:
            hh, mm = stated[day].clock
            rows.append(
                Row(
                    "",
                    "FOMC_PRESSER",
                    "FRB",
                    datetime(day.year, day.month, day.day, hh, mm),
                    True,
                    stated[day].url,
                )
            )
        else:
            rows.append(
                Row(
                    "",
                    "FOMC_PRESSER",
                    "FRB",
                    datetime(day.year, day.month, day.day, 14, 30),
                    True,
                    url,
                    "builder-time-assumed",
                )
            )

    rows += chair_events(cal, until, log)
    return rows


@dataclass
class CalEvent:
    day: date
    clock: tuple[int, int] | None
    section: str
    title: str
    detail: str
    url: str


def _cal_html(year: int, month: int) -> list[CalEvent]:
    url = f"{FRB}/newsevents/{year}-{calendar.month_name[month].lower()}.htm"
    try:
        raw = fetch(url, index=date(year, month, 1) > date.today() - timedelta(days=62))
    except FetchError as exc:
        if exc.status == 404:
            return []
        raise
    raw_s = raw.decode("utf-8", "replace")
    out: list[CalEvent] = []
    sections = re.split(r'<h4 class="col-md-12">\s*([^<]+?)\s*</h4>', raw_s)
    for section, body in zip(sections[1::2], sections[2::2], strict=True):
        for m in re.finditer(
            r'class="col-xs-2">\s*<p>(.*?)</p>\s*</div>\s*<div class="col-xs-7">(.*?)</div>\s*'
            r'<div class="col-xs-3">\s*<p>(.*?)</p>',
            body,
            flags=re.S,
        ):
            paras = [
                re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", p))).strip()
                for p in re.findall(r"<p[^>]*>(.*?)</p>", m.group(2), flags=re.S)
            ]
            paras = [p for p in paras if p and p != "Watch Live"]
            if not paras:
                continue
            for d in re.findall(r"\d{1,2}", page_text(m.group(3).encode())):
                try:
                    day = date(year, month, int(d))
                except ValueError:
                    continue
                out.append(
                    CalEvent(
                        day,
                        parse_clock(page_text(m.group(1).encode())),
                        section,
                        paras[0],
                        " | ".join(paras[1:]),
                        url,
                    )
                )
    return out


def _cal_json(until: date) -> list[CalEvent]:
    url = FED_FEEDS["calendar"]
    data = load_json(fetch(url, index=True))
    out: list[CalEvent] = []
    for e in data.get("events", []):
        month = e.get("month") or ""
        if not re.fullmatch(r"\d{4}-\d{2}", month):
            continue  # some entries carry no month; the HTML calendars cover those
        y, mo = map(int, month.split("-"))
        for d in re.findall(r"\d{1,2}", e.get("days", "")):
            try:
                day = date(y, mo, int(d))
            except ValueError:
                continue
            desc = html.unescape(html.unescape(e.get("description", "")))
            out.append(
                CalEvent(
                    day,
                    parse_clock(e.get("time", "")),
                    {"FOMC": "FOMC Meetings"}.get(e.get("type", ""), e.get("type", "")),
                    html.unescape(e.get("title", "")).strip(),
                    " | ".join(
                        x
                        for x in (html.unescape(e.get("location", "")), page_text(desc.encode()))
                        if x
                    ),
                    url,
                )
            )
    return out


_cal_cache: list[CalEvent] | None = None


def calendar_events(until: date, log: list[str]) -> list[CalEvent]:
    """Board calendar entries: the monthly HTML pages first, calendar.json filling gaps."""
    global _cal_cache
    if _cal_cache is not None:
        return _cal_cache
    events: list[CalEvent] = []
    for y in range(START.year, until.year + 1):
        for m in range(1, 13):
            if date(y, m, 1) <= until:
                events += _cal_html(y, m)

    def key(e: CalEvent):
        name = re.sub(r"[^a-z]", "", e.title.lower().replace("chairman", "chair"))
        return (e.day, e.clock, name)

    have = {key(e) for e in events}
    added = 0
    for e in _cal_json(until):
        if START <= e.day <= until and key(e) not in have:
            events.append(e)
            have.add(key(e))
            added += 1
    log.append(
        f"FRB calendar: {len(events) - added} entries from monthly pages, "
        f"{added} from calendar.json"
    )
    _cal_cache = events
    return events


def announced_presser_times(cal: list[CalEvent]) -> dict[date, CalEvent]:
    """Announcements such as '... the Chair's news conference will start at 2:30 p.m.'."""
    out: dict[date, CalEvent] = {}
    for e in cal:
        text = f"{e.title} {e.detail}"
        m = re.search(r"news conference will (?:start|begin) at ([\d:]+\s*[ap]\.?m\.?)", text, re.I)
        if not m:
            continue
        meet = re.search(r"FOMC statement will be released", text)
        if meet:
            for f in cal:
                if (
                    f.section.startswith("FOMC")
                    and "FOMC Meeting" in f.title
                    and 0 <= (f.day - e.day).days <= 2
                ):
                    out[f.day] = CalEvent(
                        f.day, parse_clock(m.group(1)), e.section, e.title, e.detail, e.url
                    )
    return out


def chair_events(cal: list[CalEvent], until: date, log: list[str]) -> list[Row]:
    rows: list[Row] = []
    testimony = [x for x in load_json(fetch(FED_FEEDS["testimony"], index=True)) if "d" in x]
    hh_feed = [
        (feed_time(x["d"]), FRB + x["l"])
        for x in testimony
        if "Semiannual Monetary Policy Report" in x.get("t", "") and CHAIR.search(x.get("s", ""))
    ]
    hh_feed = [(t, u) for t, u in hh_feed if t and START <= t.date() <= until]
    seen: set[tuple[date, tuple[int, int] | None]] = set()
    for e in sorted(cal, key=lambda e: (e.day, e.clock or (0, 0))):
        if not CHAIR.search(e.title) or not (START <= e.day <= until):
            continue
        if e.section not in ("Speeches", "Testimony", "events"):
            continue
        if (e.day, e.clock) in seen:
            continue
        seen.add((e.day, e.clock))
        if e.clock is None:
            log.append(f"FRB calendar {e.day} {e.title}: no time, skipped")
            continue
        local = datetime(e.day.year, e.day.month, e.day.day, *e.clock)
        if e.section == "Testimony":
            is_hh = any(0 <= (e.day - t.date()).days <= 3 for t, _ in hh_feed)
            kind = "FED_CHAIR_TESTIMONY" if is_hh else "FED_CHAIR_SPEECH"
        elif re.search(r"Jackson Hole", e.detail, re.I):
            if e.day.month != 8:
                # The symposium is always in August; the Sep 2019 calendar
                # page repeats the Aug 23 keynote on the 23rd by mistake.
                log.append(f"FRB calendar {e.day}: Jackson Hole entry outside August, skipped")
                continue
            kind = "JACKSON_HOLE"
        else:
            kind = "FED_CHAIR_SPEECH"
        rows.append(Row("", kind, "FRB", local, True, e.url))
    # Prepared testimony posted before the hearing opened is its own market event.
    hearings = {r.local.date(): r.local for r in rows if r.event_type == "FED_CHAIR_TESTIMONY"}
    for t, url in hh_feed:
        start = hearings.get(t.date())
        if start is None:
            log.append(
                f"FRB testimony {t:%Y-%m-%d}: in feed but no calendar hearing; using feed time"
            )
            rows.append(Row("", "FED_CHAIR_TESTIMONY", "FRB", t, True, url))
        elif t < start:
            rows.append(Row("", "FED_CHAIR_TESTIMONY", "FRB", t, True, url, "builder"))
    return rows


# --------------------------------------------------------------------------- BLS

BLS_SERIES = {"CPI": "cpi", "NFP": "empsit", "PPI": "ppi", "JOLTS": "jolts"}
BLS_EMBARGO = re.compile(
    r"embargoed\s+until\s+(\d{1,2}):(\d{2})\s*([ap])\.?m\.?\s*\(?(?:ET|EDT|EST)?\)?", re.I
)


def bls_events(until: date, log: list[str]) -> list[Row]:
    """Actual BLS releases from the per-series release archives.

    Not exercised against the live site: www.bls.gov answers 403 to automated
    clients without owner contact details (see module docstring).
    """
    rows: list[Row] = []
    for kind, code in BLS_SERIES.items():
        listing = fetch(f"{BLS}/bls/news-release/{code}.htm", index=True).decode("utf-8", "replace")
        for m in sorted(
            set(re.findall(rf"/news\.release/archives/{code}_(\d{{8}})\.htm", listing))
        ):
            day = datetime.strptime(m, "%m%d%Y").date()
            if not (START <= day <= until):
                continue
            url = f"{BLS}/news.release/archives/{code}_{m}.htm"
            em = BLS_EMBARGO.search(page_text(fetch(url)))
            if not em:
                log.append(f"BLS {url}: no embargo time, skipped")
                continue
            hh, mm = clock(em.group(1), em.group(2), em.group(3))
            local = datetime(day.year, day.month, day.day, hh, mm)
            rows.append(Row("", kind, "BLS", local, True, url))
    return rows


# --------------------------------------------------------------------------- main

PREFIX = {
    "CPI": "cpi",
    "NFP": "nfp",
    "PPI": "ppi",
    "GDP": "gdp",
    "PCE": "pce",
    "FOMC_STATEMENT": "fomc",
    "FOMC_MINUTES": "fomc-minutes",
    "FOMC_PRESSER": "fomc-presser",
    "FED_CHAIR_TESTIMONY": "chair-testimony",
    "JACKSON_HOLE": "jackson-hole",
    "FED_CHAIR_SPEECH": "chair-speech",
    "JOLTS": "jolts",
}


def assign_ids(rows: list[Row]) -> None:
    by_day: dict[tuple[str, date], list[Row]] = defaultdict(list)
    for r in rows:
        by_day[(r.event_type, r.local.date())].append(r)
    for (kind, day), group in by_day.items():
        base = f"{PREFIX[kind]}-{day:%Y-%m-%d}"
        group.sort(key=lambda r: r.local)
        if len(group) == 1:
            group[0].event_id = base
        else:
            for r in group:
                r.event_id = f"{base}-{r.local:%H%M}"


def read_existing(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


def main(argv: list[str] | None = None) -> int:
    global _refresh
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--until", type=date.fromisoformat, default=date.today())
    ap.add_argument("--refresh", action="store_true", help="re-fetch index pages and feeds")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    _refresh = args.refresh
    log: list[str] = []

    rows: list[Row] = []
    kept: list[dict[str, str]] = []
    existing = read_existing(args.out)
    for publisher, build in (("BEA", bea_events), ("FRB", fed_events), ("BLS", bls_events)):
        try:
            got = build(args.until, log)
        except FetchError as exc:
            old = [r for r in existing if r["publisher"] == publisher]
            log.append(f"{publisher}: fetch failed ({exc}); keeping {len(old)} existing rows")
            kept += old
            continue
        rows += got

    # Same event seen twice (e.g. a release listed on two pages): keep the first.
    uniq: dict[tuple[str, datetime], Row] = {}
    for r in rows:
        uniq.setdefault((r.event_type, r.local), r)
    rows = list(uniq.values())
    assign_ids(rows)

    out_rows = [r.csv() for r in rows] + kept
    out_rows.sort(key=lambda r: (r["utc_time"], r["event_id"]))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(out_rows)

    for line in log:
        print("note:", line, file=sys.stderr)
    counts = Counter((r["event_type"], r["local_time_et"][:4]) for r in out_rows)
    years = sorted({y for _, y in counts})
    kinds = sorted({k for k, _ in counts})
    print(f"{'type':<20}" + "".join(f"{y:>6}" for y in years) + f"{'total':>7}")
    for k in kinds:
        print(
            f"{k:<20}"
            + "".join(f"{counts.get((k, y), 0):>6}" for y in years)
            + f"{sum(counts.get((k, y), 0) for y in years):>7}"
        )
    print(f"{len(out_rows)} rows -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
