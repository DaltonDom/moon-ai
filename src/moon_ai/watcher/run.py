"""The watcher's steps. HTTP clients are injected, so tests never touch the network."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

CHANNEL_ID = "UCtjxa77NqamhVC8atV85Rog"  # InnerCircleTrader, checked with the Data API (#21)
UPLOADS = "UU" + CHANNEL_ID[2:]
MENTORSHIP_2022 = "PLVgHx4Z63paYiFGQ56PjTF1PGePL3r69s"
# 2023 Silver Bullet lecture and ICT's 2017 session videos
# (docs/research/ict-setup-timestamps.md §4).
FIRST_RUN_VIDEOS = (
    "tRq1hyGGtl4",
    "G8OEsUAoIWE",
    "Cg0-CFJOJvg",
    "ley5HZs4bUM",
    "JA0mLNJeytY",
    "3OEUIkkcmLE",
    "plNN9n7nrxc",
)
GEMINI_MODEL = "gemini-flash-latest"
DAILY_VIDEO_SECONDS = 8 * 3600
DAILY_REQUESTS = 20
YT = "https://www.googleapis.com/youtube/v3"
GEMINI = "https://generativelanguage.googleapis.com/v1beta"

NOTES_PROMPT = """You are taking study notes on a video by ICT (Michael J. Huddleston) for a
trading bot that codes ICT setups on index futures. List, with mm:ss timestamps
from the start of the video:
- any trading setup or model he teaches, and its rules (times of day in New York time, what
  liquidity is taken, structure shifts, fair value gaps, entries, stops, targets, filters);
- any change to a rule he taught before;
- any time window he names.
Quote him briefly where the exact words matter. Say "nothing about setups" if there is none.
Markdown bullets only. Do not transcribe the whole video."""


class QuotaExhausted(Exception):
    """The free tier is used up for today: stop, never pay."""


class Unusable(Exception):
    """Gemini failed or refused this video: it goes to the user's-notes fallback."""


# --- durations -----------------------------------------------------------------------


def iso_seconds(d: str) -> int:
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d or "")
    if not m:
        return 0
    days, h, mi, s = (int(x or 0) for x in m.groups())
    return days * 86400 + h * 3600 + mi * 60 + s


# --- clients ------------------------------------------------------------------------


class YouTube:
    def __init__(self, key: str | None = None, http: httpx.Client | None = None):
        self.key = key or os.environ.get("YOUTUBE_API_KEY")
        if not self.key:
            raise Unusable("YOUTUBE_API_KEY is not set")
        self.http = http or httpx.Client(timeout=30)

    def _get(self, path: str, **params: Any) -> dict[str, Any]:
        r = self.http.get(f"{YT}/{path}", params={**params, "key": self.key})
        r.raise_for_status()
        return r.json()

    def playlist(self, playlist_id: str, since: datetime | None = None) -> list[str]:
        """Video ids in a playlist, newest first, stopping at `since` for the uploads list."""
        out, token = [], None
        while True:
            page = self._get(
                "playlistItems",
                part="contentDetails",
                playlistId=playlist_id,
                maxResults=50,
                **({"pageToken": token} if token else {}),
            )
            for it in page.get("items", []):
                cd = it["contentDetails"]
                published = cd.get("videoPublishedAt")
                if (
                    since
                    and published
                    and datetime.fromisoformat(published.replace("Z", "+00:00")) < since
                ):
                    return out
                out.append(cd["videoId"])
            token = page.get("nextPageToken")
            if not token:
                return out

    def videos(self, ids: list[str]) -> dict[str, dict[str, Any]]:
        out = {}
        for i in range(0, len(ids), 50):
            page = self._get("videos", part="contentDetails,snippet", id=",".join(ids[i : i + 50]))
            for it in page.get("items", []):
                out[it["id"]] = {
                    "title": it["snippet"]["title"],
                    "published": it["snippet"]["publishedAt"],
                    "seconds": iso_seconds(it["contentDetails"]["duration"]),
                }
        return out


