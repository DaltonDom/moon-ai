import math
from datetime import date, timedelta

import pytest

from moon_ai.backtest.frozen import FIXTURE_STORE
from moon_ai.backtest.runner import run_backtest
from moon_ai.config import load_config
from moon_ai.data.news import Blackout, NewsEvent, load_events
from moon_ai.data.store import BarStore
from moon_ai.journal import decode_json, read_run
from moon_ai.ml.dataset import build_dataset, candidate_from_row
from moon_ai.ml.features import build, daily_from_bars
from moon_ai.ml.labels import label_candidate
from moon_ai.setups import load_setup_defaults

CFG = load_config()


@pytest.fixture(scope="module")
def ote_run(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("runs")
    return run_backtest(
        "ote_pullback",
        date(2026, 9, 28),
        date(2026, 10, 24),
        store_root=FIXTURE_STORE,
        runs_root=tmp,
        run_id="ote",
        second_bars=False,
    )


@pytest.fixture(scope="module")
def bars():
    return BarStore(FIXTURE_STORE).load("MNQ.v.0", date(2026, 9, 27), date(2026, 10, 24))


def test_labels_agree_with_the_journal(ote_run, bars):
    cands = {
        c["candidate_id"]: c
        for c in decode_json(read_run(ote_run.folder, "candidates"), "candidates")
    }
    trades = decode_json(read_run(ote_run.folder, "trades"), "trades")
    assert trades
    blackout = Blackout(load_events(), CFG.ict)
    for t in trades:
        cand = candidate_from_row(cands[t["candidate_id"]], CFG)
        lab = label_candidate(cand, bars, CFG, blackout)
        assert lab is not None
        assert lab.label == (1 if t["exit_reason"] == "target" else 0)
        assert lab.exit_time == t["exit_time"]
        # 1 lot vs the sized trade: same R up to commission rounding.
        assert math.isclose(lab.net_r, t["r"], abs_tol=0.02)


def test_unfilled_entries_get_no_label_and_blackouts_delay_the_order(ote_run, bars):
    row = decode_json(read_run(ote_run.folder, "candidates"), "candidates")[0]
    cand = candidate_from_row(row, CFG)
    from dataclasses import replace

    far = replace(cand, entry=cand.stop + (0.25 if cand.side == "long" else -0.25))
    assert label_candidate(far, bars, CFG) is None
    ev = NewsEvent("x", "CPI", "BLS", cand.decision_time + timedelta(minutes=5), True, "")
    blocked_to = Blackout([ev], CFG.ict).window_at(cand.decision_time).end
    late = replace(cand, entry_deadline=blocked_to - timedelta(minutes=1))
    assert label_candidate(late, bars, CFG, Blackout([ev], CFG.ict)) is None


def test_features_never_see_past_the_decision(ote_run, bars):
    """The truncation test: cutting every input at decision time gives the same vector."""
    events = load_events()
    daily_all = daily_from_bars(bars)
    window = CFG.sessions.windows[load_setup_defaults()["ote_pullback"].params.window]
    rows = decode_json(read_run(ote_run.folder, "candidates"), "candidates")
    assert len(rows) >= 5
    for row in rows:
        cand = candidate_from_row(row, CFG)
        full = build(cand, bars, daily_all, events, CFG, window)
        cut_bars = [b for b in bars if b.ts_close <= cand.decision_time]
        cut = build(
            cand,
            cut_bars,
            daily_from_bars(cut_bars),
            [e for e in events if e.scheduled or e.at <= cand.decision_time],
            CFG,
            window,
        )
        assert full == cut, cand.decision_time


def test_dataset_rows(ote_run):
    ds = build_dataset(ote_run.folder, store_root=FIXTURE_STORE)
    assert ds.height >= 5
    assert set(ds["label"].unique()) <= {0, 1}
    assert {"f_setup", "f_stop_ticks", "f_bias_agree_count", "f_min_to_next_event"} <= set(
        ds.columns
    )
    assert (ds["exit_time"] > ds["decision_time"]).all()
