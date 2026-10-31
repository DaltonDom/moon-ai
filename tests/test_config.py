from datetime import time
from pathlib import Path

import pytest

from moon_ai.config import ConfigError, Window, load_config


def test_defaults_carry_research_values():
    cfg = load_config()

    assert cfg.sessions.windows["ny_am_silver_bullet"] == Window(time(10), time(11))
    assert cfg.sessions.windows["london_silver_bullet"] == Window(time(3), time(4))
    assert cfg.sessions.windows["ny_pm_silver_bullet"] == Window(time(14), time(15))
    assert cfg.sessions.windows["ny_am_killzone"] == Window(time(7), time(10))
    assert cfg.sessions.windows["asian_range"] == Window(time(20), time(0))
    assert "extra_silver_bullet" not in cfg.sessions.enabled_silver_bullets
    assert cfg.ict.swing_n == 1
    assert cfg.ict.displacement_k == 1.5
    assert cfg.ict.displacement_atr_period == 14
    assert cfg.ict.ote_entry == 0.62
    assert cfg.ict.sb_min_objective_points == 10.0
    assert cfg.broker.limit_fill == "trade_through"
    assert cfg.instruments["MNQ"].tick_size == 0.25
    assert cfg.instruments["MNQ"].point_value == 2.0
    assert cfg.data.dataset == "GLBX.MDP3"
    assert cfg.data.schema == "ohlcv-1m"
    assert cfg.data.symbols == ("MNQ.v.0", "MES.v.0", "NQ.v.0", "ES.v.0")


def test_toml_file_overrides_only_the_values_it_names(tmp_path: Path):
    path = tmp_path / "moon.toml"
    path.write_text(
        """
[sessions.windows]
ny_am_killzone = ["08:30", "11:00"]

[ict]
swing_n = 2
mss_break = "wick"

[broker]
slippage_ticks = 2

[data]
max_cost_usd = 5.0
"""
    )

    cfg = load_config(path)

    assert cfg.sessions.windows["ny_am_killzone"] == Window(time(8, 30), time(11))
    assert cfg.sessions.windows["london_killzone"] == Window(time(2), time(5))
    assert cfg.ict.swing_n == 2
    assert cfg.ict.mss_break == "wick"
    assert cfg.ict.displacement_k == 1.5
    assert cfg.broker.slippage_ticks == 2
    assert cfg.data.max_cost_usd == 5.0


def test_unknown_keys_are_rejected(tmp_path: Path):
    path = tmp_path / "moon.toml"
    path.write_text("[ict]\nswing_nn = 2\n")

    with pytest.raises(ConfigError, match="swing_nn"):
        load_config(path)


def test_instrument_spec_resolves_continuous_symbols():
    cfg = load_config()

    assert cfg.instrument("MNQ.v.0").point_value == 2.0
    assert cfg.instrument("ES.v.0").point_value == 50.0