class Gemini:
    def __init__(self, key: str | None = None, http: httpx.Client | None = None):
        self.key = key or os.environ.get("GEMINI_API_KEY")
        if not self.key:
            raise Unusable("GEMINI_API_KEY is not set")
        self.http = http or httpx.Client(timeout=600)

    def notes(self, video_id: str) -> str:
        r = self.http.post(
            f"{GEMINI}/models/{GEMINI_MODEL}:generateContent",
            headers={"x-goog-api-key": self.key},
            json={
                "contents": [
                    {
                        "parts": [
                            {
                                "file_data": {
                                    "file_uri": f"https://www.youtube.com/watch?v={video_id}"
                                }
                            },
                            {"text": NOTES_PROMPT},
                        ]
                    }
                ],
                "generationConfig": {"mediaResolution": "MEDIA_RESOLUTION_LOW"},
            },
        )
        if r.status_code == 429:
            raise QuotaExhausted("Gemini free-tier quota reached")
        if r.status_code >= 400:
            raise Unusable(f"Gemini HTTP {r.status_code}: {r.text[:200]}")
        body = r.json()
        block = (body.get("promptFeedback") or {}).get("blockReason")
        cands = body.get("candidates") or []
        if block or not cands:
            raise Unusable(f"Gemini refused ({block or 'no answer'})")
        c = cands[0]
        text = "".join(p.get("text", "") for p in (c.get("content") or {}).get("parts", []))
        if c.get("finishReason") not in (None, "STOP") or not text.strip():
            raise Unusable(f"Gemini stopped early ({c.get('finishReason')})")
        return text


# --- state ---------------------------------------------------------------------------


@dataclass
class State:
    last_discovery: str | None = None
    first_run_queued: bool = False
    videos: dict[str, dict[str, Any]] = field(default_factory=dict)  # id -> info + status
    usage: dict[str, dict[str, int]] = field(default_factory=dict)  # day -> {seconds, requests}
    summarised: list[str] = field(default_factory=list)  # months

    @classmethod
    def load(cls, path: Path) -> State:
        return cls(**json.loads(path.read_text())) if path.exists() else cls()

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.__dict__, indent=1, sort_keys=True) + "\n")
        tmp.replace(path)


@dataclass
class WatchResult:
    found: int = 0
    found_hours: float = 0.0
    noted: int = 0
    fallback: int = 0
    waiting: int = 0
    from_inbox: int = 0
    summary: Path | None = None
    issue: int | None = None
    notes: list[str] = field(default_factory=list)

    def message(self) -> str:
        parts = [
            f"{self.found} new video(s) ({self.found_hours:.1f} h)",
            f"{self.noted} turned into notes",
        ]
        if self.from_inbox:
            parts.append(f"{self.from_inbox} from your notes inbox")
        if self.fallback:
            parts.append(f"{self.fallback} need your own notes (data/watcher/inbox/)")
        if self.waiting:
            parts.append(f"{self.waiting} waiting for tomorrow's free quota")
        if self.summary:
            parts.append(
                f"summary {self.summary.name}"
                + (f", review item #{self.issue}" if self.issue else "")
            )
        return ", ".join(parts) + "." + ("" if not self.notes else " " + "; ".join(self.notes))


# --- the run -------------------------------------------------------------------------


