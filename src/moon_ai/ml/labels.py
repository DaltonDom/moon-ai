"""Triple-barrier labels from the engine's own simulated trade (design.md, "ML filter").

Each candidate is traded on its own, ignoring portfolio state, with the same
SimBroker fills, costs and same-bar rule as the backtest:

- label 1 if its target fills first, 0 if its stop fills first or the time-out
  closes it; net R is stored next to it
- no label (None) if a limit entry never fills before its entry deadline
- a candidate decided inside a news blackout places its order only when the
  blackout ends, as the trader would
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from moon_ai.bars import Bar
from moon_ai.broker import Bracket, Order, OrderType, Side, SimBroker
from moon_ai.config import Config
from moon_ai.data.news import Blackout
from moon_ai.setups.base import Candidate


@dataclass(frozen=True)
class Label:
    label: int
    net_r: float
    exit_time: datetime
    exit_reason: str  # target | stop | timeout


def label_candidate(
    cand: Candidate, bars: Sequence[Bar], config: Config, blackout: Blackout | None = None
) -> Label | None:
    """`bars`: the candidate's symbol, oldest first, covering decision to time-out."""
    place_at = cand.decision_time
    if blackout is not None:
        w = blackout.window_at(place_at)
        if w is not None:
            place_at = w.end
    deadline = cand.entry_deadline or cand.timeout
    if place_at >= deadline:
        return None
    spec = config.instrument(cand.symbol)
    broker = SimBroker(config.broker, config.instrument)
    side = Side.BUY if cand.side == "long" else Side.SELL

    order = Order(
        cand.symbol,
        side,
        1,
        OrderType(cand.entry_type),
        cand.entry,
        Bracket(cand.stop, cand.target),
    )
    order_id = None
    entry_px = None
    costs = 0.0
    exiting = False
    for b in bars:
        if b.ts_close < cand.decision_time:
            continue  # the decision bar itself starts the broker's clock, as in the engine
        fills = broker.on_bar(b)
        for f in fills:
            costs += f.commission
            if f.reason == "entry" and entry_px is None:
                entry_px = f.price
            elif entry_px is not None and f.reason in ("stop", "target", "exit"):
                risk = abs(entry_px - cand.stop) * spec.point_value
                net = f.pnl - costs
                reason = "timeout" if f.reason == "exit" else f.reason
                return Label(
                    1 if f.reason == "target" else 0, net / risk if risk else 0.0, f.ts, reason
                )
        now = b.ts_close
        if order_id is None and now >= place_at:
            order_id = broker.submit(order)
        if entry_px is None and order_id is not None and now >= deadline:
            return None  # never filled
        if entry_px is not None and not exiting and now >= cand.timeout:
            broker.submit(Order(cand.symbol, Side(-side.value), 1))
            exiting = True
    return None
