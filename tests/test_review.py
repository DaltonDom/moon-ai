"""Claude trade reviews and the weekly report, against a mocked API (#52)."""

from __future__ import annotations

import json
from datetime import date, timedelta
from types import SimpleNamespace as NS

import pytest

from moon_ai.config import load_config
from moon_ai.journal import SQLiteStore, decode_json
from moon_ai.nightly.job import PAPER_RUN
from moon_ai.review import claude
from moon_ai.review.claude import InvalidReview, Reviewer, code_flags, validate
from moon_ai.review.weekly import write_weekly
from tests.test_dashboard_api import NOW, make_journal

CFG = load_config()
GOOD = {
    "bucket": "good_won",
    "summary": "Clean sweep then a strong move. Entry at the gap.",
    "reasons": ["swept_liquidity = true", "in_window held"],
    "setup_quality": "good",
    "confidence": "high",
    "execution_notes": "",
    "follow_up": "Try a 2-candle close-back on London.",
}


def usage(i=20_000, o=1_000):
    return NS(
        input_tokens=i, output_tokens=o, cache_read_input_tokens=0, cache_creation_input_tokens=0
    )


def message(text=None, stop="end_turn", category=None):
    return NS(
        stop_reason=stop,
        stop_details=NS(category=category) if stop == "refusal" else None,
        content=[NS(type="text", text=text if text is not None else json.dumps(GOOD))],
        usage=usage(),
        model=claude.MODEL,
    )


class FakeBatches:
    def __init__(self, answer):
        self.answer = answer  # custom_id -> result, or a callable(custom_id) -> result
        self.created: list[list] = []
        self.status = "ended"

    def create(self, requests):
        self.created.append(requests)
        return NS(id=f"batch{len(self.created)}")

    def retrieve(self, batch_id):
        return NS(processing_status=self.status)

    def results(self, batch_id):
        reqs = self.created[int(batch_id.removeprefix("batch")) - 1]
        for r in reqs:
            yield NS(custom_id=r["custom_id"], result=self.answer(r["custom_id"]))


def client(answer):
    return NS(messages=NS(batches=FakeBatches(answer)))


def ok(_):
    return NS(type="succeeded", message=message())


def reviewer(tmp_path, cl, cap=claude.MONTHLY_CAP_USD):
    paths = make_journal(tmp_path, n=4)
    db = SQLiteStore(paths.journal)
    return Reviewer(db, PAPER_RUN, CFG, cl, paths.root / "charts", now=lambda: NOW, cap_usd=cap), db


def reviews(db):
    return {r["candidate_id"]: r for r in decode_json(db.read("reviews", PAPER_RUN), "reviews")}


def test_submit_then_collect_stores_valid_reviews(tmp_path):
    cl = client(ok)
    r, db = reviewer(tmp_path, cl)
    first = r.run()
    assert first.submitted == 3  # 4 trades, one already reviewed in the fixture
    req = cl.messages.batches.created[0][0]
    p = req["params"]
    assert p["model"] == "claude-opus-5-5" and p["output_config"]["format"]["type"] == "json_schema"
    assert "Journal entry" in p["messages"][0]["content"][-1]["text"]
    assert len(req["custom_id"]) <= 64 and req["custom_id"].isalnum()
    assert sorted(v["status"] for v in reviews(db).values()) == ["done"] + ["submitted"] * 3
    second = r.run()
    assert second.done == 3 and second.submitted == 0
    done = [v for v in reviews(db).values() if v["model"] == claude.MODEL]
    assert len(done) == 3 and all(v["bucket"] == "good_won" for v in done)
    assert done[0]["fields"]["code_flags"] == [] and done[0]["cost_usd"] == pytest.approx(0.05)
    spend = [
        e
        for e in decode_json(db.read("events", PAPER_RUN), "events")
        if e["step"] == "claude_spend"
    ]
    assert len(spend) == 3


def test_a_batch_still_running_is_left_alone(tmp_path):
    cl = client(ok)
    r, _ = reviewer(tmp_path, cl)
    r.run()
    cl.messages.batches.status = "in_progress"
    res = r.run()
    assert res.in_flight == 3 and res.done == 0 and res.submitted == 0