class Watcher:
    def __init__(
        self,
        root: Path,
        reports: Path,
        youtube: Callable[[], YouTube] = YouTube,
        gemini: Callable[[], Gemini] = Gemini,
        summarise: Callable[[str, list[dict[str, Any]]], tuple[str, float]] | None = None,
        github: Callable[[], Any] | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        on_spend: Callable[[float, str], None] | None = None,
    ):
        self.root, self.reports = Path(root), Path(reports)
        self.youtube, self.gemini, self.summarise, self.github = youtube, gemini, summarise, github
        self.now, self.on_spend = now, on_spend
        self.state_path = self.root / "state.json"
        self.notes_dir, self.inbox = self.root / "notes", self.root / "inbox"

    def run(self, month: str | None = None) -> WatchResult:
        """`month` ("YYYY-MM") targets a past month instead of new uploads."""
        st = State.load(self.state_path)
        res = WatchResult()
        self.discover(st, res, month)
        self.read_inbox(st, res)
        self.transcribe(st, res)
        self.maybe_summarise(st, res, month)
        st.save(self.state_path)
        return res

    # 1. discovery
    def discover(self, st: State, res: WatchResult, month: str | None) -> None:
        now = self.now()
        if (
            month is None
            and st.last_discovery
            and now - datetime.fromisoformat(st.last_discovery) < timedelta(days=28)
        ):
            return
        yt = self.youtube()
        if month:
            start = datetime.fromisoformat(f"{month}-01T00:00:00+00:00")
            end = (start + timedelta(days=32)).replace(day=1)
            ids = yt.playlist(UPLOADS, since=start)
        else:
            start = (
                datetime.fromisoformat(st.last_discovery)
                if st.last_discovery
                else now - timedelta(days=1)
            )
            end = now
            ids = yt.playlist(UPLOADS, since=start)
        if not st.first_run_queued and month is None:
            ids = ids + yt.playlist(MENTORSHIP_2022) + list(FIRST_RUN_VIDEOS)
            st.first_run_queued = True
        new = [i for i in dict.fromkeys(ids) if i not in st.videos]
        info = yt.videos(new) if new else {}
        for vid, meta in info.items():
            published = datetime.fromisoformat(meta["published"].replace("Z", "+00:00"))
            in_window = start <= published < end
            if month and not in_window:
                continue
            st.videos[vid] = {
                **meta,
                "status": "queued",
                "month": published.strftime("%Y-%m") if in_window else "first-run",
                "targeted": not in_window,  # the first run's list, read after new uploads
            }
            res.found += 1
            res.found_hours += meta["seconds"] / 3600
        if month is None:
            st.last_discovery = now.isoformat()
        if res.found_hours > 8 * 30:
            res.notes.append("uploads exceed what 8 h/day can cover in a month")

    # 3. fallback inbox
    def read_inbox(self, st: State, res: WatchResult) -> None:
        if not self.inbox.exists():
            return
        for f in sorted(self.inbox.glob("*.md")):
            vid = f.stem if f.stem in st.videos else None
            dest = self.notes_dir / f.name
            self.notes_dir.mkdir(parents=True, exist_ok=True)
            dest.write_text(f.read_text())
            f.unlink()
            if vid:
                st.videos[vid].update(status="noted", source="user")
            else:
                st.videos[f"user:{f.stem}"] = {
                    "title": f.stem,
                    "published": self.now().isoformat(),
                    "seconds": 0,
                    "status": "noted",
                    "source": "user",
                    "month": self.now().strftime("%Y-%m"),
                }
            res.from_inbox += 1

    # 2. notes
    def transcribe(self, st: State, res: WatchResult) -> None:
        today = self.now().date().isoformat()
        use = st.usage.setdefault(today, {"seconds": 0, "requests": 0})
        queued = sorted(
            (v for v in st.videos.items() if v[1]["status"] == "queued"),
            key=lambda kv: (kv[1].get("targeted", False), kv[1]["published"]),
        )
        gem = None
        for vid, v in queued:
            if v["seconds"] > DAILY_VIDEO_SECONDS:
                v["status"], v["why"] = "fallback", "longer than the 8-hour daily limit"
                res.fallback += 1
                continue
            if (
                use["seconds"] + v["seconds"] > DAILY_VIDEO_SECONDS
                or use["requests"] >= DAILY_REQUESTS
            ):
                res.waiting += 1
                continue
            try:
                gem = gem or self.gemini()
                use["requests"] += 1
                text = gem.notes(vid)
            except QuotaExhausted:
                use["requests"] = DAILY_REQUESTS
                res.waiting += 1
                continue
            except Unusable as exc:
                v["status"], v["why"] = "fallback", str(exc)
                res.fallback += 1
                continue
            use["seconds"] += v["seconds"]
            self.notes_dir.mkdir(parents=True, exist_ok=True)
            (self.notes_dir / f"{vid}.md").write_text(
                f"# {v['title']}\n\nhttps://www.youtube.com/watch?v={vid}"
                f" · published {v['published'][:10]}"
                f" · notes by {GEMINI_MODEL}\n\n{text.strip()}\n"
            )
            v.update(status="noted", source="gemini")
            res.noted += 1

    # 4. summary + review item
    def maybe_summarise(self, st: State, res: WatchResult, month: str | None) -> None:
        groups: dict[str, list[str]] = {}
        for vid, v in st.videos.items():
            groups.setdefault(v["month"], []).append(vid)
        current = self.now().strftime("%Y-%m")
        for m, vids in sorted(groups.items()):
            if m in st.summarised or (m == current and month != m):
                continue  # this month is still running
            if any(st.videos[v]["status"] == "queued" for v in vids):
                continue  # wait until every video has notes or is in the fallback
            noted = [v for v in vids if st.videos[v]["status"] == "noted"]
            items = [{"id": v, **st.videos[v], "notes": self._notes(v)} for v in noted]
            text, cost = (
                self.summarise(m, items)
                if self.summarise and items
                else (_plain_summary(m, items), 0.0)
            )
            if cost and self.on_spend:
                self.on_spend(cost, f"watcher {m}")
            fallback = [v for v in vids if st.videos[v]["status"] == "fallback"]
            page = _summary_page(m, items, fallback, st.videos, text)
            self.reports.mkdir(parents=True, exist_ok=True)
            path = self.reports / f"{m}.md"
            path.write_text(page)
            res.summary = path
            if self.github and (items or fallback):
                issue = self.github().create_issue(
                    f"[ict-watcher] {m}: {len(items)} video(s) summarised",
                    page
                    + "\n\n---\n_Opened by moon-ai's ICT watcher. Approve a candidate setup in a "
                    "comment before it is coded and tested._",
                    ["ict-watcher"],
                )
                res.issue = issue["number"]
            st.summarised.append(m)

    def _notes(self, vid: str) -> str:
        name = vid.removeprefix("user:")
        p = self.notes_dir / f"{name}.md"
        return p.read_text() if p.exists() else ""


