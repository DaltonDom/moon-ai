from datetime import date

from moon_ai.backtest.evaluate import evaluate
from moon_ai.backtest.report import holdout_start, render, warnings_for
from moon_ai.backtest.runner import run_backtest
from moon_ai.journal import decode_json, read_run
from tests.test_backtest_runner import DAYS, LOSS, SETUP, WIN, session_rows
from tests.test_store import write


def make_run(tmp_path, **kw):
    rows = []
    for i, d in enumerate(DAYS):
        rows += session_rows(d, {**SETUP, **(WIN if i % 2 == 0 else LOSS)})
    write(tmp_path / "bars", "MNQ.v.0", "2026-07-12_2026-07-25", rows)
    return run_backtest(
        "ny_am_silver_bullet",
        date(2026, 7, 13),
        date(2026, 7, 25),
        store_root=tmp_path / "bars",
        runs_root=tmp_path / "runs",
        **kw,
    )


def test_report_card_says_it_plainly(tmp_path):
    r = make_run(tmp_path, news=False)
    ev = evaluate(r.folder, store_root=tmp_path / "bars", n_random=50)
    page = render(ev, r.folder, today=date(2026, 11, 1)).read_text()
    assert "NY AM Silver Bullet: <span" in page and "Not enough trades yet" in page
    for check in (
        "Beats random entries",
        "Not just luck",
        "Enough trades",
        "Still profitable with double costs",
    ):
        assert check in page
    assert "10 of 100" in page and "not run yet" in page
    assert "Run without the news blackout" in page
    assert page.count("<tr><td>2026-07-") == 10  # one row per trade
    assert "<svg" in page and "Advanced numbers" in page


def test_warnings(tmp_path):
    r = make_run(tmp_path, news=False)
    run = decode_json(read_run(r.folder, "runs"), "runs")[0]
    assert holdout_start(date(2026, 11, 1)) == date(2026, 5, 2)
    # July 2026 is inside the last 6 months on 2026-11-01, but not by mid-2027.
    assert any("holdout" in w for w in warnings_for(run, date(2026, 11, 1)))
    assert not any("holdout" in w for w in warnings_for(run, date(2027, 6, 1)))