@pytest.mark.parametrize(
    "result,why",
    [
        (
            NS(type="succeeded", message=message(stop="refusal", category="cyber")),
            "declined (cyber)",
        ),
        (NS(type="succeeded", message=message(text="not json")), "invalid answer"),
        (NS(type="errored", error=NS(type="api_error")), "batch request errored"),
    ],
)
def test_failures_retry_then_fail_after_three(tmp_path, result, why):
    cl = client(lambda _: result)
    r, db = reviewer(tmp_path, cl)
    for night in range(4):
        res = r.run()
        if night == 0:
            assert res.submitted == 3
    rows = [v for v in reviews(db).values() if v["status"] in ("failed", "pending", "submitted")]
    assert all(v["status"] == "failed" and v["attempts"] == 3 for v in rows) and len(rows) == 3
    assert why in rows[0]["fields"]["last_error"]


def test_the_monthly_cap_holds_back_reviews(tmp_path):
    cl = client(ok)
    r, _ = reviewer(tmp_path, cl, cap=claude.EST_COST_USD * 2)
    res = r.run()
    assert res.submitted == 2 and res.capped and "monthly cap" in res.message()
    r.run()  # collect: $0.05 x 2 spent, no room for the third
    res = r.run()
    assert res.submitted == 0 and res.capped


def test_validation_rules():
    cite = {"swept_liquidity", "in_window", "sweep_depth_ticks"}
    assert validate(json.dumps(GOOD), [], cite)["code_flags"] == []
    with pytest.raises(InvalidReview, match="rule_break"):
        validate(json.dumps(GOOD), ["failed rule check: x"], cite)
    flagged = {**GOOD, "bucket": "rule_break"}
    assert validate(json.dumps(flagged), ["a flag"], cite)["code_flags"] == ["a flag"]
    with pytest.raises(InvalidReview, match="not in the journal"):
        validate(json.dumps({**GOOD, "reasons": ["made_up_feature = 3"]}), [], cite)
    with pytest.raises(InvalidReview, match="cites no feature"):
        validate(json.dumps({**GOOD, "reasons": ["looked good to me"]}), [], cite)
    with pytest.raises(InvalidReview, match="wrong fields"):
        validate(json.dumps({**GOOD, "extra": 1}), [], cite)
    with pytest.raises(InvalidReview, match="bucket"):
        validate(json.dumps({**GOOD, "bucket": "great"}), [], cite)


def test_code_flags_are_deterministic():
    cand = {"candidate_id": "c", "rule_results": {"in_window": True, "fvg": False}}
    fills = [
        {"reason": "entry", "slippage_ticks": 5.0},
        {"reason": "target", "slippage_ticks": 0.0},
    ]
    orders = [{"candidate_id": "c", "stop": None, "target": 1.0}]
    events = [{"step": "order_rejected", "data": {"candidate_id": "c"}}]
    flags = code_flags(cand, orders, fills, events, CFG)
    assert len(flags) == 4
    assert any("slipped 5" in f for f in flags) and any("fvg" in f for f in flags)
    clean = code_flags({"candidate_id": "c", "rule_results": {"a": True}}, [], [], [], CFG)
    assert clean == []


def test_a_chart_is_rendered_and_sent_with_the_review(tmp_path):
    from moon_ai.bars import Bar

    cl = client(ok)
    paths = make_journal(tmp_path, n=2)
    db = SQLiteStore(paths.journal)

    def bars_for(cand, trade):
        t0 = cand["decision_time"] - timedelta(minutes=90)
        return [
            Bar(
                "MNQ.v.0",
                t0 + timedelta(minutes=i),
                t0 + timedelta(minutes=i + 1),
                20_000 + i % 5,
                20_003 + i % 5,
                19_998 + i % 5,
                20_001 + i % 5,
                10,
                1,
            )
            for i in range(150)
        ]

    r = Reviewer(db, PAPER_RUN, CFG, cl, paths.root / "charts", bars_for=bars_for, now=lambda: NOW)
    r.run()
    content = cl.messages.batches.created[0][0]["params"]["messages"][0]["content"]
    assert content[0]["type"] == "image" and content[0]["source"]["media_type"] == "image/png"
    charts = list((paths.root / "charts").glob("*.png"))
    assert len(charts) == 1 and charts[0].read_bytes()[:4] == b"\x89PNG"
    trade = [
        t
        for t in decode_json(db.read("trades", PAPER_RUN), "trades")
        if t["chart_path"] and "charts/" in t["chart_path"] and "png" in t["chart_path"]
    ]
    assert any(str(charts[0]) == t["chart_path"] for t in trade)


# --- weekly report -------------------------------------------------------------------