def _plain_summary(month: str, items: list[dict[str, Any]]) -> str:
    return "No Claude summary (no API key). Read the notes below."


def _summary_page(
    month: str,
    items: list[dict[str, Any]],
    fallback: list[str],
    videos: dict[str, dict[str, Any]],
    summary: str,
) -> str:
    hours = sum(v["seconds"] for v in videos.values() if v["month"] == month) / 3600
    out = [
        f"# ICT watcher: {month}",
        "",
        f"{len(items)} video(s) with notes, {hours:.1f} h of video.",
        "",
    ]
    out += ["## Candidate setups", "", summary.strip(), ""]
    if fallback:
        out += ["## Need your own notes", ""]
        out += [
            f"- [{videos[v]['title']}](https://www.youtube.com/watch?v={v}): "
            f"{videos[v].get('why', '')}. "
            f"Drop notes in `data/watcher/inbox/{v}.md`."
            for v in fallback
        ]
        out.append("")
    out += ["## Videos", ""]
    out += [
        f"- [{i['title']}](https://www.youtube.com/watch?v={i['id']}) ({i['seconds'] // 60} min)"
        for i in items
    ]
    return "\n".join(out) + "\n"


# --- Claude summary ------------------------------------------------------------------

SUMMARY_SYSTEM = """You read study notes from ICT's (Michael J. Huddleston's) videos and pull out
candidate trading setups for a bot that trades MNQ futures. For each candidate: a name, the exact
rules as stated (with the video and mm:ss timestamp for each rule), how it differs from the bot's
existing setups (NY AM/PM Silver Bullet, London sweep-and-reverse, OTE pullback, 2022 model), and
what is still unclear. Only use what the notes say. If the notes contain no new setup or rule
change, say so in one line. Markdown, plain language."""


def claude_summariser(client: Any) -> Callable[[str, list[dict[str, Any]]], tuple[str, float]]:
    def run(month: str, items: list[dict[str, Any]]) -> tuple[str, float]:
        notes = "\n\n".join(f"## {i['title']} ({i['id']})\n{i['notes']}" for i in items)
        msg = client.messages.create(
            model="claude-opus-5-5",
            max_tokens=16000,
            system=SUMMARY_SYSTEM,
            output_config={"effort": "high"},
            messages=[{"role": "user", "content": f"Notes for {month}:\n\n{notes}"}],
        )
        cost = ((msg.usage.input_tokens or 0) * 4.0 + (msg.usage.output_tokens or 0) * 20.0) / 1e6
        if msg.stop_reason == "refusal":
            return "Claude declined to summarise this month; read the notes below.", cost
        return next((b.text for b in msg.content if b.type == "text"), ""), cost

    return run
