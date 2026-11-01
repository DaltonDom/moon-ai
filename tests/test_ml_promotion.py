from datetime import date, timedelta

import numpy as np
import pytest

from moon_ai.ml.promotion import (
    Adwin,
    DriftMonitors,
    Evidence,
    Holdout,
    PromotionInputs,
    decide_promotion,
    holdout_passes,
    refresh_ok,
    rolling_check,
    session_bootstrap,
)

D0 = date(2025, 1, 1)


def paired(n_sessions=60, per=8, edge=0.4, seed=0):
    """Candidates where the challenger skips the losers more often than the champion."""
    rng = np.random.default_rng(seed)
    n = n_sessions * per
    r = rng.normal(0.0, 1.5, n)
    sessions = [D0 + timedelta(days=i // per) for i in range(n)]
    champ = np.ones(n, bool)
    chall = ~((r < -edge) & (rng.random(n) < 0.9))  # skip most bad trades
    return champ, chall, r, sessions


def test_bootstrap_detects_a_real_improvement():
    ev = session_bootstrap(*paired())
    assert ev.enough and ev.better and ev.mean_diff > 0
    same = session_bootstrap(np.ones(200, bool), np.ones(200, bool), np.ones(200), [D0] * 200)
    assert same.disagreements == 0 and not same.better


def test_too_little_evidence_is_never_pass_or_fail():
    ev = session_bootstrap(*paired(n_sessions=20))
    assert not ev.enough
    d, why = decide_promotion(PromotionInputs(ev, ev, 0.99, 0.1, True, shadow_weeks=3))
    assert d == "not enough evidence" and "150" in why[0]
    d, _ = decide_promotion(PromotionInputs(ev, ev, 0.99, 0.1, True, shadow_weeks=12))
    assert d == "reject"


def test_promotion_needs_every_gate():
    ev = session_bootstrap(*paired())
    ok = PromotionInputs(ev, ev, dsr=0.97, pbo=0.1, holdout_passed=True, shadow_weeks=4)
    assert decide_promotion(ok) == ("promote", [])
    from dataclasses import replace

    for bad, word in [
        (replace(ok, dsr=0.9), "DSR"),
        (replace(ok, pbo=0.4), "PBO"),
        (replace(ok, holdout_passed=None), "holdout"),
        (replace(ok, shadow=Evidence(-0.2, -0.5, 10, 5, 0.1)), "shadow"),
    ]:
        d, why = decide_promotion(bad)
        assert d == "reject" and any(word in w for w in why)
    assert decide_promotion(replace(ok, evaluation_active=True))[0] == "frozen"
    assert decide_promotion(replace(ok, drift_alarm=True))[0] == "frozen"


def test_holdout_rules_and_its_one_check(tmp_path):
    champ, chall, r, _ = paired()
    assert holdout_passes(champ, chall, r)
    assert not holdout_passes(champ, ~chall, r)
    h = Holdout.carve(date(2026, 10, 31), today=date(2026, 11, 1))
    assert (h.end - h.start).days == 183
    h.check("m-1")
    with pytest.raises(PermissionError):
        h.check("m-1")
    h.save(tmp_path / "holdout.json")
    assert Holdout.load(tmp_path / "holdout.json").checks == {"m-1": 1}
    assert h.due_for_refresh(date(2027, 5, 3), promoted_since=False)
    assert h.due_for_refresh(date(2026, 12, 1), promoted_since=True)
    assert not h.due_for_refresh(date(2026, 12, 1), promoted_since=False)


def test_refresh_guardrails():
    fine = Evidence(0.0, -0.1, 20, 5, 0.1)
    assert refresh_ok(0.20, 0.21, fine, reproducible=True)
    assert not refresh_ok(0.22, 0.21, fine, reproducible=True)
    assert not refresh_ok(0.20, 0.21, fine, reproducible=False)
    assert not refresh_ok(0.20, 0.21, Evidence(-0.5, -0.8, 40, 10, -0.2), reproducible=True)
    assert not refresh_ok(0.20, 0.21, fine, reproducible=True, evaluation_active=True)


def test_rolling_check_falls_back_or_rolls_back():
    _, good, r, sessions = paired(n_sessions=70)
    bad = ~(r > 0.4)  # skips the winners: clearly worse than taking everything
    assert rolling_check(good, None, r, sessions)[0] == "keep"
    assert rolling_check(bad, None, r, sessions)[0] == "fallback"
    assert rolling_check(bad, good, r, sessions)[0] == "rollback"
    assert rolling_check(bad, good, r, sessions, evaluation_active=True)[0] == "fallback"


def test_adwin_flags_a_shift_but_not_noise():
    rng = np.random.default_rng(1)
    a = Adwin()
    assert not any(a.update(x) for x in rng.normal(0.2, 0.05, 400))
    b = Adwin()
    hits = [
        b.update(x)
        for x in np.concatenate([rng.normal(0.2, 0.05, 300), rng.normal(0.5, 0.05, 300)])
    ]
    assert any(hits[300:])
    m = DriftMonitors()
    alarms = [m.update(0.6, 1, True) for _ in range(200)] + [
        m.update(0.6, 0, False) for _ in range(200)
    ]
    assert any(alarms[200:])
