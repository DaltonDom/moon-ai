from datetime import UTC, datetime, timedelta

import pytest

from moon_ai.bars import InMemoryBarFeed
from moon_ai.broker import Bracket, Order, Side, SimBroker
from moon_ai.config import BrokerConfig, load_config
from moon_ai.engine import run
from moon_ai.journal import (
    TABLES,
    JournalError,
    ParquetRun,
    RunJournal,
    SQLiteStore,
    candidate_id,
    decode_json,
    read_run,
    stores,
)
from tests.helpers import bar

T = datetime(2026, 10, 27, 14, 14, tzinfo=UTC)


def run_row(run_id, kind):
    return {
        "run_id": run_id,
        "kind": kind,
        "created_at": T,
        "code_commit": "abc123",
        "defaults_hash": "h1",
        "model_id": None,
        "data_start": T - timedelta(days=30),
        "data_end": T,
        "account_usd": 50_000.0,
        "risk_per_trade_usd": 250.0,
        "notes": {"why": "test"},
    }


def sample_rows(run_id):
    cid = candidate_id(run_id, "ny_am_sb", T, "long")
    return {
        "candidates": {
            "candidate_id": cid,
            "run_id": run_id,
            "setup": "ny_am_sb",
            "symbol": "MNQ.v.0",
            "side": "long",
            "decision_time": T,
            "entry_type": "limit",
            "entry": 29600.25,
            "stop": 29592.0,
            "target": 29640.0,
            "timeout": T + timedelta(hours=5),
            "rule_results": {"swept": True, "mss": True},
            "features": {"atr": 8.5, "dow": 2},
            "feature_set": "f1",
            "ml_p": 0.42,
            "ml_threshold": 0.33,
            "status": "taken",
            "label": 1,
            "tags": ["ote"],
        },
        "orders": {
            "order_id": f"{run_id}:o1",
            "run_id": run_id,
            "candidate_id": cid,
            "symbol": "MNQ.v.0",
            "side": "buy",
            "type": "limit",
            "qty": 1,
            "price": 29600.25,
            "stop": 29592.0,
            "target": 29640.0,
            "submitted_at": T,
        },
        "fills": {
            "fill_id": f"{run_id}:o1:1",
            "run_id": run_id,
            "order_id": f"{run_id}:o1",
            "candidate_id": cid,
            "symbol": "MNQ.v.0",
            "side": "buy",
            "qty": 1,
            "price": 29600.25,
            "ts": T + timedelta(minutes=2),
            "reason": "entry",
            "commission": 1.0,
            "slippage_ticks": 0.0,
            "pnl": 0.0,
            "ambiguous": False,
            "resolved_by": None,
        },
        "trades": {
            "candidate_id": cid,
            "run_id": run_id,
            "entry_fill_id": f"{run_id}:o1:1",
            "exit_fill_id": None,
            "entry_time": T + timedelta(minutes=2),
            "exit_time": None,
            "entry_price": 29600.25,
            "exit_price": None,
            "exit_reason": None,
            "mae_r": None,
            "mfe_r": None,
            "r": None,
            "net_usd": None,
            "chart_path": None,
        },
        "events": {
            "event_id": f"{run_id}:replay:1",
            "run_id": run_id,
            "ts": T,
            "step": "replay",
            "status": "ok",
            "message": "1 session",
            "data": {"sessions": 1},
        },
    }


def test_rows_round_trip_through_both_stores(tmp_path):
    db = SQLiteStore(tmp_path / "j.sqlite")
    db.start_run(run_row("paper-1", "paper"))
    pq = ParquetRun(tmp_path / "runs", run_row("bt-1", "backtest"))
    for store, rid in ((db, "paper-1"), (pq, "bt-1")):
        for table, row in sample_rows(rid).items():
            store.insert(table, row)
    folder = pq.write()

    for rid, read in (
        ("paper-1", lambda t: db.read(t, "paper-1")),
        ("bt-1", lambda t: read_run(folder, t)),
    ):
        for table, row in sample_rows(rid).items():
            frame = read(table)
            assert frame.columns == list(TABLES[table])
            assert decode_json(frame, table) == [row]
        assert decode_json(read("runs"), "runs")[0]["schema_version"] == 1


def test_run_kinds_never_mix(tmp_path):
    db = SQLiteStore(tmp_path / "j.sqlite")
    with pytest.raises(JournalError, match="Parquet"):
        db.start_run(run_row("bt", "backtest"))
    with pytest.raises(JournalError, match="SQLite"):
        ParquetRun(tmp_path / "runs", run_row("p", "paper"))
    with pytest.raises(JournalError, match="not in this journal"):
        db.insert("events", sample_rows("nobody")["events"])
    pq = ParquetRun(tmp_path / "runs", run_row("bt-1", "backtest"))
    with pytest.raises(JournalError, match="in run"):
        pq.insert("events", sample_rows("bt-2")["events"])
    with pytest.raises(JournalError, match="can't hold"):
        pq.insert("reviews", {"candidate_id": "x", "run_id": "bt-1"})


