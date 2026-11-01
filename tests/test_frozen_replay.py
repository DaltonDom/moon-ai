"""The frozen replay: real MNQ bars from 2026-09-28 to 2026-10-23 through every setup.

If this fails after an intentional change, run `uv run moon-ai verify --update-frozen`
and commit tests/frozen/expected.json with the change, so the diff shows what moved.
"""

from moon_ai.backtest.frozen import diff, load_expected, replay


def test_frozen_replay_matches():
    problems = diff(load_expected(), replay())
    assert not problems, "\n".join(problems[:40])


def test_diff_reads_plainly():
    e = {"setups": {"x": {"candidates": [{"candidate_id": "a", "status": "taken"}], "trades": []}}}
    a = {
        "setups": {
            "x": {
                "candidates": [
                    {"candidate_id": "a", "status": "unfilled"},
                    {"candidate_id": "b", "status": "taken"},
                ],
                "trades": [],
            }
        }
    }
    assert diff(e, a) == ["x: new candidate b", "x: candidate a changed status"]
    assert diff(e, e) == []
