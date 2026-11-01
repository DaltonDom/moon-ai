import math
from datetime import UTC, date, datetime, time, timedelta

import numpy as np
import pytest

from moon_ai.backtest.baseline import TradeShape, prepare_days, random_entry_means, simulate
from moon_ai.backtest.evaluate import decide, evaluate
from moon_ai.backtest.stats import (
    bootstrap_mean_ci,
    deflated_sharpe,
    expected_max_sharpe,
    metrics,
    pbo,
    probabilistic_sharpe,
    sharpe,
    sortino,
)
from moon_ai.bars import Bar
from moon_ai.config import Window, load_config
from moon_ai.sessions import NY

CFG = load_config()


def test_trade_metrics_by_hand():
    m = metrics([2.0, -1.0, -1.0, 3.0], [400, -200, -200, 600], [2.0, -2.0, 3.0])
    assert m.trades == 4 and m.win_rate == 0.5
    assert m.profit_factor == 1000 / 400
    assert m.expectancy_r == 0.75 and m.avg_win_r == 2.5 and m.avg_loss_r == -1.0
    assert m.max_drawdown_r == -2.0  # +2 then -1, -1
    assert m.net_r == 3.0 and m.net_usd == 600
    assert m.sharpe == pytest.approx(
        np.mean([2, -2, 3]) / np.std([2, -2, 3], ddof=1) * math.sqrt(252)
    )


def test_sharpe_and_sortino_closed_forms():
    x = [1.0, -1.0, 1.0, -1.0, 2.0]
    assert sharpe(x) == pytest.approx(0.4 / np.std(x, ddof=1))
    assert sortino(x) == pytest.approx(0.4 / math.sqrt(2 / 5))
    assert sharpe([1.0, 1.0]) == 0.0 and sortino([1.0, 2.0]) == 0.0


def test_bootstrap_ci():
    assert bootstrap_mean_ci([1.5] * 20) == (1.5, 1.5)
    x = np.random.default_rng(1).normal(0.3, 1.0, 400)
    lo, hi = bootstrap_mean_ci(x)
    se = x.std(ddof=1) / math.sqrt(len(x))
    assert lo < x.mean() < hi
    assert hi - lo == pytest.approx(2 * 1.96 * se, rel=0.1)


def test_probabilistic_sharpe_matches_the_normal_case():
    sr, t = 0.1, 250
    expect = 0.5 * (1 + math.erf(sr * math.sqrt(t - 1) / math.sqrt(1 + sr**2 / 2) / math.sqrt(2)))
    assert probabilistic_sharpe(sr, 0.0, t, 0.0, 3.0) == pytest.approx(expect)


def test_expected_max_sharpe_matches_monte_carlo():
    assert expected_max_sharpe(1, 1.0) == 0.0
    mc = np.random.default_rng(0).standard_normal((20_000, 100)).max(axis=1).mean()
    assert expected_max_sharpe(100, 1.0) == pytest.approx(mc, abs=0.05)
    assert expected_max_sharpe(100, 0.25) == pytest.approx(0.5 * expected_max_sharpe(100, 1.0))


def test_dsr_is_psr_against_zero_for_one_trial_and_falls_with_more_trials():
    x = np.random.default_rng(3).normal(0.1, 1.0, 500)
    one = deflated_sharpe(x, 1, 0.0)
    assert 0.5 < one < 1
    assert deflated_sharpe(x, 50, 0.01) < one


def test_pbo_separates_signal_from_noise():
    rng = np.random.default_rng(7)
    noise = rng.normal(0, 1, (800, 20))
    assert 0.3 < pbo(noise) < 0.7
    signal = noise.copy()
    signal[:, 0] += 0.5
    assert pbo(signal) < 0.1
    with pytest.raises(ValueError):
        pbo(noise[:, :1])


def test_verdict_rules():
    assert decide(150, 0.05, 0.97) == ("go-forward", [])
    v, why = decide(150, -0.01, 0.97)
    assert v == "fail" and "random" in why[0]
    v, why = decide(150, 0.05, 0.9)
    assert v == "fail" and "luck" in why[0]
    v, why = decide(40, 0.05, 0.99)
    assert v == "insufficient" and "40 trades" in why[0]


# --- random-entry baseline ------------------------------------------------------

WINDOW = Window(time(10), time(11))


def flat_day(d: date, price=100.0, drift=0.0):
    bars, t = [], datetime.combine(d, time(9, 30), tzinfo=NY).astimezone(UTC)
    for i in range(400):
        p = price + drift * i
        bars.append(Bar("MNQ.v.0", t, t + timedelta(minutes=1), p, p + 0.25, p - 0.25, p, 1, 1))
        t += timedelta(minutes=1)
    return bars


def test_a_flat_market_loses_exactly_the_costs():
    d = date(2026, 7, 15)
    days = prepare_days(flat_day(d), {d}, WINDOW, time(15, 55), CFG)
    shape = TradeShape(1, 10.0, 20.0)
    i = int(days[0].entry_idx[0])
    # Entry 100 + 1 tick, time-out exit 100 - 1 tick, $2 round trip = 1 MNQ point.
    assert simulate(days[0], i, shape, "MNQ.v.0", CFG) == pytest.approx(-(0.5 + 1.0) / 10.0)
    means = random_entry_means(days, [shape], "MNQ.v.0", CFG, n_runs=5)
    assert np.allclose(means, -0.15)


def test_trending_days_reward_trades_with_the_trend():
    d = date(2026, 7, 15)
    days = prepare_days(flat_day(d, drift=0.25), {d}, WINDOW, time(15, 55), CFG)
    up = random_entry_means(days, [TradeShape(1, 5.0, 10.0)], "MNQ.v.0", CFG, n_runs=20)
    down = random_entry_means(days, [TradeShape(-1, 5.0, 10.0)], "MNQ.v.0", CFG, n_runs=20)
    assert up.mean() > 1.5 and down.mean() < -1.0


def test_evaluate_a_small_run_is_insufficient(tmp_path):
    from tests.test_backtest_runner import DAYS, LOSS, SETUP, WIN, session_rows
    from tests.test_store import write

    rows = []
    for i, d in enumerate(DAYS):
        rows += session_rows(d, {**SETUP, **(WIN if i % 2 == 0 else LOSS)})
    write(tmp_path / "bars", "MNQ.v.0", "2026-07-12_2026-07-25", rows)
    from moon_ai.backtest.runner import run_backtest

    r = run_backtest(
        "ny_am_silver_bullet",
        date(2026, 7, 13),
        date(2026, 7, 25),
        store_root=tmp_path / "bars",
        runs_root=tmp_path / "runs",
        news=False,
    )
    ev = evaluate(r.folder, store_root=tmp_path / "bars", n_random=50)
    assert ev.metrics.trades == 10 and ev.verdict == "insufficient"
    assert ev.n_trials == 1 and ev.pbo is None
    assert ev.edge_ci[0] <= ev.edge_ci[1]
