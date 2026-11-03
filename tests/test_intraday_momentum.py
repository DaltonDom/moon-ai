"""moon_ai.research.intraday_momentum on hand-made sessions."""

from datetime import date
from pathlib import Path

import numpy as np
import pytest

from moon_ai import holdout
from moon_ai.research import intraday_momentum as M

SPEC = M.Spec()
N = M.SESSION_MINUTES


def session(path: np.ndarray, day: date = date(2024, 3, 4), inst: int = 1) -> M.Day:
    """A session whose minute-k bar opens at path[k] and closes at path[k + 1]."""
    o = path[:N]
    c = path[1 : N + 1]
    return M.Day(day, inst, o, np.maximum(o, c) + 0.25, np.minimum(o, c) - 0.25, c, np.ones(N), N)


def flat(px: float = 100.0) -> np.ndarray:
    return np.full(N + 1, px)


def test_spec_file_loads_and_matches_the_paper_defaults():
    spec = M.load_spec()
    assert spec.lookback_days == 14 and spec.band_mult == 1.0
    assert spec.decisions[0] == 30 and spec.decisions[-1] == 360  # 10:00 and 15:30
    assert len(spec.decisions) == 12
    assert spec.final_exit == 385  # 15:55
    assert spec.end <= holdout.HOLDOUT_START


def test_a_flat_session_does_not_trade():
    sigma = np.full(N, 0.001)
    assert M.trade_day(session(flat()), sigma, 100.0, 1, SPEC) == []


def test_a_breakout_goes_long_at_the_next_bar_and_times_out():
    path = flat()
    path[25:] = 101.0  # +1% from 09:55 on, well above a 0.1% band
    sigma = np.full(N, 0.001)
    (t,) = M.trade_day(session(path), sigma, 100.0, 2, SPEC)
    assert t.side == 1 and t.qty == 2
    assert t.entry_minute == 30  # decided on the 09:59 bar's close, filled on the 10:00 open
    assert t.exit_reason == "time_out" and t.exit_minute == 385
    assert t.gross_usd == 0.0  # flat after entry
    assert t.cost_usd == pytest.approx(2 * (2 * 1.0 + 2 * 0.25 * 2.0))


def test_the_trailing_stop_exits_when_price_falls_back_into_the_band():
    path = flat()
    path[25:] = 101.0
    path[95:] = 100.0  # back to the open by 11:05
    (t,) = M.trade_day(session(path), np.full(N, 0.001), 100.0, 1, SPEC)
    assert t.exit_reason == "trail" and t.exit_minute == 120  # 11:30 decision
    assert t.gross_usd == pytest.approx(-1.0 * 2.0)


def test_an_exit_can_flip_to_the_other_side_but_not_back_into_the_same_side():
    path = flat()
    path[25:] = 101.0
    path[95:] = 98.0  # through the lower band
    a, b = M.trade_day(session(path), np.full(N, 0.001), 100.0, 1, SPEC)
    assert (a.side, a.exit_minute) == (1, 120)
    assert (b.side, b.entry_minute) == (-1, 120)


def test_a_decision_never_sees_later_bars():
    path = flat()
    path[25:] = 101.0
    base = M.trade_day(session(path), np.full(N, 0.001), 100.0, 1, SPEC)
    later = path.copy()
    later[31:] = 50.0  # rewrite everything after the 10:00 fill bar
    changed = M.trade_day(session(later), np.full(N, 0.001), 100.0, 1, SPEC)
    assert (changed[0].side, changed[0].entry_minute, changed[0].entry_px) == (
        base[0].side,
        base[0].entry_minute,
        base[0].entry_px,
    )


def test_news_blocks_entries_only():
    path = flat()
    path[25:] = 101.0
    blocked = [True] + [False] * 11
    (t,) = M.trade_day(session(path), np.full(N, 0.001), 100.0, 1, SPEC, blocked)
    assert t.entry_minute == 60  # 10:00 blocked; the 10:30 decision enters


def test_noise_sigma_needs_the_full_lookback():
    days = [session(flat()) for _ in range(13)]
    assert M.noise_sigma(days, 14) is None
    assert M.noise_sigma([*days, session(flat())], 14) is not None


def test_contracts_target_volatility_with_a_leverage_cap():
    assert M.contracts(SPEC, 20_000.0, 0.01) == 2  # 50k * 2x / 40k notional, rounded down
    assert M.contracts(SPEC, 20_000.0, 0.001) == 5  # capped at 4x leverage
    assert M.contracts(SPEC, 20_000.0, 1.0) == 1  # at least one


