from datetime import UTC, date, datetime, time

import pytest

from moon_ai.config import Window
from moon_ai.sessions import in_window, trading_day, window_bounds

SB_AM = Window(time(10), time(11))
ASIAN = Window(time(20), time(0))


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


def test_window_tracks_new_york_wall_clock_across_us_dst_change():
    # US DST began 2026-03-08. 14:30 UTC is 09:30 EST before, 10:30 EDT after.
    assert not in_window(utc(2026, 3, 6, 14, 30), SB_AM)
    assert in_window(utc(2026, 3, 9, 14, 30), SB_AM)
    # 10:00 New York is 15:00 UTC in winter.
    assert in_window(utc(2026, 3, 6, 15, 0), SB_AM)


def test_window_start_is_inclusive_and_end_exclusive():
    # 2026-07-15 is EDT (UTC-4).
    assert in_window(utc(2026, 7, 15, 14, 0), SB_AM)  # 10:00
    assert in_window(utc(2026, 7, 15, 14, 59, 59), SB_AM)  # 10:59:59
    assert not in_window(utc(2026, 7, 15, 15, 0), SB_AM)  # 11:00
    assert not in_window(utc(2026, 7, 15, 13, 59), SB_AM)  # 09:59


def test_window_crossing_midnight():
    # 2026-07-15 EDT: 20:00 NY = 00:00 UTC next day.
    assert in_window(utc(2026, 7, 16, 0, 0), ASIAN)  # 20:00
    assert in_window(utc(2026, 7, 16, 3, 59), ASIAN)  # 23:59
    assert not in_window(utc(2026, 7, 16, 4, 0), ASIAN)  # 00:00
    assert not in_window(utc(2026, 7, 15, 23, 59), ASIAN)  # 19:59


def test_naive_timestamps_are_rejected():
    with pytest.raises(ValueError, match="timezone"):
        in_window(datetime(2026, 7, 15, 14, 0), SB_AM)


def test_trading_day_rolls_at_1800_new_york():
    # Sunday 18:00 EDT opens Monday's session.
    assert trading_day(utc(2026, 7, 12, 22, 0)) == date(2026, 7, 13)  # Sun 18:00
    assert trading_day(utc(2026, 7, 12, 21, 59)) == date(2026, 7, 12)  # Sun 17:59
    assert trading_day(utc(2026, 7, 13, 20, 59)) == date(2026, 7, 13)  # Mon 16:59


def test_window_bounds_in_utc_for_a_new_york_date():
    assert window_bounds(date(2026, 3, 6), SB_AM) == (utc(2026, 3, 6, 15), utc(2026, 3, 6, 16))
    assert window_bounds(date(2026, 3, 9), SB_AM) == (utc(2026, 3, 9, 14), utc(2026, 3, 9, 15))
    # A window crossing midnight ends on the next calendar day.
    assert window_bounds(date(2026, 7, 15), ASIAN) == (utc(2026, 7, 16, 0), utc(2026, 7, 16, 4))


def test_window_bounds_on_dst_transition_day():
    # 2026-11-01: clocks fall back at 02:00 EDT -> 01:00 EST.
    lon = Window(time(2), time(5))
    assert window_bounds(date(2026, 11, 1), lon) == (utc(2026, 11, 1, 7), utc(2026, 11, 1, 10))
