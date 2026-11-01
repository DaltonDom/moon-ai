import random
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from moon_ai.bars import Bar, InMemoryBarFeed
from moon_ai.broker import SimBroker
from moon_ai.config import load_config
from moon_ai.engine import run
from moon_ai.journal import InMemoryJournal
from moon_ai.sessions import NY
from moon_ai.setups import REGISTRY, load_setup_defaults
from moon_ai.setups.silver_bullet import NyAmSilverBullet

CFG = load_config()
AM = load_setup_defaults()["ny_am_silver_bullet"].params
DAY_START = datetime(2026, 7, 14, 22, 0, tzinfo=UTC)  # 18:00 New York, trading day 2026-07-15
FLAT = (100.0, 100.25, 99.75, 100.0)


def ny(h, m):
    return datetime(2026, 7, 15, h, m, tzinfo=NY)


def day(special: dict, end=(10, 30), overnight_high=112.0):
    """One CME session of flat bars, with `special` {(h, m): (o, h, l, c)} New York bars."""
    special = {
        (2, 0): (100.0, overnight_high, 99.75, 100.0),  # overnight high (the draw on liquidity)
        (3, 0): (100.0, 100.25, 97.0, 100.0),  # overnight low (the pool to sweep)
        **special,
    }
    bars, t = [], DAY_START
    stop = ny(*end)
    while t < stop:
        local = t.astimezone(NY)
        o, h, lo, c = special.get((local.hour, local.minute), FLAT)
        bars.append(Bar("MNQ.v.0", t, t + timedelta(minutes=1), o, h, lo, c, 100, 1))
        t += timedelta(minutes=1)
    return bars


SETUP_BARS = {
    (10, 1): (100.0, 100.25, 99.75, 100.0),
    (10, 2): (100.0, 100.75, 99.75, 100.25),  # swing high 100.75
    (10, 3): (100.25, 100.5, 98.5, 98.75),
    (10, 4): (98.75, 99.0, 96.5, 98.0),  # sweeps the overnight low 97, closes back above
    (10, 5): (98.0, 100.0, 97.75, 99.75),
    (10, 6): (99.75, 102.0, 99.5, 101.75),  # displacement, closes through 100.75: MSS
    (10, 7): (101.75, 102.25, 100.5, 102.0),
}


def scan_all(bars, params=AM, cls=NyAmSilverBullet):
    setup = cls(params, CFG)
    found = []

    class Collect:
        def on_bar(self, bar, ctx):
            found.extend(setup.scan(ctx))

    run(InMemoryBarFeed(bars), SimBroker(CFG.broker, CFG.instrument), Collect(), InMemoryJournal())
    return found


def test_a_textbook_am_silver_bullet():
    (c,) = scan_all(day(SETUP_BARS))
    assert c.setup == "ny_am_silver_bullet" and c.side == "long"
    # The first bullish FVG after the sweep is 99.0-99.5 (10:04-10:06), complete at 10:07,
    # the same close that confirms the MSS.
    assert c.decision_time == ny(10, 7)
    assert (c.entry_type, c.entry, c.stop, c.target) == ("limit", 99.5, 96.25, 112.0)
    assert c.entry_deadline == ny(11, 0)
    assert c.timeout == ny(15, 55)
    assert c.rule_results["swept_pool"] == "overnight"
    assert c.features["sweep_depth_ticks"] == 2


def test_too_little_room_to_the_draw_on_liquidity_is_not_a_setup():
    assert scan_all(day(SETUP_BARS, overnight_high=108.0)) == []  # 7.5 points < 10
    looser = replace(AM, min_objective_points=5.0)
    assert len(scan_all(day(SETUP_BARS, overnight_high=108.0), looser)) == 1


def test_a_setup_completed_before_the_window_is_ignored():
    early = {(h, m - 15): bar for (h, m), bar in SETUP_BARS.items()}  # 09:46-09:52
    assert scan_all(day(early)) == []


def test_ce_entry_and_one_candidate_per_day():
    again = {**SETUP_BARS, **{(10, m + 15): b for (_, m), b in SETUP_BARS.items()}}
    (c,) = scan_all(day(again, end=(10, 45)), replace(AM, fvg_entry="ce"))
    assert c.entry == 99.25  # CE of 99.0-99.5


def test_unbuilt_rescue_variants_fail_loudly():
    with pytest.raises(NotImplementedError):
        NyAmSilverBullet(replace(AM, fvg_selection="first_tethered"), CFG)
    assert REGISTRY["ny_am_silver_bullet"] is NyAmSilverBullet


def random_day(seed):
    rng = random.Random(seed)
    bars, t, px = [], DAY_START, 18000.0
    while t < ny(11, 30):
        burst = rng.random() < 0.08
        step = 0.25 * rng.randint(-12, 12) if burst else 0.25 * rng.randint(-3, 3)
        o, c = px, px + step
        h = max(o, c) + 0.25 * rng.randint(0, 6 if burst else 2)
        lo = min(o, c) - 0.25 * rng.randint(0, 6 if burst else 2)
        bars.append(Bar("MNQ.v.0", t, t + timedelta(minutes=1), o, h, lo, c, 100, 1))
        px, t = c, t + timedelta(minutes=1)
    return bars


@pytest.mark.parametrize("seed", range(6))
def test_no_look_ahead(seed):
    loose = replace(AM, min_objective_points=0.0)
    bars = random_day(seed)
    full = scan_all(bars, loose)
    for c in full:
        cut = [b for b in bars if b.ts_close <= c.decision_time]
        assert scan_all(cut, loose)[-1] == c


def test_round2_minimum_reward_to_risk():
    # The textbook plan risks 3.25 (99.5 -> 96.25) for 12.5 to the target: 3.85:1.
    assert scan_all(day(SETUP_BARS), replace(AM, min_rr=4.0)) == []
    assert len(scan_all(day(SETUP_BARS), replace(AM, min_rr=3.5))) == 1


def test_round2_bias_gate_keeps_only_shifts_with_the_bias():
    from types import SimpleNamespace as NS

    sb = NyAmSilverBullet(replace(AM, bias_gate=True), CFG)
    sb._bias = "bear"
    assert not sb._accept(NS(direction="bull"), [])
    assert sb._accept(NS(direction="bear"), [])
    sb._bias = None  # no bias (an inside close): either side
    assert sb._accept(NS(direction="bull"), [])
    # With no earlier sessions there's no bias, so the textbook day still trades.
    assert len(scan_all(day(SETUP_BARS), replace(AM, bias_gate=True))) == 1


@pytest.mark.parametrize("seed", range(4))
def test_round2_five_minute_patterns_are_decided_only_as_each_5m_bar_closes(seed):
    five = replace(AM, timeframe=5, min_objective_points=0.0)
    bars = random_day(seed)
    for c in scan_all(bars, five):
        assert c.decision_time.minute % 5 == 0
        cut = [b for b in bars if b.ts_close <= c.decision_time]
        assert scan_all(cut, five)[-1] == c  # still no look-ahead


def test_resample_builds_only_whole_clock_aligned_bars():
    from moon_ai.bars import resample

    bars = day({}, end=(10, 7))[-12:]  # 09:55 .. 10:06 New York, 1-minute
    five = resample(bars, 5)
    assert [b.ts_open.astimezone(NY).strftime("%H:%M") for b in five] == ["09:55", "10:00"]
    first = bars[:5]
    assert five[0].high == max(b.high for b in first) and five[0].close == first[-1].close
    assert five[0].ts_close == first[-1].ts_close
