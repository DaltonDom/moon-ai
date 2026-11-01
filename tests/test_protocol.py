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
        return ev(script.get(folder.name, "fail"), [f"{folder.name} failed"])

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
