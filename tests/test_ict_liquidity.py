from datetime import UTC, datetime, time

from moon_ai.config import Window
from moon_ai.ict.liquidity import Level, find_sweeps, prior_day_levels, window_levels
from tests.helpers import bar

TICK = 0.25


def high_level(price: float, known_bar, instrument_id: int = 1) -> Level:
    return Level("high", price, known_bar.ts_close, "test", instrument_id)


def low_level(price: float, known_bar) -> Level:
    return Level("low", price, known_bar.ts_close, "test", 1)


def test_trade_through_and_close_back_in_the_same_bar_is_a_sweep():
    bars = [bar(0, 99, 100, 98, 99), bar(1, 99, 100.5, 98.5, 99.5)]
    level = high_level(100.0, bars[0])

    sweeps = find_sweeps(bars, [level], tick=TICK)

    assert [(s.level, s.index, s.extreme, s.known_at) for s in sweeps] == [
        (level, 1, 100.5, bars[1].ts_close)
    ]


def test_close_back_within_m_bars_confirms_at_the_close_back_bar():
    bars = [
        bar(0, 99, 100, 98, 99),
        bar(1, 99.5, 100.5, 99.5, 100.25),  # through, closes above
        bar(2, 100.25, 101, 100, 100.5),  # still above
        bar(3, 100.5, 100.75, 99, 99.25),  # closes back below
    ]

    sweeps = find_sweeps(bars, [high_level(100.0, bars[0])], tick=TICK, close_back_bars=3)

    assert [(s.index, s.extreme, s.known_at) for s in sweeps] == [(1, 101, bars[3].ts_close)]


def test_no_close_back_within_m_bars_is_a_breakout_and_consumes_the_level():
    bars = [
        bar(0, 99, 100, 98, 99),
        bar(1, 99.5, 100.5, 99.5, 100.25),  # through, no close back (m=1)
        bar(2, 100.25, 101, 99, 99.5),  # later close back doesn't count
    ]

    assert find_sweeps(bars, [high_level(100.0, bars[0])], tick=TICK, close_back_bars=1) == []


def test_a_touch_is_not_a_trade_through():
    bars = [
        bar(0, 99, 100, 98, 99),
        bar(1, 99, 100, 98.5, 99.5),  # touches 100 exactly
        bar(2, 99.5, 100.25, 99, 99.25),  # trades through by one tick
    ]

    sweeps = find_sweeps(bars, [high_level(100.0, bars[0])], tick=TICK)

    assert [s.index for s in sweeps] == [2]


def test_minimum_penetration_is_configurable():
    bars = [bar(0, 99, 100, 98, 99), bar(1, 99, 100.25, 98.5, 99.5)]
    level = high_level(100.0, bars[0])

    assert find_sweeps(bars, [level], tick=TICK, min_penetration_ticks=2) == []


def test_a_bar_that_opened_before_the_level_was_known_cannot_sweep_it():
    bars = [bar(0, 99, 100, 98, 99), bar(1, 99, 100.5, 98.5, 99.5)]
    level = high_level(100.0, bars[1])  # only known at bar 1's close

    assert find_sweeps(bars, [level], tick=TICK) == []


def test_without_the_close_back_rule_the_trade_through_is_the_sweep():
    bars = [bar(0, 99, 100, 98, 99), bar(1, 99.5, 100.5, 99.5, 100.25)]

    sweeps = find_sweeps(bars, [high_level(100.0, bars[0])], tick=TICK, require_close_back=False)

    assert [(s.index, s.known_at) for s in sweeps] == [(1, bars[1].ts_close)]


def test_sweep_of_a_low_mirrors():
    bars = [bar(0, 101, 102, 100, 101), bar(1, 101, 101.5, 99.5, 100.5)]

    sweeps = find_sweeps(bars, [low_level(100.0, bars[0])], tick=TICK)

    assert [(s.index, s.extreme) for s in sweeps] == [(1, 99.5)]


def test_a_level_does_not_survive_a_contract_roll():
    bars = [bar(0, 99, 100, 98, 99), bar(1, 139, 140.5, 98.5, 99.5, instrument_id=2)]

    assert find_sweeps(bars, [high_level(100.0, bars[0])], tick=TICK) == []


# --- level sources -----------------------------------------------------------

# 2026-07-15 is EDT: 20:00 New York = 00:00 UTC on 07-16.
ASIA_START = datetime(2026, 7, 16, 0, 0, tzinfo=UTC)
ASIAN = Window(time(20), time(0))


def test_session_window_high_and_low_are_known_when_the_window_ends():
    bars = [
        bar(-1, 100, 109, 91, 100, start=ASIA_START),  # 19:59, outside
        bar(0, 100, 101, 99, 100, start=ASIA_START),  # 20:00
        bar(120, 100, 103, 99.5, 102, start=ASIA_START),  # 22:00
        bar(239, 102, 102.5, 98, 99, start=ASIA_START),  # 23:59
        bar(240, 99, 110, 90, 100, start=ASIA_START),  # 00:00, outside
    ]

    levels = window_levels(bars, ASIAN, "asia")

    end = datetime(2026, 7, 16, 4, 0, tzinfo=UTC)
    assert sorted((lv.kind, lv.price, lv.known_at, lv.source) for lv in levels) == [
        ("high", 103, end, "asia"),
        ("low", 98, end, "asia"),
    ]


def test_an_unfinished_window_yields_no_levels():
    bars = [
        bar(0, 100, 101, 99, 100, start=ASIA_START),
        bar(120, 100, 103, 99.5, 102, start=ASIA_START),
    ]

    assert window_levels(bars, ASIAN, "asia") == []


def test_prior_day_high_low_are_known_at_the_1700_close():
    # Trading day 2026-07-16 runs 18:00 EDT 07-15 (22:00 UTC) to 17:00 EDT 07-16.
    day_start = datetime(2026, 7, 15, 22, 0, tzinfo=UTC)
    bars = [
        bar(0, 100, 101, 99, 100, start=day_start),
        bar(600, 100, 105, 97, 104, start=day_start),
        bar(1379, 104, 104.5, 103, 104, start=day_start),  # 16:59
        bar(1440, 104, 120, 80, 104, start=day_start),  # 18:00, next trading day
    ]

    levels = prior_day_levels(bars)

    close = datetime(2026, 7, 16, 21, 0, tzinfo=UTC)
    assert sorted((lv.kind, lv.price, lv.known_at) for lv in levels) == [
        ("high", 105, close),
        ("low", 97, close),
    ]
