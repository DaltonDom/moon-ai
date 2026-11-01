"""One chart PNG per taken trade (docs/design.md, "Journal storage" → Charts).

It shows the setup window and the trade: 1-minute candles from 90 minutes
before the decision to 30 minutes after the exit, with entry, stop and target
lines and a marker at the decision. It feeds the Claude review and the
dashboard's trade page. Rendering never looks past the exit by more than the
30-minute margin, and the review happens after the trade closed, so the chart
can't leak anything into trading.
"""

from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from moon_ai.bars import Bar
from moon_ai.sessions import to_ny

BEFORE = timedelta(minutes=90)
AFTER = timedelta(minutes=30)
WIN, LOSS, INK, SUB = "#12a37f", "#e0533f", "#161a2b", "#5d6378"


def chart_name(candidate_id: str) -> str:
    """A filesystem-safe file name for a candidate id (ids hold ':' and '+')."""
    return re.sub(r"[^A-Za-z0-9_.-]", "_", candidate_id) + ".png"


def window(cand: dict[str, Any], trade: dict[str, Any]):
    end = trade["exit_time"] or trade["entry_time"]
    return cand["decision_time"] - BEFORE, end + AFTER


def render(cand: dict[str, Any], trade: dict[str, Any], bars: list[Bar], folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / chart_name(cand["candidate_id"])
    lo, hi = window(cand, trade)
    bars = [b for b in bars if lo <= b.ts_open < hi]
    fig, ax = plt.subplots(figsize=(10, 4.6), dpi=110)
    for i, b in enumerate(bars):
        col = WIN if b.close >= b.open else LOSS
        ax.vlines(i, b.low, b.high, color=col, linewidth=0.8)
        ax.add_patch(
            plt.Rectangle(
                (i - 0.35, min(b.open, b.close)),
                0.7,
                max(abs(b.close - b.open), 1e-9),
                color=col,
            )
        )
    n = max(len(bars), 1)
    idx = {b.ts_open: i for i, b in enumerate(bars)}

    def at(t) -> float:
        return next((i for ts, i in idx.items() if ts >= t), n - 1)

    start = at(trade["entry_time"])
    end = at(trade["exit_time"]) if trade["exit_time"] else n - 1
    for y, col, name in (
        (trade["entry_price"], "#4b5bd6", "entry"),
        (cand["stop"], LOSS, "stop"),
        (cand["target"], WIN, "target"),
    ):
        ax.hlines(y, start, max(end, start + 1), color=col, linewidth=1.4)
        ax.text(max(end, start + 1) + 0.5, y, f" {name} {y:g}", color=col, va="center", fontsize=8)
    if trade["exit_price"] is not None:
        ax.plot([end], [trade["exit_price"]], marker="o", color=INK, markersize=5)
    ax.axvline(at(cand["decision_time"]), color=SUB, linestyle=":", linewidth=1)
    ticks = list(range(0, n, max(1, n // 8)))
    ax.set_xticks(ticks, [to_ny(bars[i].ts_open).strftime("%H:%M") for i in ticks] if bars else [])
    ax.set_xlim(-1, n + 6)
    ax.set_title(
        f"{cand['setup']} · {cand['side']} · "
        f"{to_ny(cand['decision_time']):%Y-%m-%d %H:%M} New York",
        fontsize=10,
        color=INK,
    )
    ax.grid(axis="y", color="#e1e4ee", linewidth=0.6)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path
