"""Simulated broker behaviour, observed through the Broker interface.

Instrument: MNQ, tick 0.25, $2/point. Config: 1 tick slippage, $0.50/side.
"""

import pytest

from moon_ai.broker import Bracket, Order, OrderType, Side, SimBroker
from moon_ai.config import BrokerConfig, load_config
from tests.helpers import bar, second_bars

CFG = BrokerConfig(commission_per_contract=0.5, slippage_ticks=1, limit_fill="trade_through")


def broker(cfg: BrokerConfig = CFG, second_bar_source=None) -> SimBroker:
    return SimBroker(cfg, load_config().instrument, second_bar_source)


def buy(type_=OrderType.MARKET, price=None, bracket=None, qty=1) -> Order:
    return Order("MNQ.v.0", Side.BUY, qty, type_, price=price, bracket=bracket)


def sell(type_=OrderType.MARKET, price=None, bracket=None, qty=1) -> Order:
    return Order("MNQ.v.0", Side.SELL, qty, type_, price=price, bracket=bracket)


# --- entries ---------------------------------------------------------------


def test_market_order_fills_at_the_next_bar_open_plus_slippage():
    b = broker()
    assert b.on_bar(bar(0, 100, 101, 99, 100.5)) == []  # decision bar
    b.submit(buy())

    fills = b.on_bar(bar(1, 101, 102, 100, 101.5))

    assert [(f.price, f.reason, f.commission) for f in fills] == [(101.25, "entry", 0.5)]
    assert b.position("MNQ.v.0") == 1


def test_an_order_never_fills_on_bars_that_opened_before_it_was_submitted():
    b = broker()
    b.on_bar(bar(1, 100, 101, 99, 100.5))
    b.submit(buy())

    # A late, out-of-order bar from before the submit time must not fill it.
    assert b.on_bar(bar(0, 100, 101, 99, 100)) == []
    assert b.position("MNQ.v.0") == 0


def test_buy_stop_triggers_when_the_high_reaches_it():
    b = broker()
    b.on_bar(bar(0, 100, 101, 99, 100))
    b.submit(buy(OrderType.STOP, price=102.0))

    assert b.on_bar(bar(1, 100, 101.75, 99, 101)) == []
    fills = b.on_bar(bar(2, 101, 102.5, 100.5, 102))

    assert [f.price for f in fills] == [102.25]  # stop + 1 tick slippage


def test_buy_stop_gapped_through_fills_at_the_open_plus_slippage():
    b = broker()
    b.on_bar(bar(0, 100, 101, 99, 100))
    b.submit(buy(OrderType.STOP, price=102.0))

    fills = b.on_bar(bar(1, 103, 104, 102.5, 103.5))

    assert [f.price for f in fills] == [103.25]


def test_buy_limit_needs_a_trade_through_by_default():
    b = broker()
    b.on_bar(bar(0, 101, 102, 100.5, 101))
    b.submit(buy(OrderType.LIMIT, price=100.0))

    assert b.on_bar(bar(1, 101, 101.5, 100.0, 100.5)) == []  # touch only
    fills = b.on_bar(bar(2, 100.5, 101, 99.75, 100.25))

    assert [(f.price, f.slippage) for f in fills] == [(100.0, 0.0)]  # limits don't slip


def test_buy_limit_fills_on_touch_when_configured():
    b = broker(BrokerConfig(commission_per_contract=0.5, slippage_ticks=1, limit_fill="touch"))
    b.on_bar(bar(0, 101, 102, 100.5, 101))
    b.submit(buy(OrderType.LIMIT, price=100.0))

    fills = b.on_bar(bar(1, 101, 101.5, 100.0, 100.5))

    assert [f.price for f in fills] == [100.0]


def test_buy_limit_gapped_through_fills_at_the_better_open():
    b = broker()
    b.on_bar(bar(0, 101, 102, 100.5, 101))
    b.submit(buy(OrderType.LIMIT, price=100.0))

    fills = b.on_bar(bar(1, 99, 99.5, 98, 99.25))

    assert [f.price for f in fills] == [99.0]


def test_cancelled_order_never_fills():
    b = broker()
    b.on_bar(bar(0, 100, 101, 99, 100))
    order_id = b.submit(buy())
    b.cancel(order_id)

    assert b.on_bar(bar(1, 100, 101, 99, 100)) == []


def test_bars_for_another_symbol_do_not_fill_the_order():
    b = broker()
    b.on_bar(bar(0, 100, 101, 99, 100))
    b.submit(buy())

    assert b.on_bar(bar(1, 5000, 5001, 4999, 5000, symbol="ES.v.0")) == []
    assert len(b.on_bar(bar(1, 100, 101, 99, 100))) == 1


def test_orders_need_a_price_unless_they_are_market_orders():
    with pytest.raises(ValueError, match="price"):
        buy(OrderType.LIMIT)
