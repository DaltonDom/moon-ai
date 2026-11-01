"""What the dashboard shows, read from the journal and the runs folder.

docs/design.md, "Dashboard". Plain functions over plain data, so each view is
tested against a fixture journal without a web server.

- Every number on Today, Trades and the paper side of Setups comes from the
  `paper` run only. Backtest numbers can't leak into the go-live bar.
- Money is in dollars first; R and the advanced statistics come alongside.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from moon_ai.backtest.stats import metrics
from moon_ai.config import Config
from moon_ai.journal import SQLiteStore, decode_json
from moon_ai.nightly.job import PAPER_RUN, Paths
from moon_ai.sessions import to_ny, trading_day
from moon_ai.setups import load_setup_defaults

# The go-live bar (docs/design.md, "Phases & where they run").
GOAL_TRADES = 200
GOAL_MONTHS = 3.0
GOAL_PROFIT_FACTOR = 1.3
GOAL_MAX_DIP_PCT = 10.0
STALE_NIGHTLY_HOURS = 36
REVIEW_RETRIES = 3


@dataclass
class Journal:
    """One read of the paper run: candidates, trades, reviews, models, events."""

    candidates: dict[str, dict[str, Any]]
    trades: list[dict[str, Any]]  # closed and open, in entry order
    reviews: dict[str, dict[str, Any]]
    models: list[dict[str, Any]]
    events: list[dict[str, Any]]

    @classmethod
    def empty(cls) -> Journal:
        return cls({}, [], {}, [], [])

    @classmethod
    def load(cls, path: Path) -> Journal:
        if not path.exists():
            return cls.empty()
        db = SQLiteStore(path)
        try:
            cands = decode_json(db.read("candidates", PAPER_RUN), "candidates")
            trades = decode_json(db.read("trades", PAPER_RUN), "trades")
            reviews = decode_json(db.read("reviews", PAPER_RUN), "reviews")
            models = decode_json(db.read("models"), "models")
            events = decode_json(db.read("events", PAPER_RUN), "events")
        finally:
            db.close()
        return cls(
            {c["candidate_id"]: c for c in cands},
            sorted(trades, key=lambda t: t["entry_time"]),
            {r["candidate_id"]: r for r in reviews},
            models,
            events,
        )

    @property
    def closed(self) -> list[dict[str, Any]]:
        done = [t for t in self.trades if t["exit_time"] is not None and t["net_usd"] is not None]
        return sorted(done, key=lambda t: t["exit_time"])


# --- shared pieces -------------------------------------------------------------------


def money_stats(trades: list[dict[str, Any]], account_usd: float) -> dict[str, Any]:
    """Dollar-first numbers for a list of closed trades, in exit order."""
    usd = [t["net_usd"] for t in trades]
    r = [t["r"] or 0.0 for t in trades]
    days: dict[date, float] = defaultdict(float)
    for t in trades:
        days[trading_day(t["exit_time"])] += t["r"] or 0.0
    m = metrics(r, usd, list(days.values()))
    wins = [u for u in usd if u > 0]
    losses = [u for u in usd if u <= 0]
    equity = account_usd + np.concatenate([[0.0], np.cumsum(usd)])
    peaks = np.maximum.accumulate(equity)
    dips = peaks - equity
    worst = int(np.argmax(dips)) if len(dips) else 0
    return {
        "trades": len(usd),
        "net_usd": float(sum(usd)),
        "avg_usd": float(np.mean(usd)) if usd else None,
        "wins": len(wins),
        "win_rate": m.win_rate if usd else None,
        "avg_win_usd": float(np.mean(wins)) if wins else None,
        "avg_loss_usd": float(np.mean(losses)) if losses else None,
        "profit_factor": None
        if not usd or m.profit_factor == float("inf")
        else float(m.profit_factor),
        "max_dip_usd": float(dips.max()) if len(dips) else 0.0,
        "max_dip_pct": float(dips[worst] / peaks[worst] * 100) if len(dips) else 0.0,
        "advanced": {
            "expectancy_r": m.expectancy_r if usd else None,
            "net_r": m.net_r,
            "sharpe": m.sharpe,
            "sortino": m.sortino,
            "max_drawdown_r": m.max_drawdown_r,
        },
    }


def _setup_title(setup: str) -> str:
    d = load_setup_defaults().get(setup)
    return d.title if d else setup


def trade_row(j: Journal, t: dict[str, Any]) -> dict[str, Any]:
    c = j.candidates.get(t["candidate_id"], {})
    rv = j.reviews.get(t["candidate_id"])
    return {
        "candidate_id": t["candidate_id"],
        "setup": c.get("setup"),
        "setup_title": _setup_title(c.get("setup", "")),
        "side": c.get("side"),
        "session": trading_day(t["entry_time"]).isoformat(),
        "entry_time": t["entry_time"].isoformat(),
        "exit_time": t["exit_time"].isoformat() if t["exit_time"] else None,
        "exit_reason": t["exit_reason"],
        "open": t["exit_time"] is None,
        "net_usd": t["net_usd"],
        "r": t["r"],
        "review": _review_word(rv),
        "bucket": rv["bucket"] if rv and rv["status"] == "done" else None,
        "has_chart": bool(t["chart_path"]),
    }


def _review_word(rv: dict[str, Any] | None) -> str:
    if rv is None:
        return "not reviewed yet"
    if rv["status"] == "done":
        return rv["bucket"] or "reviewed"
    if rv["status"] == "failed":
        return f"review failed after {REVIEW_RETRIES} tries"
    return "Claude review pending"


# --- nightly runs --------------------------------------------------------------------


def nightly_runs(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Nightly runs, newest first, each with its steps in order."""
    by_run: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in events:
        if e["data"] and "run" in e["data"]:
            by_run[e["data"]["run"]].append(e)
    out = []
    for stamp in sorted(by_run, reverse=True):
        steps = sorted(by_run[stamp], key=lambda e: e["ts"])
        out.append(
            {
                "run": stamp,
                "ran_at": steps[0]["ts"].isoformat(),
                "status": "fail" if any(s["status"] == "fail" for s in steps) else "ok",
                "sessions": sorted(
                    {s["data"]["session"] for s in steps if s["data"].get("session")}
                ),
                "steps": [
                    {"step": s["step"], "status": s["status"], "message": s["message"]}
                    for s in steps
                ],
            }
        )
    return out


