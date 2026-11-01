"""Hard risk rules the ML can't override (docs/design.md, "Hard risk rules").

`RiskBook` tracks equity across a run and per CME session, and answers two
questions for the trader: may this candidate open a trade now (and if not,
which skip status), and how many contracts does 1% risk buy.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from moon_ai.config import RiskConfig


@dataclass
class RiskBook:
    cfg: RiskConfig
    equity: float = 0.0
    peak: float = 0.0
    session: date | None = None
    session_start_equity: float = 0.0
    trades_this_session: int = 0
    killed: bool = False

    def __post_init__(self) -> None:
        if self.equity == 0.0:
            self.equity = self.cfg.account_usd
        self.peak = max(self.peak, self.equity)
        self.session_start_equity = self.equity

    def start_session(self, day: date) -> None:
        if day != self.session:
            self.session = day
            self.session_start_equity = self.equity
            self.trades_this_session = 0

    def book(self, pnl_usd: float) -> None:
        """Realised P&L net of costs, as fills arrive."""
        self.equity += pnl_usd
        self.peak = max(self.peak, self.equity)
        if self.peak - self.equity >= self.peak * self.cfg.kill_switch_drawdown_pct / 100:
            self.killed = True

    def trade_opened(self) -> None:
        self.trades_this_session += 1

    @property
    def daily_stop_hit(self) -> bool:
        limit = self.session_start_equity * self.cfg.daily_stop_pct / 100
        return self.session_start_equity - self.equity >= limit

    def block_reason(self) -> str | None:
        """Why no new trade may open now, as a candidate status, or None."""
        if self.killed:
            return "skipped:kill_switch"
        if self.daily_stop_hit:
            return "skipped:daily_stop"
        if self.trades_this_session >= self.cfg.max_trades_per_session:
            return "skipped:cap"
        return None

    def contracts(self, stop_distance_points: float, point_value: float) -> int:
        """Whole contracts whose stop-out loses at most risk_per_trade_pct of equity."""
        if stop_distance_points <= 0:
            return 0
        budget = self.equity * self.cfg.risk_per_trade_pct / 100
        return math.floor(budget / (stop_distance_points * point_value))
