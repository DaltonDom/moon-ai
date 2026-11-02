from datetime import date, timedelta

import pytest

from moon_ai.propfirm import (
    RULES_PATH,
    Account,
    Payouts,
    Phase,
    Rules,
    Trade,
    load_rules,
    replay,
    score,
    summarise,
    trades_from_run,
)

D0 = date(2024, 1, 2)


def day(i):
    return D0 + timedelta(days=i)


def t(i, pnl, risk=50.0, worst=None, best=None):
    """One trade on day i, per contract: risk $50 (25 MNQ points)."""
    return Trade(
        day(i),
        pnl,
        risk,
        worst if worst is not None else min(pnl, 0.0),
        best if best is not None else max(pnl, 0.0),
    )


def rules(**ev):
    evaluation = dict(max_loss=2000.0, drawdown="eod_trailing", profit_target=3000.0)
    evaluation.update(ev)
    return Rules(
        name="test",
        title="Test 50K",
        evaluation=Phase(**evaluation),
        funded=Phase(max_loss=2000.0, drawdown="eod_trailing", lock_floor_at=100.0),
        payouts=Payouts(min_days=2, buffer=100.0, split=0.9),
        eval_fee=100.0,
    )


def test_sizing_rounds_down_and_caps():
    acc = Account(Phase(max_loss=2000, drawdown="static", max_contracts=4))
    assert acc.contracts(t(0, 0, risk=50), 200) == 4  # $200 buys 4 at $50
    assert acc.contracts(t(0, 0, risk=60), 200) == 3
    assert acc.contracts(t(0, 0, risk=30), 200) == 4  # 6, capped at 4
    assert acc.contracts(t(0, 0, risk=250), 200) == 0  # too wide: skipped


def test_eod_trailing_floor_follows_closing_balance_and_locks():
    acc = Account(Phase(max_loss=2000, drawdown="eod_trailing", lock_floor_at=100))
    acc.take(t(0, 500, worst=-100, best=900), 1)
    assert acc.floor == -2000  # intraday highs don't move an EOD floor
    acc.end_day()
    assert acc.floor == -1500
    acc.take(t(1, 5000), 1)
    acc.end_day()
    assert acc.floor == 100  # locked at start + 100


def test_intraday_trailing_counts_open_profit_first():
    acc = Account(Phase(max_loss=2000, drawdown="intraday_trailing"))
    # Up $1,500 open, then back to -$600: the floor rose to -$500 first.
    assert acc.take(t(0, -600, worst=-600, best=1500), 1) == "max loss"
    assert acc.balance == -500


def test_open_loss_breaches_even_if_trade_closes_green():
    acc = Account(Phase(max_loss=1000, drawdown="static"))
    assert acc.take(t(0, 200, worst=-1100, best=200), 1) == "max loss"


def test_daily_loss_soft_stops_the_day_hard_fails():
    soft = Account(Phase(max_loss=5000, drawdown="static", daily_loss=500))
    assert soft.take(t(0, -400), 2) is None  # -800 open, closed at -500
    assert soft.balance == -500 and soft.done_for_day(day(0))
    hard = Account(Phase(max_loss=5000, drawdown="static", daily_loss=500, daily_loss_hard=True))
    assert hard.take(t(0, -400), 2) == "daily loss limit"


def test_evaluation_passes_on_target_and_counts_days():
    trades = [t(0, 100), t(1, 100), t(2, 100)]  # +$400/day at 4 contracts
    r = rules(profit_target=1000.0, min_days=3)
    a = replay(trades, r, risk_usd=200)[0]
    assert a.outcome == "passed" and a.end == day(2) and a.trading_days == 3


def test_min_days_and_consistency_delay_a_pass():
    trades = [t(0, 300), t(1, 25), t(2, 25)]  # +1200, +100, +100 at 4 contracts
    r = rules(profit_target=1000.0, consistency_pct=50.0)
    a = replay(trades, r, risk_usd=200)[0]
    # Target hit on day 0, but the best day is 100% of profit: never consistent here.
    assert a.outcome == "ran out"
    r2 = rules(profit_target=1000.0, min_days=2)
    assert replay(trades, r2, risk_usd=200)[0].end == day(1)


