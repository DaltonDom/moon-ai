from moon_ai.ict.liquidity import Level, Sweep
from moon_ai.ict.structure import find_market_structure_shifts
from moon_ai.ict.swings import Swing
from tests.helpers import bar

# Bars 0-2 build a swing low at 98 (confirmed at bar 2's close); bar 3 sweeps
# a high at 103 and closes back below it.
BASE = [
    bar(0, 99.5, 100, 99, 99.25),
    bar(1, 99.25, 99.5, 98, 98.75),
    bar(2, 98.75, 101, 98.5, 100.75),
    bar(3, 100.75, 103.5, 100.5, 102.5),
]
SWING_LOW = Swing("low", 98, BASE[1].ts_open, 1, BASE[2].ts_close, 1)
HIGH_SWEEP = Sweep(Level("high", 103, BASE[0].ts_close, "test", 1), 3, 103.5, BASE[3].ts_close)


def test_close_below_the_last_swing_low_after_a_high_sweep_is_a_bearish_mss():
    bars = [
        *BASE,
        bar(4, 102.5, 102.75, 98.25, 98.5),  # wick and close above 98
        bar(5, 98.5, 98.75, 97.25, 97.5),  # closes below 98
    ]

    shifts = find_market_structure_shifts(bars, [SWING_LOW], [HIGH_SWEEP])

    assert [(s.direction, s.index, s.broken_swing, s.known_at) for s in shifts] == [
        ("bear", 5, SWING_LOW, bars[5].ts_close)
    ]


def test_wick_mode_breaks_on_the_low():
    bars = [*BASE, bar(4, 102.5, 102.75, 97.75, 98.5)]

    close_mode = find_market_structure_shifts(bars, [SWING_LOW], [HIGH_SWEEP], mode="close")
    wick_mode = find_market_structure_shifts(bars, [SWING_LOW], [HIGH_SWEEP], mode="wick")

    assert close_mode == []
    assert [s.index for s in wick_mode] == [4]


def test_mss_must_come_within_max_bars_of_the_sweep():
    bars = [*BASE, *[bar(4 + i, 100, 100.5, 99.5, 100) for i in range(3)]]
    bars.append(bar(7, 100, 100, 97, 97.25))

    assert find_market_structure_shifts(bars, [SWING_LOW], [HIGH_SWEEP], max_bars=3) == []
    assert len(find_market_structure_shifts(bars, [SWING_LOW], [HIGH_SWEEP], max_bars=4)) == 1


def test_only_swings_confirmed_by_the_sweep_count():
    bars = [*BASE, bar(4, 102.5, 102.75, 99, 99.25), bar(5, 99.25, 99.5, 98.75, 99)]
    late_low = Swing("low", 99.5, bars[3].ts_open, 3, bars[4].ts_close, 1)

    # The swing low at 99.5 is confirmed after the sweep, so the reference
    # stays the 98 low, which bars 4-5 do not close below.
    assert find_market_structure_shifts(bars, [SWING_LOW, late_low], [HIGH_SWEEP]) == []


def test_sweep_of_a_low_needs_a_close_above_the_last_swing_high():
    swing_high = Swing("high", 101, BASE[2].ts_open, 2, BASE[3].ts_close, 1)
    bars = [*BASE, bar(4, 100, 100.25, 97.5, 98.5), bar(5, 98.5, 101.5, 98.25, 101.25)]
    low_sweep = Sweep(Level("low", 98, bars[0].ts_close, "test", 1), 4, 97.5, bars[4].ts_close)

    shifts = find_market_structure_shifts(bars, [swing_high], [low_sweep])

    assert [(s.direction, s.index) for s in shifts] == [("bull", 5)]


def test_no_reference_swing_means_no_mss():
    bars = [*BASE, bar(4, 102.5, 102.75, 90, 91)]

    assert find_market_structure_shifts(bars, [], [HIGH_SWEEP]) == []