# --- the six views -------------------------------------------------------------------


def today(j: Journal, config: Config, now: datetime, proposals: int = 0) -> dict[str, Any]:
    account = config.risk.account_usd
    closed = j.closed
    s = money_stats(closed, account)
    first = closed[0]["entry_time"] if closed else None
    months = (now - first).days / 30.44 if first else 0.0
    goals = [
        _goal("trades", "Number of trades", s["trades"], GOAL_TRADES, s["trades"] >= GOAL_TRADES),
        _goal("months", "Time on paper", round(months, 1), GOAL_MONTHS, months >= GOAL_MONTHS),
        _goal(
            "profit_factor",
            "Profit factor",
            s["profit_factor"],
            GOAL_PROFIT_FACTOR,
            s["profit_factor"] is not None and s["profit_factor"] >= GOAL_PROFIT_FACTOR,
        ),
        _goal(
            "max_dip_pct",
            "Biggest dip",
            round(s["max_dip_pct"], 2),
            GOAL_MAX_DIP_PCT,
            bool(closed) and s["max_dip_pct"] <= GOAL_MAX_DIP_PCT,
        ),
    ]
    runs = nightly_runs(j.events)
    last = runs[0] if runs else None
    return {
        "account_usd": account,
        "goals": goals,
        "goals_met": sum(g["ok"] for g in goals),
        "stats": s,
        "last_night": _last_night(j, last),
        "needs_you": needs_you(j, now, last, proposals),
        "equity": _equity(closed),
        "calendar": _calendar(closed),
    }


def _goal(key: str, title: str, value: Any, need: float, ok: Any) -> dict[str, Any]:
    return {"key": key, "title": title, "value": value, "need": need, "ok": bool(ok)}


def _last_night(j: Journal, last: dict[str, Any] | None) -> dict[str, Any] | None:
    if last is None:
        return None
    sessions = set(last["sessions"])
    trades = [
        trade_row(j, t) for t in j.trades if trading_day(t["entry_time"]).isoformat() in sessions
    ]
    skipped: dict[str, int] = defaultdict(int)
    for c in j.candidates.values():
        if trading_day(c["decision_time"]).isoformat() in sessions and c["status"] != "taken":
            skipped[c["status"]] += 1
    return {
        **last,
        "trades": trades,
        "net_usd": sum(t["net_usd"] or 0 for t in trades),
        "skipped": dict(skipped),
    }


