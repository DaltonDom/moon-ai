"""Killzone and Silver Bullet window membership."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from moon_ai.bars import Bar
from moon_ai.config import Config, Window
from moon_ai.sessions import in_window


@dataclass(frozen=True)
class WindowTag:
    index: int
    windows: frozenset[str]
    known_at: datetime


def window_membership(bars: Sequence[Bar], windows: Mapping[str, Window]) -> list[WindowTag]:
    """Which named windows each bar's close falls in.

    A bar is judged at its close, the moment a decision can use it: the bar
    opening 09:59 (closing 10:00) is inside 10:00-11:00; the bar opening 10:59
    (closing 11:00) is not.
    """
    return [
        WindowTag(
            i,
            frozenset(name for name, w in windows.items() if in_window(b.ts_close, w)),
            b.ts_close,
        )
        for i, b in enumerate(bars)
    ]


def killzones(cfg: Config) -> dict[str, Window]:
    return {name: cfg.sessions.windows[name] for name in cfg.sessions.killzones}


def silver_bullets(cfg: Config) -> dict[str, Window]:
    return {name: cfg.sessions.windows[name] for name in cfg.sessions.enabled_silver_bullets}
