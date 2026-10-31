"""The event loop: BarFeed -> Broker -> Strategy, with everything journaled.

For each closed bar, in close-time order:

1. the broker processes the bar against working orders (orders submitted on
   earlier bars), and every fill is journaled;
2. the bar joins the history;
3. the strategy sees the bar, with `ctx.now == bar.ts_close`, and may submit
   orders, which can first fill on a later bar.

The strategy only ever sees bars that have closed, so it can't act on a bar's
high or low before they are known.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from moon_ai.bars import Bar, BarFeed
from moon_ai.broker import Broker
from moon_ai.journal import Journal, JournalEntry


class Context:
    """What a strategy can see and do at `now`."""

    def __init__(self, broker: Broker, journal: Journal):
        self.broker = broker
        self.journal = journal
        self.now: datetime | None = None
        self._history: dict[str, list[Bar]] = {}

    def history(self, symbol: str, n: int | None = None) -> Sequence[Bar]:
        """Closed bars for `symbol`, oldest first; the last `n` if given."""
        bars = self._history.get(symbol, [])
        return tuple(bars if n is None else bars[-n:])

    def _append(self, bar: Bar) -> None:
        self._history.setdefault(bar.symbol, []).append(bar)
        self.now = bar.ts_close


class Strategy(Protocol):
    def on_bar(self, bar: Bar, ctx: Context) -> None: ...


def run(feed: BarFeed, broker: Broker, strategy: Strategy, journal: Journal) -> Context:
    ctx = Context(broker, journal)
    for bar in feed:
        if ctx.now is not None and bar.ts_close < ctx.now:
            raise ValueError(
                f"feed out of order: bar closing {bar.ts_close.isoformat()} "
                f"after {ctx.now.isoformat()}"
            )
        for fill in broker.on_bar(bar):
            journal.record(JournalEntry(fill.ts, "fill", {"fill": fill}))
        if bar.roll:
            journal.record(
                JournalEntry(
                    bar.ts_close, "roll", {"symbol": bar.symbol, "instrument_id": bar.instrument_id}
                )
            )
        ctx._append(bar)
        strategy.on_bar(bar, ctx)
    return ctx
