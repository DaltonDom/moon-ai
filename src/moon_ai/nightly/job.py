"""The nightly job: eight logged steps that paper-trade every new session.

Each step writes a pass/fail/skipped `events` row with a plain-language
message. A failed step skips the steps that depend on it, and the next run
retries. Each session's replay is one transaction, so nothing half-written
is kept. The job catches up: it replays every completed session it hasn't
replayed yet, oldest first. The very first run replays only the latest
session, because the backtests already cover history.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from moon_ai.broker import SimBroker
from moon_ai.config import Config, load_config
from moon_ai.data.calendar import SessionCalendar, session_info
from moon_ai.data.download import Downloader, DownloadRequest
from moon_ai.data.news import NEWS_CSV, Blackout, load_events
from moon_ai.data.quality import degraded_sessions, load_degraded_dates
from moon_ai.data.store import BarStore, ParquetBarFeed
from moon_ai.engine import run as run_engine
from moon_ai.journal import JournalError, RunJournal, SQLiteStore, decode_json
from moon_ai.sessions import NY, to_ny
from moon_ai.setups import REGISTRY, load_setup_defaults
from moon_ai.trader import Trader

PAPER_RUN = "paper"
RUN_AFTER = time(18, 30)  # New York; launchd wakes the job hourly
COST_CAP_USD = 1.0
KEEP_BACKUPS = 14
MIN_BARS_REGULAR = 1300  # a full session has 1,380 one-minute bars


@dataclass
class StepResult:
    step: str
    status: str  # ok | fail | skipped | warn
    message: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class Paths:
    root: Path = Path("data")

    @property
    def journal(self) -> Path:
        return self.root / "journal" / "journal.sqlite"

    @property
    def bars(self) -> Path:
        return self.root / "bars"

    @property
    def backups(self) -> Path:
        return self.root / "backups"

    @property
    def lock(self) -> Path:
        return self.root / "nightly.lock"


def sessions_between(after: date, through: date) -> list[date]:
    out, d = [], after + timedelta(days=1)
    while d <= through:
        if session_info(d).kind not in ("weekend", "closed"):
            out.append(d)
        d += timedelta(days=1)
    return out


def last_complete_session(now: datetime) -> date:
    """The latest CME session that has closed (17:00 New York)."""
    ny = to_ny(now)
    d = ny.date() if ny.time() >= time(17) else ny.date() - timedelta(days=1)
    while session_info(d).kind in ("weekend", "closed"):
        d -= timedelta(days=1)
    return d


class NightlyJob:
    def __init__(
        self,
        paths: Paths | None = None,
        config: Config | None = None,
        client_factory: Callable[[], Any] | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        notify: Callable[[str, str], None] | None = None,
        symbol: str = "MNQ.v.0",
        news_csv: Path = NEWS_CSV,
        refresh_news: Callable[[], StepResult] | None = None,
    ):
        self.paths = paths or Paths()
        self.config = config or load_config()
        self.client_factory = client_factory
        self.now = now
        self.notify = notify or notify_user
        self.symbol = symbol
        self.news_csv = news_csv
        self.refresh_news = refresh_news or self._news_builder

    # --- helpers --------------------------------------------------------------------

    def _db(self) -> SQLiteStore:
        db = SQLiteStore(self.paths.journal)
        with contextlib.suppress(JournalError):  # already started on an earlier night
            db.start_run(
                {
                    "run_id": PAPER_RUN,
                    "kind": "paper",
                    "created_at": self.now(),
                    "account_usd": self.config.risk.account_usd,
                    "risk_per_trade_usd": self.config.risk.account_usd
                    * self.config.risk.risk_per_trade_pct
                    / 100,
                    "notes": {"symbol": self.symbol},
                }
            )
        return db

    def replayed_sessions(self, db: SQLiteStore) -> set[date]:
        rows = decode_json(db.read("events", PAPER_RUN), "events")
        return {
            date.fromisoformat(r["data"]["session"])
            for r in rows
            if r["step"] == "replay" and r["status"] == "ok" and r["data"]
        }

    def _event(self, db: SQLiteStore, stamp: str, r: StepResult) -> None:
        db.insert(
            "events",
            {
                "event_id": f"{stamp}:{r.step}:{r.data.get('session', '')}",
                "run_id": PAPER_RUN,
                "ts": self.now(),
                "step": r.step,
                "status": r.status,
                "message": r.message,
                "data": {**r.data, "run": stamp},
            },
        )

    # --- the run ------------------------------------------------------------------------

    def should_run(self, db: SQLiteStore) -> bool:
        """For the hourly launchd wake-up: after 18:30 New York, once per day."""
        ny = to_ny(self.now())
        if ny.time() < RUN_AFTER:
            return False
        rows = decode_json(db.read("events", PAPER_RUN), "events")
        return not any(r["step"] == "summary" and to_ny(r["ts"]).date() == ny.date() for r in rows)

    def run(self, only_session: date | None = None, scheduled: bool = False) -> list[StepResult]:
        self.paths.root.mkdir(parents=True, exist_ok=True)
        with self.paths.lock.open("w") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return [StepResult("preflight", "skipped", "Another nightly run is already going.")]
            db = self._db()
            if scheduled and not self.should_run(db):
                return []
            stamp = f"{self.now():%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:6]}"
            results = self._steps(db, only_session)
            for r in results:
                self._event(db, stamp, r)
            failed = [r for r in results if r.status == "fail"]
            if failed:
                self.notify(
                    "moon-ai nightly run needs a look",
                    "; ".join(f"{r.step}: {r.message}" for r in failed),
                )
            db.close()
            return results

    def _steps(self, db: SQLiteStore, only_session: date | None) -> list[StepResult]:
        out = [self.preflight()]
        if out[-1].status == "fail":
            return [
                *out,
                *(
                    StepResult(s, "skipped", "Skipped because preflight failed.")
                    for s in (
                        "pull",
                        "check",
                        "news",
                        "replay",
                        "reviews",
                        "models",
                        "housekeeping",
                        "summary",
                    )
                ),
            ]
        through = last_complete_session(self.now())
        done = self.replayed_sessions(db)
        if only_session:
            todo = [only_session]
        elif done:
            todo = sessions_between(max(done), through)
        else:
            todo = [through]
        out.append(self.pull(todo))
        ready, check = self.check(todo)
        out.append(check)
        out.append(self.news())
        replays = [self.replay(db, s) for s in ready] if out[1].status != "fail" else []
        out.extend(replays or [StepResult("replay", "ok", "No new session to replay.")])
        out.append(StepResult("reviews", "skipped", "Claude trade reviews aren't built yet."))
        out.append(self.models(db))
        out.append(self.housekeeping())
        out.append(self.summary(db, out))
        return out

    # --- the steps ----------------------------------------------------------------------

    def preflight(self) -> StepResult:
        free = shutil.disk_usage(self.paths.root).free / 1e9
        if free < 2:
            return StepResult(
                "preflight", "fail", f"Only {free:.1f} GB of disk left; free some space."
            )
        if (
            self.client_factory is None
            and not os.environ.get("DATABENTO_API_KEY")
            and not Path.home().joinpath(".config/moon-ai/.env").exists()
        ):
            return StepResult(
                "preflight", "fail", "No Databento key, so prices can't be downloaded."
            )
        return StepResult("preflight", "ok", f"{free:.0f} GB free, key present.")

    def pull(self, sessions: list[date]) -> StepResult:
        store = BarStore(self.paths.bars, self.config.data.dataset)
        missing = [s for s in sessions if not store.covers(self.symbol, s)]
        if not missing:
            return StepResult("pull", "ok", "All the prices needed are already here.")
        if self.client_factory is None:
            from moon_ai.data.download import DEFAULT_ENV_FILE, databento_client, resolve_api_key

            client = databento_client(resolve_api_key(env_file=DEFAULT_ENV_FILE))
        else:
            client = self.client_factory()
        start, end = missing[0] - timedelta(days=1), missing[-1] + timedelta(days=1)
        req = DownloadRequest(
            (self.symbol,),
            start,
            end,
            self.config.data.dataset,
            self.config.data.schema,
            self.config.data.stype_in,
        )
        try:
            res = Downloader(client, self.paths.bars, COST_CAP_USD).download(req)
        except Exception as exc:
            return StepResult(
                "pull", "fail", f"Couldn't download prices ({exc}). Will retry next run."
            )
        return StepResult(
            "pull",
            "ok",
            f"Downloaded {len(missing)} session(s) for ${res.cost_usd:.2f}.",
            {"cost_usd": res.cost_usd},
        )

    def check(self, sessions: list[date]) -> tuple[list[date], StepResult]:
        store = BarStore(self.paths.bars, self.config.data.dataset)
        degraded = degraded_sessions(load_degraded_dates())
        ready, notes = [], []
        for s in sessions:
            if s in degraded:
                notes.append(f"{s} held: Databento marks it degraded")
                continue
            open_, close = (
                datetime.combine(s - timedelta(days=1), time(18), tzinfo=NY),
                datetime.combine(s, time(17), tzinfo=NY),
            )
            n = len(store.load(self.symbol, open_, close))
            if n == 0:
                notes.append(f"{s}: no prices yet")
                continue
            if session_info(s).kind == "regular" and n < MIN_BARS_REGULAR:
                notes.append(f"{s}: only {n} bars (expected about 1,380)")
            ready.append(s)
        status = "ok" if not notes else "warn"
        msg = f"{len(ready)} session(s) ready." + (" " + "; ".join(notes) if notes else "")
        return ready, StepResult("check", status, msg)

    def news(self) -> StepResult:
        """Refresh the news calendar once a week (Saturdays): the builder fetches
        hundreds of official pages politely, and the committed file covers the week."""
        if to_ny(self.now()).weekday() != 5:
            return StepResult("news", "ok", "News calendar is current (refreshed on Saturdays).")
        return self.refresh_news()

    def _news_builder(self) -> StepResult:
        script = Path(__file__).resolve().parents[3] / "scripts" / "build_news_history.py"
        if not script.exists():
            return StepResult("news", "skipped", "No news builder script found.")
        try:
            subprocess.run(
                [sys.executable, str(script)], check=True, timeout=900, capture_output=True
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            return StepResult(
                "news",
                "warn",
                f"Couldn't refresh the news calendar ({type(exc).__name__}); "
                "the committed one is used.",
            )
        return StepResult("news", "ok", "News calendar refreshed.")

    def replay(self, db: SQLiteStore, session: date) -> StepResult:
        """Paper-trade one session through every setup, in one transaction."""
        store = BarStore(self.paths.bars, self.config.data.dataset)
        events = load_events(self.news_csv) if self.news_csv.exists() else []
        defaults = load_setup_defaults()
        setups = [REGISTRY[n](d.params, self.config, self.symbol) for n, d in defaults.items()]
        journal = RunJournal(
            db,
            PAPER_RUN,
            lambda s: self.config.instrument(s).tick_size,
            order_prefix=f"{session.isoformat()}:",
        )
        trader = Trader(
            setups,
            journal,
            self.config,
            calendar=SessionCalendar(degraded=degraded_sessions(load_degraded_dates())),
            blackout=Blackout(events, self.config.ict),
        )
        trader.risk.equity = trader.risk.peak = self.config.risk.account_usd + self._paper_pnl(db)
        start = datetime.combine(session - timedelta(days=15), time(18), tzinfo=NY)
        end = datetime.combine(session, time(17), tzinfo=NY)
        lo = datetime.combine(session - timedelta(days=1), time(18), tzinfo=NY)
        feed = ParquetBarFeed(store, [self.symbol], start, end)
        before = {
            r["candidate_id"] for r in decode_json(db.read("candidates", PAPER_RUN), "candidates")
        }

        class OnlySession:
            """Earlier sessions only fill the engine's bar history, which the setups
            read once per day (bias, prior sessions); they aren't traded."""

            def on_bar(self, bar, ctx):
                if bar.ts_close > lo:
                    trader.on_bar(bar, ctx)

        try:
            with db.transaction():
                run_engine(
                    feed,
                    SimBroker(self.config.broker, self.config.instrument),
                    OnlySession(),
                    trader.tap(journal),
                )
                trader.finish()
        except (JournalError, sqlite3.Error) as exc:
            return StepResult(
                "replay",
                "fail",
                f"{session}: replay failed ({exc}); nothing was kept.",
                {"session": session.isoformat()},
            )
        after = decode_json(db.read("candidates", PAPER_RUN), "candidates")
        new = [r for r in after if r["candidate_id"] not in before]
        taken = sum(r["status"] == "taken" for r in new)
        return StepResult(
            "replay",
            "ok",
            f"{session}: {len(new)} setup(s) found, {taken} traded.",
            {"session": session.isoformat(), "candidates": len(new), "taken": taken},
        )

    def _paper_pnl(self, db: SQLiteStore) -> float:
        return sum(t["net_usd"] or 0.0 for t in decode_json(db.read("trades", PAPER_RUN), "trades"))

    def models(self, db: SQLiteStore) -> StepResult:
        champs = [m for m in decode_json(db.read("models"), "models") if m["role"] == "champion"]
        if not champs:
            return StepResult(
                "models", "ok", "Rules-only is in charge (no ML model has been promoted)."
            )
        return StepResult(
            "models",
            "skipped",
            f"Model {champs[0]['model_id']} is in charge; the nightly model checks "
            "aren't wired in yet.",
        )

    def housekeeping(self) -> StepResult:
        src = self.paths.journal
        if not src.exists():
            return StepResult("housekeeping", "ok", "Nothing to back up yet.")
        self.paths.backups.mkdir(parents=True, exist_ok=True)
        dest = self.paths.backups / f"journal-{self.now():%Y%m%dT%H%M%S}.sqlite"
        with sqlite3.connect(src) as a, sqlite3.connect(dest) as b:
            a.backup(b)
        olds = sorted(self.paths.backups.glob("journal-*.sqlite"))[:-KEEP_BACKUPS]
        for o in olds:
            o.unlink()
        return StepResult(
            "housekeeping", "ok", f"Journal backed up ({min(KEEP_BACKUPS, len(olds) + 1)} kept)."
        )

    def summary(self, db: SQLiteStore, results: list[StepResult]) -> StepResult:
        bad = [r for r in results if r.status == "fail"]
        trades = decode_json(db.read("trades", PAPER_RUN), "trades")
        total = sum(t["net_usd"] or 0 for t in trades)
        champ = next((r.message for r in results if r.step == "models"), "")
        head = "Something needs a look." if bad else "All steps passed."
        return StepResult(
            "summary",
            "fail" if bad else "ok",
            f"{head} Paper account: {len(trades)} trades, ${total:+,.0f}. {champ}",
        )


def notify_user(title: str, message: str) -> None:
    """A macOS notification, plus an optional ntfy.sh phone push (NTFY_TOPIC)."""
    if sys.platform == "darwin":
        script = f"display notification {json.dumps(message[:200])} with title {json.dumps(title)}"
        subprocess.run(["osascript", "-e", script], check=False, capture_output=True)
    topic = os.environ.get("NTFY_TOPIC")
    if topic:
        import urllib.request

        req = urllib.request.Request(
            f"https://ntfy.sh/{topic}", data=message[:1000].encode(), headers={"Title": title}
        )
        with contextlib.suppress(OSError):
            urllib.request.urlopen(req, timeout=10)
