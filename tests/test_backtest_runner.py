from datetime import UTC, date, datetime, timedelta

import pytest

from moon_ai.backtest.runner import NewsCalendarMissing, roll_days_in_store, run_backtest
from moon_ai.cli import main
from moon_ai.data.news import COLUMNS
from moon_ai.data.store import BarStore
from moon_ai.journal import decode_json, read_run
from moon_ai.sessions import NY
from tests.test_store import write

FLAT = (100.0, 100.25, 99.75, 100.0)
SETUP = {
    (2, 0): (100.0, 112.0, 99.75, 100.0),  # overnight high: the draw on liquidity
    (3, 0): (100.0, 100.25, 97.0, 100.0),  # overnight low: the pool to sweep
    (10, 1): (100.0, 100.25, 99.75, 100.0),
    (10, 2): (100.0, 100.75, 99.75, 100.25),
    (10, 3): (100.25, 100.5, 98.5, 98.75),
    (10, 4): (98.75, 99.0, 96.5, 98.0),
    (10, 5): (98.0, 100.0, 97.75, 99.75),
    (10, 6): (99.75, 102.0, 99.5, 101.75),
    (10, 7): (101.75, 102.25, 100.5, 102.0),  # long setup: limit 99.5, stop 96.25, target 112
    (10, 8): (102.0, 102.0, 99.25, 100.0),  # fills the entry
}
WIN = {(10, 9): (100.0, 112.5, 100.0, 112.25)}
LOSS = {(10, 9): (100.0, 100.0, 96.0, 96.25)}
DAYS = [date(2026, 7, d) for d in (13, 14, 15, 16, 17, 20, 21, 22, 23, 24)]


def session_rows(day, special, inst=1):
    rows, last = [], 100.0
    t = datetime.combine(day - timedelta(days=1), datetime.min.time().replace(hour=18), tzinfo=NY)
    end = datetime.combine(day, datetime.min.time().replace(hour=17), tzinfo=NY)
    while t < end:
        local = (t.hour, t.minute)
        if local in special:
            o, h, lo, c = special[local]
            last = c
        else:
            o = h = lo = c = last
            h, lo = last + 0.25, last - 0.25
        rows.append((t.astimezone(UTC), o, h, lo, c, inst))
        t += timedelta(minutes=1)
    return rows


@pytest.fixture
def store(tmp_path):
    rows = []
    for i, d in enumerate(DAYS):
        rows += session_rows(d, {**SETUP, **(WIN if i % 2 == 0 else LOSS)}, inst=1 if i < 7 else 2)
    write(tmp_path / "bars", "MNQ.v.0", "2026-07-12_2026-07-25", rows)
    news = tmp_path / "news.csv"
    news.write_text(",".join(COLUMNS) + "\n")
    return tmp_path


def bt(store, run_id, **kw):
    kw.setdefault("news_csv", store / "news.csv")
    return run_backtest(
        "ny_am_silver_bullet",
        date(2026, 7, 13),
        date(2026, 7, 25),
        store_root=store / "bars",
        runs_root=store / "runs",
        run_id=run_id,
        **kw,
    )


def strip(rows, run_id):
    return [
        {
            k: (v.removeprefix(f"{run_id}:") if isinstance(v, str) else v)
            for k, v in r.items()
            if k != "run_id"
        }
        for r in rows
    ]


def test_two_runs_give_identical_candidates_and_trades(store):
    a, b = bt(store, "a"), bt(store, "b")
    for table in ("candidates", "trades", "fills"):
        ra = decode_json(read_run(a.folder, table), table)
        rb = decode_json(read_run(b.folder, table), table)
        assert strip(ra, "a") == strip(rb, "b")
    # 10 days: the roll on 2026-07-22 is skipped; the other 9 trade, alternating win/loss.
    assert a.summary["statuses"] == {"skipped:session": 1, "taken": 9}
    assert a.summary["trades"] == 9
    run = decode_json(read_run(a.folder, "runs"), "runs")[0]
    assert run["kind"] == "backtest" and len(run["defaults_hash"]) == 64
    assert run["notes"]["trial"] == "default"


def test_roll_days_come_from_the_store(store):
    assert roll_days_in_store(
        BarStore(store / "bars"), "MNQ.v.0", date(2026, 7, 12), date(2026, 7, 25)
    ) == {date(2026, 7, 22)}


def test_news_calendar_is_required_unless_opted_out(store):
    with pytest.raises(NewsCalendarMissing):
        bt(store, "x", news_csv=store / "missing.csv")
    r = bt(store, "y", news=False)
    run = decode_json(read_run(r.folder, "runs"), "runs")[0]
    assert "optimistic" in run["notes"]["warning"]


def test_rescue_trials_must_be_pre_registered(store):
    with pytest.raises(ValueError, match="no pre-registered"):
        bt(store, "z", trial="make_it_profitable")
    r = bt(store, "ce", trial="fvg_entry_ce")
    assert r.summary["trades"] > 0


def test_cli_backtest_prints_a_summary(store, capsys):
    code = main(
        [
            "backtest",
            "ny_am_silver_bullet",
            "--from",
            "2026-07-13",
            "--to",
            "2026-07-25",
            "--store",
            str(store / "bars"),
            "--runs",
            str(store / "runs"),
            "--no-news",
        ]
    )
    out = capsys.readouterr().out
    assert code == 0 and "9 trades" in out and "wrote" in out
    assert (
        main(
            [
                "backtest",
                "nope",
                "--from",
                "2026-07-13",
                "--to",
                "2026-07-14",
                "--store",
                str(store / "bars"),
                "--no-news",
            ]
        )
        == 2
    )
