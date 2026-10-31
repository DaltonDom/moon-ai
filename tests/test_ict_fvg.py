from moon_ai.ict.fvg import find_fvgs
from tests.helpers import bar


def test_bullish_fvg_zone_and_known_at_the_third_candle_close():
    bars = [
        bar(0, 100, 101, 99.5, 100.75),
        bar(1, 100.75, 104, 100.5, 103.75),  # displacement candle
        bar(2, 103.75, 104.5, 102, 104),  # low 102 > first high 101
    ]

    fvgs = find_fvgs(bars, tick=0.25)

    assert [(g.direction, g.low, g.high, g.ts, g.known_at) for g in fvgs] == [
        ("bull", 101, 102, bars[1].ts_open, bars[2].ts_close)
    ]
    assert fvgs[0].ce == 101.5


def test_bearish_fvg_mirrors():
    bars = [
        bar(0, 104, 104.5, 103, 103.25),
        bar(1, 103.25, 103.5, 99, 99.25),
        bar(2, 99.25, 101.5, 99, 100),  # high 101.5 < first low 103
    ]

    fvgs = find_fvgs(bars, tick=0.25)

    assert [(g.direction, g.low, g.high) for g in fvgs] == [("bear", 101.5, 103)]


def test_touching_wicks_leave_no_gap():
    bars = [
        bar(0, 100, 101, 99.5, 100.75),
        bar(1, 100.75, 104, 100.5, 103.75),
        bar(2, 103.75, 104.5, 101, 104),
    ]

    assert find_fvgs(bars, tick=0.25) == []


def test_gaps_smaller_than_the_minimum_size_are_ignored():
    bars = [
        bar(0, 100, 101, 99.5, 100.75),
        bar(1, 100.75, 104, 100.5, 103.75),
        bar(2, 103.75, 104.5, 101.5, 104),  # 2-tick gap
    ]

    assert find_fvgs(bars, tick=0.25, min_size_ticks=3) == []
    assert len(find_fvgs(bars, tick=0.25, min_size_ticks=2)) == 1


def test_fvg_needs_all_three_candles_on_one_contract():
    bars = [
        bar(0, 100, 101, 99.5, 100.75),
        bar(1, 100.75, 104, 100.5, 103.75),
        bar(2, 103.75, 104.5, 102, 104, instrument_id=2),
    ]

    assert find_fvgs(bars, tick=0.25) == []