class FakeGH:
    def __init__(self):
        self.issues = []

    def create_issue(self, title, body, labels):
        self.issues.append((title, body, labels))
        return {"number": 100 + len(self.issues), "html_url": "https://github.com/x/y/issues/1"}


def proposal_client(props):
    msg = NS(
        stop_reason="end_turn",
        content=[NS(type="text", text=json.dumps({"proposals": props}))],
        usage=NS(input_tokens=10_000, output_tokens=2_000),
    )
    calls = []

    def create(**kw):
        calls.append(kw)
        return msg

    return NS(messages=NS(create=create)), calls


PROP = {
    "title": "London: wait 2 candles for the close back",
    "setup": "london_sweep_and_reverse",
    "change": "close_back_candles 1 -> 2",
    "evidence": "4 of 6 losses closed back on the 2nd candle.",
    "test": "Backtest London with close_back_candles = 2; pass if it clears all four checks.",
}


def test_weekly_report_renders_from_fixture_trades(tmp_path):
    paths = make_journal(tmp_path, n=12)
    db = SQLiteStore(paths.journal)
    saturday = date(2026, 7, 4)  # the first fixture week: Wed Jul 1 to Fri Jul 3
    cl, calls = proposal_client([PROP, {**PROP, "setup": "not_a_setup"}])
    gh = FakeGH()
    path, notes = write_weekly(
        db,
        PAPER_RUN,
        saturday,
        tmp_path / "reports" / "weekly",
        lambda: cl,
        lambda: gh,
        now=lambda: NOW,
    )
    text = path.read_text()
    assert path.name == "2026-W27.md" and notes == []
    assert text.startswith("# Good week: up $750 on 3 trades.")
    assert (
        "## Skipped setups" in text
        and "## Claude's reviews" in text
        and "Good setup, won: 1" in text
    )
    assert "## Trades worth a look" in text and "#trade/paper:" in text
    assert "Model m1 is in charge." in text and "Model m2 is in tryout" in text
    assert len(gh.issues) == 1 and gh.issues[0][2] == ["proposal"]  # the unknown setup was dropped
    assert "[#101]" in text and "close_back_candles 1 -> 2" in gh.issues[0][1]
    assert calls[0]["model"] == "claude-opus-5-5"
    spend = [
        e
        for e in decode_json(db.read("events", PAPER_RUN), "events")
        if e["step"] == "claude_spend"
    ]
    assert spend and spend[0]["data"]["cost_usd"] == pytest.approx(0.08)


def test_weekly_report_without_claude_still_writes(tmp_path):
    paths = make_journal(tmp_path, n=3)
    db = SQLiteStore(paths.journal)
    path, notes = write_weekly(
        db, PAPER_RUN, date(2026, 7, 4), tmp_path / "w", None, None, now=lambda: NOW
    )
    assert "None this week." in path.read_text() and "no Claude API key" in notes[0]


def test_an_empty_week(tmp_path):
    paths = make_journal(tmp_path, n=1)
    db = SQLiteStore(paths.journal)
    path, _ = write_weekly(
        db, PAPER_RUN, date(2026, 10, 31), tmp_path / "w", None, None, now=lambda: NOW
    )
    assert path.read_text().startswith("# No trades this week.")


def test_the_nightly_job_reviews_and_writes_the_saturday_report(tmp_path):
    from moon_ai.nightly.job import NightlyJob, Paths

    paths = make_journal(tmp_path, n=3)
    cl = client(ok)
    cl.messages.create = proposal_client([])[0].messages.create
    saturday = NOW.replace(day=31, hour=23)  # Sat Oct 31 2026, 19:00 New York
    job = NightlyJob(Paths(paths.root), CFG, now=lambda: saturday, claude_factory=lambda: cl)
    db = SQLiteStore(paths.journal)
    r = job.reviews(db)
    assert r.status == "ok" and "2 sent" in r.message
    w = job.weekly(db)
    assert w.status == "ok" and "2026-W44.md" in w.message
    assert (tmp_path / "reports" / "weekly" / "2026-W44.md").exists()


def test_without_a_key_reviews_are_skipped(tmp_path):
    from moon_ai.nightly.job import NightlyJob, Paths

    paths = make_journal(tmp_path, n=1)
    job = NightlyJob(Paths(paths.root), CFG, now=lambda: NOW)
    r = job.reviews(SQLiteStore(paths.journal))
    assert r.status == "skipped" and "ANTHROPIC_API_KEY" in r.message
