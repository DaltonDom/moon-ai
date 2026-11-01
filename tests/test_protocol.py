from dataclasses import replace
from datetime import date
from pathlib import Path
from types import SimpleNamespace as NS

from moon_ai.backtest.evaluate import Evaluation
from moon_ai.backtest.protocol import Hooks, judge, judge_all
from moon_ai.backtest.stats import metrics
from moon_ai.setups import load_setup_defaults

M = metrics([1.0], [100.0], [1.0])


def ev(verdict, reasons=()):
    return Evaluation("r", "s", "t", M, 0.0, (0.1, 0.2), 0.97, 1, None, verdict, list(reasons))


def fake_hooks(script, stress_r=1.0):
    """script: trial name (None = default) -> verdict. Records what ran."""
    ran = []

    def run(setup, start, end, trial=None, **kw):
        ran.append(trial or "default")
        return NS(folder=Path(f"/tmp/{trial or 'default'}"))

    def evaluate(folder, **kw):
        # A real run folder is "<setup>.<trial>.<window>.<stamp>"; a fake one is "<trial>".
        name = folder.name.split(".")[1] if "." in folder.name else folder.name
        return ev(script.get(name, "fail"), [f"{name} failed"])

    hooks = Hooks(
        run=run,
        evaluate=evaluate,
        stress=lambda *a, **k: replace(M, net_r=stress_r),
        render=lambda e, folder, stress: folder / "report.html",
    )
    return hooks, ran


START, END = date(2019, 5, 6), date(2026, 5, 1)


def test_a_passing_default_needs_no_rescue():
    hooks, ran = fake_hooks({"default": "go-forward"})
    v = judge("ny_am_silver_bullet", START, END, hooks=hooks)
    assert (v.verdict, v.trial, ran) == ("go-forward", "default", ["default"])


def test_insufficient_gets_no_rescue_pass():
    hooks, ran = fake_hooks({"default": "insufficient"})
    v = judge("london_sweep_and_reverse", START, END, hooks=hooks)
    assert v.verdict == "insufficient" and ran == ["default"]


def test_a_failing_default_tries_retests_in_order_until_one_passes():
    trials = [t.name for t in load_setup_defaults()["ny_am_silver_bullet"].rescue]
    hooks, ran = fake_hooks({"default": "fail", trials[2]: "go-forward"})
    v = judge("ny_am_silver_bullet", START, END, hooks=hooks)
    assert (v.verdict, v.trial) == ("go-forward", trials[2])
    assert ran == ["default", *trials[:3]]


def test_failing_double_costs_is_not_a_pass_and_all_retests_failing_retires_it():
    trials = load_setup_defaults()["ote_pullback"].rescue
    hooks, ran = fake_hooks({"default": "go-forward"}, stress_r=-1.0)
    v = judge("ote_pullback", START, END, hooks=hooks)
    assert v.verdict == "retired" and len(ran) == 1 + len(trials)
    assert "none of its" in v.reasons[-1]


def test_judge_all_writes_verdicts_and_a_summary(tmp_path):
    hooks, _ = fake_hooks({"default": "insufficient"})
    out = judge_all(
        START, END, tmp_path, hooks=hooks, setups=["ny_am_silver_bullet", "ote_pullback"]
    )
    assert [v.verdict for v in out] == ["insufficient", "insufficient"]
    assert (tmp_path / "verdicts.json").exists()
    page = (tmp_path / "summary.html").read_text()
    assert "0 of 2 setups go forward" in page and "Not enough trades" in page


def test_judge_all_says_what_it_is_doing(tmp_path):
    hooks, _ = fake_hooks({"default": "insufficient"})
    lines: list[str] = []
    judge_all(START, END, tmp_path, hooks=hooks, setups=["ote_pullback"], say=lines.append)
    assert lines[0].startswith("[1/1] ") and "testing default version" in lines[1]
    assert "trades, did not pass" in lines[2]


