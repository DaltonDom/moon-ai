from dataclasses import replace

import pytest

from moon_ai.bars import InMemoryBarFeed, mark_rolls
from tests.helpers import MINUTE, T0, bar


def test_a_bar_is_known_one_interval_after_its_open_stamp():
    b = bar(0, 100, 101, 99, 100.5)

    assert b.ts_open == T0
    assert b.known_at == T0 + MINUTE


def test_feed_yields_bars_in_close_time_order_across_symbols():
    es = bar(0, 5000, 5001, 4999, 5000, symbol="ES.v.0")
    mnq0 = bar(0, 100, 101, 99, 100)
    mnq1 = bar(1, 100, 101, 99, 100)

    feed = InMemoryBarFeed([mnq1, es, mnq0])

    assert list(feed) == [es, mnq0, mnq1]


def test_feed_rejects_duplicate_bars():
    b = bar(0, 100, 101, 99, 100)

    with pytest.raises(ValueError, match="duplicate"):
        InMemoryBarFeed([b, b])


def test_feed_rejects_bars_with_impossible_ranges():
    with pytest.raises(ValueError, match="high"):
        InMemoryBarFeed([bar(0, 100, 99, 98, 100)])


def test_roll_is_flagged_on_the_first_bar_of_a_new_contract():
    bars = [
        bar(0, 100, 101, 99, 100, instrument_id=7),
        bar(1, 100, 101, 99, 100, instrument_id=7),
        bar(2, 140, 141, 139, 140, instrument_id=9),
        bar(3, 140, 141, 139, 140, instrument_id=9),
    ]

    flags = [b.roll for b in mark_rolls(bars)]

    assert flags == [False, False, True, False]


def test_rolls_are_tracked_per_symbol():
    bars = [
        bar(0, 100, 101, 99, 100, instrument_id=7),
        replace(bar(0, 5000, 5001, 4999, 5000, symbol="ES.v.0"), instrument_id=3),
        bar(1, 100, 101, 99, 100, instrument_id=7),
    ]

    assert [b.roll for b in mark_rolls(bars)] == [False, False, False]
