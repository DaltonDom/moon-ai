"""Silver Bullet setups (NY AM; NY PM reuses the same model with other pools).

Rule card: ict-setup-definitions.md §2.1 (branch research/ict-setup-definitions),
with the #21 changes; parameters from config/defaults.toml.

At the close of each bar inside the setup window, on the current CME trading
day's bars only:

1. **Pools:** the setup's liquidity pools (e.g. the overnight and opening-range
   highs/lows), plus swing levels confirmed since `sweep_from`.
2. **Sweep:** a pool traded through and closed back on (`find_sweeps`), with the
   sweep bar opening at or after `sweep_from`.
3. **MSS:** structure broken on close within `mss_max_bars` of the sweep, in
   the opposite direction to the swept side.
4. **Displacement + FVG:** the first fair value gap in the MSS direction formed
   after the sweep, with a displacement candle (body >= k x ATR) between the
   sweep and that gap.
5. **Plan:**
   - entry: a limit at the FVG's near edge (or CE)
   - stop: beyond the sweep extreme plus `stop_offset_ticks`
   - target: the nearest unswept opposing pool, the draw on liquidity
   - the trade is skipped if the room from entry to target is under `min_objective_points`
6. A candidate is emitted on the bar where all of it is first known, at most
   once per setup per trading day. Its entry must fill before the window ends.

Not yet implemented (they raise if a rescue trial asks for them): the bias
gate and first-tethered FVG selection. The research card's pre-fill cancels
(price reaching the target first, or a close through the FVG's far side) are
also not enforced yet; only the entry deadline is.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, time

from moon_ai.bars import Bar
from moon_ai.config import Config, Window
from moon_ai.engine import Context
from moon_ai.ict.displacement import find_displacements
from moon_ai.ict.fvg import FairValueGap, find_fvgs
from moon_ai.ict.liquidity import Level, Sweep, find_sweeps, swing_levels, window_levels
from moon_ai.ict.structure import MarketStructureShift, find_market_structure_shifts
from moon_ai.ict.swings import find_swings
from moon_ai.sessions import NY, in_window, to_ny, trading_day, window_bounds
from moon_ai.setups.base import Candidate, SetupParams, register

FEATURE_SET = "sb-v0"
# Named pools: New York windows whose completed high and low are liquidity.
POOL_WINDOWS: dict[str, Window] = {
    "asia": Window(time(20), time(0)),
    "overnight": Window(time(18), time(9, 30)),
    "opening_range": Window(time(9, 30), time(10)),
    "am_session": Window(time(9, 30), time(12)),
    "lunch": Window(time(12), time(13, 30)),
}
HISTORY_BARS = 1600  # more than one CME session of 1-minute bars


class SilverBullet:
    name = "silver_bullet"
    supports_bias = False  # subclasses that implement `_accept` for the bias gate set this
    extra_pools: frozenset[str] = frozenset()

    def __init__(self, params: SetupParams, config: Config, symbol: str = "MNQ.v.0"):
        if params.bias_gate and not self.supports_bias:
            raise NotImplementedError(f"bias gate for {type(self).__name__}")
        if params.fvg_selection != "first":
            raise NotImplementedError(f"fvg_selection={params.fvg_selection!r}")
        unknown = set(params.pools) - set(POOL_WINDOWS) - {"session_swing"} - self.extra_pools
        if unknown:
            raise ValueError(f"unknown pools {sorted(unknown)}")
        self.params = params
        self.config = config
        self.symbol = symbol
        self.window = config.sessions.windows[params.window]
        self.tick = config.instrument(symbol).tick_size
        self._done_days: set[date] = set()

    # --- Setup protocol -----------------------------------------------------------

    def scan(self, ctx: Context) -> list[Candidate]:
        now = ctx.now
        if now is None or not in_window(now, self.window):
            return []
        day = trading_day(now)
        if day in self._done_days:
            return []
        history = ctx.history(self.symbol, self.history_bars)
        bars = [b for b in history if trading_day(b.ts_close) == day]
        if not bars or bars[-1].ts_close != now:
            return []
        self._prepare(history, bars, day)
        cand = self._find(bars, now, day)
        if cand is not None:
            self._done_days.add(day)
            return [cand]
        return []

    # --- hooks for variants (London) ------------------------------------------------

    history_bars = HISTORY_BARS

    def _prepare(self, history: Sequence[Bar], bars: Sequence[Bar], day: date) -> None:
        """Per-bar context from longer history (bias, reference opens); none by default."""

    def _accept(self, mss: MarketStructureShift, bars: Sequence[Bar]) -> bool:
        """Extra rules a structure shift must pass (bias gate, PO3); all pass by default."""
        return True

    def _extra_levels(self) -> list[Level]:
        return []

    # --- the model -----------------------------------------------------------------

    def _find(self, bars: Sequence[Bar], now: datetime, day: date) -> Candidate | None:
        p, ict = self.params, self.config.ict
        ny_date = to_ny(now).date()
        sweep_from = datetime.combine(ny_date, p.sweep_from or self.window.start, tzinfo=NY)
        swings = find_swings(bars, p.swing_n)
        pools = self._pools(bars, swings, sweep_from)
        sweeps = [
            s
            for s in find_sweeps(
                bars,
                pools,
                self.tick,
                p.sweep_close_back_bars,
                ict.sweep_require_close_back,
                ict.sweep_min_penetration_ticks,
            )
            if bars[s.index].ts_open >= sweep_from
        ]
        shifts = [
            m
            for m in find_market_structure_shifts(
                bars, swings, sweeps, p.mss_break, ict.mss_max_bars
            )
            if self._accept(m, bars)
        ]
        if not shifts:
            return None
        fvgs = find_fvgs(bars, self.tick, ict.fvg_min_size_ticks)
        disps = find_displacements(
            bars,
            self.tick,
            p.displacement_k,
            ict.displacement_atr_period,
            ict.displacement_require_fvg,
        )
        for mss in shifts:  # oldest first: the first complete setup of the day wins
            cand = self._plan(bars, mss, fvgs, disps, pools, now, ny_date)
            if cand is not None:
                return cand
        return None

    def _pools(self, bars: Sequence[Bar], swings, sweep_from: datetime) -> list[Level]:
        levels: list[Level] = []
        for name in self.params.pools:
            if name == "session_swing":
                levels += [lv for lv in swing_levels(swings) if lv.known_at >= sweep_from]
            elif name in POOL_WINDOWS:
                levels += window_levels(bars, POOL_WINDOWS[name], name)
        return levels + self._extra_levels()

    def _plan(
        self,
        bars: Sequence[Bar],
        mss: MarketStructureShift,
        fvgs: list[FairValueGap],
        disps,
        pools: list[Level],
        now: datetime,
        ny_date: date,
    ) -> Candidate | None:
        p = self.params
        sweep: Sweep = mss.sweep
        long = mss.direction == "bull"
        gap = next(
            (g for g in fvgs if g.direction == mss.direction and g.index > sweep.index),
            None,
        )
        if gap is None:
            return None
        known = max(mss.known_at, gap.known_at)
        if known != now:  # emit exactly on the bar it all became known
            return None
        if not any(
            d.direction == mss.direction and sweep.index <= d.index <= gap.index for d in disps
        ):
            return None
        near = gap.high if long else gap.low
        entry = _round(gap.ce, self.tick) if p.fvg_entry == "ce" else near
        off = p.stop_offset_ticks * self.tick
        stop = sweep.extreme - off if long else sweep.extreme + off
        if (entry <= stop) if long else (entry >= stop):
            return None  # the gap sits beyond the sweep extreme: no valid stop
        target = self._draw_on_liquidity(bars, pools, entry, long, now)
        if target is None:
            return None
        objective = abs(target - entry)
        if p.min_objective_points is not None and objective < p.min_objective_points:
            return None
        _, window_end = window_bounds(ny_date, self.window)
        timeout = datetime.combine(ny_date, p.timeout, tzinfo=NY)
        return Candidate(
            setup=self.name,
            symbol=self.symbol,
            side="long" if long else "short",
            decision_time=now,
            entry_type="limit",
            entry=entry,
            stop=stop,
            target=target,
            timeout=timeout,
            entry_deadline=window_end,
            rule_results={
                "swept_pool": sweep.level.source,
                "swept_price": sweep.level.price,
                "mss_broke": mss.broken_swing.price,
                "fvg": [gap.low, gap.high],
                "objective_points": objective,
            },
            features={
                "sweep_depth_ticks": round(abs(sweep.extreme - sweep.level.price) / self.tick),
                "risk_ticks": round(abs(entry - stop) / self.tick),
                "objective_points": objective,
                "minutes_into_window": (
                    to_ny(now) - datetime.combine(ny_date, self.window.start, tzinfo=NY)
                ).total_seconds()
                / 60,
            },
            feature_set=FEATURE_SET,
        )

    def _draw_on_liquidity(
        self, bars: Sequence[Bar], pools: list[Level], entry: float, long: bool, now: datetime
    ) -> float | None:
        """Nearest pool on the target side of entry that price hasn't traded through yet."""
        side = "high" if long else "low"
        best: float | None = None
        for lv in pools:
            if lv.kind != side or lv.known_at > now:
                continue
            if (lv.price <= entry) if long else (lv.price >= entry):
                continue
            later = [b for b in bars if b.ts_open >= lv.known_at]
            taken = (
                any(b.high > lv.price for b in later)
                if long
                else any(b.low < lv.price for b in later)
            )
            if taken:
                continue
            if best is None or (lv.price < best if long else lv.price > best):
                best = lv.price
        return best


def _round(price: float, tick: float) -> float:
    return round(price / tick) * tick


@register("ny_am_silver_bullet")
class NyAmSilverBullet(SilverBullet):
    """NY AM Silver Bullet: setup and entry inside 10:00-11:00 New York."""


@register("ny_pm_silver_bullet")
class NyPmSilverBullet(SilverBullet):
    """NY PM Silver Bullet: setup and entry inside 14:00-15:00 New York.

    Pools are the AM session (09:30-12:00), the lunch range (12:00-13:30) and
    swings since 13:30. On FOMC statement days the news blackout (13:45-15:30)
    blocks its entries, so it doesn't trade.
    """
