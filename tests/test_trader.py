from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest

from moon_ai.bars import InMemoryBarFeed
from moon_ai.broker import SimBroker
from moon_ai.config import load_config
from moon_ai.data.calendar import SessionCalendar
from moon_ai.data.news import Blackout, NewsEvent
from moon_ai.engine import run
from moon_ai.journal import ParquetRun, RunJournal, decode_json, read_run
from moon_ai.setups.base import Candidate, SetupParams
from moon_ai.trader import Trader
from tests.helpers import T0, bar

CFG = load_config()
PRIORITY = {"ny_am_silver_bullet": 1, "ny_pm_silver_bullet": 2, "london_sweep_and_reverse": 3}


class Scripted:
    """A fake setup that proposes given candidates after given bars."""

    def __init__(self, name, script):
        self.name = name
        self.params = SetupParams(priority=PRIORITY.get(name, 9))
        self.script = script  # bar index -> list of candidate kwargs
        self.i = -1

    def scan(self, ctx):
        self.i += 1
        out = []
        for kw in self.script.get(self.i, []):
            base = dict(
                setup=self.name,
                symbol="MNQ.v.0",
                side="long",
                decision_time=ctx.now,
                entry_type="limit",
                entry=99.75,
                stop=98.0,
                target=104.0,
                timeout=ctx.now + timedelta(hours=5),
            )
            out.append(Candidate(**{**base, **kw}))
        return out


QUIET = (100, 100.5, 99.9, 100.25)  # never reaches 99.5 or 104.25


def bars_from(rows, start=T0):
    return [bar(i, *r, start=start) for i, r in enumerate(rows)]


def go(tmp_path, rows, setups, start=T0, config=CFG, **kw):
    store = ParquetRun(tmp_path, {"run_id": "bt", "kind": "backtest"})
    journal = RunJournal(store, "bt", lambda s: config.instrument(s).tick_size)
    trader = Trader(setups, journal, config, **kw)
    run(
        InMemoryBarFeed(bars_from(rows, start)),
        SimBroker(config.broker, config.instrument),
        trader,
        trader.tap(journal),
    )
    trader.finish()
    folder = store.write()
    return {t: decode_json(read_run(folder, t), t) for t in ("candidates", "trades", "orders")}


def statuses(out):
    return [c["status"] for c in out["candidates"]]


def test_a_filled_candidate_is_taken_and_its_trade_written_at_close(tmp_path):
    rows = [QUIET, (100, 100.25, 99.5, 99.75), (100, 104.5, 99.9, 104)]
    out = go(tmp_path, rows, [Scripted("ny_am_silver_bullet", {0: [{}]})])
    assert statuses(out) == ["taken"]
    (t,) = out["trades"]
    assert t["exit_reason"] == "target" and t["entry_price"] == 99.75
    qty = 500 // ((99.75 - 98.0) * 2)  # 1% of $50k over a 1.75-point stop on MNQ
    assert out["orders"][0]["qty"] == qty
    assert t["r"] == pytest.approx(((104 - 99.75) * 2 * qty - 2.0 * qty) / ((99.75 - 98) * 2 * qty))


def test_entry_not_filled_by_its_deadline_is_unfilled(tmp_path):
    rows = [QUIET] * 4
    out = go(
        tmp_path,
        rows,
        [Scripted("ny_am_silver_bullet", {0: [{"entry_deadline": T0 + timedelta(minutes=3)}]})],
    )
    assert statuses(out) == ["unfilled"] and out["trades"] == []


def news(at):
    return NewsEvent("cpi", "CPI", "BLS", at, True, "https://bls.gov")


def test_a_blackout_start_cancels_the_working_entry_and_blocks_new_ones(tmp_path):
    bo = Blackout([news(T0 + timedelta(minutes=20))])  # window 10:05-10:35 NY
    script = {0: [{}], 6: [{}]}
    out = go(tmp_path, [QUIET] * 8, [Scripted("ny_am_silver_bullet", script)], blackout=bo)
    assert statuses(out) == ["unfilled", "skipped:blackout"]


