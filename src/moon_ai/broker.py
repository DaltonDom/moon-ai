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

Brackets: an order's stop and target become active the moment it fills.

- The stop triggers on a touch and slips; the target is a limit and follows the
  limit rule. A bar that opens beyond either fills it at the open ("gap").
- **Pessimistic same-bar rule:** if one bar touches both, the stop fills first,
  unless 1-second bars for that minute are supplied, in which case the minute
  is replayed through them. The fill is flagged `ambiguous` either way.
- On the bar a stop or limit entry fills, the order of the entry and the bar's
  extremes is unknown. A touched stop counts; a touched target doesn't (unless
  1-second bars decide it).
- An order on the opposite side of an open position closes it (oldest first)
  and cancels that part of the bracket.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass, field, replace
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
"""(symbol, minute ts_open) -> that minute's 1-second bars, or None if unavailable."""
InstrumentLookup = Callable[[str], InstrumentSpec]


@dataclass
class _Working:
    id: str
    order: Order
    submitted_at: datetime


@dataclass
class _Lot:
    """An open position from one entry fill, with its (optional) bracket."""

    id: str
    symbol: str
    side: Side
    qty: int
    entry_price: float
    bracket: Bracket | None


@dataclass
class _State:
    next_id: int = 1
    now: datetime | None = None
    working: dict[str, _Working] = field(default_factory=dict)
    lots: list[_Lot] = field(default_factory=list)


