from dataclasses import fields
from datetime import UTC, datetime, time, timedelta

import pytest

from moon_ai.config import ConfigError, SessionConfig
from moon_ai.setups import (
    Candidate,
    SetupParams,
    defaults_hash,
    load_setup_defaults,
    register,
)
from moon_ai.setups.base import REGISTRY

D = load_setup_defaults()


ICT = {
    "ny_am_silver_bullet",
    "ny_pm_silver_bullet",
    "london_sweep_and_reverse",
    "ote_pullback",
    "ict_2022_model",
}


def test_the_setups_are_pre_registered_in_priority_order():
    by_priority = sorted(D.values(), key=lambda d: d.params.priority)
    assert [d.name for d in by_priority] == [
        "ny_am_silver_bullet",
        "ny_pm_silver_bullet",
        "london_sweep_and_reverse",
        "ote_pullback",
        "ict_2022_model",
        # Non-ICT batch 1 (#102), pre-registered 2026-11-02.
        "orb_5m",
        "noise_breakout",
        "intraday_momentum",
        "overnight_breakout",
        "gap_fill",
        # Non-ICT batch 2, pre-registered 2026-11-02.
        "orb_high_vol",
        "vwap_pullback",
        "vwap_reversion",
        "turn_of_month",
        # Batch 3 (overnight), pre-registered 2026-11-02.
        "overnight_hold",
        "overnight_after_down",
        "euro_open_drift",
    ]


def test_windows_and_time_outs_follow_the_design():
    w = SessionConfig().windows
    assert w[D["ny_am_silver_bullet"].params.window] == w["ny_am_silver_bullet"]
    assert (w["ny_am_silver_bullet"].start, w["ny_pm_silver_bullet"].start) == (time(10), time(14))
    assert w[D["ote_pullback"].params.window].start == time(8, 30)
    assert D["london_sweep_and_reverse"].params.timeout == time(9, 30)
    ict = {n: d for n, d in D.items() if n in ICT}
    assert {d.params.timeout for n, d in ict.items() if n != "london_sweep_and_reverse"} == {
        time(15, 55)
    }
    # Batch 1 is flat before the 16:00 flat-by rule; intraday momentum holds to 15:59.
    overnight = {"overnight_hold", "overnight_after_down", "euro_open_drift"}
    assert all(d.params.timeout <= time(15, 59) for n, d in D.items() if n not in ICT | overnight)
    # Overnight setups exit before the cash open, inside the same trading day.
    assert all(D[n].params.timeout <= time(9, 30) for n in overnight)


def test_ict_timestamp_changes_are_applied():
    am, pm = D["ny_am_silver_bullet"].params, D["ny_pm_silver_bullet"].params
    assert am.min_objective_points == pm.min_objective_points == 10.0
    assert any(t.changes == {"min_objective_points": 5.0} for t in D["ny_pm_silver_bullet"].rescue)
    london_windows = {
        D["london_sweep_and_reverse"].trial_params(t).window
        for t in D["london_sweep_and_reverse"].rescue
    }
    assert london_windows <= {"london_killzone", "london_silver_bullet"}  # no 02:00-03:00 variant
    assert "extra_silver_bullet" not in {d.params.window for d in D.values()}


@pytest.mark.parametrize("name", sorted(D))
def test_each_rescue_trial_changes_exactly_one_known_parameter(name):
    d = D[name]
    assert 1 <= len(d.rescue) <= 12
    known = {f.name for f in fields(SetupParams)}
    for t in d.rescue:
        (key,) = t.changes
        assert key in known
        assert getattr(d.trial_params(t), key) != getattr(d.params, key)


def write(tmp_path, text):
    p = tmp_path / "defaults.toml"
    p.write_text(text)
    return p


def test_bad_files_are_rejected(tmp_path):
    with pytest.raises(ConfigError, match="unknown keys"):
        load_setup_defaults(write(tmp_path, '[setups.x]\nwindoww = "london_killzone"\n'))
    with pytest.raises(ConfigError, match="unknown window"):
        load_setup_defaults(write(tmp_path, '[setups.x]\nwindow = "lunch"\n'))
    with pytest.raises(ConfigError, match="exactly one"):
        load_setup_defaults(
            write(
                tmp_path,
                "[setups.x]\n[[setups.x.rescue]]\nname='a'\nswing_n = 2\ndisplacement_k = 2.0\n",
            )
        )
    with pytest.raises(ConfigError, match="changes nothing"):
        load_setup_defaults(write(tmp_path, "[setups.x]\n[[setups.x.rescue]]\nswing_n = 1\n"))
    many = "".join(
        f"[[setups.x.rescue]]\nname='t{i}'\nstop_offset_ticks = {i + 2}\n" for i in range(13)
    )
    with pytest.raises(ConfigError, match="max 12"):
        load_setup_defaults(write(tmp_path, "[setups.x]\n" + many))


def test_defaults_hash_tracks_the_file(tmp_path):
    p = write(tmp_path, "[setups.x]\n")
    h = defaults_hash(p)
    assert h == defaults_hash(p) and len(h) == 64
    p.write_text("[setups.x]\nswing_n = 2\n")
    assert defaults_hash(p) != h


T = datetime(2026, 10, 27, 14, 14, tzinfo=UTC)


def cand(**kw):
    base = dict(
        setup="ny_am_silver_bullet",
        symbol="MNQ.v.0",
        side="long",
        decision_time=T,
        entry_type="limit",
        entry=100.0,
        stop=95.0,
        target=115.0,
        timeout=T + timedelta(hours=5),
    )
    return Candidate(**{**base, **kw})


def test_candidate_checks_and_journal_row():
    c = cand(rule_results={"swept": True}, tags=("ote",))
    row = c.journal_row("bt-1", "taken", ml_p=0.4)
    assert row["candidate_id"] == "bt-1:ny_am_silver_bullet:2026-10-27T14:14:00+00:00:long"
    assert (row["status"], row["ml_p"], row["tags"]) == ("taken", 0.4, ["ote"])
    with pytest.raises(ValueError, match="opposite sides"):
        cand(side="short")
    with pytest.raises(ValueError, match="needs a price"):
        cand(entry=None)
    with pytest.raises(ValueError, match="timezone-aware"):
        cand(decision_time=T.replace(tzinfo=None))


def test_register_names_a_setup_once():
    @register("demo_setup_for_test")
    class Demo:
        params = SetupParams()

        def scan(self, ctx):
            return []

    try:
        assert REGISTRY["demo_setup_for_test"] is Demo and Demo.name == "demo_setup_for_test"
        with pytest.raises(ValueError, match="twice"):
            register("demo_setup_for_test")(Demo)
    finally:
        REGISTRY.pop("demo_setup_for_test")


def test_built_setups_register_through_the_package():
    import subprocess
    import sys

    # A fresh interpreter, so no test module has imported a setup module first.
    code = "from moon_ai.setups import REGISTRY; print(sorted(REGISTRY))"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    for name in ("ny_am_silver_bullet", "ny_pm_silver_bullet", "london_sweep_and_reverse"):
        assert name in out.stdout