def test_retests_whose_rule_is_not_built_are_skipped_not_crashed():
    """On the real Mac, NY AM's 'first_tethered_fvg' retest raised NotImplementedError
    and ended `backtest --all` halfway."""
    trials = [t.name for t in load_setup_defaults()["ny_am_silver_bullet"].rescue]
    hooks, ran = fake_hooks({"default": "fail"})
    lines: list[str] = []
    v = judge("ny_am_silver_bullet", START, END, hooks=hooks, say=lines.append)
    unbuilt = {"first_tethered_fvg"}  # the bias gate is built now (round 2)
    assert v.verdict == "retired"
    assert ran == ["default", *(t for t in trials if t not in unbuilt)]
    assert f"none of its {len(trials) - 1} pre-registered retests" in v.reasons[-2]
    assert "first_tethered_fvg" in v.reasons[-1]
    assert any("first_tethered_fvg: skipped, not built yet" in ln for ln in lines)


def test_round2_runs_only_new_and_skipped_trials_and_never_repeats(tmp_path):
    from moon_ai.backtest.protocol import judge_round2

    d = load_setup_defaults()["ny_am_silver_bullet"]
    # The first pass logged every built retest; fake those folders.
    for t in ["default", *(t.name for t in d.rescue if t.name != "first_tethered_fvg")]:
        if t == "trade_with_bias_only":
            continue  # skipped as unbuilt in the first pass
        _fake_run(tmp_path, "ny_am_silver_bullet", t)
    hooks, ran = fake_hooks({"timeframe_5m": "go-forward"})
    lines: list[str] = []
    out = judge_round2(
        START, END, tmp_path, hooks=hooks, setups=["ny_am_silver_bullet"], say=lines.append
    )
    assert ran == ["trade_with_bias_only", "min_rr_2", "timeframe_5m"]
    assert out[-1] == ("ny_am_silver_bullet", "timeframe_5m", True)
    assert "3 trial(s) to run" in lines[0]


def _fake_run(root, setup, trial):
    from datetime import UTC, datetime

    from moon_ai.journal.stores import ParquetRun

    run_id = f"{setup}.{trial}.{START}_{END}.x"
    ParquetRun(
        root,
        {
            "run_id": run_id,
            "kind": "backtest",
            "created_at": datetime(2026, 11, 1, tzinfo=UTC),
            "notes": {"setup": setup, "trial": trial},
        },
    ).write()


def test_round2_trials_resolve_everywhere_a_rescue_trial_does():
    """On the Mac, evaluate() looked only in `rescue`, so min_rr_2 crashed with StopIteration."""
    d = load_setup_defaults()["ny_am_silver_bullet"]
    assert d.trial("min_rr_2").changes == {"min_rr": 2.0}
    assert d.trial("displacement_k_1.0") in d.rescue
    assert [t.name for t in d.all_trials][-2:] == ["min_rr_2", "timeframe_5m"]


def test_round2_scores_a_logged_but_unjudged_run_instead_of_rerunning(tmp_path):
    """The Mac's round 2 crashed after writing min_rr_2's run but before judging it."""
    import json

    from moon_ai.backtest.protocol import judge_round2

    d = load_setup_defaults()["ny_am_silver_bullet"]
    judged = ["default", *(t.name for t in d.rescue if t.name != "first_tethered_fvg")]
    (tmp_path / "verdicts.json").write_text(
        json.dumps(
            {
                "window": [str(START), str(END)],
                "setups": [
                    {
                        "setup": "ny_am_silver_bullet",
                        "title": d.title,
                        "verdict": "retired",
                        "trial": "default",
                        "reasons": ["x"],
                        "report": "r",
                        "trials_run": judged,
                        "checks": {},
                    }
                ],
            }
        )
    )
    _fake_run(tmp_path, "ny_am_silver_bullet", "min_rr_2")  # logged, never judged
    hooks, ran = fake_hooks({"min_rr_2": "go-forward"})
    lines: list[str] = []
    out = judge_round2(
        START, END, tmp_path, hooks=hooks, setups=["ny_am_silver_bullet"], say=lines.append
    )
    assert ran == []  # nothing re-run: the logged run was scored
    assert out == [("ny_am_silver_bullet", "min_rr_2", True)]
    assert any("min_rr_2: already run, scoring that run" in ln for ln in lines)
    saved = json.loads((tmp_path / "verdicts.json").read_text())["setups"][0]
    assert saved["verdict"] == "go-forward" and saved["trial"] == "min_rr_2"
