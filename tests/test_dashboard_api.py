"""The dashboard API against a fixture journal (#53)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from moon_ai.config import load_config
from moon_ai.dashboard import data
from moon_ai.dashboard.api import create_app
from moon_ai.dashboard.jobs import Job, JobQueue
from moon_ai.dashboard.proposals import NoGitHub, RestGitHub, stage
from moon_ai.journal import SQLiteStore
from moon_ai.nightly.job import PAPER_RUN, Paths

CFG = load_config()
NOW = datetime(2026, 10, 30, 23, 0, tzinfo=UTC)  # Friday 19:00 New York
FIRST = datetime(2026, 7, 1, 14, 10, tzinfo=UTC)  # 10:10 New York
WRITE = {"X-Moon-AI": "1"}


def _cand(i: int, setup: str, t: datetime, status: str = "taken") -> dict:
    return {
        "candidate_id": f"{PAPER_RUN}:{setup}:{t.isoformat()}:long",
        "run_id": PAPER_RUN,
        "setup": setup,
        "symbol": "MNQ.v.0",
        "side": "long",
        "decision_time": t,
        "entry_type": "limit",
        "entry": 20_000.0,
        "stop": 19_990.0,
        "target": 20_020.0,
        "timeout": t + timedelta(hours=1),
        "rule_results": {"in_window": True, "swept_liquidity": True},
        "features": {},
        "feature_set": "v1",
        "ml_p": 0.55,
        "ml_threshold": 0.4,
        "status": status,
        "tags": [],
    }


def make_journal(root: Path, n: int = 12, net=None, ran_at: datetime = NOW) -> Paths:
    """`n` paper trades, one a weekday, alternating +$500 / -$250 unless `net` is given."""
    paths = Paths(root / "data")
    db = SQLiteStore(paths.journal)
    db.start_run({"run_id": PAPER_RUN, "kind": "paper", "created_at": FIRST, "account_usd": 50_000})
    t, sessions = FIRST, []
    for i in range(n):
        setup = "ny_am_silver_bullet" if i % 3 else "ny_pm_silver_bullet"
        c = _cand(i, setup, t)
        db.insert("candidates", c)
        usd = net[i] if net else (500.0 if i % 2 == 0 else -250.0)
        db.insert(
            "trades",
            {
                "candidate_id": c["candidate_id"],
                "run_id": PAPER_RUN,
                "entry_time": t + timedelta(minutes=1),
                "exit_time": t + timedelta(minutes=30),
                "entry_price": 20_000.0,
                "exit_price": 20_020.0 if usd > 0 else 19_990.0,
                "exit_reason": "target" if usd > 0 else "stop",
                "r": usd / 250,
                "net_usd": usd,
                "chart_path": f"data/charts/{i}.png" if i == 0 else None,
            },
        )
        sessions.append(t.date())
        last_t = t
        t += timedelta(days=1 if t.weekday() < 4 else 3)
    last = _cand(99, "ny_am_silver_bullet", last_t + timedelta(minutes=5), "skipped:ml")
    db.insert("candidates", last)
    first_id = _cand(0, "ny_pm_silver_bullet", FIRST)["candidate_id"]
    db.set_review(
        first_id,
        run_id=PAPER_RUN,
        status="done",
        attempts=1,
        bucket="good_won",
        fields={"summary": "clean"},
    )
    db.insert(
        "models",
        {
            "model_id": "m1",
            "created_at": FIRST,
            "recipe": {},
            "role": "champion",
            "records": {"pf": 1.4},
        },
    )
    db.insert(
        "models",
        {"model_id": "m2", "created_at": NOW, "recipe": {}, "role": "challenger", "records": {}},
    )
    stamp = f"{ran_at:%Y%m%dT%H%M%S}-abc123"
    for k, (step, status, msg, extra) in enumerate(
        [
            ("preflight", "ok", "Ready.", {}),
            ("replay", "ok", "1 setup found", {"session": sessions[-1].isoformat()}),
            ("summary", "ok", "All steps passed.", {}),
        ]
    ):
        db.insert(
            "events",
            {
                "event_id": f"{stamp}:{step}",
                "run_id": PAPER_RUN,
                "ts": ran_at + timedelta(seconds=k),
                "step": step,
                "status": status,
                "message": msg,
                "data": {**extra, "run": stamp},
            },
        )
    db.close()
    return paths


class FakeGitHub:
    def __init__(self, issues=None):
        self.issues = (
            issues
            if issues is not None
            else [
                {
                    "number": 14,
                    "title": "London: wait 2 candles",
                    "body": "why",
                    "state": "open",
                    "labels": [{"name": "proposal"}],
                },
                {
                    "number": 13,
                    "title": "NY PM: skip Fed minutes",
                    "body": "",
                    "state": "open",
                    "labels": [{"name": "proposal"}, {"name": "approved"}, {"name": "test-passed"}],
                },
                {
                    "number": 12,
                    "title": "In test",
                    "body": "",
                    "state": "open",
                    "labels": [{"name": "proposal"}, {"name": "approved"}],
                },
            ]
        )
        self.calls: list[tuple] = []

    def proposals(self):
        return self.issues

    def add_label(self, number, label):
        self.calls.append(("label", number, label))

    def comment(self, number, body):
        self.calls.append(("comment", number))

    def close(self, number, reason):
        self.calls.append(("close", number, reason))


def client(tmp_path: Path, paths: Paths | None = None, gh=None, runner=None) -> TestClient:
    paths = paths or make_journal(tmp_path)
    fake = gh or FakeGitHub()
    app = create_app(
        paths=paths,
        config=CFG,
        reports_root=tmp_path / "reports",
        github=lambda: fake,
        jobs=JobQueue(
            paths.root / "jobs",
            runner=runner or (lambda j, log: (0, "report.html")),
            now=lambda: NOW,
        ),
        now=lambda: NOW,
    )
    return TestClient(app, base_url="http://localhost")


# --- safety ------------------------------------------------------------------------


def test_only_localhost_hosts_are_answered(tmp_path):
    c = client(tmp_path)
    assert c.get("/api/health").status_code == 200
    evil = TestClient(c.app, base_url="http://evil.example")
    assert evil.get("/api/health").status_code == 400


def test_writes_need_the_custom_header(tmp_path):
    c = client(tmp_path)
    assert c.post("/api/backtests", json={"setup": "ny_am_silver_bullet"}).status_code == 403
    assert c.post("/api/proposals/14/approve").status_code == 403


# --- Today -------------------------------------------------------------------------


def test_today_reports_the_go_live_goals_in_dollars(tmp_path):
    body = client(tmp_path).get("/api/today").json()
    s = body["stats"]
    assert s["trades"] == 12 and s["net_usd"] == 6 * 500 - 6 * 250
    assert s["wins"] == 6 and s["win_rate"] == 0.5
    assert s["profit_factor"] == pytest.approx(2.0)
    assert s["avg_win_usd"] == 500 and s["avg_loss_usd"] == -250
    goals = {g["key"]: g for g in body["goals"]}
    assert not goals["trades"]["ok"] and goals["trades"]["need"] == 200
    assert goals["months"]["ok"]  # July to the end of October
    assert goals["profit_factor"]["ok"] and goals["max_dip_pct"]["ok"]
    assert body["goals_met"] == 3
    assert len(body["equity"]) == 12 and body["equity"][-1]["profit_usd"] == 1500
    assert body["equity"][1]["dip_usd"] == -250
    assert sum(d["net_usd"] for d in body["calendar"]) == 1500


def test_the_biggest_dip_is_a_percent_of_the_peak(tmp_path):
    paths = make_journal(tmp_path, n=4, net=[1000.0, -2000.0, -3000.0, 500.0])
    s = client(tmp_path, paths).get("/api/today").json()["stats"]
    assert s["max_dip_usd"] == 5000
    assert s["max_dip_pct"] == pytest.approx(5000 / 51_000 * 100)


def test_last_night_lists_its_sessions_trades_and_skips(tmp_path):
    night = client(tmp_path).get("/api/today").json()["last_night"]
    assert night["status"] == "ok" and [s["step"] for s in night["steps"]] == [
        "preflight",
        "replay",
        "summary",
    ]
    assert len(night["trades"]) == 1 and night["sessions"] == [night["trades"][0]["session"]]
    assert night["skipped"] == {"skipped:ml": 1}


def test_needs_you_flags_a_stale_nightly_run_and_proposals(tmp_path):
    paths = make_journal(tmp_path, ran_at=NOW - timedelta(days=3))
    items = client(tmp_path, paths).get("/api/today").json()["needs_you"]
    kinds = [i["kind"] for i in items]
    assert kinds[0] == "stale" and "proposal" in kinds
    assert next(i for i in items if i["kind"] == "proposal")["title"].startswith("2 ")


def test_an_empty_journal_still_loads(tmp_path):
    c = client(tmp_path, Paths(tmp_path / "nothing"))
    body = c.get("/api/today").json()
    assert body["stats"]["trades"] == 0 and body["goals_met"] == 0
    assert body["needs_you"][0]["kind"] == "setup"
    assert c.get("/api/trades").json() == []
    assert c.get("/api/models").json()["in_charge"] == "rules-only"
    assert not c.get("/api/health").json()["ok"]


# --- Setups, Models, Trades -------------------------------------------------------


def test_setups_combine_the_verdict_with_paper_results(tmp_path):
    paths = make_journal(tmp_path)
    runs = paths.root / "runs"
    runs.mkdir(parents=True)
    (runs / "verdicts.json").write_text(
        json.dumps(
            {
                "window": ["2019-01-01", "2026-06-30"],
                "setups": [
                    {
                        "setup": "ny_am_silver_bullet",
                        "title": "x",
                        "verdict": "go-forward",
                        "trial": "default",
                        "reasons": [],
                        "report": "r.html",
                        "trials_run": ["default"],
                        "checks": {"trades": 300, "edge_r": 0.2, "dsr": 0.97, "stress_net_r": 12.0},
                    },
                ],
            }
        )
    )
    rows = {s["setup"]: s for s in client(tmp_path, paths).get("/api/setups").json()}
    assert len(rows) == 14  # five ICT setups, five of batch 1 and four of batch 2 (#102)
    am = rows["ny_am_silver_bullet"]
    assert am["verdict"] == "go-forward" and am["checks"]["dsr"] == 0.97
    assert am["window_ny"] == "10:00-11:00" and am["risk_per_trade_usd"] == 500
    assert am["paper"]["trades"] == 8 and len(am["paper_curve"]) == 8
    assert rows["london_sweep_and_reverse"]["verdict"] is None
    assert rows["london_sweep_and_reverse"]["paper"]["trades"] == 0


def test_models_say_who_is_in_charge(tmp_path):
    m = client(tmp_path).get("/api/models").json()
    assert m["in_charge"] == "m1" and m["champion"]["records"] == {"pf": 1.4}
    assert [c["model_id"] for c in m["challengers"]] == ["m2"]


def test_trades_filter_and_detail(tmp_path):
    c = client(tmp_path)
    all_ = c.get("/api/trades").json()
    assert len(all_) == 12 and all_[0]["entry_time"] > all_[-1]["entry_time"]
    assert len(c.get("/api/trades?filter=wins").json()) == 6
    assert len(c.get("/api/trades?filter=losses").json()) == 6
    assert len(c.get("/api/trades?setup=ny_pm_silver_bullet").json()) == 4
    assert c.get("/api/trades?filter=nope").status_code == 422
    first = all_[-1]
    assert first["review"] == "good_won" and first["bucket"] == "good_won"
    assert all_[0]["review"] == "not reviewed yet"
    d = c.get(f"/api/trades/{first['candidate_id']}").json()
    assert d["stop"] == 19_990 and d["target"] == 20_020 and d["confidence"] == 0.55
    assert d["rules"]["swept_liquidity"] and d["review_fields"] == {"summary": "clean"}
    assert c.get("/api/trades/paper:nope").status_code == 404


def test_charts_are_served_only_from_the_charts_folder(tmp_path):
    paths = make_journal(tmp_path)
    c = client(tmp_path, paths)
    first = c.get("/api/trades").json()[-1]["candidate_id"]
    assert c.get(f"/api/trades/{first}/chart").status_code == 404  # not rendered yet
    (paths.root / "charts").mkdir()
    (paths.root / "charts" / "0.png").write_bytes(b"\x89PNG")
    r = c.get(f"/api/trades/{first}/chart")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"


# --- Weekly report, nightly --------------------------------------------------------


def test_weekly_reports_are_listed_and_read(tmp_path):
    c = client(tmp_path)
    assert c.get("/api/weekly").json() == []
    folder = tmp_path / "reports" / "weekly"
    folder.mkdir(parents=True)
    (folder / "2026-W43.md").write_text("# Good week\n")
    (folder / "2026-W44.md").write_text("# Next\n")
    assert [w["week"] for w in c.get("/api/weekly").json()] == ["2026-W44", "2026-W43"]
    assert c.get("/api/weekly/2026-W43").text == "# Good week\n"
    assert c.get("/api/weekly/2026-W01").status_code == 404
    assert c.get("/api/weekly/..%2Fsecrets").status_code == 404


def test_nightly_lists_runs_newest_first(tmp_path):
    runs = client(tmp_path).get("/api/nightly").json()
    assert len(runs) == 1 and runs[0]["status"] == "ok"


# --- actions: backtest jobs --------------------------------------------------------


def test_a_backtest_is_queued_and_run(tmp_path):
    ran: list[Job] = []

    def runner(job, log):
        ran.append(job)
        log.write_text("report card: data/runs/x/report.html\n")
        return 0, "data/runs/x/report.html"

    paths = make_journal(tmp_path)
    c = client(tmp_path, paths, runner=runner)
    r = c.post(
        "/api/backtests",
        headers=WRITE,
        json={"setup": "ny_am_silver_bullet", "start": "2024-01-01", "end": "2024-06-30"},
    )
    assert r.status_code == 202 and r.json()["state"] == "queued"
    q = JobQueue(paths.root / "jobs", runner=runner, now=lambda: NOW)
    done = q.run_next()
    assert done.state == "done" and done.report.endswith("report.html")
    assert ran[0].setup == "ny_am_silver_bullet" and q.run_next() is None
    jobs = c.get("/api/backtests").json()
    assert jobs[0]["state"] == "done"
    assert "report card" in c.get(f"/api/backtests/{jobs[0]['job_id']}/log").text


def test_a_backtest_defaults_to_the_last_protocol_window(tmp_path):
    paths = make_journal(tmp_path)
    c = client(tmp_path, paths)
    assert (
        c.post("/api/backtests", headers=WRITE, json={"setup": "ny_am_silver_bullet"}).status_code
        == 422
    )
    (paths.root / "runs").mkdir(parents=True)
    (paths.root / "runs" / "verdicts.json").write_text(
        json.dumps({"window": ["2019-01-01", "2026-06-30"], "setups": []})
    )
    job = c.post("/api/backtests", headers=WRITE, json={"setup": "ny_am_silver_bullet"}).json()
    assert (job["start"], job["end"]) == ("2019-01-01", "2026-06-30")


def test_bad_backtest_requests_are_refused(tmp_path):
    c = client(tmp_path)
    bad = [
        {"setup": "nope", "start": "2024-01-01", "end": "2024-02-01"},
        {"setup": "ny_am_silver_bullet", "start": "2024-02-01", "end": "2024-01-01"},
        {
            "setup": "ny_am_silver_bullet",
            "trial": "made_up",
            "start": "2024-01-01",
            "end": "2024-02-01",
        },
    ]
    for b in bad:
        assert c.post("/api/backtests", headers=WRITE, json=b).status_code == 422


def test_a_crashed_job_fails_without_stopping_the_queue(tmp_path):
    def boom(job, log):
        raise RuntimeError("no data")

    q = JobQueue(tmp_path / "jobs", runner=boom, now=lambda: NOW)
    q.submit("ny_am_silver_bullet", date(2024, 1, 1), date(2024, 2, 1))
    q.submit("ny_pm_silver_bullet", date(2024, 1, 1), date(2024, 2, 1))
    assert q.run_next().state == "failed" and q.run_next().state == "failed"
    assert "no data" in q.log(q.list()[0].job_id)


def test_a_job_left_running_by_a_restart_is_marked_failed(tmp_path):
    q = JobQueue(tmp_path / "jobs", now=lambda: NOW)
    job = q.submit("ny_am_silver_bullet", date(2024, 1, 1), date(2024, 2, 1))
    job.state = "running"
    q._save(job)
    q.recover()
    assert q.get(job.job_id).state == "failed"


# --- actions: proposals ------------------------------------------------------------


def test_proposals_show_their_stage(tmp_path):
    rows = {p["number"]: p for p in client(tmp_path).get("/api/proposals").json()}
    assert rows[14]["stage"] == "approve test" and rows[14]["needs_you"]
    assert rows[13]["stage"] == "approve change" and rows[13]["needs_you"]
    assert rows[12]["stage"] == "testing" and not rows[12]["needs_you"]


def test_approving_moves_a_proposal_one_stage(tmp_path):
    gh = FakeGitHub()
    c = client(tmp_path, gh=gh)
    assert c.post("/api/proposals/14/approve", headers=WRITE).json()["stage"] == "testing"
    assert ("label", 14, "approved") in gh.calls
    assert c.post("/api/proposals/13/approve", headers=WRITE).json()["stage"] == "live"
    assert ("label", 13, "adopted") in gh.calls
    assert c.post("/api/proposals/12/approve", headers=WRITE).status_code == 409  # still testing
    assert c.post("/api/proposals/99/approve", headers=WRITE).status_code == 404


def test_rejecting_closes_the_issue(tmp_path):
    gh = FakeGitHub()
    c = client(tmp_path, gh=gh)
    assert c.post("/api/proposals/12/reject", headers=WRITE).json()["stage"] == "closed"
    assert ("label", 12, "rejected") in gh.calls and ("close", 12, "not_planned") in gh.calls


def test_without_a_token_proposals_explain_what_to_do(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    paths = make_journal(tmp_path)
    app = create_app(paths=paths, config=CFG, reports_root=tmp_path, now=lambda: NOW)
    c = TestClient(app, base_url="http://localhost")
    r = c.get("/api/proposals")
    assert r.status_code == 503 and "GITHUB_TOKEN" in r.json()["detail"]
    assert c.get("/api/today").status_code == 200  # Today doesn't need GitHub
    with pytest.raises(NoGitHub):
        RestGitHub()


def test_stage_rules():
    lab = lambda *n: [{"name": x} for x in ("proposal", *n)]  # noqa: E731
    assert stage({"state": "open", "labels": lab("approved", "test-passed", "adopted")}) == "live"
    assert stage({"state": "closed", "labels": lab("approved", "test-failed")}) == "closed"
    assert stage({"state": "closed", "labels": lab()}) == "closed"


def test_money_stats_with_no_trades():
    s = data.money_stats([], 50_000)
    assert s["trades"] == 0 and s["profit_factor"] is None and s["max_dip_pct"] == 0


# --- the UI and its launch agent ----------------------------------------------------

UI = Path(__file__).resolve().parents[1] / "src" / "moon_ai" / "dashboard" / "ui"


def test_the_ui_is_served_beside_the_api(tmp_path):
    paths = make_journal(tmp_path)
    app = create_app(paths=paths, config=CFG, static_dir=UI, now=lambda: NOW)
    c = TestClient(app, base_url="http://localhost")
    page = c.get("/")
    assert page.status_code == 200 and '<script src="app.js">' in page.text
    assert c.get("/app.js").status_code == 200 and c.get("/style.css").status_code == 200
    assert c.get("/api/health").status_code == 200  # the static mount doesn't shadow the API


def test_the_ui_calls_only_endpoints_that_exist():
    import re

    js = (UI / "app.js").read_text()
    used = set(re.findall(r'api\("([a-z]+)', js)) | set(re.findall(r'post\(\s*[`"]([a-z]+)', js))
    routes = {
        r.path.split("/")[2] for r in create_app(config=CFG).routes if r.path.startswith("/api/")
    }
    assert used and used <= routes


def test_the_dashboard_agent_stays_up(tmp_path):
    import plistlib

    from moon_ai.nightly import launchd

    path = launchd.install(tmp_path, repo=tmp_path, load=False, label=launchd.DASHBOARD_LABEL)
    p = plistlib.loads(path.read_bytes())
    assert p["Label"] == "com.moonai.dashboard" and p["KeepAlive"] and p["RunAtLoad"]
    assert p["ProgramArguments"][-2:] == ["moon-ai", "dashboard"]
    assert launchd.uninstall(tmp_path, unload=False, label=launchd.DASHBOARD_LABEL)
