"""Non-ICT intraday setups, batch 1 (#102; design.md, "Revision 2026-11-02").

Five published, mechanical day-trading ideas for MNQ. Each fires at most once
per day, enters at market and is flat by its time-out, so all of them trade
often enough for prop-firm payout rules. Their defaults and trials are
pre-registered in config/defaults.toml before any backtest.

- `orb_5m`: opening-range breakout. The first 5 minutes of the cash session
  set the direction (up candle: long, down candle: short, doji: no trade);
  enter at 09:35, stop beyond the range, hold to the close. Zarattini & Aziz
  (2023), "Can Day Trading Really Be Profitable?".
- `noise_breakout`: trade only when price leaves its usual intraday "noise
  area" (the average absolute move from the open at that time of day over the
  last 14 days), checked every 30 minutes. Stop back at the area's anchor,
  hold to the close. Zarattini, Aziz & Barbon (2024), "Beat the Market".
- `intraday_momentum`: the first half hour's return (previous close to 10:00)
  predicts the last half hour's. Enter at 15:30 in that direction. Gao, Han,
  Li & Zhou (2018), "Market Intraday Momentum".
- `overnight_breakout`: the first 5-minute close beyond the overnight high or
  low before 11:00 continues (stop runs tend to extend, Osler 2005).
- `gap_fill`: mean reversion. A moderate opening gap against the previous
  close is faded toward that close.

Daily figures (ATR, previous close, overnight range) come from finished days
only, and the noise area from finished days at the same minute, so nothing
here is known later than the decision bar's close.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from moon_ai.bars import Bar
from moon_ai.config import Config
from moon_ai.engine import Context
from moon_ai.sessions import NY, to_ny, trading_day
from moon_ai.setups.base import Candidate, SetupParams, register

FEATURE_SET = "intraday-v0"
RTH_OPEN = time(9, 30)
RTH_CLOSE = time(16, 0)
FAR_TARGET_R = 10.0  # "hold to the close": a target the day almost never reaches


@dataclass
class _Day:
    date: date
    instrument_id: int
    open: float | None = None
    high: float = float("-inf")
    low: float = float("inf")
    close: float | None = None
    on_high: float = float("-inf")  # overnight: 18:00 the evening before to 09:30
    on_low: float = float("inf")
    moves: dict[int, float] = field(default_factory=dict)  # minute after 09:30 -> |close/open - 1|
    pv: float = 0.0  # cash-session sum of typical price x volume, for VWAP
    volume: float = 0.0

    @property
    def vwap(self) -> float | None:
        return self.pv / self.volume if self.volume else None


@dataclass(frozen=True)
class DayStats:
    """What is known about the past at today's decision time."""

    atr: float  # average true range of the cash session, over finished days
    prev_close: float
    open: float  # today's 09:30 open
    on_high: float
    on_low: float


