"""The `Broker` interface and the simulated broker used for backtests and replay.

Fill rules of `SimBroker`, against 1-minute OHLC bars:

- An order is eligible only for bars that open at or after the moment it was
  submitted (the close of the bar the strategy decided on).
- Market: fills at the bar's open, plus slippage.
- Stop: triggers when the bar trades at the stop price; fills at the stop, or
  at the open if the bar gaps through it, plus slippage.
- Limit: fills at the limit, or at the better open on a gap. By default the bar
  must trade *through* the limit by a tick; `limit_fill = "touch"` fills on a
  touch. Limit fills don't slip.
- Commission is charged per contract on every fill.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Literal, Protocol

from moon_ai.bars import Bar
from moon_ai.config import BrokerConfig, InstrumentSpec


class Side(Enum):
    BUY = 1
    SELL = -1


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"


@dataclass(frozen=True)
class Bracket:
    """Stop and target attached at entry; they become active once the entry fills."""

    stop: float
    target: float


@dataclass(frozen=True)
class Order:
    symbol: str
    side: Side
    qty: int
    type: OrderType = OrderType.MARKET
    price: float | None = None
    bracket: Bracket | None = None
    tag: str = ""

    def __post_init__(self) -> None:
        if self.type is not OrderType.MARKET and self.price is None:
            raise ValueError(f"{self.type.value} order needs a price")
        if self.qty <= 0:
            raise ValueError("qty must be positive")


FillReason = Literal["entry", "exit", "stop", "target"]


@dataclass(frozen=True)
class Fill:
    order_id: str
    symbol: str
    side: Side
    qty: int
    price: float
    ts: datetime
    reason: FillReason
    commission: float
    slippage: float  # price units, always >= 0, against us
    pnl: float = 0.0  # gross realized USD for closing fills
    ambiguous: bool = False  # stop and target both touched in one bar
    resolved_by: Literal["gap", "1s", "pessimistic"] | None = None


class Broker(Protocol):
    def submit(self, order: Order) -> str: ...

    def cancel(self, order_id: str) -> None: ...

    def on_bar(self, bar: Bar) -> list[Fill]: ...

    def position(self, symbol: str) -> int: ...


SecondBarSource = Callable[[str, datetime], list[Bar] | None]
InstrumentLookup = Callable[[str], InstrumentSpec]


@dataclass
class _Working:
    id: str
    order: Order
    submitted_at: datetime


class SimBroker:
    def __init__(
        self,
        config: BrokerConfig,
        instruments: InstrumentLookup,
        second_bars: SecondBarSource | None = None,
    ):
        self._cfg = config
        self._instrument = instruments
        self._second_bars = second_bars
        self._ids = (f"o{i}" for i in itertools.count(1))
        self._now: datetime | None = None
        self._working: dict[str, _Working] = {}
        self._positions: dict[str, int] = {}

    # --- Broker interface ---------------------------------------------------

    def submit(self, order: Order) -> str:
        if self._now is None:
            raise RuntimeError("submit before the first bar: the simulator has no clock yet")
        order_id = next(self._ids)
        self._working[order_id] = _Working(order_id, order, self._now)
        return order_id

    def cancel(self, order_id: str) -> None:
        self._working.pop(order_id, None)

    def position(self, symbol: str) -> int:
        return self._positions.get(symbol, 0)

    def on_bar(self, bar: Bar) -> list[Fill]:
        fills: list[Fill] = []
        for w in list(self._working.values()):
            if w.order.symbol != bar.symbol or bar.ts_open < w.submitted_at:
                continue
            price = self._entry_price(w.order, bar)
            if price is None:
                continue
            del self._working[w.id]
            fills.append(self._fill(w, price, bar))
        self._now = bar.ts_close if self._now is None else max(self._now, bar.ts_close)
        return fills

    # --- internals ------------------------------------------------------------

    def _entry_price(self, order: Order, bar: Bar) -> float | None:
        """Raw (pre-slippage) fill price of `order` in `bar`, or None."""
        sign = order.side.value
        tick = self._instrument(order.symbol).tick_size
        if order.type is OrderType.MARKET:
            return bar.open
        assert order.price is not None
        if order.type is OrderType.STOP:
            if sign > 0:
                return max(bar.open, order.price) if bar.high >= order.price else None
            return min(bar.open, order.price) if bar.low <= order.price else None
        # LIMIT
        through = 0.0 if self._cfg.limit_fill == "touch" else tick
        if sign > 0:
            return min(bar.open, order.price) if bar.low <= order.price - through else None
        return max(bar.open, order.price) if bar.high >= order.price + through else None

    def _fill(self, w: _Working, raw_price: float, bar: Bar) -> Fill:
        order = w.order
        slip = 0.0
        if order.type is not OrderType.LIMIT:
            slip = self._cfg.slippage_ticks * self._instrument(order.symbol).tick_size
        price = raw_price + order.side.value * slip
        self._positions[order.symbol] = self.position(order.symbol) + order.side.value * order.qty
        return Fill(
            order_id=w.id,
            symbol=order.symbol,
            side=order.side,
            qty=order.qty,
            price=price,
            ts=bar.ts_close,
            reason="entry",
            commission=self._cfg.commission_per_contract * order.qty,
            slippage=slip,
        )