@dataclass(frozen=True)
class _Mirror:
    """Maps a short to long-space prices (negation) and back."""

    sign: int

    def bar(self, b: Bar) -> tuple[float, float, float]:
        """(open, high, low) seen from the position's side."""
        if self.sign > 0:
            return b.open, b.high, b.low
        return -b.open, -b.low, -b.high

    def px(self, price: float) -> float:
        return self.sign * price


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
        self._s = _State()

    # --- Broker interface ---------------------------------------------------

    def submit(self, order: Order) -> str:
        if self._s.now is None:
            raise RuntimeError("submit before the first bar: the simulator has no clock yet")
        order_id = f"o{self._s.next_id}"
        self._s.next_id += 1
        self._s.working[order_id] = _Working(order_id, order, self._s.now)
        return order_id

    def cancel(self, order_id: str) -> None:
        self._s.working.pop(order_id, None)

    def position(self, symbol: str) -> int:
        return sum(lot.side.value * lot.qty for lot in self._s.lots if lot.symbol == symbol)

    def on_bar(self, bar: Bar) -> list[Fill]:
        snapshot = copy.deepcopy(self._s)
        fills, uncertain = self._step(bar)
        if uncertain and self._second_bars is not None:
            seconds = self._second_bars(bar.symbol, bar.ts_open)
            if seconds:
                self._s = snapshot
                fills = self._replay(seconds)
        self._s.now = bar.ts_close if self._s.now is None else max(self._s.now, bar.ts_close)
        return fills

    # --- one bar ----------------------------------------------------------------

    def _replay(self, seconds: list[Bar]) -> list[Fill]:
        fills: list[Fill] = []
        for sb in seconds:
            step_fills, _ = self._step(sb)
            fills.extend(step_fills)
        return [
            replace(f, ambiguous=True, resolved_by="1s")
            if f.reason in ("stop", "target") and f.resolved_by != "pessimistic"
            else f
            for f in fills
        ]

    def _step(self, bar: Bar) -> tuple[list[Fill], bool]:
        """Process one bar. Returns the fills and whether intra-bar order mattered."""
        fills: list[Fill] = []
        uncertain = False
        eligible = [
            w
            for w in list(self._s.working.values())
            if w.order.symbol == bar.symbol and bar.ts_open >= w.submitted_at
        ]
        # 1. Market orders trade at the open, before anything else in the bar.
        for w in eligible:
            if w.order.type is OrderType.MARKET:
                fills.extend(self._execute(w, bar.open, bar))
        # 2. Brackets of positions open at this point.
        for lot in [lot for lot in self._s.lots if lot.symbol == bar.symbol]:
            fill, unsure = self._check_bracket(lot, bar, entry_bar=False)
            uncertain |= unsure
            if fill:
                fills.append(fill)
        # 3. Stop and limit entries, then their brackets on the entry bar.
        for w in eligible:
            if w.order.type is OrderType.MARKET:
                continue
            price = self._entry_price(w.order, bar)
            if price is None:
                continue
            fills.extend(self._execute(w, price, bar))
            for lot in [lot for lot in self._s.lots if lot.id == w.id]:
                fill, unsure = self._check_bracket(lot, bar, entry_bar=True)
                uncertain |= unsure
                if fill:
                    fills.append(fill)
        return fills, uncertain

    # --- entries -------------------------------------------------------------------

    def _entry_price(self, order: Order, bar: Bar) -> float | None:
        """Raw (pre-slippage) fill price of a stop or limit order in `bar`, or None."""
        assert order.price is not None
        m = _Mirror(order.side.value)
        o, h, low = m.bar(bar)
        px = m.px(order.price)
        if order.type is OrderType.STOP:
            return m.px(max(o, px)) if h >= px else None
        return m.px(min(o, px)) if low <= px - self._through(order.symbol) else None

    def _execute(self, w: _Working, raw_price: float, bar: Bar) -> list[Fill]:
        """Fill working order `w`: close opposite lots first, open a lot with the rest."""
        del self._s.working[w.id]
        order = w.order
        slip = 0.0 if order.type is OrderType.LIMIT else self._slip(order.symbol)
        price = raw_price + order.side.value * slip
        fills: list[Fill] = []
        remaining = order.qty
        for lot in [lt for lt in self._s.lots if lt.symbol == order.symbol]:
            if remaining == 0 or lot.side == order.side:
                continue
            qty = min(remaining, lot.qty)
            fills.append(self._close(lot, qty, price, bar, "exit", w.id, slip))
            remaining -= qty
        if remaining:
            self._s.lots.append(
                _Lot(w.id, order.symbol, order.side, remaining, price, order.bracket)
            )
            fills.append(
                Fill(
                    order_id=w.id,
                    symbol=order.symbol,
                    side=order.side,
                    qty=remaining,
                    price=price,
                    ts=bar.ts_close,
                    reason="entry",
                    commission=self._cfg.commission_per_contract * remaining,
                    slippage=slip,
                )
            )
        return fills

    # --- exits ----------------------------------------------------------------------

    def _check_bracket(self, lot: _Lot, bar: Bar, *, entry_bar: bool) -> tuple[Fill | None, bool]:
        """Exit `lot` on its stop or target in `bar` if hit. Returns (fill, uncertain)."""
        if lot.bracket is None:
            return None, False
        m = _Mirror(lot.side.value)
        o, h, low = m.bar(bar)
        stop, target = m.px(lot.bracket.stop), m.px(lot.bracket.target)
        through = self._through(lot.symbol)
        stop_hit = low <= stop
        target_hit = h >= target + through

        def close(raw: float, reason: FillReason, **flags: object) -> Fill:
            slip = self._slip(lot.symbol) if reason == "stop" else 0.0
            price = m.px(raw) - lot.side.value * slip
            fill = self._close(lot, lot.qty, price, bar, reason, f"{lot.id}-{reason}", slip)
            return replace(fill, **flags)  # type: ignore[arg-type]

        if entry_bar:
            # Entry happened somewhere inside this bar: a touched stop counts,
            # a touched target can't be credited without finer data.
            if stop_hit and target_hit:
                return close(stop, "stop", ambiguous=True, resolved_by="pessimistic"), True
            if stop_hit:
                return close(stop, "stop"), False
            return None, target_hit
        if o <= stop:
            return close(o, "stop", resolved_by="gap"), False
        if o >= target + through:
            return close(o, "target", resolved_by="gap"), False
        if stop_hit and target_hit:
            return close(stop, "stop", ambiguous=True, resolved_by="pessimistic"), True
        if stop_hit:
            return close(stop, "stop"), False
        if target_hit:
            return close(target, "target"), False
        return None, False

    def _close(
        self,
        lot: _Lot,
        qty: int,
        price: float,
        bar: Bar,
        reason: FillReason,
        order_id: str,
        slip: float,
    ) -> Fill:
        lot.qty -= qty
        if lot.qty == 0:
            self._s.lots.remove(lot)
        point_value = self._instrument(lot.symbol).point_value
        return Fill(
            order_id=order_id,
            symbol=lot.symbol,
            side=Side(-lot.side.value),
            qty=qty,
            price=price,
            ts=bar.ts_close,
            reason=reason,
            commission=self._cfg.commission_per_contract * qty,
            slippage=slip,
            pnl=(price - lot.entry_price) * lot.side.value * qty * point_value,
        )

    # --- costs ------------------------------------------------------------------------

    def _slip(self, symbol: str) -> float:
        return self._cfg.slippage_ticks * self._instrument(symbol).tick_size

    def _through(self, symbol: str) -> float:
        """How far past a limit price a bar must trade to fill it."""
        return 0.0 if self._cfg.limit_fill == "touch" else self._instrument(symbol).tick_size
