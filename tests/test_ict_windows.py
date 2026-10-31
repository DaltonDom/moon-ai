from datetime import UTC, datetime

from moon_ai.config import load_config
from moon_ai.ict.windows import killzones, silver_bullets, window_membership
from tests.helpers import bar

# 2026-07-15 is EDT. 13:58 UTC = 09:58 New York.
START = datetime(2026, 7, 15, 13, 58, tzinfo=UTC)


def test_membership_is_judged_at_each_bar_close():
    bars = [bar(i, 100, 101, 99, 100, start=START) for i in range(3)]
    # Bars open 09:58, 09:59, 10:00 and close 09:59, 10:00, 10:01.

    tags = window_membership(bars, silver_bullets(load_config()))

    assert [sorted(t.windows) for t in tags] == [
        [],
        ["ny_am_silver_bullet"],
        ["ny_am_silver_bullet"],
    ]
    assert [t.known_at for t in tags] == [b.ts_close for b in bars]


def test_bar_closing_at_the_window_end_is_outside_it():
    end_start = datetime(2026, 7, 15, 14, 59, tzinfo=UTC)  # opens 10:59, closes 11:00

    tags = window_membership(
        [bar(0, 100, 101, 99, 100, start=end_start)], silver_bullets(load_config())
    )

    assert tags[0].windows == frozenset()


def test_killzones_and_silver_bullets_come_from_config():
    cfg = load_config()

    assert set(silver_bullets(cfg)) == {
        "london_silver_bullet",
        "ny_am_silver_bullet",
        "ny_pm_silver_bullet",
    }
    assert set(killzones(cfg)) == {
        "london_killzone",
        "ny_am_killzone",
        "london_close_killzone",
        "ny_pm_session",
    }


def test_a_bar_can_sit_in_overlapping_windows():
    bars = [bar(0, 100, 101, 99, 100, start=datetime(2026, 7, 15, 14, 30, tzinfo=UTC))]  # 10:31
    cfg = load_config()

    tags = window_membership(bars, {**killzones(cfg), **silver_bullets(cfg)})

    assert tags[0].windows == frozenset({"london_close_killzone", "ny_am_silver_bullet"})
