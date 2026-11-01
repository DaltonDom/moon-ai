"""Model promotion, holdout and rollback (design.md, "Model promotion and rollback").

Rules-only is the starting champion and the permanent fallback. Every check
works on paired R differences of disagreements: candidates where one recipe
takes and the other skips. Each candidate's R comes from its own simulated
trade, so a skipped trade's R is still known.

The drift detector is a small ADWIN written here. The River package has no
Apple Silicon wheel for its current version, so on the Mac it would need a
compiler.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Literal

import numpy as np

MIN_DISAGREEMENTS = 150
MIN_SESSIONS = 30
BOOTSTRAP_N = 10_000
DSR_BAR = 0.95
PBO_BAR = 0.25
MAX_SHADOW_WEEKS = 12
ROLLING_SESSIONS = 60
HOLDOUT_MONTHS = 6


# --- the paired test ------------------------------------------------------------------


@dataclass(frozen=True)
class Evidence:
    mean_diff: float  # challenger minus champion, R per disagreement
    lower_95: float  # one-sided 95% lower bound (session-block bootstrap)
    disagreements: int
    sessions: int

    @property
    def enough(self) -> bool:
        return self.disagreements >= MIN_DISAGREEMENTS and self.sessions >= MIN_SESSIONS

    @property
    def better(self) -> bool:
        return self.enough and self.lower_95 > 0

    @property
    def worse(self) -> bool:
        """The challenger is worse at one-sided 95% (used by the rolling check)."""
        return self.enough and self.upper_95 < 0

    upper_95: float = 0.0


def paired_differences(
    champion_takes: np.ndarray, challenger_takes: np.ndarray, net_r: np.ndarray
) -> np.ndarray:
    """Per-candidate R difference (challenger - champion); 0 where they agree."""
    return (challenger_takes.astype(float) - champion_takes.astype(float)) * net_r


def session_bootstrap(
    champion_takes: Sequence[bool],
    challenger_takes: Sequence[bool],
    net_r: Sequence[float],
    sessions: Sequence[date],
    n: int = BOOTSTRAP_N,
    seed: int = 0,
) -> Evidence:
    """One-sided 95% session-block bootstrap of the mean difference on disagreements."""
    a, b = np.asarray(champion_takes, bool), np.asarray(challenger_takes, bool)
    r, s = np.asarray(net_r, float), np.asarray(sessions)
    dis = a != b
    if not dis.any():
        return Evidence(0.0, 0.0, 0, 0, 0.0)
    d = paired_differences(a[dis], b[dis], r[dis])
    sess = s[dis]
    keys = sorted(set(sess.tolist()))
    sums = np.array([d[sess == k].sum() for k in keys])
    counts = np.array([(sess == k).sum() for k in keys])
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(keys), size=(n, len(keys)))
    means = sums[pick].sum(axis=1) / counts[pick].sum(axis=1)
    return Evidence(
        float(d.mean()),
        float(np.quantile(means, 0.05)),
        int(dis.sum()),
        len(keys),
        float(np.quantile(means, 0.95)),
    )


# --- promotion --------------------------------------------------------------------------

Decision = Literal["promote", "not enough evidence", "reject", "frozen"]


@dataclass(frozen=True)
class PromotionInputs:
    evidence: Evidence  # walk-forward + shadow, paired against the champion
    shadow: Evidence  # the forward shadow weeks alone
    dsr: float  # counting every trial, challenger and holdout check
    pbo: float | None
    holdout_passed: bool | None  # None until checked
    shadow_weeks: int
    evaluation_active: bool = False
    drift_alarm: bool = False


def decide_promotion(x: PromotionInputs) -> tuple[Decision, list[str]]:
    if x.evaluation_active:
        return "frozen", ["a prop-firm evaluation is running: no promotions"]
    if x.drift_alarm:
        return "frozen", ["a drift alarm froze promotions until the rolling check clears"]
    if not x.evidence.enough:
        if x.shadow_weeks >= MAX_SHADOW_WEEKS:
            return "reject", [f"no detectable difference after {MAX_SHADOW_WEEKS} shadow weeks"]
        return "not enough evidence", [
            f"{x.evidence.disagreements} disagreements over {x.evidence.sessions} sessions; "
            f"{MIN_DISAGREEMENTS} over {MIN_SESSIONS} needed"
        ]
    reasons = []
    if not x.evidence.better:
        reasons.append("not better than the champion at one-sided 95%")
    if x.shadow.disagreements and x.shadow.mean_diff < 0:
        reasons.append("the shadow weeks show it losing to the champion")
    if x.dsr <= DSR_BAR:
        reasons.append(f"DSR {x.dsr:.2f} is not above {DSR_BAR}")
    if x.pbo is None or x.pbo > PBO_BAR:
        reasons.append(f"PBO {x.pbo} is not at or below {PBO_BAR}")
    if x.holdout_passed is not True:
        reasons.append(
            "the holdout check didn't pass"
            if x.holdout_passed is False
            else "the holdout hasn't been checked"
        )
    return ("promote", []) if not reasons else ("reject", reasons)


def holdout_passes(
    champion_takes: Sequence[bool], challenger_takes: Sequence[bool], net_r: Sequence[float]
) -> bool:
    """Paired mean difference >= 0 and the challenger's own taken trades > 0R."""
    a, b, r = (
        np.asarray(champion_takes, bool),
        np.asarray(challenger_takes, bool),
        np.asarray(net_r, float),
    )
    d = paired_differences(a, b, r)
    dis = a != b
    diff_ok = (d[dis].mean() if dis.any() else 0.0) >= 0
    taken = r[b]
    return bool(diff_ok and taken.size > 0 and taken.mean() > 0)