def test_time_out_closes_the_trade_at_market(tmp_path):
    rows = [QUIET, (100, 100.25, 99.5, 99.75), QUIET, QUIET, QUIET]
    out = go(
        tmp_path,
        rows,
        [Scripted("ny_am_silver_bullet", {0: [{"timeout": T0 + timedelta(minutes=3)}]})],
    )
    (t,) = out["trades"]
    assert t["exit_reason"] == "timeout" and t["exit_price"] < 100.25  # market exit pays slippage


def test_positions_are_flat_before_16_00(tmp_path):
    start = datetime(2026, 7, 15, 19, 56, tzinfo=UTC)  # 15:56 New York
    rows = [QUIET, (100, 100.25, 99.5, 99.75), QUIET, QUIET, QUIET]
    out = go(tmp_path, rows, [Scripted("ny_am_silver_bullet", {0: [{}]})], start=start)
    assert out["trades"][0]["exit_reason"] == "flat_by"
    assert out["trades"][0]["exit_time"] <= datetime(2026, 7, 15, 20, 0, tzinfo=UTC)


def test_busy_while_a_trade_is_open_then_the_session_cap(tmp_path):
    rows = [QUIET, (100, 100.25, 99.5, 99.75), QUIET, (100, 104.5, 99.9, 104), QUIET]
    script = {0: [{}], 2: [{}], 4: [{}]}
    out = go(tmp_path / "a", rows, [Scripted("ny_am_silver_bullet", script)])
    # bar 2: the first trade is still open; bar 4: it closed, so a new entry is allowed.
    assert statuses(out)[:2] == ["taken", "skipped:busy"]
    assert statuses(out)[2] == "unfilled"
    cfg = replace(CFG, risk=replace(CFG.risk, max_trades_per_session=1))
    out = go(tmp_path / "b", rows, [Scripted("ny_am_silver_bullet", script)], config=cfg)
    assert statuses(out) == ["taken", "skipped:cap", "skipped:cap"]


def test_daily_stop_blocks_the_rest_of_the_session(tmp_path):
    cfg = replace(CFG, risk=replace(CFG.risk, daily_stop_pct=0.5))
    rows = [QUIET, (100, 100.25, 99.5, 99.75), (99.75, 99.8, 97.5, 97.75), QUIET]
    out = go(tmp_path, rows, [Scripted("ny_am_silver_bullet", {0: [{}], 3: [{}]})], config=cfg)
    assert statuses(out) == ["taken", "skipped:daily_stop"]
    assert out["trades"][0]["exit_reason"] == "stop" and out["trades"][0]["r"] < -1


def test_session_calendar_ml_gate_and_size(tmp_path):
    cal = SessionCalendar(rolls=frozenset({date(2026, 7, 15)}))
    assert statuses(
        go(tmp_path / "a", [QUIET] * 2, [Scripted("ny_am_silver_bullet", {0: [{}]})], calendar=cal)
    ) == ["skipped:session"]
    out = go(
        tmp_path / "b",
        [QUIET] * 2,
        [Scripted("ny_am_silver_bullet", {0: [{}]})],
        ml_gate=lambda c: (0.2, 0.33, False),
    )
    assert statuses(out) == ["skipped:ml"] and out["candidates"][0]["ml_p"] == 0.2
    tiny = replace(CFG, risk=replace(CFG.risk, account_usd=100.0))
    assert statuses(
        go(tmp_path / "c", [QUIET] * 2, [Scripted("ny_am_silver_bullet", {0: [{}]})], config=tiny)
    ) == ["skipped:size"]


def test_london_minimum_stop(tmp_path):
    out = go(tmp_path, [QUIET] * 2, [Scripted("london_sweep_and_reverse", {0: [{}]})])
    assert statuses(out) == ["skipped:london_min_stop"]  # 1.75 points = 7 ticks < 40


def test_same_bar_candidates_are_one_trade_owned_by_priority(tmp_path):
    setups = [
        Scripted("ny_pm_silver_bullet", {0: [{}]}),
        Scripted("ny_am_silver_bullet", {0: [{}]}),
    ]
    out = go(tmp_path, [QUIET] * 2, setups)
    (c,) = out["candidates"]
    assert (c["setup"], c["tags"], c["status"]) == (
        "ny_am_silver_bullet",
        ["ny_pm_silver_bullet"],
        "unfilled",
    )
