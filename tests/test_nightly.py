import fcntl
import plistlib
import shutil
from datetime import date, datetime

import pytest

from moon_ai.backtest.frozen import FIXTURE_STORE
from moon_ai.journal import SQLiteStore, decode_json
from moon_ai.nightly import launchd
from moon_ai.nightly.job import (
    PAPER_RUN,
    NightlyJob,
    Paths,
    StepResult,
    last_complete_session,
    sessions_between,
)
from moon_ai.nightly.status import status_text
from moon_ai.sessions import NY


@pytest.fixture
def paths(tmp_path):
    shutil.copytree(FIXTURE_STORE, tmp_path / "data" / "bars")
    return Paths(tmp_path / "data")


def job(paths, when=datetime(2026, 10, 23, 19, 0, tzinfo=NY)):
    sent = []
    j = NightlyJob(
        paths,
        client_factory=lambda: None,
        now=lambda: when,
        notify=lambda t, m: sent.append((t, m)),
        refresh_news=lambda: StepResult("news", "ok", "stub"),
    )
    return j, sent


def steps(results):
    return {r.step: r.status for r in results}


def test_session_helpers():
    assert last_complete_session(datetime(2026, 10, 23, 19, 0, tzinfo=NY)) == date(2026, 10, 23)
    assert last_complete_session(datetime(2026, 10, 24, 12, 0, tzinfo=NY)) == date(2026, 10, 23)
    assert sessions_between(date(2026, 10, 22), date(2026, 10, 27)) == [
        date(2026, 10, 23),
        date(2026, 10, 26),
        date(2026, 10, 27),
    ]


def test_first_run_replays_the_latest_session_then_catches_up(paths):
    j, sent = job(paths)
    first = j.run()
    assert steps(first)["preflight"] == "ok" and steps(first)["summary"] == "ok"
    replays = [r for r in first if r.step == "replay"]
    assert [r.data["session"] for r in replays] == ["2026-10-23"]
    assert sent == []
    # Re-running one older session, then a normal run, catches up what's missing after it.
    j.run(only_session=date(2026, 10, 19))
    j2, _ = job(paths, datetime(2026, 10, 23, 21, 0, tzinfo=NY))
    assert j2.replayed_sessions(SQLiteStore(paths.journal)) == {
        date(2026, 10, 19),
        date(2026, 10, 23),
    }


def test_catch_up_and_idempotent(paths):
    j, _ = job(paths)
    j.run(only_session=date(2026, 10, 20))
    out = j.run()
    assert [r.data["session"] for r in out if r.step == "replay"] == [
        "2026-10-21",
        "2026-10-22",
        "2026-10-23",
    ]
    again = j.run()
    assert [r.message for r in again if r.step == "replay"] == ["No new session to replay."]
    db = SQLiteStore(paths.journal)
    ids = [c["candidate_id"] for c in decode_json(db.read("candidates", PAPER_RUN), "candidates")]
    assert len(ids) == len(set(ids))  # nothing written twice


def test_scheduled_runs_wait_for_1830_and_run_once_a_day(paths):
    early, _ = job(paths, datetime(2026, 10, 23, 17, 0, tzinfo=NY))
    assert early.run(scheduled=True) == []
    j, _ = job(paths)
    assert j.run(scheduled=True)
    assert j.run(scheduled=True) == []


def test_the_lock_stops_a_second_run(paths):
    paths.root.mkdir(parents=True, exist_ok=True)
    with paths.lock.open("w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        j, _ = job(paths)
        (r,) = j.run()
        assert r.status == "skipped" and "already going" in r.message


def test_backups_and_status(paths):
    j, _ = job(paths)
    j.run()
    assert len(list(paths.backups.glob("journal-*.sqlite"))) == 1
    text = status_text(paths)
    assert "Run of" in text and "replay: 2026-10-23" in text and "Rules-only is in charge" in text


def test_launchd_plist_runs_the_scheduled_job(tmp_path):
    path = launchd.install(agents=tmp_path, repo=tmp_path, load=False)
    p = plistlib.loads(path.read_bytes())
    assert p["Label"] == "com.moonai.nightly"
    assert p["ProgramArguments"][-3:] == ["nightly", "run", "--scheduled"]
    assert p["StartCalendarInterval"] == {"Minute": 35}
    assert launchd.uninstall(agents=tmp_path, unload=False) and not path.exists()
