"""The trader: the one `Strategy`, turning setups' candidates into orders.

docs/design.md: "Code layout and commands", "Setup testing protocol"
(overlaps), "News blackout", "Backtest realism" and "Hard risk rules".

On every closed bar:

1. **Housekeeping** for open plans: cancel unfilled entries when a news
   blackout starts or the entry deadline passes; close open trades at their
   time-out or before the flat-by time.
2. **Scan** every setup. Candidates on the same bar, symbol and side are one
   trade: the highest-priority setup owns it, and the others become tags.
3. **Gate** each candidate in priority order. The first rule that blocks it
   sets its skip status:
   - session calendar (`skipped:session`)
   - kill switch, daily stop or session cap
   - a trade already open or working on the symbol (`skipped:busy`)
   - the London minimum stop
   - news blackout (entries only)
   - the ML gate
   - position size
4. **Submit** a bracket order (stop and target attached) for the survivors.

Every candidate reaches the journal exactly once, with its final status:
skipped ones at once, taken ones when the entry fills (`taken`) or is
cancelled (`unfilled`). Trades are written complete when they close. The
trader also receives the engine's fills: pass `trader.tap(journal)` to the
engine as its journal.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from typing import Any

from moon_ai.bars import Bar
from moon_ai.broker import Bracket, Fill, Order, OrderType, Side
from moon_ai.config import Config, IctConfig
from moon_ai.data.calendar import SessionCalendar
from moon_ai.data.news import Blackout
from moon_ai.engine import Context
from moon_ai.journal import Journal, JournalEntry, RunJournal
from moon_ai.risk import RiskBook
from moon_ai.sessions import NY, to_ny, trading_day
from moon_ai.setups.base import Candidate, Setup

LONDON = "london_sweep_and_reverse"

MLGate = Callable[[Candidate], tuple[float | None, float | None, bool]]
"""candidate -> (probability, threshold, take). Rules-only takes everything."""


def rules_only(_: Candidate) -> tuple[float | None, float | None, bool]:
    return None, None, True


@dataclass
class _Plan:
    """A candidate whose entry order is working or filled."""

    cand: Candidate
    cid: str
    order_id: str
    qty: int
    extra: dict[str, Any]
    entry_fill: Fill | None = None
    entry_fill_id: str | None = None
    exiting: bool = False
    exit_reason: str | None = None
    pnl: float = 0.0  # gross realised USD
    costs: float = 0.0  # commissions USD
    hi: float = float("-inf")
    lo: float = float("inf")


@dataclass
class Trader:
    setups: Sequence[Setup]
    journal: RunJournal
    config: Config
    calendar: SessionCalendar = field(default_factory=SessionCalendar)
    blackout: Blackout | None = None
    ml_gate: MLGate = rules_only

    def __post_init__(self) -> None:
        self.risk = RiskBook(self.config.risk)
        self._ict: IctConfig = self.config.ict
        self._priority = {s.name: s.params.priority for s in self.setups}
        self._plans: dict[str, _Plan] = {}  # by broker order id
        self._last_now: datetime | None = None

    # --- Journal tap: the engine's fills arrive here first ---------------------

    def tap(self, journal: Journal) -> Journal:
        trader = self

        class _Tee:
            def record(self, entry: JournalEntry) -> None:
                journal.record(entry)
                if entry.kind == "fill":
                    trader._on_fill(entry.data["fill"])

        return _Tee()

    # --- Strategy ------------------------------------------------------------

    def on_bar(self, bar: Bar, ctx: Context) -> None:
        now = ctx.now
        assert now is not None
        self.risk.start_session(trading_day(now))
        self._track_excursions(bar)
        self._housekeeping(ctx, now)
        cands = [c for s in self.setups for c in s.scan(ctx)]
        for cand in self._dedupe(cands):
            self._consider(cand, ctx, now)
        self._last_now = now

    def finish(self) -> None:
        """At run end: write still-open trades and still-working candidates."""
        for oid, plan in list(self._plans.items()):
            if plan.entry_fill is None:
                self._write_candidate(plan, "unfilled")
            else:
                self._write_trade(plan, None)
            del self._plans[oid]

    # --- step 1: housekeeping ----------------------------------------------------

    def _housekeeping(self, ctx: Context, now: datetime) -> None:
        blackout_started = bool(
            self.blackout
            and self._last_now is not None
            and self.blackout.starts_between(self._last_now, now)
        )
        flat_at = datetime.combine(to_ny(now).date(), self.config.risk.flat_by, tzinfo=NY)
        flat_now = now >= flat_at - timedelta(minutes=1) and now < flat_at + timedelta(hours=2)
        for oid, plan in list(self._plans.items()):
            if plan.entry_fill is None:
                late = plan.cand.entry_deadline is not None and now >= plan.cand.entry_deadline
                if blackout_started or late or now >= plan.cand.timeout or flat_now:
                    ctx.broker.cancel(oid)
                    self._write_candidate(plan, "unfilled")
                    del self._plans[oid]
            elif not plan.exiting and (now >= plan.cand.timeout or flat_now):
                side = Side.SELL if plan.cand.side == "long" else Side.BUY
                order = Order(plan.cand.symbol, side, plan.qty, tag=f"exit:{plan.cid}")
                exit_id = ctx.broker.submit(order)
                self.journal.add_order(exit_id, order, now, plan.cid)
                plan.exiting = True
                plan.exit_reason = "timeout" if now >= plan.cand.timeout else "flat_by"
                self._plans[exit_id] = plan

    # --- step 2: dedupe ------------------------------------------------------------

    def _dedupe(self, cands: list[Candidate]) -> list[Candidate]:
        groups: dict[tuple[str, str, datetime], list[Candidate]] = {}
        for c in cands:
            groups.setdefault((c.symbol, c.side, c.decision_time), []).append(c)
        out = []
        for group in groups.values():
            group.sort(key=lambda c: self._priority.get(c.setup, 99))
            owner, others = group[0], group[1:]
            tags = tuple(dict.fromkeys([*owner.tags, *(o.setup for o in others)]))
            out.append(_retag(owner, tags))
        return sorted(out, key=lambda c: self._priority.get(c.setup, 99))

    # --- steps 3-4: gate and submit -------------------------------------------------

    def _consider(self, cand: Candidate, ctx: Context, now: datetime) -> None:
        cid = cand.id(self.journal.run_id)
        extra: dict[str, Any] = {}
        status = self._gate(cand, now, extra)
        qty = 0
        if status is None:
            spec = self.config.instrument(cand.symbol)
            ref = cand.entry if cand.entry is not None else ctx.history(cand.symbol, 1)[-1].close
            qty = self.risk.contracts(abs(ref - cand.stop), spec.point_value)
            if qty < 1:
                status = "skipped:size"
        if status is not None:
            self.journal.add_candidate(cand.journal_row(self.journal.run_id, status, **extra))
            return
        order = Order(
            cand.symbol,
            Side.BUY if cand.side == "long" else Side.SELL,
            qty,
            OrderType(cand.entry_type),
            cand.entry,
            Bracket(cand.stop, cand.target),
            tag=cid,
        )
        oid = ctx.broker.submit(order)
        self.journal.add_order(oid, order, now, cid)
        self._plans[oid] = _Plan(cand, cid, oid, qty, extra)

    def _gate(self, cand: Candidate, now: datetime, extra: dict[str, Any]) -> str | None:
        if self.calendar.no_new_trades(trading_day(now)):
            return "skipped:session"
        reason = self.risk.block_reason()
        if reason:
            return reason
        if any(p.cand.symbol == cand.symbol for p in self._plans.values()):
            return "skipped:busy"
        if cand.setup == LONDON:
            tick = self.config.instrument(cand.symbol).tick_size
            ref = cand.entry if cand.entry is not None else cand.stop
            if abs(ref - cand.stop) < self._ict.london_min_stop_ticks * tick:
                return "skipped:london_min_stop"
        if self.blackout is not None and self.blackout.in_blackout(now):
            return "skipped:blackout"
        p, threshold, take = self.ml_gate(cand)
        extra.update(ml_p=p, ml_threshold=threshold)
        if not take:
            return "skipped:ml"
        return None

    # --- fills ------------------------------------------------------------------------

    def _on_fill(self, fill: Fill) -> None:
        plan = self._plans.get(fill.order_id) or self._plans.get(fill.order_id.rsplit("-", 1)[0])
        if plan is None:
            return
        plan.costs += fill.commission
        self.risk.book(fill.pnl - fill.commission)
        if fill.reason == "entry" and plan.entry_fill is None:
            plan.entry_fill = fill
            plan.entry_fill_id = self._fill_id(fill)
            plan.hi = plan.lo = fill.price
            self.risk.trade_opened()
            self._write_candidate(plan, "taken")
            return
        plan.pnl += fill.pnl
        reason = fill.reason if fill.reason in ("stop", "target") else plan.exit_reason or "exit"
        self._write_trade(plan, fill, reason)
        for oid in [k for k, v in self._plans.items() if v is plan]:
            del self._plans[oid]

    def _fill_id(self, fill: Fill) -> str:
        # RunJournal numbers fills per order from 1; an entry is its order's first fill.
        return f"{self.journal.order_key(fill.order_id)}:1"

    # --- journal rows --------------------------------------------------------------

    def _write_candidate(self, plan: _Plan, status: str) -> None:
        self.journal.add_candidate(plan.cand.journal_row(self.journal.run_id, status, **plan.extra))

    def _write_trade(self, plan: _Plan, exit_fill: Fill | None, reason: str | None = None) -> None:
        entry = plan.entry_fill
        assert entry is not None
        spec = self.config.instrument(plan.cand.symbol)
        risk_usd = abs(entry.price - plan.cand.stop) * spec.point_value * plan.qty
        sign = 1 if plan.cand.side == "long" else -1
        net = plan.pnl - plan.costs if exit_fill is not None else None
        r_of = (lambda pts: pts * spec.point_value * plan.qty / risk_usd) if risk_usd else None
        mae = mfe = None
        if r_of is not None:
            adverse = (plan.lo - entry.price) if sign > 0 else (entry.price - plan.hi)
            favourable = (plan.hi - entry.price) if sign > 0 else (entry.price - plan.lo)
            mae, mfe = r_of(min(adverse, 0.0)), r_of(max(favourable, 0.0))
        self.journal.add_trade(
            {
                "candidate_id": plan.cid,
                "entry_fill_id": plan.entry_fill_id,
                "exit_fill_id": (
                    f"{self.journal.order_key(exit_fill.order_id)}:1" if exit_fill else None
                ),
                "entry_time": entry.ts,
                "exit_time": exit_fill.ts if exit_fill else None,
                "entry_price": entry.price,
                "exit_price": exit_fill.price if exit_fill else None,
                "exit_reason": reason,
                "mae_r": mae,
                "mfe_r": mfe,
                "r": net / risk_usd if net is not None and risk_usd else None,
                "net_usd": net,
                "chart_path": None,
            }
        )

    def _track_excursions(self, bar: Bar) -> None:
        for plan in {id(p): p for p in self._plans.values()}.values():
            if plan.entry_fill is not None and plan.cand.symbol == bar.symbol:
                plan.hi = max(plan.hi, bar.high)
                plan.lo = min(plan.lo, bar.low)


def _retag(c: Candidate, tags: tuple[str, ...]) -> Candidate:
    return c if tags == c.tags else replace(c, tags=tags)
