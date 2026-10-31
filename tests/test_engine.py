from dataclasses import dataclass, field

import pytest

from moon_ai.bars import Bar, InMemoryBarFeed
from moon_ai.broker import Bracket, Order, Side, SimBroker
from moon_ai.config import BrokerConfig, load_config
from moon_ai.engine import Context, run
from moon_ai.journal import InMemoryJournal
from tests.helpers import bar


def sim() -> SimBroker:
    return SimBroker(
        BrokerConfig(commission_per_contract=0.5, entry_slippage_ticks=1, stop_slippage_ticks=1),
        load_config().instrument,
    )


@dataclass
class Recorder:
    seen: list[tuple] = field(default_factory=list)

    def on_bar(self, bar: Bar, ctx: Context) -> None:
        history = ctx.history(bar.symbol)
        self.seen.append((ctx.now, bar, history[-1], max(b.ts_close for b in history)))


def test_strategy_only_ever_sees_closed_bars():
    bars = [bar(i, 100, 101, 99, 100) for i in range(5)]
    rec = Recorder()

    run(InMemoryBarFeed(bars), sim(), rec, InMemoryJournal())

    assert len(rec.seen) == 5
    for now, current, last_in_history, latest_close in rec.seen:
        assert now == current.ts_close
        assert last_in_history == current
        assert latest_close <= now


class BuyOnce:
    def __init__(self):
        self.done = False

    def on_bar(self, bar: Bar, ctx: Context) -> None:
        if not self.done:
            ctx.broker.submit(Order(bar.symbol, Side.BUY, 1, bracket=Bracket(98.0, 104.0)))
            self.done = True


def test_orders_fill_on_the_next_bar_and_every_fill_is_journaled():
    bars = [
        bar(0, 100, 100.5, 99.5, 100),
        bar(1, 100, 100.5, 99.75, 100.25),
        bar(2, 101, 104.5, 100.75, 104.25),
    ]
    journal = InMemoryJournal()

    run(InMemoryBarFeed(bars), sim(), BuyOnce(), journal)

    fills = [e.data["fill"] for e in journal.of_kind("fill")]
    assert [(f.reason, f.price, f.ts) for f in fills] == [
        ("entry", 100.25, bars[1].ts_close),
        ("target", 104.0, bars[2].ts_close),
    ]


def test_rolls_are_journaled():
    bars = [bar(0, 100, 101, 99, 100, instrument_id=1), bar(1, 140, 141, 139, 140, instrument_id=2)]
    journal = InMemoryJournal()

    run(InMemoryBarFeed(bars), sim(), Recorder(), journal)

    rolls = journal.of_kind("roll")
    assert [(e.ts, e.data["symbol"], e.data["instrument_id"]) for e in rolls] == [
        (bars[1].ts_close, "MNQ.v.0", 2)
    ]


def test_engine_refuses_a_feed_that_goes_back_in_time():
    class Backwards:
        def __iter__(self):
            return iter([bar(1, 100, 101, 99, 100), bar(0, 100, 101, 99, 100)])

    with pytest.raises(ValueError, match="order"):
        run(Backwards(), sim(), Recorder(), InMemoryJournal())


def test_history_can_be_limited_to_the_last_n_bars():
    bars = [bar(i, 100 + i, 101 + i, 99 + i, 100 + i) for i in range(4)]
    seen = []

    class LastTwo:
        def on_bar(self, bar: Bar, ctx: Context) -> None:
            seen.append([b.open for b in ctx.history(bar.symbol, 2)])

    run(InMemoryBarFeed(bars), sim(), LastTwo(), InMemoryJournal())

    assert seen == [[100], [100, 101], [101, 102], [102, 103]]
