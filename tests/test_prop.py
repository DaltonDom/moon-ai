from moon_ai.research.prop import Account, DayTrade, contracts, rolling, run

ACCT = Account("test", 10_000, 1_000, 500, 10, 100)


def t(day, pnl, mae=0.0, risk=10.0):
    return DayTrade(day, pnl, mae, risk)


def test_sizing_rounds_down_and_caps():
    assert contracts(ACCT, 10.0, 2.0) == 8  # 100 // 12
    assert contracts(ACCT, 1.0, 0.0) == 10  # capped
    assert contracts(ACCT, 200.0, 2.0) == 0


def test_passes_when_target_reached():
    o = run(ACCT, [t(0, 50.0), t(1, 80.0)], 0, 5, commission_rt=0.0)  # 10 contracts each
    assert (o.status, o.days, o.balance) == ("pass", 2, 11_300)


def test_intraday_mae_breach_fails_even_if_trade_closes_green():
    o = run(ACCT, [t(0, 5.0, mae=60.0)], 0, 3, commission_rt=0.0)
    assert o.status == "fail"


def test_floor_trails_end_of_day_high_and_locks_at_start():
    # +400 lifts the floor to 9_900; a -550 day then breaches it.
    o = run(ACCT, [t(0, 40.0), t(1, -55.0)], 0, 3, commission_rt=0.0)
    assert o.status == "fail"
    # after +900 the floor would be 10_400 but locks at the 10_000 start
    o = run(ACCT, [t(0, 90.0), t(1, -85.0)], 0, 3, commission_rt=0.0)
    assert o.status == "open" and o.balance == 10_050


def test_consistency_holds_pass_until_best_day_is_small_enough():
    acct = Account("c", 10_000, 1_000, 5_000, 10, 100, consistency=0.5)
    o = run(acct, [t(0, 100.0), t(1, 20.0)], 0, 5, commission_rt=0.0)  # best 1000 of 1200
    assert o.status == "open"
    o = run(acct, [t(0, 60.0), t(1, 50.0)], 0, 5, commission_rt=0.0)  # best 600 of 1100
    assert o.status == "open"
    o = run(acct, [t(0, 60.0), t(1, 50.0), t(2, 30.0)], 0, 5, commission_rt=0.0)
    assert o.status == "pass"


def test_daily_loss_limit_caps_the_day():
    acct = Account("d", 10_000, 1_000, 2_000, 10, 100, daily_loss=300)
    o = run(acct, [t(0, -80.0, mae=80.0)], 0, 2, commission_rt=0.0)
    assert o.status == "open" and o.balance == 9_700


def test_rolling_counts_every_start():
    s = rolling(ACCT, [t(0, 100.0)], 3, commission_rt=0.0)
    assert (s.starts, s.passed, s.open) == (3, 1, 2)
    assert s.pass_rate == 1 / 3