def refresh_ok(
    new_last_fold_brier: float,
    current_last_fold_brier: float,
    shadow: Evidence,
    reproducible: bool,
    evaluation_active: bool = False,
) -> bool:
    """A same-recipe refresh is adopted when none of its guardrails fail."""
    if evaluation_active:
        return False
    shadow_worse = shadow.disagreements > 0 and shadow.upper_95 < 0
    return reproducible and new_last_fold_brier <= current_last_fold_brier and not shadow_worse


# --- holdout ledger -------------------------------------------------------------------------


@dataclass
class Holdout:
    start: date
    end: date
    created: date
    checks: dict[str, int] = field(default_factory=dict)  # model id -> times checked

    def due_for_refresh(self, today: date, promoted_since: bool) -> bool:
        return promoted_since or today >= self.created + timedelta(
            days=round(HOLDOUT_MONTHS * 30.44)
        )

    def check(self, model_id: str) -> None:
        """Record a model's one allowed look at the holdout (it counts as a DSR trial)."""
        if self.checks.get(model_id):
            raise PermissionError(f"{model_id} already checked this holdout once")
        self.checks[model_id] = 1

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "start": self.start.isoformat(),
                    "end": self.end.isoformat(),
                    "created": self.created.isoformat(),
                    "checks": self.checks,
                },
                indent=2,
            )
            + "\n"
        )

    @classmethod
    def load(cls, path: Path) -> Holdout:
        d = json.loads(path.read_text())
        return cls(
            date.fromisoformat(d["start"]),
            date.fromisoformat(d["end"]),
            date.fromisoformat(d["created"]),
            d.get("checks", {}),
        )

    @classmethod
    def carve(cls, data_end: date, today: date | None = None) -> Holdout:
        start = data_end - timedelta(days=round(HOLDOUT_MONTHS * 30.44))
        return cls(start, data_end, today or datetime.now(UTC).date())


# --- the rolling check and rollback ----------------------------------------------------------

Action = Literal["keep", "fallback", "rollback"]


def rolling_check(
    live_takes: Sequence[bool],
    previous_takes: Sequence[bool] | None,
    net_r: Sequence[float],
    sessions: Sequence[date],
    evaluation_active: bool = False,
) -> tuple[Action, Evidence]:
    """Live model vs rules-only (which takes everything) on the last 60 sessions.

    Worse at one-sided 95%: roll back to the previous version if it passes the
    same check, otherwise fall back to rules-only. During an evaluation only
    the fallback is allowed.
    """
    keep = sorted(set(sessions))[-ROLLING_SESSIONS:]
    mask = np.isin(np.asarray(sessions), keep)
    rules = np.ones(mask.sum(), bool)
    live = np.asarray(live_takes, bool)[mask]
    r, s = np.asarray(net_r, float)[mask], np.asarray(sessions)[mask]
    ev = session_bootstrap(rules, live, r, s)
    if not ev.worse:
        return "keep", ev
    if previous_takes is not None and not evaluation_active:
        prev = session_bootstrap(rules, np.asarray(previous_takes, bool)[mask], r, s)
        if not prev.worse:
            return "rollback", ev
    return "fallback", ev


# --- drift: ADWIN ------------------------------------------------------------------------------


class Adwin:
    """ADWIN (Bifet & Gavalda 2007): keeps a window and drops its older part
    whenever the two sub-windows' means differ more than chance allows at
    confidence `delta`. `update` returns True when it detected a change."""

    def __init__(self, delta: float = 0.002, min_window: int = 30, max_window: int = 2000):
        self.delta, self.min_window, self.max_window = delta, min_window, max_window
        self.window: list[float] = []

    def update(self, x: float) -> bool:
        self.window.append(float(x))
        if len(self.window) > self.max_window:
            self.window.pop(0)
        n = len(self.window)
        if n < 2 * self.min_window:
            return False
        w = np.asarray(self.window)
        var = w.var()
        csum = np.cumsum(w)
        total = csum[-1]
        for cut in range(self.min_window, n - self.min_window + 1, max(1, n // 50)):
            n0, n1 = cut, n - cut
            mu0, mu1 = csum[cut - 1] / n0, (total - csum[cut - 1]) / n1
            m = 1.0 / (1.0 / n0 + 1.0 / n1)
            dd = math.log(2 * math.log(n) / self.delta)
            eps = math.sqrt(2 / m * var * dd) + 2 / (3 * m) * dd
            if abs(mu0 - mu1) > eps:
                self.window = self.window[cut:]
                return True
        return False


@dataclass
class DriftMonitors:
    """Per-candidate Brier score and take rate. An alarm freezes refreshes and
    promotions and triggers the rolling check; it never disables the model."""

    brier: Adwin = field(default_factory=Adwin)
    take_rate: Adwin = field(default_factory=Adwin)

    def update(self, p: float, label: int, taken: bool) -> list[str]:
        alarms = []
        if self.brier.update((p - label) ** 2):
            alarms.append("Brier score drifted")
        if self.take_rate.update(1.0 if taken else 0.0):
            alarms.append("take rate drifted")
        return alarms