def test_failed_evaluation_reports_why():
    trades = [t(0, -300), t(1, -300)]  # -1200 per day at 4 contracts
    a = replay(trades, rules(), risk_usd=200)[0]
    assert a.outcome == "failed" and a.reason == "max loss" and a.end == day(1)


def test_pass_continues_into_funded_payouts():
    # Pass on day 0 (+$3,200), then funded: +$400 a day.
    trades = [t(0, 800)] + [t(i, 100) for i in range(1, 7)]
    a = replay(trades, rules(), risk_usd=200)[0]
    assert a.outcome == "passed"
    # Payout after every 2 funded days: $800 profit - $100 buffer, then $800 each.
    assert [round(x) for _, x in a.payouts] == [630, 720, 720]
    assert a.funded_outcome == "still running" and a.funded_days == 6


def test_summary_numbers():
    trades = [t(0, 800)] + [t(i, 100) for i in range(1, 7)]
    r = rules()
    s = summarise(replay(trades, r, 200), r, 200)
    assert s.attempts == 1 and s.pass_rate == 1.0
    assert s.median_days_to_pass == 1
    assert s.cost_per_funded == 100.0
    assert s.payout_per_month == pytest.approx(2070 / (6 / 30.44))
    assert [x.risk_usd for x in score(trades, r, (100, 200))] == [100, 200]


def test_committed_rules_load():
    firms = load_rules(RULES_PATH)
    assert firms, "config/prop_firms.toml has no firms"
    for f in firms.values():
        assert f.evaluation.profit_target and f.source


def test_trades_from_a_real_run(tmp_path):
    from tests.test_report_card import make_run

    r = make_run(tmp_path, news=False)
    trades = trades_from_run(r.folder)
    assert len(trades) == r.summary["trades"]
    assert all(x.risk > 0 and x.worst <= 0 <= x.best for x in trades)
    assert all(x.worst <= x.pnl <= x.best for x in trades)
    assert sum(x.pnl for x in trades) != 0


def test_scaling_plan_raises_size_from_the_next_day():
    acc = Account(Phase(max_loss=2000, drawdown="eod_trailing", scaling=[[0, 2], [300, 4]]))
    assert acc.contracts(t(0, 0), 500) == 2
    acc.take(t(0, 200), 2)  # +400
    assert acc.contracts(t(0, 0), 500) == 2  # not intraday
    acc.end_day()
    assert acc.contracts(t(1, 0), 500) == 4


def funded_rules(**po):
    base = rules()
    payouts = dict(min_days=1, split=1.0)
    payouts.update(po)
    return Rules(
        name="f",
        title="F",
        evaluation=Phase(max_loss=2000, drawdown="static", profit_target=400),
        funded=Phase(max_loss=2000, drawdown="static"),
        payouts=Payouts(**payouts),
        eval_fee=base.eval_fee,
    )


def paid(trades, r):
    return [round(x) for _, x in replay(trades, r, 200)[0].payouts]


def test_payout_caps_by_number_and_by_share_of_profit():
    trades = [t(0, 100)] + [t(i, 250) for i in range(1, 5)]  # eval day, then +$1,000/day
    assert paid(trades, funded_rules(max_request=[300.0, 500.0])) == [300, 500, 500, 500]
    # 50% of profit: 500, then (500+1000)*0.5=750, then (750+1000)*.5=875, ...
    assert paid(trades, funded_rules(max_pct_of_profit=50.0)) == [500, 750, 875, 938]


def test_payout_needs_min_balance_and_cycle_profit():
    trades = [t(0, 100)] + [t(i, 250) for i in range(1, 5)]
    assert paid(trades, funded_rules(min_balance=2500.0, buffer=2100.0)) == [900, 1000]
    losing = [t(0, 100), t(1, 250), t(2, -100), t(3, -100)]  # +1000, -400, -400
    assert paid(losing, funded_rules(min_days=3, min_cycle_profit=0.0)) == [200]


def test_cli_prints_a_table(tmp_path, capsys):
    from moon_ai.cli import main
    from tests.test_report_card import make_run

    r = make_run(tmp_path, news=False)
    assert main(["propfirm", str(r.folder), "--firm", "lucidflex_50k", "--risk", "100"]) == 0
    out = capsys.readouterr().out
    assert "LucidFlex 50K" in out and "payout/month" in out
    assert main(["propfirm", str(r.folder), "--firm", "nope"]) == 2