def needs_you(
    j: Journal, now: datetime, last: dict[str, Any] | None, proposals: int
) -> list[dict[str, str]]:
    """Things the user should act on or know about, most urgent first."""
    out = []
    if last is None:
        out.append(
            {
                "kind": "setup",
                "title": "The nightly run hasn't run yet",
                "detail": "Install it with `uv run moon-ai nightly install`.",
            }
        )
    else:
        age = now - datetime.fromisoformat(last["ran_at"])
        if age > timedelta(hours=STALE_NIGHTLY_HOURS):
            out.append(
                {
                    "kind": "stale",
                    "title": f"The nightly run last ran {age.days} day(s) ago",
                    "detail": "Is the Mac asleep or the launch agent off? "
                    "Check with `uv run moon-ai nightly status`.",
                }
            )
        for s in last["steps"]:
            if s["status"] == "fail":
                out.append(
                    {
                        "kind": "fail",
                        "title": f"Last night's {s['step']} failed",
                        "detail": s["message"],
                    }
                )
    if proposals:
        out.append(
            {
                "kind": "proposal",
                "title": f"{proposals} proposed change(s) to approve",
                "detail": "See the Changes page. Nothing changes without your OK.",
            }
        )
    failed = [r for r in j.reviews.values() if r["status"] == "failed"]
    late = [r for r in j.reviews.values() if r["status"] == "pending" and (r["attempts"] or 0) > 0]
    if failed:
        out.append(
            {
                "kind": "review",
                "title": f"{len(failed)} trade review(s) failed",
                "detail": f"Claude couldn't review them after {REVIEW_RETRIES} tries. "
                "They're listed in the weekly report; trading isn't affected.",
            }
        )
    if late:
        out.append(
            {
                "kind": "review",
                "title": f"{len(late)} trade review(s) late",
                "detail": "Claude will retry tonight. Nothing to do unless it fails "
                f"{REVIEW_RETRIES} times.",
            }
        )
    return out


