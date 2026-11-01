"""`moon-ai doctor`: check the Mac setup and say, in plain words, what to fix.

Each check returns ok / warn / fail with one sentence and, if needed, the fix.
Only a fail makes the command exit non-zero; warnings are things that are
fine for now (e.g. the nightly job not installed yet).
"""

from __future__ import annotations

import os
import platform
import shutil
import sqlite3
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Literal

from moon_ai.config import Config
from moon_ai.data.download import DEFAULT_ENV_FILE, _read_dotenv
from moon_ai.data.news import NEWS_CSV, load_events
from moon_ai.data.store import BarStore

Level = Literal["ok", "warn", "fail"]
KEYS = {
    "DATABENTO_API_KEY": ("fail", "needed to download prices"),
    "ANTHROPIC_API_KEY": ("warn", "needed for Claude's trade reviews and weekly report"),
    "GITHUB_TOKEN": ("warn", "needed for the dashboard's Approve/No buttons"),
    "GEMINI_API_KEY": ("warn", "needed for the monthly ICT watcher"),
    "YOUTUBE_API_KEY": ("warn", "needed for the monthly ICT watcher"),
}
LAUNCH_AGENTS = Path.home() / "Library" / "LaunchAgents"
MIN_FREE_GB = 5.0


@dataclass(frozen=True)
class Result:
    level: Level
    name: str
    message: str
    fix: str = ""


def check_python() -> Result:
    v = sys.version_info
    if v >= (3, 12):
        return Result("ok", "Python", f"Python {v.major}.{v.minor} is installed.")
    return Result(
        "fail",
        "Python",
        f"Python {v.major}.{v.minor} is too old.",
        "Run `uv sync`; it installs Python 3.12 for this project.",
    )


def check_keys(environ: Mapping[str, str], env_file: Path = DEFAULT_ENV_FILE) -> list[Result]:
    found = {**_read_dotenv(env_file), **{k: v for k, v in environ.items() if v}}
    out = []
    for key, (level, why) in KEYS.items():
        if found.get(key):
            out.append(Result("ok", key, f"{key} is set."))
        else:
            out.append(
                Result(
                    level,
                    key,
                    f"{key} is missing ({why}).",
                    f"Add a line `{key}=...` to {env_file}. Never put keys in the repo.",
                )
            )
    return out


def check_bars(store: BarStore, symbol: str, today: date) -> Result:
    spans = store.files(symbol)
    if not spans:
        return Result(
            "fail",
            "Price data",
            f"No {symbol} price data in {store.root}.",
            "Download it: see the README's Databento section.",
        )
    first, last = min(s.start for s in spans), max(s.end for s in spans)
    if first > date(2019, 6, 1):
        return Result(
            "warn",
            "Price data",
            f"{symbol} data starts {first}, after the 2019 launch.",
            "Download the earlier history before running the full backtest.",
        )
    if last < today - timedelta(days=7):
        return Result(
            "warn",
            "Price data",
            f"{symbol} data runs {first} to {last}; the last week is missing.",
            "Fine for backtests; the nightly job will top it up.",
        )
    return Result("ok", "Price data", f"{symbol} data runs {first} to {last}.")


def check_disk(path: Path) -> Result:
    path = path if path.exists() else Path(".")
    free = shutil.disk_usage(path).free / 1e9
    if free < MIN_FREE_GB:
        return Result(
            "fail",
            "Disk space",
            f"Only {free:.1f} GB free.",
            f"Free at least {MIN_FREE_GB:.0f} GB; backtest runs and the journal need room.",
        )
    return Result("ok", "Disk space", f"{free:.0f} GB free.")


def check_news(path: Path = NEWS_CSV) -> Result:
    if not path.exists():
        return Result(
            "fail",
            "News calendar",
            "The news calendar file is missing.",
            "Pull the latest code (`git pull`); it ships with the repo.",
        )
    events = load_events(path)
    if not any(e.event_type == "CPI" for e in events):
        return Result(
            "warn",
            "News calendar",
            f"{len(events)} release times, but no CPI, jobs report or PPI yet.",
            "Backtests will be slightly optimistic until they're added.",
        )
    return Result("ok", "News calendar", f"{len(events)} release times.")


