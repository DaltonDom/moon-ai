from datetime import date, datetime

from moon_ai.data.news import COLUMNS
from moon_ai.data.store import BarStore
from moon_ai.doctor import (
    check_bars,
    check_disk,
    check_journal,
    check_keys,
    check_native,
    check_news,
    check_nightly,
    check_python,
    report,
)
from moon_ai.journal import SQLiteStore
from tests.test_store import row, write


def test_python_and_disk_pass_here(tmp_path):
    assert check_python().level == "ok"
    assert check_disk(tmp_path).level == "ok"


def test_keys_from_env_or_file(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("DATABENTO_API_KEY=db-x\n")
    got = {r.name: r.level for r in check_keys({"GEMINI_API_KEY": "g"}, env_file)}
    assert got == {
        "DATABENTO_API_KEY": "ok",
        "GITHUB_TOKEN": "warn",
        "GEMINI_API_KEY": "ok",
        "ANTHROPIC_API_KEY": "warn",
        "YOUTUBE_API_KEY": "warn",
    }
    missing = {r.name: r for r in check_keys({}, tmp_path / "none")}
    assert missing["DATABENTO_API_KEY"].level == "fail"
    assert "Never put keys in the repo" in missing["DATABENTO_API_KEY"].fix


def test_bar_coverage(tmp_path):
    store = BarStore(tmp_path)
    assert check_bars(store, "MNQ.v.0", date(2026, 11, 1)).level == "fail"
    t = datetime.fromisoformat("2026-10-27T14:00:00+00:00")
    write(tmp_path, "MNQ.v.0", "2019-05-06_2026-10-31", [row(t, 100)])
    assert check_bars(store, "MNQ.v.0", date(2026, 11, 1)).level == "ok"
    assert check_bars(store, "MNQ.v.0", date(2026, 12, 1)).level == "warn"
    write(tmp_path / "late", "MNQ.v.0", "2024-01-01_2026-10-31", [row(t, 100)])
    assert (
        "after the 2019 launch"
        in check_bars(BarStore(tmp_path / "late"), "MNQ.v.0", date(2026, 11, 1)).message
    )


def test_news_calendar(tmp_path):
    assert check_news(tmp_path / "missing.csv").level == "fail"
    empty = tmp_path / "news.csv"
    empty.write_text(",".join(COLUMNS) + "\n")
    assert check_news(empty).level == "warn"


def test_journal_and_nightly(tmp_path):
    assert check_journal(tmp_path / "j.sqlite").level == "warn"
    SQLiteStore(tmp_path / "j.sqlite").close()
    assert check_journal(tmp_path / "j.sqlite").level == "ok"
    (tmp_path / "bad.sqlite").write_text("not a database")
    assert check_journal(tmp_path / "bad.sqlite").level == "fail"
    assert check_nightly(tmp_path).level == "warn"
    (tmp_path / "com.moonai.nightly.plist").write_text("")
    assert check_nightly(tmp_path).level == "ok"


def test_report_reads_as_sentences():
    from moon_ai.doctor import Result

    text, code = report(
        [
            Result("ok", "a", "Python 3.12 is installed."),
            Result("warn", "b", "The nightly paper run isn't installed yet.", "Later."),
        ]
    )
    assert code == 0 and "✓ Python 3.12 is installed." in text and "→ Later." in text
    assert "nothing blocking" in text
    _, code = report([Result("fail", "c", "No price data.", "Download it.")])
    assert code == 1


def test_intel_mode_python_on_an_apple_chip_fails():
    r = check_native("Darwin", "x86_64", apple_chip=lambda: True)
    assert r.level == "fail" and "Rosetta" in r.message and "aarch64" in r.fix
    assert check_native("Darwin", "arm64", apple_chip=lambda: True).level == "ok"
    assert check_native("Darwin", "x86_64", apple_chip=lambda: False).level == "ok"  # Intel Mac
    assert check_native("Linux", "x86_64", apple_chip=lambda: True).level == "ok"


def test_a_nightly_run_that_stopped_is_flagged(tmp_path):
    import sqlite3
    from datetime import UTC, datetime, timedelta

    path = tmp_path / "j.sqlite"
    SQLiteStore(path).close()
    last = datetime(2026, 11, 1, 23, 0, tzinfo=UTC)

    with sqlite3.connect(path) as conn:
        conn.execute(
            "INSERT INTO events (event_id, run_id, ts, step, status, message) "
            "VALUES ('e1', 'paper', ?, 'summary', 'ok', 'done')",
            (last.isoformat(),),
        )
    assert check_journal(path, now=last + timedelta(hours=30)).level == "ok"
    stale = check_journal(path, now=last + timedelta(days=3))
    assert stale.level == "warn" and "3 day(s) ago" in stale.message
