from moon_ai.ict.swings import find_swings
from tests.helpers import bar


def ohlc_from_highs_lows(pairs):
    """Bars with the given (high, low); open/close sit inside the range."""
    return [bar(i, low + 0.25, h, low, h - 0.25) for i, (h, low) in enumerate(pairs)]


def test_three_bar_swing_high_is_known_at_the_close_of_the_next_bar():
    bars = ohlc_from_highs_lows([(101, 99), (103, 100), (102, 100.5), (101.5, 100)])

    swings = find_swings(bars, n=1)

    highs = [s for s in swings if s.kind == "high"]
    assert [(s.price, s.ts, s.known_at) for s in highs] == [
        (103, bars[1].ts_open, bars[2].ts_close)
    ]


def test_swing_low_mirrors_the_high():
    bars = ohlc_from_highs_lows([(101, 99), (100.5, 98), (101, 99.5)])

    swings = find_swings(bars, n=1)

    assert [(s.kind, s.price, s.known_at) for s in swings] == [("low", 98, bars[2].ts_close)]


def test_equal_neighbouring_highs_are_not_a_swing():
    bars = ohlc_from_highs_lows([(101, 99), (103, 100), (103, 100.5), (101, 100)])

    assert [s for s in find_swings(bars, n=1) if s.kind == "high"] == []


def test_five_bar_swing_needs_two_lower_highs_each_side_and_confirms_two_bars_later():
    bars = ohlc_from_highs_lows(
        [(100, 98), (101, 99), (104, 100), (102, 100), (101.5, 99.5), (101, 99)]
    )

    highs = [s for s in find_swings(bars, n=2) if s.kind == "high"]

    assert [(s.price, s.known_at) for s in highs] == [(104, bars[4].ts_close)]


def test_unconfirmed_last_bar_is_not_a_swing_yet():
    bars = ohlc_from_highs_lows([(101, 99), (103, 100)])

    assert find_swings(bars, n=1) == []


def test_swings_do_not_span_a_contract_roll():
    bars = ohlc_from_highs_lows([(101, 99), (103, 100), (102, 100.5)])
    rolled = [*bars[:2], bar(2, 140.25, 141, 140, 140.75, instrument_id=2)]

    assert [s for s in find_swings(rolled, n=1) if s.kind == "high"] == []