class DayBook:
    """Daily statistics built bar by bar from 1-minute bars of one symbol."""

    def __init__(self, atr_days: int = 14, noise_days: int = 14, regime_days: int = 100):
        self.atr_days = atr_days
        self.noise_days = noise_days
        self.today: _Day | None = None
        self.done: deque[_Day] = deque(maxlen=max(atr_days, noise_days) + 1)
        self.atr_hist: deque[float] = deque(maxlen=regime_days)  # ATR at each finished day
        self._last: datetime | None = None

    def update(self, bar: Bar) -> None:
        if self._last is not None and bar.ts_close <= self._last:
            return
        self._last = bar.ts_close
        day = trading_day(bar.ts_close)
        if self.today is None or self.today.date != day:
            if self.today is not None and self.today.close is not None:
                self.done.append(self.today)
                atr = self._atr()
                if atr is not None:
                    self.atr_hist.append(atr)
            self.today = _Day(day, bar.instrument_id)
        d = self.today
        ny = to_ny(bar.ts_open)
        t = ny.time()
        if ny.date() < day or t < RTH_OPEN:
            d.on_high, d.on_low = max(d.on_high, bar.high), min(d.on_low, bar.low)
        elif t >= RTH_OPEN and t < RTH_CLOSE:
            if d.open is None:
                if t != RTH_OPEN:
                    return  # no 09:30 bar: no clean open today
                d.open = bar.open
            d.high, d.low, d.close = max(d.high, bar.high), min(d.low, bar.low), bar.close
            d.pv += (bar.high + bar.low + bar.close) / 3 * bar.volume
            d.volume += bar.volume
            minute = (to_ny(bar.ts_close) - datetime.combine(d.date, RTH_OPEN, tzinfo=NY)).seconds
            d.moves[minute // 60] = abs(bar.close / d.open - 1)

    def _atr(self) -> float | None:
        if len(self.done) < self.atr_days + 1:
            return None
        days = list(self.done)
        ranges = []
        for prev, cur in zip(days[-self.atr_days - 1 : -1], days[-self.atr_days :], strict=True):
            if prev.instrument_id == cur.instrument_id and prev.close is not None:
                ranges.append(max(cur.high, prev.close) - min(cur.low, prev.close))
            else:  # contract roll: prices aren't comparable across it
                ranges.append(cur.high - cur.low)
        return sum(ranges) / len(ranges)

    def regime(self) -> str | None:
        """ "high" or "low": the latest ATR against the median of the last
        `regime_days` days' ATRs (finished days only). None until that many."""
        if len(self.atr_hist) < (self.atr_hist.maxlen or 0):
            return None
        ranked = sorted(self.atr_hist)
        median = ranked[len(ranked) // 2]
        return "high" if self.atr_hist[-1] > median else "low"

    def stats(self) -> DayStats | None:
        d = self.today
        atr = self._atr()
        if d is None or d.open is None or atr is None:
            return None
        prev = self.done[-1]
        if prev.instrument_id != d.instrument_id or prev.close is None:
            return None
        return DayStats(atr, prev.close, d.open, d.on_high, d.on_low)

    def noise(self, minute: int) -> float | None:
        """Average |close/open - 1| at this minute over the last `noise_days` days."""
        vals = [d.moves[minute] for d in list(self.done)[-self.noise_days :] if minute in d.moves]
        return sum(vals) / len(vals) if len(vals) >= self.noise_days else None


class _Intraday:
    """Shared plumbing: one DayBook, at most one candidate per day."""

    name = ""

    def __init__(self, params: SetupParams, config: Config, symbol: str = "MNQ.v.0"):
        self.params = params
        self.config = config
        self.symbol = symbol
        self.tick = config.instrument(symbol).tick_size
        self.book = DayBook(params.atr_days, params.noise_days, params.regime_days)
        self._done: set[date] = set()

    def scan(self, ctx: Context) -> list[Candidate]:
        last = ctx.history(self.symbol, 1)
        if not last or ctx.now is None or last[-1].ts_close != ctx.now:
            return []
        bar = last[-1]
        self.book.update(bar)
        day = trading_day(ctx.now)
        if day in self._done:
            return []
        stats = self.stats()
        if stats is None:
            return []
        if self.params.vol_regime != "any" and self.book.regime() != self.params.vol_regime:
            return []
        cand = self.decide(bar, ctx.now, to_ny(ctx.now), stats)
        if cand is None:
            return []
        if self.once_a_day:
            self._done.add(day)
        return [cand]

    once_a_day = True

    def stats(self) -> DayStats | None:
        return self.book.stats()

    def decide(self, bar: Bar, now: datetime, ny: datetime, s: DayStats) -> Candidate | None:
        raise NotImplementedError

    def _round(self, price: float) -> float:
        return round(price / self.tick) * self.tick

    def _candidate(
        self,
        now: datetime,
        long: bool,
        price: float,
        stop: float,
        s: DayStats,
        rule_results: dict,
        target: float | None = None,
    ) -> Candidate | None:
        """A market entry at about `price`. The stop is rounded away from the entry."""
        p = self.params
        sign = 1 if long else -1
        stop = self._round(stop - sign * p.stop_offset_ticks * self.tick)
        risk = sign * (price - stop)
        if risk < max(p.min_stop_ticks, 1) * self.tick:
            return None
        if target is None:
            target = price + sign * (p.target_r or FAR_TARGET_R) * risk
        target = self._round(target)
        if sign * (target - price) <= 0:
            return None
        return Candidate(
            setup=self.name,
            symbol=self.symbol,
            side="long" if long else "short",
            decision_time=now,
            entry_type="market",
            entry=None,
            stop=stop,
            target=target,
            # On the trading day (18:00-17:00), so an evening entry exits next morning.
            timeout=datetime.combine(trading_day(now), p.timeout, tzinfo=NY),
            rule_results=rule_results,
            features={
                "risk_atr": risk / s.atr,
                "gap_atr": (s.open - s.prev_close) / s.atr,
                "risk_ticks": round(risk / self.tick),
            },
            feature_set=FEATURE_SET,
        )

    def _atr_stop(self, long: bool, price: float, s: DayStats) -> float:
        sign = 1 if long else -1
        return price - sign * (self.params.stop_atr or 0.1) * s.atr


def _at(ny: datetime, t: time) -> bool:
    """True when the bar closing at `ny` (New York) closes at wall time `t`."""
    return ny.time() == t


def _minute(ny: datetime) -> int:
    return (ny.hour * 60 + ny.minute) - (RTH_OPEN.hour * 60 + RTH_OPEN.minute)


@register("orb_5m")
class OpeningRangeBreakout(_Intraday):
    def decide(self, bar, now, ny, s):
        p = self.params
        end = (datetime.combine(ny.date(), RTH_OPEN) + timedelta(minutes=p.or_minutes)).time()
        if not _at(ny, end):
            return None
        d = self.book.today
        assert d is not None and d.open is not None
        o, c = d.open, bar.close
        if c == o:
            return None  # doji: no direction
        long = c > o
        stop = self._atr_stop(long, c, s) if p.stop_atr is not None else (d.low if long else d.high)
        return self._candidate(now, long, c, stop, s, {"or_open": o, "or_close": c})


@register("noise_breakout")
class NoiseBreakout(_Intraday):
    """Round 2 adds the paper's own exit and re-entry (`exit_rule`, `noise_variant`)."""

    @property
    def once_a_day(self) -> bool:  # type: ignore[override]
        return self.params.noise_variant != "paper"

    def _bands(self, ny: datetime) -> tuple[float, float, DayStats] | None:
        p = self.params
        m = _minute(ny)
        if m < p.checkpoint_minutes or m % p.checkpoint_minutes or ny.time() > time(15, 30):
            return None
        sigma = self.book.noise(m)
        s = self.book.stats()
        if sigma is None or s is None:
            return None
        upper = max(s.open, s.prev_close) * (1 + p.noise_mult * sigma)
        lower = min(s.open, s.prev_close) * (1 - p.noise_mult * sigma)
        return upper, lower, s

    def manage(self, cand: Candidate, ctx: Context) -> bool:
        """At a checkpoint, exit if the close is back inside the stricter of the
        noise boundary and VWAP (long: below max(upper, VWAP))."""
        p = self.params
        if p.exit_rule != "boundary_vwap" and p.noise_variant != "paper":
            return False
        if ctx.now is None or trading_day(ctx.now) != trading_day(cand.decision_time):
            return False
        bands = self._bands(to_ny(ctx.now))
        d = self.book.today
        if bands is None or d is None or d.vwap is None:
            return False
        upper, lower, _ = bands
        c = ctx.history(self.symbol, 1)[-1].close
        if cand.side == "long":
            return c < max(upper, d.vwap)
        return c > min(lower, d.vwap)

    def decide(self, bar, now, ny, s):
        p = self.params
        bands = self._bands(ny)
        if bands is None:
            return None
        upper, lower, s = bands
        c = bar.close
        if lower <= c <= upper:
            return None
        long = c > upper
        anchor = max(s.open, s.prev_close) if long else min(s.open, s.prev_close)
        stop = self._atr_stop(long, c, s) if p.stop_atr is not None else anchor
        return self._candidate(now, long, c, stop, s, {"upper": upper, "lower": lower})


@register("intraday_momentum")
class IntradayMomentum(_Intraday):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._first: dict[date, float] = {}

    def decide(self, bar, now, ny, s):
        if _at(ny, time(10, 0)):
            self._first = {ny.date(): bar.close / s.prev_close - 1}
            return None
        if not _at(ny, self.params.entry_time or time(15, 30)):
            return None
        r = self._first.get(ny.date())
        if not r or abs(r) < (self.params.min_move_atr or 0.0) * s.atr / s.prev_close:
            return None
        long = r > 0
        c = bar.close
        return self._candidate(now, long, c, self._atr_stop(long, c, s), s, {"first_half_hour": r})


@register("overnight_breakout")
class OvernightBreakout(_Intraday):
    def decide(self, bar, now, ny, s):
        m = _minute(ny)
        if m < 5 or m % 5 or ny.time() > time(11, 0):
            return None
        if s.on_high == float("-inf") or s.on_low == float("inf"):
            return None
        c = bar.close
        if s.on_low <= c <= s.on_high:
            return None
        long = c > s.on_high
        return self._candidate(
            now, long, c, self._atr_stop(long, c, s), s, {"on_high": s.on_high, "on_low": s.on_low}
        )


@register("gap_fill")
class GapFill(_Intraday):
    def decide(self, bar, now, ny, s):
        p = self.params
        if not _at(ny, time(9, 31)):
            return None
        gap = s.open - s.prev_close
        size = abs(gap) / s.atr
        if not (p.gap_min_atr or 0.0) <= size <= (p.gap_max_atr or 1e9):
            return None
        long = gap < 0  # fade the gap toward the previous close
        c = bar.close
        if (c >= s.prev_close) if long else (c <= s.prev_close):
            return None  # already filled in the first minute
        sign = 1 if long else -1
        stop = c - sign * p.gap_stop_mult * abs(gap)
        return self._candidate(
            now, long, c, stop, s, {"gap": gap, "gap_atr": size}, target=s.prev_close
        )


# --- Batch 2 (2026-11-02, #102 follow-up) -------------------------------------------------


@register("orb_high_vol")
class OrbHighVol(OpeningRangeBreakout):
    """The opening-range breakout, only when volatility is high (`vol_regime`)."""


@register("vwap_pullback")
class VwapPullback(_Intraday):
    """Trend-day continuation: once the day has moved `trend_min_atr` from the
    open and VWAP sits on the trend side of the open, enter on the first bar
    (10:30-14:00) that touches VWAP and closes back on the trend side."""

    def decide(self, bar, now, ny, s):
        p = self.params
        if not time(10, 30) <= ny.time() <= time(14, 0):
            return None
        d = self.book.today
        if d is None or d.vwap is None or d.open is None:
            return None
        vwap, need = d.vwap, p.trend_min_atr * s.atr
        up = d.high - d.open >= need and vwap > d.open
        down = d.open - d.low >= need and vwap < d.open
        if up and bar.low <= vwap < bar.close:
            long = True
        elif down and bar.high >= vwap > bar.close:
            long = False
        else:
            return None
        c = bar.close
        sign = 1 if long else -1
        stop = vwap - sign * (p.stop_atr or 0.25) * s.atr
        return self._candidate(
            now, long, c, stop, s, {"vwap": vwap, "trend": "up" if up else "down"}
        )


@register("vwap_reversion")
class VwapReversion(_Intraday):
    """Quiet-market mean reversion: 10:30-15:00, a close at least `vwap_dev_atr`
    ATRs from VWAP is faded toward VWAP; stop the same distance beyond."""

    def decide(self, bar, now, ny, s):
        p = self.params
        if not time(10, 30) <= ny.time() <= time(15, 0):
            return None
        d = self.book.today
        if d is None or d.vwap is None:
            return None
        dev = bar.close - d.vwap
        if abs(dev) < p.vwap_dev_atr * s.atr:
            return None
        long = dev < 0
        sign = 1 if long else -1
        stop = bar.close - sign * p.dev_stop_mult * abs(dev)
        return self._candidate(
            now, long, bar.close, stop, s, {"vwap": d.vwap, "dev_atr": dev / s.atr}, target=d.vwap
        )


def _weekdays_between(a: date, b: date) -> int:
    """Weekdays in (a, b]."""
    n, d = 0, a
    while d < b:
        d += timedelta(days=1)
        n += d.weekday() < 5
    return n


@register("turn_of_month")
class TurnOfMonth(_Intraday):
    """Long the cash session on the last `tom_days_before` weekdays of a month
    and the first `tom_days_after` of the next (holidays not excluded; the
    calendar is known in advance). Entry at 09:31, held to the time-out."""

    def decide(self, bar, now, ny, s):
        p = self.params
        if not _at(ny, time(9, 31)):
            return None
        today = ny.date()
        first_next = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
        left = _weekdays_between(today, first_next - timedelta(days=1))  # after today
        into = _weekdays_between(today.replace(day=1) - timedelta(days=1), today)
        if left >= p.tom_days_before and into > p.tom_days_after:
            return None
        c = bar.close
        return self._candidate(
            now, True, c, self._atr_stop(True, c, s), s, {"left": left, "into": into}
        )


# --- Batch 3 (2026-11-02): overnight drift ----------------------------------------------


class _Overnight(_Intraday):
    """Long at `entry_time` and out at the time-out, both inside one CME trading
    day (18:00 to 17:00 New York), so the prop firms' flat-by-16:45 rule holds.

    Lou, Polk & Skouras (2019) and Kelly & Clark (2011): index returns accrue
    overnight. Boyarchenko, Larsen & Whelan (2023, NY Fed Staff Report 917): in
    S&P futures the overnight drift concentrates around the European open and
    is larger after the US session sold off.
    """

    def stats(self) -> DayStats | None:
        """Before the cash open there is no 'today' open: use the last finished day."""
        atr = self.book._atr()
        if atr is None or not self.book.done:
            return None
        prev = self.book.done[-1]
        today = self.book.today
        if prev.close is None or today is None or prev.instrument_id != today.instrument_id:
            return None
        return DayStats(atr, prev.close, prev.close, today.on_high, today.on_low)

    def decide(self, bar, now, ny, s):
        p = self.params
        if p.entry_time is None or not _at(ny, p.entry_time):
            return None
        prev = self.book.done[-1]
        if p.after_down and not (prev.open is not None and prev.close < prev.open):
            return None
        c = bar.close
        return self._candidate(
            now, True, c, self._atr_stop(True, c, s), s, {"prev_rth": prev.close / prev.open - 1}
        )


@register("overnight_hold")
class OvernightHold(_Overnight):
    """From the 18:00 reopen to just before the 09:30 cash open."""


@register("overnight_after_down")
class OvernightAfterDown(_Overnight):
    """The same hold, only after a cash session that closed below its open."""


@register("euro_open_drift")
class EuroOpenDrift(_Overnight):
    """Long around the European open (02:00 to 03:30 New York)."""
