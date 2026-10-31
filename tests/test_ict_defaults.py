"""Primitive keyword defaults must match the research defaults in IctConfig."""

import inspect

import pytest

from moon_ai.config import IctConfig
from moon_ai.ict.displacement import find_displacements
from moon_ai.ict.fvg import find_fvgs
from moon_ai.ict.liquidity import find_sweeps
from moon_ai.ict.structure import find_market_structure_shifts
from moon_ai.ict.swings import find_swings

CFG = IctConfig()

CASES = [
    (find_swings, "n", CFG.swing_n),
    (find_fvgs, "min_size_ticks", CFG.fvg_min_size_ticks),
    (find_displacements, "k", CFG.displacement_k),
    (find_displacements, "atr_period", CFG.displacement_atr_period),
    (find_displacements, "require_fvg", CFG.displacement_require_fvg),
    (find_sweeps, "close_back_bars", CFG.sweep_close_back_bars),
    (find_sweeps, "require_close_back", CFG.sweep_require_close_back),
    (find_sweeps, "min_penetration_ticks", CFG.sweep_min_penetration_ticks),
    (find_market_structure_shifts, "mode", CFG.mss_break),
    (find_market_structure_shifts, "max_bars", CFG.mss_max_bars),
]


@pytest.mark.parametrize(
    ("fn", "param", "expected"), CASES, ids=lambda c: getattr(c, "__name__", str(c))
)
def test_primitive_default_matches_config(fn, param, expected):
    assert inspect.signature(fn).parameters[param].default == expected
