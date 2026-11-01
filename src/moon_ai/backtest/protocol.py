"""The setup testing protocol end to end (docs/design.md, "Setup testing protocol").

For each setup:

1. Backtest its pre-registered default and evaluate it.
   - **Insufficient** (under 100 trades): reported as such. A rescue pass is
     only for a default that *fails*, so it doesn't get one.
   - **Passes:** re-run with double slippage; it goes forward only if it stays
     profitable.
2. **Rescue pass** for a failing default: run its pre-registered trials one
   at a time, in file order, each counted as a trial for the DSR. The first
   trial that clears every check (double costs included) takes the setup
   forward. If none does, the setup is **retired**, with the reasons on its
   report card.

Every run writes its own report card. The protocol also writes
`verdicts.json` and a `summary.html` that links them, in the runs folder.
"""

from __future__ import annotations

import html
import json
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Literal

from moon_ai.backtest.evaluate import Evaluation, evaluate, stress_test
from moon_ai.backtest.report import CSS, render
from moon_ai.backtest.runner import BacktestResult, run_backtest
from moon_ai.backtest.stats import Metrics
from moon_ai.setups import load_setup_defaults

Final = Literal["go-forward", "retired", "insufficient"]


@dataclass
class SetupVerdict:
    setup: str
    title: str
    verdict: Final
    trial: str  # "default" or the rescue trial that passed
    reasons: list[str]
    report: str  # path of the deciding run's report card
    trials_run: list[str] = field(default_factory=list)
    # The deciding run's four checks, for the dashboard: trades, edge over random
    # entries (R per trade), DSR, and net R with double costs (None if not run).
    checks: dict[str, Any] = field(default_factory=dict)


@dataclass
class Hooks:
    """The expensive steps, injectable for tests."""

    run: Callable[..., BacktestResult] = run_backtest
    evaluate: Callable[..., Evaluation] = evaluate
    stress: Callable[..., Metrics] = stress_test
    render: Callable[..., Path] = render


def _checks(ev: Evaluation, stress: Metrics | None) -> dict[str, Any]:
    return {
        "trades": ev.metrics.trades,
        "edge_r": ev.metrics.expectancy_r - ev.random_mean_r,
        "edge_ci": list(ev.edge_ci),
        "dsr": ev.dsr,
        "stress_net_r": None if stress is None else stress.net_r,
    }


def _quiet(_: str) -> None:
    pass


def _try(
    setup: str,
    trial: str | None,
    start: date,
    end: date,
    kw: dict[str, Any],
    hooks: Hooks,
    say: Callable[[str], None] = _quiet,
) -> tuple[Evaluation, Path, bool, dict[str, Any]]:
    """Run, evaluate, stress if it passes, write the report card. Returns
    (evaluation, report path, passed everything, the four checks)."""
    began = time.monotonic()
    say(f"  testing {trial or 'default'} version...")
    result = hooks.run(setup, start, end, trial=trial, **kw)
    ev = hooks.evaluate(result.folder, store_root=kw.get("store_root"), config=kw.get("config"))
    stress = None
    if ev.verdict == "go-forward":
        stress = hooks.stress(setup, trial, start, end, **kw)
    page = hooks.render(ev, result.folder, stress)
    passed = ev.verdict == "go-forward" and stress is not None and stress.net_r > 0
    minutes = (time.monotonic() - began) / 60
    say(
        f"  {trial or 'default'}: {ev.metrics.trades} trades, "
        f"{'passed' if passed else 'did not pass'} ({minutes:.0f} min)"
    )
    return ev, page, passed, _checks(ev, stress)


def judge(
    setup: str,
    start: date,
    end: date,
    *,
    hooks: Hooks | None = None,
    say: Callable[[str], None] = _quiet,
    **kw: Any,
) -> SetupVerdict:
    hooks = hooks or Hooks()
    defaults = load_setup_defaults()[setup]
    ev, page, passed, checks = _try(setup, None, start, end, kw, hooks, say)
    tried = ["default"]
    if passed:
        return SetupVerdict(
            setup, defaults.title, "go-forward", "default", [], str(page), tried, checks
        )
    if ev.verdict == "insufficient":
        return SetupVerdict(
            setup, defaults.title, "insufficient", "default", ev.reasons, str(page), tried, checks
        )
    reasons = list(ev.reasons) or ["lost money when costs were doubled"]
    last_page = page
    for trial in defaults.rescue:
        _, t_page, t_passed, t_checks = _try(setup, trial.name, start, end, kw, hooks, say)
        tried.append(trial.name)
        last_page = t_page
        if t_passed:
            return SetupVerdict(
                setup, defaults.title, "go-forward", trial.name, [], str(t_page), tried, t_checks
            )
    reasons.append(f"none of its {len(defaults.rescue)} pre-registered retests passed either")
    return SetupVerdict(
        setup, defaults.title, "retired", "default", reasons, str(last_page), tried, checks
    )


def judge_all(
    start: date,
    end: date,
    runs_root: Path,
    *,
    hooks: Hooks | None = None,
    setups: list[str] | None = None,
    say: Callable[[str], None] = _quiet,
    **kw: Any,
) -> list[SetupVerdict]:
    defaults = load_setup_defaults()
    names = setups or sorted(defaults, key=lambda n: defaults[n].params.priority)
    verdicts = []
    for i, n in enumerate(names, 1):
        say(f"[{i}/{len(names)}] {defaults[n].title}")
        verdicts.append(judge(n, start, end, hooks=hooks, say=say, runs_root=runs_root, **kw))
    runs_root.mkdir(parents=True, exist_ok=True)
    (runs_root / "verdicts.json").write_text(
        json.dumps(
            {
                "window": [start.isoformat(), end.isoformat()],
                "setups": [asdict(v) for v in verdicts],
            },
            indent=2,
        )
        + "\n"
    )
    write_summary(verdicts, start, end, runs_root / "summary.html")
    return verdicts


WORDS = {
    "go-forward": ("Goes forward", "win"),
    "retired": ("Retired", "loss"),
    "insufficient": ("Not enough trades", "amber"),
}


def write_summary(verdicts: list[SetupVerdict], start: date, end: date, path: Path) -> Path:
    rows = []
    for v in verdicts:
        word, cls = WORDS[v.verdict]
        how = "" if v.trial == "default" else f" (with the retest “{html.escape(v.trial)}”)"
        why = "".join(f"<li>{html.escape(r)}</li>" for r in v.reasons)
        rel = (
            Path(v.report).relative_to(path.parent)
            if Path(v.report).is_relative_to(path.parent)
            else v.report
        )
        rows.append(
            f'<section class="card"><h2>{html.escape(v.title)}: <span class="{cls}">{word}</span>{how}</h2>'
            f"<ul>{why}</ul><p class=sub>{len(v.trials_run)} version(s) tested. "
            f'<a href="{html.escape(str(rel))}">Open its report card</a></p></section>'
        )
    passed = sum(v.verdict == "go-forward" for v in verdicts)
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Setup verdicts</title>
<style>{CSS}</style></head><body><main>
<p class="eyebrow">All setups · {start} to {end}</p>
<h1>{passed} of {len(verdicts)} setups go forward</h1>
<p class="lead">Each setup's default was tested first. A failing one got up to 12 pre-registered
retests, one setting at a time. A setup goes forward only if it beats random entries, isn't just
luck, has 100+ trades and still makes money with double costs.</p>
{"".join(rows)}</main></body></html>"""
    path.write_text(page)
    return path
