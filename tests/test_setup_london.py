from dataclasses import replace
from datetime import date, datetime, timedelta

from moon_ai.bars import Bar
from moon_ai.sessions import NY
from moon_ai.setups import REGISTRY, load_setup_defaults
from moon_ai.setups.london import LondonSweepAndReverse, prev_day_range_bias, session_ohlc
from tests.test_setup_silver_bullet import scan_all

LON = load_setup_defaults()["london_sweep_and_reverse"].params

# The Silver Bullet pattern, moved to 02:01-02:07: it sweeps the Asian low (97) at 02:04.
PATTERN = {
    (2, 1): (100.0, 100.25, 99.75, 100.0),
    (2, 2): (100.0, 100.75, 99.75, 100.25),
    (2, 3): (100.25, 100.5, 98.5, 98.75),
    (2, 4): (98.75, 99.0, 96.5, 98.0),
    (2, 5): (98.0, 100.0, 97.75, 99.75),
    (2, 6): (99.75, 102.0, 99.5, 101.75),
    (2, 7): (101.75, 102.25, 100.5, 102.0),
}
ASIA = {(21, 0): (100.0, 100.25, 97.0, 100.0), (22, 0): (100.0, 112.0, 99.75, 100.0)}


def session(d: date, special: dict, end=(17, 0)):
    bars, last = [], 100.0
    t = datetime.combine(d - timedelta(days=1), datetime.min.time().replace(hour=18), tzinfo=NY)
    stop = datetime.combine(d, datetime.min.time().replace(hour=end[0], minute=end[1]), tzinfo=NY)
    while t < stop:
        o, h, lo, c = special.get((t.hour, t.minute), (last, last + 0.25, last - 0.25, last))
        last = c
        bars.append(Bar("MNQ.v.0", t, t + timedelta(minutes=1), o, h, lo, c, 1, 1))
        t += timedelta(minutes=1)
    return bars


def three_days(day2_close=101.0, today_extra=None):
    d1 = session(date(2026, 7, 13), {})
    d2 = session(date(2026, 7, 14), {(16, 59): (100.0, 101.0, 99.0, day2_close)})
    d3 = session(date(2026, 7, 15), {**ASIA, **PATTERN, **(today_extra or {})}, end=(3, 0))
    return d1 + d2 + d3


def test_prev_day_range_bias():
    s = {date(2026, 7, 13): (100, 101, 99, 100), date(2026, 7, 14): (100, 102, 99, 101.5)}
    assert prev_day_range_bias(s, date(2026, 7, 15)) == "bull"
    s[date(2026, 7, 14)] = (100, 101, 98, 98.5)
    assert prev_day_range_bias(s, date(2026, 7, 15)) == "bear"
    s[date(2026, 7, 14)] = (100, 101, 99, 100)
    assert prev_day_range_bias(s, date(2026, 7, 15)) is None
    assert prev_day_range_bias(s, date(2026, 7, 14)) is None  # only one session before
    assert session_ohlc(session(date(2026, 7, 13), {}))[date(2026, 7, 13)][0] == 100.0


def test_a_judas_swing_with_the_bias():
    (c,) = scan_all(three_days(), LON, cls=LondonSweepAndReverse)
    assert c.setup == "london_sweep_and_reverse" and c.side == "long"
    assert c.decision_time == datetime(2026, 7, 15, 2, 7, tzinfo=NY)
    assert (c.entry, c.stop, c.target) == (99.5, 96.25, 112.0)  # target: the Asian high
    assert c.rule_results["swept_pool"] == "asia"
    assert c.timeout == datetime(2026, 7, 15, 9, 30, tzinfo=NY)
    assert REGISTRY["london_sweep_and_reverse"] is LondonSweepAndReverse


def test_a_sweep_with_the_bias_is_not_a_judas_swing():
    bearish = three_days(day2_close=99.0)  # closed below the day before's low
    assert scan_all(bearish, LON, cls=LondonSweepAndReverse) == []
    either = replace(LON, bias_gate=False)
    assert len(scan_all(bearish, either, cls=LondonSweepAndReverse)) == 1


def test_po3_needs_the_sweep_beyond_the_midnight_open():
    # With Asian-range pools the filter rarely bites: a midnight open below the Asian low
    # would itself sweep it. So test the rule directly.
    from types import SimpleNamespace as NS

    from tests.test_setup_silver_bullet import CFG

    setup = LondonSweepAndReverse(replace(LON, bias_gate=False), CFG)
    setup._bias, setup._midnight = None, 100.0
    long_mss = NS(direction="bull", sweep=NS(extreme=99.0))
    short_mss = NS(direction="bear", sweep=NS(extreme=101.0))
    assert setup._accept(long_mss, []) and setup._accept(short_mss, [])
    setup._midnight = 98.0  # the long's sweep stayed above the midnight open
    assert not setup._accept(long_mss, [])
    off = LondonSweepAndReverse(replace(LON, bias_gate=False, po3_filter=False), CFG)
    off._bias, off._midnight = None, 98.0
    assert off._accept(long_mss, [])


def test_prior_day_pools_trial_runs():
    with_prior = replace(LON, pools=("asia", "prior_day"))
    assert len(scan_all(three_days(), with_prior, cls=LondonSweepAndReverse)) == 1
