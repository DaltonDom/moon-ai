"""The ICT 2022 model (ict-setup-definitions.md §2.5; config/defaults.toml).

ICT's own checklist (X, 2022-07-23): "Determine most likely expansion on the
weekly candle. Find Med or High impact econ event in ICT Killzones. Wait for
opposing Liquidity to be taken out. Look for displacement & FVG. Target
Opposing PD Array."

Coded on the Silver Bullet machinery, in the killzone window (08:30-11:00 by
default):

- **Weekly expansion** (research §1.4 proxy 2): this week's first raid of last
  week's range sets it. Taking last week's low first means expansion up, so
  only longs; the high first means shorts. With no raid yet there's no bias,
  and with the bias gate on (the default) no trade.
- **News day** (`news_day_filter`): a release from the news calendar inside the
  window that day. Blocking and recorded types both count; unscheduled ones don't.
- **Opposing liquidity:** a sweep of the prior session's, Asian, London or
  session-swing pools on the side opposite the expansion, then displacement,
  MSS and the FVG entry; the target is the opposing pool.
- **Discount FVG** (rescue trial `require_discount_fvg`): the entry FVG must
  sit in the discount half of the displacement range (premium half for shorts).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
from typing import Literal

from moon_ai.bars import Bar
from moon_ai.data.news import NEWS_CSV, NewsEvent, load_events
from moon_ai.engine import Context
from moon_ai.ict.fvg import FairValueGap
from moon_ai.ict.liquidity import Level, Sweep
from moon_ai.ict.structure import MarketStructureShift
from moon_ai.sessions import trading_day, window_bounds
from moon_ai.setups.base import SetupParams, register
from moon_ai.setups.london import session_ohlc
from moon_ai.setups.silver_bullet import SilverBullet

Bias = Literal["bull", "bear"] | None
WEEK_BARS = 12 * 1440  # last week's sessions plus this week's so far


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def weekly_expansion(bars: Sequence[Bar], day: date) -> Bias:
    """Which side of last week's range this week (up to the bars given) took first."""
    this_week = week_start(day)
    last_week = this_week - timedelta(days=7)
    prev = [b for b in bars if week_start(trading_day(b.ts_close)) == last_week]
    if not prev:
        return None
    hi, lo = max(b.high for b in prev), min(b.low for b in prev)
    for b in bars:
        if week_start(trading_day(b.ts_close)) != this_week:
            continue
        took_low, took_high = b.low < lo, b.high > hi
        if took_low and took_high:
            return None  # both in one bar: no clear first raid
        if took_low:
            return "bull"
        if took_high:
            return "bear"
    return None


@register("ict_2022_model")
class Ict2022Model(SilverBullet):
    supports_bias = True
    extra_pools = frozenset({"prior_day", "london"})

    def __init__(
        self,
        params: SetupParams,
        config,
        symbol: str = "MNQ.v.0",
        news: Sequence[NewsEvent] | None = None,
    ):
        super().__init__(params, config, symbol)
        self._news = (
            list(news)
            if news is not None
            else (load_events(NEWS_CSV) if params.news_day_filter and NEWS_CSV.exists() else [])
        )

    def _on_new_day(self, ctx: Context, day: date) -> None:
        history = ctx.history(self.symbol, WEEK_BARS)
        self._week_bars = [b for b in history if trading_day(b.ts_close) < day]
        self._bias_before_today: Bias = weekly_expansion(self._week_bars, day)
        last_week = week_start(day) - timedelta(days=7)
        prev = [b for b in self._week_bars if week_start(trading_day(b.ts_close)) == last_week]
        self._last_week_range = (
            (max(b.high for b in prev), min(b.low for b in prev)) if prev else None
        )
        self._checked_upto = 0  # how many of today's bars the raid check has seen
        sessions = session_ohlc(self._week_bars)
        prior = [d for d in sorted(sessions) if d < day]
        self._prior_hl = sessions[prior[-1]][1:3] if prior else None
        start, end = window_bounds(day, self.window)
        self._news_day = any(e.scheduled and start <= e.at < end for e in self._news)

    def _prepare(self, bars: Sequence[Bar], day: date) -> None:
        # This week's first raid of last week's range, checking only today's new bars.
        if self._bias_before_today is None and self._last_week_range is not None:
            hi, lo = self._last_week_range
            for b in bars[self._checked_upto :]:
                took_low, took_high = b.low < lo, b.high > hi
                if took_low or took_high:
                    if took_low != took_high:
                        self._bias_before_today = "bull" if took_low else "bear"
                    else:
                        self._last_week_range = None  # both in one bar: no clear first raid
                    break
        self._checked_upto = len(bars)
        self._bias: Bias = self._bias_before_today
        self._prior: list[Level] = []
        if "prior_day" in self.params.pools and self._prior_hl is not None:
            h, lo = self._prior_hl
            start, inst = bars[0].ts_open, bars[-1].instrument_id
            self._prior = [
                Level("high", h, start, "prior_day", inst),
                Level("low", lo, start, "prior_day", inst),
            ]

    def _accept(self, mss: MarketStructureShift, bars: Sequence[Bar]) -> bool:
        if self.params.news_day_filter and not self._news_day:
            return False
        if self.params.bias_gate:
            return self._bias is not None and self._bias == mss.direction
        return True

    def _extra_levels(self) -> list[Level]:
        return list(self._prior)

    def _accept_gap(self, gap: FairValueGap, sweep: Sweep, bars: Sequence[Bar]) -> bool:
        if not self.params.require_discount_fvg:
            return True
        leg = bars[sweep.index : gap.index + 2]
        hi, lo = max(b.high for b in leg), min(b.low for b in leg)
        mid = (hi + lo) / 2
        return gap.high <= mid if gap.direction == "bull" else gap.low >= mid
