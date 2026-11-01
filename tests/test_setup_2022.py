from dataclasses import replace
from datetime import date, datetime

from moon_ai.data.news import NewsEvent
from moon_ai.sessions import NY
from moon_ai.setups import REGISTRY, load_setup_defaults
from moon_ai.setups.model_2022 import Ict2022Model, weekly_expansion
from tests.test_setup_london import ASIA, session
from tests.test_setup_silver_bullet import CFG

M22 = load_setup_defaults()["ict_2022_model"].params
PATTERN = {  # sweeps the Asian low (97) at 08:34, MSS + FVG by 08:37
    (8, 31): (100.0, 100.25, 99.75, 100.0),
    (8, 32): (100.0, 100.75, 99.75, 100.25),
    (8, 33): (100.25, 100.5, 98.5, 98.75),
    (8, 34): (98.75, 99.0, 96.5, 98.0),
    (8, 35): (98.0, 100.0, 97.75, 99.75),
    (8, 36): (99.75, 102.0, 99.5, 101.75),
    (8, 37): (101.75, 102.25, 100.5, 102.0),
}
CPI = NewsEvent("cpi", "CPI", "BLS", datetime(2026, 7, 15, 8, 30, tzinfo=NY), True, "x")


def two_weeks(monday_raid=(100.0, 100.25, 99.0, 100.0)):
    bars = []
    for d in (6, 7, 8, 9, 10):  # last week: flat, range 99.75-100.25
        bars += session(date(2026, 7, d), {})
    bars += session(date(2026, 7, 13), {(10, 0): monday_raid})  # this week's first raid
    bars += session(date(2026, 7, 14), {})
    bars += session(date(2026, 7, 15), {**ASIA, **PATTERN}, end=(9, 0))
    return bars


def scan(bars, params=M22, news=(CPI,)):
    from moon_ai.bars import InMemoryBarFeed
    from moon_ai.broker import SimBroker
    from moon_ai.engine import run
    from moon_ai.journal import InMemoryJournal

    setup = Ict2022Model(params, CFG, news=list(news))
    found = []

    class Collect:
        def on_bar(self, bar, ctx):
            found.extend(setup.scan(ctx))

    run(InMemoryBarFeed(bars), SimBroker(CFG.broker, CFG.instrument), Collect(), InMemoryJournal())
    return found


def test_weekly_expansion():
    bars = two_weeks()
    assert weekly_expansion(bars, date(2026, 7, 15)) == "bull"
    high_first = two_weeks(monday_raid=(100.0, 101.0, 99.75, 100.0))
    assert weekly_expansion(high_first, date(2026, 7, 15)) == "bear"
    no_raid = [
        b
        for b in two_weeks(monday_raid=(100.0, 100.25, 99.75, 100.0))
        if b.ts_close < datetime(2026, 7, 14, 18, 0, tzinfo=NY)  # before today's session
    ]
    assert weekly_expansion(no_raid, date(2026, 7, 15)) is None


def test_a_textbook_2022_model_trade():
    (c,) = scan(two_weeks())
    assert c.setup == "ict_2022_model" and c.side == "long"
    assert c.decision_time == datetime(2026, 7, 15, 8, 37, tzinfo=NY)
    assert (c.entry, c.stop, c.target) == (99.5, 96.25, 112.0)
    assert c.rule_results["swept_pool"] == "asia"
    assert REGISTRY["ict_2022_model"] is Ict2022Model


def test_it_needs_a_news_day_unless_the_rescue_trial_drops_it():
    assert scan(two_weeks(), news=()) == []
    assert len(scan(two_weeks(), replace(M22, news_day_filter=False), news=())) == 1


def test_it_trades_only_with_the_weekly_expansion():
    bearish = two_weeks(monday_raid=(100.0, 101.0, 99.75, 100.0))
    assert scan(bearish) == []
    assert len(scan(bearish, replace(M22, bias_gate=False))) == 1


def test_discount_fvg_trial():
    # FVG 99.0-99.5 sits above the 96.5-102.25 range's midpoint (99.375): not in discount.
    assert scan(two_weeks(), replace(M22, require_discount_fvg=True)) == []
