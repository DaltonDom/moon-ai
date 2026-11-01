"""The monthly ICT watcher against fake YouTube, Gemini, Claude and GitHub (#55)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from moon_ai.watcher.run import (
    DAILY_REQUESTS,
    FIRST_RUN_VIDEOS,
    MENTORSHIP_2022,
    UPLOADS,
    QuotaExhausted,
    Unusable,
    Watcher,
    iso_seconds,
)

NOW = datetime(2026, 11, 1, 23, 0, tzinfo=UTC)
SEPT = {  # a fixed past month: id -> (published, seconds)
    "a1": ("2026-09-03T12:00:00Z", 3 * 3600),
    "a2": ("2026-09-10T12:00:00Z", 3 * 3600),
    "a3": ("2026-09-20T12:00:00Z", 3 * 3600),
    "long": ("2026-09-25T12:00:00Z", 9 * 3600),
}
OCT = {"b1": ("2026-11-01T12:00:00Z", 1800)}


class FakeYT:
    def __init__(self):
        self.calls = []

    def playlist(self, pid, since=None):
        self.calls.append(pid)
        if pid == UPLOADS:
            vids = {**OCT, **SEPT}
            return [
                v
                for v, (p, _) in sorted(vids.items(), key=lambda kv: kv[1][0], reverse=True)
                if since is None or datetime.fromisoformat(p.replace("Z", "+00:00")) >= since
            ]
        if pid == MENTORSHIP_2022:
            return ["m1"]
        return []

    def videos(self, ids):
        everything = {**SEPT, **OCT, "m1": ("2022-05-01T00:00:00Z", 3600)}
        everything |= {v: ("2023-01-01T00:00:00Z", 1200) for v in FIRST_RUN_VIDEOS}
        return {
            i: {"title": f"Video {i}", "published": everything[i][0], "seconds": everything[i][1]}
            for i in ids
        }


class FakeGemini:
    def __init__(self, fail=(), quota_after=None):
        self.calls, self.fail, self.quota_after = [], set(fail), quota_after

    def notes(self, vid):
        self.calls.append(vid)
        if self.quota_after is not None and len(self.calls) > self.quota_after:
            raise QuotaExhausted("429")
        if vid in self.fail:
            raise Unusable("Gemini refused (SAFETY)")
        return f"- 10:00 ICT names a window for {vid}"


class FakeGH:
    def __init__(self):
        self.issues = []

    def create_issue(self, title, body, labels):
        self.issues.append((title, body, labels))
        return {"number": 7}


def watcher(tmp_path, gem, now=NOW, summarise=None, gh=None):
    yt = FakeYT()
    w = Watcher(
        tmp_path / "watcher",
        tmp_path / "reports",
        youtube=lambda: yt,
        gemini=lambda: gem,
        summarise=summarise,
        github=(lambda: gh) if gh else None,
        now=lambda: now,
    )
    return w, yt


def state(tmp_path):
    return json.loads((tmp_path / "watcher" / "state.json").read_text())


def test_iso_durations():
    assert (
        iso_seconds("PT1H2M3S") == 3723
        and iso_seconds("PT45M") == 2700
        and iso_seconds("P1DT1S") == 86401
    )
    assert iso_seconds("") == 0


def test_a_past_month_gets_notes_within_the_daily_quota(tmp_path):
    gem, gh = FakeGemini(), FakeGH()
    spent = []
    w, _ = watcher(
        tmp_path, gem, summarise=lambda m, items: (f"{len(items)} candidates", 0.12), gh=gh
    )
    w.on_spend = lambda usd, what: spent.append((usd, what))
    r = w.run(month="2026-09")
    assert r.found == 4 and r.found_hours == 18
    # 8 h/day: two 3-hour videos fit, the third waits; the 9-hour one goes to the fallback.
    assert r.noted == 2 and r.waiting == 1 and r.fallback == 1
    assert sorted(gem.calls) == ["a1", "a2"]
    s = state(tmp_path)
    assert s["usage"]["2026-11-01"] == {"seconds": 6 * 3600, "requests": 2}
    assert s["videos"]["long"]["status"] == "fallback" and "8-hour" in s["videos"]["long"]["why"]
    assert r.summary is None  # a3 still queued

    w2, _ = watcher(
        tmp_path,
        gem,
        now=NOW.replace(day=2),
        summarise=lambda m, items: (f"{len(items)} candidates", 0.12),
        gh=gh,
    )
    w2.on_spend = lambda usd, what: spent.append((usd, what))
    r2 = w2.run(month="2026-09")
    assert r2.found == 0 and r2.noted == 1 and gem.calls[-1] == "a3"
    assert r2.summary.name == "2026-09.md" and r2.issue == 7
    page = r2.summary.read_text()
    assert (
        "3 candidates" in page
        and "Need your own notes" in page
        and "data/watcher/inbox/long.md" in page
    )
    assert gh.issues[0][2] == ["ict-watcher"] and spent == [(0.12, "watcher 2026-09")]
    assert (tmp_path / "watcher" / "notes" / "a1.md").read_text().startswith("# Video a1")


def test_quota_errors_stop_the_day_without_paying(tmp_path):
    gem = FakeGemini(quota_after=1)
    w, _ = watcher(tmp_path, gem)
    r = w.run(month="2026-09")
    assert r.noted == 1 and r.waiting == 2
    assert len(gem.calls) == 2  # the 429 ended the day; nothing more was tried
    assert state(tmp_path)["usage"]["2026-11-01"]["requests"] == DAILY_REQUESTS


def test_a_refused_video_goes_to_the_inbox_fallback(tmp_path):
    gem = FakeGemini(fail={"a1"})
    w, _ = watcher(tmp_path, gem)
    r = w.run(month="2026-09")
    assert r.fallback == 2 and state(tmp_path)["videos"]["a1"]["why"].startswith("Gemini refused")
    inbox = tmp_path / "watcher" / "inbox"
    inbox.mkdir(parents=True)
    (inbox / "a1.md").write_text("My notes: 10:00 window.")
    r = watcher(tmp_path, gem, now=NOW.replace(day=2))[0].run()
    assert r.from_inbox == 1 and state(tmp_path)["videos"]["a1"]["source"] == "user"
    assert not (inbox / "a1.md").exists()


def test_the_first_run_queues_new_uploads_and_the_targeted_list(tmp_path):
    gem = FakeGemini()
    w, yt = watcher(tmp_path, gem)
    r = w.run()
    s = state(tmp_path)
    assert MENTORSHIP_2022 in yt.calls and s["first_run_queued"]
    assert s["videos"]["b1"]["month"] == "2026-11" and not s["videos"]["b1"]["targeted"]
    assert s["videos"]["m1"]["targeted"] and s["videos"]["tRq1hyGGtl4"]["month"] == "first-run"
    assert gem.calls[0] == "b1"  # new uploads before the targeted list
    assert r.found == 1 + 1 + len(FIRST_RUN_VIDEOS)
    # Discovery is monthly: a run the next day finds nothing new.
    yt2_calls = watcher(tmp_path, gem, now=NOW.replace(day=2))
    yt2_calls[0].run()
    assert yt2_calls[1].calls == []


def test_without_a_claude_key_the_summary_is_still_written(tmp_path):
    gem = FakeGemini()
    w, _ = watcher(tmp_path, gem)
    w.run(month="2026-09")
    r = watcher(tmp_path, gem, now=NOW.replace(day=2))[0].run(month="2026-09")
    assert "No Claude summary" in r.summary.read_text()
