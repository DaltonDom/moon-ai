"""No ICT primitive may use future bars.

For a primitive f and every cut point t, f(bars[:t]) must equal the outputs of
f(bars) whose known_at is at or before bars[t-1].ts_close. If a primitive
peeked at bars after t, its truncated output would differ (or the full-series
output would contain something stamped earlier than it could be known).
"""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, time, timedelta

import pytest

from moon_ai.bars import Bar
from moon_ai.config import Window, load_config
from moon_ai.ict.displacement import find_displacements
from moon_ai.ict.fvg import find_fvgs
from moon_ai.ict.liquidity import find_sweeps, prior_day_levels, swing_levels, window_levels
from moon_ai.ict.structure import find_market_structure_shifts
from moon_ai.ict.swings import find_swings
from moon_ai.ict.windows import killzones, silver_bullets, window_membership
from moon_ai.sessions import in_window

TICK = 0.25
ASIAN = Window(time(20), time(0))
MAINTENANCE = Window(time(17), time(18))


def synthetic_session(seed: int = 7) -> list[Bar]:
    """15:30 New York to 01:00 next day on 2026-07-15/16 (EDT), skipping the
    17:00-18:00 maintenance break, with a contract roll at 19:00 and a few
    volatility bursts so every primitive has something to find."""
    rng = random.Random(seed)
    start = datetime(2026, 7, 15, 19, 30, tzinfo=UTC)  # 15:30 New York
    roll_at = datetime(2026, 7, 15, 23, 0, tzinfo=UTC)  # 19:00 New York
    bars: list[Bar] = []
    price = 18000.0
    for i in range(570):
        ts = start + timedelta(minutes=i)
        if in_window(ts, MAINTENANCE):
            continue
        rolled = ts >= roll_at
        if rolled and bars and bars[-1].instrument_id == 1:
            price += 40.0  # unadjusted roll gap
        burst = rng.random() < 0.06
        scale = 12 if burst else 3
        o = price + TICK * rng.randint(-1, 1)
        c = o + TICK * rng.randint(-scale, scale)
        h = max(o, c) + TICK * rng.randint(0, scale)
        low = min(o, c) - TICK * rng.randint(0, scale)
        bars.append(
            Bar(
                symbol="MNQ.v.0",
                ts_open=ts,
                ts_close=ts + timedelta(minutes=1),
                open=o,
                high=h,
                low=low,
                close=c,
                volume=100,
                instrument_id=2 if rolled else 1,
            )
        )
        price = c
    return bars


def swings_n1(bars):
    return find_swings(bars, n=1)


def swings_n2(bars):
    return find_swings(bars, n=2)


def fvgs(bars):
    return find_fvgs(bars, tick=TICK)


def displacement_with_fvg(bars):
    return find_displacements(bars, tick=TICK, k=1.5, atr_period=14, require_fvg=True)


def displacement_body_only(bars):
    return find_displacements(bars, tick=TICK, k=1.0, atr_period=14, require_fvg=False)


def levels(bars):
    return (
        swing_levels(find_swings(bars, n=1))
        + window_levels(bars, ASIAN, "asia")
        + prior_day_levels(bars)
    )


def _sweeps(bars, **kw):
    return find_sweeps(bars, levels(bars), tick=TICK, **kw)


def sweeps_m1(bars):
    return _sweeps(bars, close_back_bars=1)


def sweeps_m3(bars):
    return _sweeps(bars, close_back_bars=3)


def sweeps_no_close_back(bars):
    return _sweeps(bars, require_close_back=False)


def mss_close(bars):
    return find_market_structure_shifts(bars, find_swings(bars, n=1), sweeps_m3(bars), "close")


def mss_wick(bars):
    return find_market_structure_shifts(bars, find_swings(bars, n=1), sweeps_m1(bars), "wick")


def windows(bars):
    cfg = load_config()
    return window_membership(bars, {**killzones(cfg), **silver_bullets(cfg)})


PRIMITIVES: list[Callable[[Sequence[Bar]], list]] = [
    swings_n1,
    swings_n2,
    fvgs,
    displacement_with_fvg,
    displacement_body_only,
    levels,
    sweeps_m1,
    sweeps_m3,
    sweeps_no_close_back,
    mss_close,
    mss_wick,
    windows,
]


@pytest.fixture(scope="module")
def bars() -> list[Bar]:
    return synthetic_session()


def test_fixture_spans_the_day_close_the_asian_window_and_a_roll(bars):
    assert {b.instrument_id for b in bars} == {1, 2}
    assert any(lv.source == "asia" for lv in levels(bars))
    assert any(lv.source == "day" for lv in levels(bars))


@pytest.mark.parametrize("primitive", PRIMITIVES, ids=lambda f: f.__name__)
def test_primitive_never_uses_future_bars(primitive, bars):
    full = primitive(bars)
    assert full, f"{primitive.__name__} found nothing; the test would be vacuous"

    cuts = sorted({*range(1, len(bars) + 1, 7), len(bars)})
    for t in cuts:
        now = bars[t - 1].ts_close
        truncated = primitive(bars[:t])
        expected = [x for x in full if x.known_at <= now]
        assert sorted(truncated, key=repr) == sorted(expected, key=repr), f"cut at t={t}"
        assert all(x.known_at <= now for x in truncated), f"cut at t={t}"