def _equity(closed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out, cum, peak = [], 0.0, 0.0
    for t in closed:
        cum += t["net_usd"]
        peak = max(peak, cum)
        out.append(
            {
                "candidate_id": t["candidate_id"],
                "t": t["exit_time"].isoformat(),
                "profit_usd": cum,
                "dip_usd": cum - peak,
            }
        )
    return out


def _calendar(closed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    days: dict[date, list[float]] = defaultdict(list)
    for t in closed:
        days[trading_day(t["exit_time"])].append(t["net_usd"])
    return [
        {"day": d.isoformat(), "net_usd": sum(v), "trades": len(v)} for d, v in sorted(days.items())
    ]


def setups(j: Journal, config: Config, runs_root: Path) -> list[dict[str, Any]]:
    """Each setup: its window, the backtest verdict and checks, and its paper results."""
    verdicts = _verdicts(runs_root)
    by_setup: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in j.closed:
        c = j.candidates.get(t["candidate_id"])
        if c:
            by_setup[c["setup"]].append(t)
    out = []
    defaults = load_setup_defaults()
    for name in sorted(defaults, key=lambda n: defaults[n].params.priority):
        d = defaults[name]
        v = verdicts.get(name)
        trades = by_setup.get(name, [])
        out.append(
            {
                "setup": name,
                "title": d.title,
                "window": d.params.window,
                "verdict": v["verdict"] if v else None,
                "trial": v["trial"] if v else None,
                "reasons": v["reasons"] if v else [],
                "trials_run": len(v["trials_run"]) if v else 0,
                "rescue_trials": len(d.rescue),
                "checks": v.get("checks", {}) if v else {},
                "risk_per_trade_usd": config.risk.account_usd
                * config.risk.risk_per_trade_pct
                / 100,
                "paper": money_stats(trades, config.risk.account_usd),
                "paper_curve": [float(x) for x in np.cumsum([t["net_usd"] for t in trades])],
            }
        )
    return out


def _verdicts(runs_root: Path) -> dict[str, dict[str, Any]]:
    path = runs_root / "verdicts.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return {v["setup"]: v for v in data.get("setups", [])}


def models(j: Journal) -> dict[str, Any]:
    """Who's in charge, who's in tryout and who retired. Rules-only when no champion."""
    rows = sorted(j.models, key=lambda m: m["created_at"])
    plain = [
        {
            "model_id": m["model_id"],
            "role": m["role"],
            "created_at": m["created_at"].isoformat(),
            "train_end": m["train_end"].isoformat() if m["train_end"] else None,
            "holdout_checks": m["holdout_checks"],
            "records": m["records"] or {},
        }
        for m in rows
    ]
    champ = next((m for m in plain if m["role"] == "champion"), None)
    return {
        "in_charge": champ["model_id"] if champ else "rules-only",
        "champion": champ,
        "challengers": [m for m in plain if m["role"] == "challenger"],
        "retired": [m for m in plain if m["role"] == "retired"],
    }


TRADE_FILTERS = ("all", "wins", "losses", "open")


def trades(
    j: Journal,
    filter: str = "all",
    setup: str | None = None,
    bucket: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    rows = [trade_row(j, t) for t in reversed(j.trades)]
    if filter == "wins":
        rows = [r for r in rows if (r["net_usd"] or 0) > 0]
    elif filter == "losses":
        rows = [r for r in rows if not r["open"] and (r["net_usd"] or 0) <= 0]
    elif filter == "open":
        rows = [r for r in rows if r["open"]]
    elif filter != "all":
        raise ValueError(f"unknown filter {filter!r}; use one of {', '.join(TRADE_FILTERS)}")
    if setup:
        rows = [r for r in rows if r["setup"] == setup]
    if bucket:
        rows = [r for r in rows if r["bucket"] == bucket]
    return rows[:limit]


def trade_detail(j: Journal, candidate_id: str) -> dict[str, Any] | None:
    t = next((t for t in j.trades if t["candidate_id"] == candidate_id), None)
    c = j.candidates.get(candidate_id)
    if t is None or c is None:
        return None
    rv = j.reviews.get(candidate_id)
    return {
        **trade_row(j, t),
        "entry": t["entry_price"],
        "exit": t["exit_price"],
        "stop": c["stop"],
        "target": c["target"],
        "decision_time": c["decision_time"].isoformat(),
        "mae_r": t["mae_r"],
        "mfe_r": t["mfe_r"],
        "rules": c["rule_results"] or {},
        "confidence": c["ml_p"],
        "confidence_needed": c["ml_threshold"],
        "review_fields": rv["fields"] if rv and rv["status"] == "done" else None,
    }


def weekly_list(reports_root: Path) -> list[dict[str, str]]:
    folder = reports_root / "weekly"
    if not folder.exists():
        return []
    return [{"week": p.stem} for p in sorted(folder.glob("*-W*.md"), reverse=True)]


def weekly_report(reports_root: Path, week: str) -> str | None:
    if not _is_week(week):
        return None
    path = reports_root / "weekly" / f"{week}.md"
    return path.read_text() if path.exists() else None


def _is_week(s: str) -> bool:
    year, _, w = s.partition("-W")
    return year.isdigit() and len(year) == 4 and w.isdigit() and 1 <= int(w) <= 53


def health(paths: Paths, j: Journal, now: datetime) -> dict[str, Any]:
    runs = nightly_runs(j.events)
    last = runs[0] if runs else None
    age = (now - datetime.fromisoformat(last["ran_at"])) if last else None
    return {
        "ok": last is not None
        and last["status"] == "ok"
        and age is not None
        and age <= timedelta(hours=STALE_NIGHTLY_HOURS),
        "journal": paths.journal.exists(),
        "last_nightly": last["ran_at"] if last else None,
        "last_nightly_status": last["status"] if last else None,
        "hours_since_nightly": round(age.total_seconds() / 3600, 1) if age else None,
        "now": now.astimezone(UTC).isoformat(),
        "now_ny": to_ny(now).isoformat(),
    }


def last_protocol_window(runs_root: Path) -> tuple[date, date] | None:
    """The date range of the last `backtest --all`, the default for a re-test."""
    path = runs_root / "verdicts.json"
    if not path.exists():
        return None
    start, end = json.loads(path.read_text())["window"]
    return date.fromisoformat(start), date.fromisoformat(end)
