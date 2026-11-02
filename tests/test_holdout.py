from datetime import date

import pytest

from moon_ai.cli import main
from moon_ai.holdout import (
    HOLDOUT_END,
    HOLDOUT_START,
    HoldoutLocked,
    checks,
    guard,
    sign_off,
    touches,
)


def test_window_is_fixed_twelve_months():
    assert (date(2025, 11, 1), date(2026, 11, 1)) == (HOLDOUT_START, HOLDOUT_END)


def test_research_stops_at_the_holdout():
    guard(date(2019, 6, 1), HOLDOUT_START)  # end is exclusive: Oct 31 is the last day
    assert not touches(date(2019, 6, 1), HOLDOUT_START)
    assert touches(date(2019, 6, 1), date(2025, 11, 2))
    assert touches(date(2026, 10, 31), date(2027, 1, 1))
    assert not touches(HOLDOUT_END, date(2027, 1, 1))
    with pytest.raises(HoldoutLocked, match="locked holdout"):
        guard(date(2019, 6, 1), date(2026, 4, 30))


def test_one_look_per_setup_and_trial(tmp_path):
    ledger = tmp_path / "holdout_checks.jsonl"
    sign_off("ote_pullback", "default", HOLDOUT_START, HOLDOUT_END, ledger)
    with pytest.raises(HoldoutLocked, match="already had its one look"):
        sign_off("ote_pullback", "default", HOLDOUT_START, HOLDOUT_END, ledger)
    sign_off("ote_pullback", "min_rr_2", HOLDOUT_START, HOLDOUT_END, ledger)
    assert [(c.setup, c.trial) for c in checks(ledger)] == [
        ("ote_pullback", "default"),
        ("ote_pullback", "min_rr_2"),
    ]


def test_sign_off_covers_only_the_holdout(tmp_path):
    with pytest.raises(HoldoutLocked, match="exactly the holdout"):
        sign_off("x", "default", date(2019, 6, 1), HOLDOUT_END, tmp_path / "l.jsonl")
    assert not (tmp_path / "l.jsonl").exists()


@pytest.mark.parametrize(
    "argv",
    [
        ["backtest", "--all", "--from", "2019-06-01", "--to", "2026-04-30"],
        ["backtest", "--round2", "--from", "2019-06-01", "--to", "2026-04-30"],
        ["backtest", "ote_pullback", "--from", "2026-01-01", "--to", "2026-02-01"],
        ["funnel", "ote_pullback", "--from", "2025-10-01", "--to", "2025-12-01"],
        ["review-days", "ote_pullback", "--to", "2026-05-01", "--no-open"],
        [
            "backtest",
            "--all",
            "--holdout-signoff",
            "--from",
            "2025-11-01",
            "--to",
            "2026-11-01",
        ],
    ],
)
def test_cli_refuses_research_on_the_holdout(argv, tmp_path, capsys):
    runs = ["--runs", str(tmp_path / "runs")] if argv[0] == "backtest" else []
    assert main([*argv, *runs]) == 2
    assert "refused" in capsys.readouterr().err


def test_one_look_per_market(tmp_path):
    ledger = tmp_path / "holdout_checks.jsonl"
    sign_off("noise_breakout", "default", HOLDOUT_START, HOLDOUT_END, ledger)
    sign_off("noise_breakout", "default", HOLDOUT_START, HOLDOUT_END, ledger, symbol="MES.v.0")
    with pytest.raises(HoldoutLocked, match=r"on MES\.v\.0 already"):
        sign_off("noise_breakout", "default", HOLDOUT_START, HOLDOUT_END, ledger, symbol="MES.v.0")
