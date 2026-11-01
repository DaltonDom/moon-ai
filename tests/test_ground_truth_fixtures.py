"""The user's marked days (tests/fixtures/ground_truth/<setup>/) must match the setups, both ways.

Skipped until the first verdict file is committed (`moon-ai review-days --import FILE`).
"""

import pytest

from moon_ai.groundtruth import FIXTURES, check

SETUPS = (
    sorted(p.parent.name for p in FIXTURES.glob("*/verdicts.json")) if FIXTURES.exists() else []
)


@pytest.mark.skipif(not SETUPS, reason="no ground-truth days marked yet")
@pytest.mark.parametrize("setup", SETUPS or ["none"])
def test_setup_matches_the_ground_truth(setup):
    problems = check(setup)
    assert not problems, "\n".join(f"{p.day}: {p.message}" for p in problems)