def test_rows_are_append_only_except_trade_exits_and_reviews(tmp_path):
    db = SQLiteStore(tmp_path / "j.sqlite")
    db.start_run(run_row("paper-1", "paper"))
    rows = sample_rows("paper-1")
    for table, row in rows.items():
        db.insert(table, row)
    cid = rows["trades"]["candidate_id"]

    with pytest.raises(JournalError, match="append-only"):
        db.insert("candidates", rows["candidates"])
    with pytest.raises(JournalError, match="can't be changed"):
        db.close_trade(cid, entry_price=1.0)

    db.close_trade(
        cid,
        exit_time=T + timedelta(minutes=30),
        exit_price=29640.0,
        exit_reason="target",
        r=4.6,
        net_usd=1150.0,
    )
    trade = decode_json(db.read("trades"), "trades")[0]
    assert (trade["exit_reason"], trade["r"], trade["entry_price"]) == ("target", 4.6, 29600.25)

    db.set_review(cid, run_id="paper-1", status="pending", attempts=1, updated_at=T)
    db.set_review(
        cid,
        status="done",
        attempts=2,
        bucket="good trade, won",
        fields={"reasons": ["sweep_depth_ticks = 6"]},
        updated_at=T,
    )
    review = decode_json(db.read("reviews"), "reviews")[0]
    assert (review["status"], review["attempts"], review["fields"]) == (
        "done",
        2,
        {"reasons": ["sweep_depth_ticks = 6"]},
    )


def test_bad_rows_are_rejected(tmp_path):
    db = SQLiteStore(tmp_path / "j.sqlite")
    db.start_run(run_row("paper-1", "paper"))
    row = sample_rows("paper-1")["candidates"]
    with pytest.raises(JournalError, match="unknown columns"):
        db.insert("candidates", {**row, "colour": "red"})
    with pytest.raises(JournalError, match="status"):
        db.insert("candidates", {**row, "status": "maybe"})
    with pytest.raises(JournalError, match="timezone-aware"):
        db.insert("candidates", {**row, "decision_time": T.replace(tzinfo=None)})


def test_a_written_parquet_run_is_never_rewritten(tmp_path):
    ParquetRun(tmp_path, run_row("bt-1", "backtest")).write()
    with pytest.raises(JournalError, match="new run"):
        ParquetRun(tmp_path, run_row("bt-1", "backtest"))


def test_migrations_run_once_and_newer_files_are_refused(tmp_path):
    path = tmp_path / "j.sqlite"
    assert SQLiteStore(path).version() == 1
    calls = []

    def v2(conn):
        calls.append(1)
        conn.execute("ALTER TABLE events ADD COLUMN severity TEXT")

    assert SQLiteStore(path, migrations=[*stores.MIGRATIONS, v2]).version() == 2
    assert SQLiteStore(path, migrations=[*stores.MIGRATIONS, v2]).version() == 2
    assert calls == [1]
    with pytest.raises(JournalError, match="newer than this code"):
        SQLiteStore(path)


def test_run_journal_records_the_engines_fills_against_their_candidate(tmp_path):
    cfg = load_config()
    pq = ParquetRun(tmp_path, run_row("bt-1", "backtest"))
    journal = RunJournal(pq, "bt-1", lambda s: cfg.instrument(s).tick_size)
    cid = candidate_id("bt-1", "demo", T, "long")

    class BuyOnce:
        done = False

        def on_bar(self, b, ctx):
            if not self.done:
                order = Order(b.symbol, Side.BUY, 1, bracket=Bracket(98.0, 104.0))
                journal.add_order(ctx.broker.submit(order), order, ctx.now, cid)
                self.done = True

    bars = [
        bar(0, 100, 100.5, 99.5, 100),
        bar(1, 100, 100.5, 99.75, 100.25),
        bar(2, 101, 104.5, 100.75, 104.25),
    ]
    broker = SimBroker(BrokerConfig(), cfg.instrument)
    run(InMemoryBarFeed(bars), broker, BuyOnce(), journal)
    fills = decode_json(read_run(pq.write(), "fills"), "fills")

    assert [f["reason"] for f in fills] == ["entry", "target"]
    assert {f["candidate_id"] for f in fills} == {cid}
    assert fills[0]["slippage_ticks"] == 1.0  # NY entry slippage, market order
