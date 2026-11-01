import pytest

from moon_ai.ict.displacement import atr, find_displacements
from tests.helpers import bar


def quiet(n: int, start_index: int = 0, base: float = 100.0):
    """n bars with a 1-point range and a 0.25 body (true range 1.0)."""
    return [bar(start_index + i, base, base + 0.5, base - 0.5, base + 0.25) for i in range(n)]


def test_atr_is_the_mean_true_range_of_the_last_period_bars():
    bars = [
        bar(0, 100, 101, 99, 100.5),  # TR 2 (no previous close)
        bar(1, 100.5, 101, 100, 100.75),  # TR 1
        bar(2, 103, 104, 102.5, 103),  # gap: TR = 104 - 100.75 = 3.25
    ]

    assert atr(bars, period=3) == [None, None, pytest.approx((2 + 1 + 3.25) / 3)]
    assert atr(bars, period=2) == [None, 1.5, pytest.approx((1 + 3.25) / 2)]


def test_big_body_against_the_prior_atr_is_a_displacement_once_its_fvg_confirms():
    bars = [
        *quiet(14),
        bar(14, 100.25, 102.5, 100.25, 102.25),  # body 2.0 >= 1.5 * ATR(1.0)
        bar(15, 102.25, 103, 101.5, 102.75),  # low 101.5 > high 100.5 two bars back: FVG
    ]

    found = find_displacements(bars, tick=0.25, k=1.5, atr_period=14, require_fvg=True)

    assert [(d.direction, d.index, d.body, d.atr, d.known_at) for d in found] == [
        ("bull", 14, 2.0, 1.0, bars[15].ts_close)
    ]


def test_without_the_fvg_requirement_it_is_known_at_its_own_close():
    bars = [*quiet(14), bar(14, 100.25, 102.5, 100.25, 102.25)]

    found = find_displacements(bars, tick=0.25, k=1.5, atr_period=14, require_fvg=False)

    assert [(d.index, d.known_at) for d in found] == [(14, bars[14].ts_close)]


def test_no_displacement_when_the_body_is_below_k_atr():
    bars = [*quiet(14), bar(14, 100.25, 101.75, 100.25, 101.5)]  # body 1.25 < 1.5

    assert find_displacements(bars, tick=0.25, k=1.5, atr_period=14, require_fvg=False) == []


def test_big_body_without_an_fvg_is_not_a_displacement_when_one_is_required():
    bars = [
        *quiet(14),
        bar(14, 100.25, 102.5, 100.25, 102.25),
        bar(15, 102.25, 102.5, 100.25, 100.5),  # low trades back into the range
    ]

    assert find_displacements(bars, tick=0.25, k=1.5, atr_period=14, require_fvg=True) == []


def test_bearish_displacement():
    bars = [
        *quiet(14),
        bar(14, 100.0, 100.0, 97.5, 97.75),  # body 2.25
        bar(15, 97.75, 99.0, 97.0, 98.5),  # high 99 < low 99.5 two bars back
    ]

    found = find_displacements(bars, tick=0.25, k=1.5, atr_period=14, require_fvg=True)

    assert [d.direction for d in found] == ["bear"]


def test_atr_restarts_after_a_roll():
    rolled = [*quiet(3)] + [
        bar(3 + i, 140, 140.5, 139.5, 140.25, instrument_id=2) for i in range(2)
    ]

    values = atr(rolled, period=2)

    # Bar 3 opens a new contract: no previous close and no carried ATR.
    assert values[3] is None
    assert values[4] == pytest.approx(1.0)


def test_no_displacement_after_a_frozen_market():
    """14 flat bars give ATR 0; the next small candle must not count (it crashed OTE)."""
    flat = [bar(i, 100, 100, 100, 100) for i in range(14)]
    bars = [*flat, bar(14, 100, 100.5, 100, 100.25)]

    assert atr(bars, 14)[13] == 0
    assert find_displacements(bars, tick=0.25, k=1.5, atr_period=14, require_fvg=False) == []