STALE_NIGHTLY_HOURS = 36  # the job runs once a day; this allows a late or skipped wake-up


def check_journal(path: Path, now: datetime | None = None) -> Result:
    if not path.exists():
        return Result(
            "warn",
            "Trade journal",
            "No paper-trading journal yet.",
            "Normal until the nightly job is installed.",
        )
    try:
        with sqlite3.connect(path) as conn:
            conn.execute("SELECT COUNT(*) FROM runs").fetchone()
            (last,) = conn.execute("SELECT MAX(ts) FROM events WHERE run_id = 'paper'").fetchone()
    except sqlite3.Error as exc:
        return Result(
            "fail",
            "Trade journal",
            f"The journal at {path} can't be read ({exc}).",
            "Restore the latest copy from data/backups/.",
        )
    if last is not None:
        age = (now or datetime.now(UTC)) - datetime.fromisoformat(last)
        if age > timedelta(hours=STALE_NIGHTLY_HOURS):
            return Result(
                "warn",
                "Trade journal",
                f"The nightly paper run last ran {age.days} day(s) ago.",
                "Keep the Mac awake and plugged in overnight, then check "
                "`uv run moon-ai nightly status`.",
            )
    return Result("ok", "Trade journal", f"The journal at {path} opens fine.")


def check_nightly(agents: Path = LAUNCH_AGENTS) -> Result:
    plists = sorted(agents.glob("com.moonai.*.plist")) if agents.exists() else []
    if not plists:
        return Result(
            "warn",
            "Nightly job",
            "The nightly paper run isn't installed yet.",
            "Later: `uv run moon-ai nightly install`.",
        )
    return Result("ok", "Nightly job", f"Installed ({', '.join(p.stem for p in plists)}).")


def _apple_chip() -> bool:
    """True on Apple silicon, even when this Python runs in Intel mode (Rosetta)."""
    try:
        out = subprocess.run(
            ["sysctl", "-n", "hw.optional.arm64"], capture_output=True, text=True, timeout=5
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return out.stdout.strip() == "1"


def check_native(
    system: str | None = None,
    machine: str | None = None,
    apple_chip: Callable[[], bool] = _apple_chip,
) -> Result:
    """Polars crashes or crawls when Python runs in Intel mode on an Apple-chip Mac."""
    system = system or platform.system()
    machine = machine or platform.machine()
    if system == "Darwin" and machine == "x86_64" and apple_chip():
        return Result(
            "fail",
            "Native Python",
            "Python is running in Intel mode (Rosetta) on an Apple-chip Mac.",
            "Install the native uv (`curl -LsSf https://astral.sh/uv/install.sh | sh`), then "
            "`rm -rf .venv && uv venv --python cpython-3.12-macos-aarch64 --managed-python "
            "&& uv sync`.",
        )
    return Result("ok", "Native Python", f"Python runs natively ({machine}).")


def run_checks(
    config: Config, today: date | None = None, environ: Mapping[str, str] | None = None
) -> list[Result]:
    today = today or date.today()
    root = Path(config.data.store_root)
    checks: list[Callable[[], Result | list[Result]]] = [
        check_python,
        check_native,
        lambda: check_keys(os.environ if environ is None else environ),
        lambda: check_bars(BarStore(root, config.data.dataset), "MNQ.v.0", today),
        lambda: check_disk(root),
        check_news,
        lambda: check_journal(Path("data/journal/journal.sqlite")),
        check_nightly,
    ]
    out: list[Result] = []
    for c in checks:
        r = c()
        out.extend(r if isinstance(r, list) else [r])
    return out


def report(results: list[Result]) -> tuple[str, int]:
    marks = {"ok": "✓", "warn": "!", "fail": "✕"}
    lines = []
    for r in results:
        lines.append(f"{marks[r.level]} {r.message}")
        if r.fix and r.level != "ok":
            lines.append(f"    → {r.fix}")
    fails = sum(r.level == "fail" for r in results)
    warns = sum(r.level == "warn" for r in results)
    lines.append("")
    lines.append(
        "All good."
        if not fails and not warns
        else f"{fails} problem(s) to fix, {warns} thing(s) to know about."
        if fails
        else f"Ready. {warns} thing(s) to know about, nothing blocking."
    )
    return "\n".join(lines), 1 if fails else 0