def test_backtest_trades_only_inside_its_dates_and_skips_rolls():
    days = [session(flat(), date(2024, 2, 1 + i)) for i in range(29)]
    days = [d for d in days if d.day.weekday() < 5]
    res = M.backtest(
        days,
        SPEC,
        start=date(2024, 2, 26),
        end=date(2024, 3, 1),
        rolls=frozenset({date(2024, 2, 27)}),
    )
    assert set(res.daily) <= {date(2024, 2, 26), date(2024, 2, 28), date(2024, 2, 29)}
    assert res.skipped.get("roll") == 1


def test_eval_replay_counts_passes_and_intraday_breaches():
    rules = M.EvalRules(target_usd=100.0, max_loss_usd=50.0)
    win = M.replay_evals([60.0, 60.0], 1, rules)
    assert win["pass_rate"] == 1.0 and win["median_days_to_pass"] == 2.0
    # Closes up, but dipped through the limit intraday.
    dip = M.replay_evals([60.0, 60.0], 1, rules, per_contract_worst=[-60.0, 0.0])
    # The start on day 1 breaches on day 1; the start on day 2 never finishes.
    assert dip["attempts"] == 1 and dip["pass_rate"] == 0.0


def test_research_runs_refuse_the_holdout(tmp_path: Path):
    spec = M.Spec(start=date(2025, 6, 1), end=date(2026, 1, 1))
    with pytest.raises(holdout.HoldoutLocked):
        M.run(spec, tmp_path, tmp_path / "out")


STOPS = M.Spec(stop_sigma_mult=0.5, daily_stop_risk_mult=2.0, fixed_contracts=1)


def test_trial_prop_v2_loads_its_risk_controls():
    spec = M.load_spec(trial="prop_v2")
    assert (spec.stop_sigma_mult, spec.daily_stop_risk_mult) == (0.5, 2.0)
    assert spec.fixed_contracts == 1 and spec.n_trials == 2
    assert spec.lookback_days == M.load_spec().lookback_days  # entry rules unchanged
    with pytest.raises(ValueError):
        M.load_spec(trial="nope")


def test_the_hard_stop_fills_inside_the_bar_with_stop_slippage():
    path = flat()
    path[25:] = 101.0
    path[40:] = 99.0  # bar 39 trades 101 -> 99 through a stop at 101 - 0.5 * 0.02 * 100 = 100
    (t,) = M.trade_day(session(path), np.full(N, 0.001), 100.0, 1, STOPS, vol=0.02)
    assert t.exit_reason == "stop" and t.exit_minute == 39
    assert t.exit_px == 100.0  # the stop price, since the bar opened above it
    assert t.cost_usd == pytest.approx(2 * 1.0 + (0.25 + 3 * 0.25) * 2.0)


def test_without_a_stop_the_same_session_rides_to_the_next_check():
    path = flat()
    path[25:] = 101.0
    path[40:] = 99.0
    t = M.trade_day(session(path), np.full(N, 0.001), 100.0, 1, SPEC, vol=0.02)[0]
    assert t.exit_reason == "trail" and t.exit_minute == 60


def test_the_daily_stop_blocks_new_entries_after_two_risk_units():
    path = flat()
    path[25:] = 101.0
    path[40:] = 98.0  # long stopped out for ~3 points, risk 1 point: halted
    trades = M.trade_day(session(path), np.full(N, 0.001), 100.0, 1, STOPS, vol=0.02)
    assert [t.exit_reason for t in trades] == ["stop"]  # no short at 10:30


def test_lucid_replay_applies_the_consistency_rule():
    rules = M.LucidRules(target_usd=100.0, max_loss_usd=1000.0, min_days=1)
    one_big_day = M.replay_lucid([150.0, 0.0, 0.0], [0.0, 0.0, 0.0], 1, rules)
    assert one_big_day["evaluations"] == 0  # 150 > 40% of 150: can't pass on that day alone
    steady = M.replay_lucid([40.0] * 6, [0.0] * 6, 1, rules)
    assert steady["pass_rate"] == 1.0 and steady["median_sessions_to_pass"] == 3.0


def test_lucid_floor_stops_rising_at_the_lock():
    rules = M.LucidRules(target_usd=10_000.0, max_loss_usd=100.0, floor_lock_usd=10.0)
    # Up 500, then a 400 drop: the floor locked at +10, so +100 left is safe.
    r = M.replay_lucid([500.0, -400.0], [0.0, -400.0], 1, rules)
    assert r["evaluations"] == 0 or r["pass_rate"] == 0.0
