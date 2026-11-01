from dataclasses import replace

import pytest

from moon_ai.setups import REGISTRY, load_setup_defaults
from moon_ai.setups.ote import OtePullback
from tests.test_setup_silver_bullet import day, ny, random_day, scan_all

OTE = load_setup_defaults()["ote_pullback"].params
LEG = {
    (8, 35): (100.0, 101.0, 99.75, 100.0),  # swing high 101: the structure to break
    (8, 40): (100.0, 100.25, 98.0, 99.0),  # swing low 98: the leg's origin
    (8, 41): (99.0, 99.5, 98.75, 99.25),
    (8, 42): (99.25, 99.5, 99.0, 99.25),
    (8, 43): (99.5, 103.5, 99.25, 103.25),  # displacement, closes above 101
    (8, 44): (103.25, 104.5, 103.0, 104.25),  # completes the FVG 99.5-103.0
    (8, 45): (104.25, 106.0, 104.0, 105.5),  # the leg's high, 106
    (8, 46): (105.5, 105.75, 104.5, 105.0),  # confirms the swing high
}


def test_a_textbook_ote_pullback():
    (c,) = scan_all(day(LEG, end=(9, 30)), OTE, cls=OtePullback)
    assert c.setup == "ote_pullback" and c.side == "long"
    assert c.decision_time == ny(8, 47)
    # Leg 98 -> 106: entry at 62% = 101.04 -> 101.0, stop under the origin, target the high.
    assert (c.entry, c.stop, c.target) == (101.0, 97.75, 106.0)
    assert c.entry_deadline == ny(11, 0)
    assert REGISTRY["ote_pullback"] is OtePullback


def test_deeper_ote_levels_and_the_fvg_overlap_trial():
    (c,) = scan_all(day(LEG, end=(9, 30)), replace(OTE, ote_entry=0.79), cls=OtePullback)
    assert c.entry == 99.75  # 106 - 0.79 x 8 = 99.68 -> 99.75
    assert (
        len(
            scan_all(day(LEG, end=(9, 30)), replace(OTE, require_ote_overlap=True), cls=OtePullback)
        )
        == 1
    )


def test_no_setup_if_price_is_already_back_at_the_entry():
    retraced = {**LEG, (8, 46): (105.5, 105.75, 100.5, 101.5)}
    assert scan_all(day(retraced, end=(9, 30)), OTE, cls=OtePullback) == []


def test_outside_the_window_or_without_a_break_is_nothing():
    early = {(h - 1, m): b for (h, m), b in LEG.items()}  # 07:35-07:46
    assert scan_all(day(early, end=(9, 30)), OTE, cls=OtePullback) == []
    weak = {**LEG, (8, 43): (99.5, 100.75, 99.25, 100.5)}  # no displacement through 101
    assert scan_all(day(weak, end=(9, 30)), OTE, cls=OtePullback) == []


@pytest.mark.parametrize("seed", range(4))
def test_no_look_ahead(seed):
    bars = random_day(seed)
    full = scan_all(bars, OTE, cls=OtePullback)
    for c in full:
        cut = [b for b in bars if b.ts_close <= c.decision_time]
        assert scan_all(cut, OTE, cls=OtePullback)[-1] == c
