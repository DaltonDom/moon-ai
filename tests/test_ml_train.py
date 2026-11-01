from datetime import UTC, datetime, timedelta

import numpy as np
import polars as pl
import pytest

from moon_ai.journal import SQLiteStore, decode_json
from moon_ai.ml.train import (
    EMBARGO,
    check_minimums,
    load_model,
    register,
    save_model,
    take_threshold,
    train,
    uniqueness_weights,
    walk_forward_folds,
)


def synthetic(n=900, signal=True, seed=0):
    rng = np.random.default_rng(seed)
    t0 = datetime(2020, 1, 1, 14, tzinfo=UTC)
    dec = [t0 + timedelta(hours=8 * i) for i in range(n)]
    x = rng.normal(size=n)
    noise = rng.normal(scale=0.7, size=n)
    label = ((x + noise) > 0.4).astype(int) if signal else (rng.random(n) < 0.35).astype(int)
    return pl.DataFrame(
        {
            "candidate_id": [f"c{i}" for i in range(n)],
            "setup": ["ny_am_silver_bullet" if i % 2 else "ote_pullback" for i in range(n)],
            "decision_time": dec,
            "exit_time": [d + timedelta(minutes=45) for d in dec],
            "label": label,
            "net_r": np.where(label == 1, 1.9, -1.1),
            "f_setup": [i % 2 for i in range(n)],
            "f_x": x,
            "f_noise": rng.normal(size=n),
            "f_stop_ticks": np.full(n, 40.0),
            "f_target_ticks": np.full(n, 80.0),
        }
    )


def test_the_filter_finds_a_real_signal_and_beats_rules_only():
    rep, model = train(synthetic())
    assert rep.status == "trained" and model is not None
    assert rep.ml_beats_rules_only and rep.ml_mean_r > rep.rules_only_mean_r + 0.2
    assert rep.brier_calibrated <= rep.brier_raw + 1e-9


def test_on_noise_it_finds_no_real_edge():
    rep, _ = train(synthetic(signal=False))
    assert rep.status == "trained"
    assert rep.ml_mean_r is None or rep.ml_mean_r < rep.rules_only_mean_r + 0.25


def test_minimums_keep_the_filter_off():
    small = synthetic(n=300)
    rep, model = train(small)
    assert rep.status == "off" and model is None
    assert any("500 needed" in r for r in rep.reasons)
    assert any("100 needed" in r for r in check_minimums(synthetic().head(150)))


def test_folds_are_walk_forward_purged_and_embargoed():
    df = synthetic()
    dec, ext = df["decision_time"].to_list(), df["exit_time"].to_list()
    for train_idx, test_idx in walk_forward_folds(df):
        t0 = min(dec[i] for i in test_idx)
        assert all(ext[i] < t0 - EMBARGO for i in train_idx)


def test_uniqueness_weights_and_take_threshold():
    t = datetime(2020, 1, 1, tzinfo=UTC)
    df = pl.DataFrame(
        {
            "decision_time": [t, t + timedelta(minutes=10), t + timedelta(hours=5)],
            "exit_time": [
                t + timedelta(minutes=30),
                t + timedelta(minutes=40),
                t + timedelta(hours=6),
            ],
        }
    )
    assert list(uniqueness_weights(df)) == [0.5, 0.5, 1.0]
    # 40-tick stop, 80-tick target, 5 ticks of costs: net R:R = 75/45, cut = 1/(1+75/45).
    assert take_threshold(np.array([40.0]), np.array([80.0]), 5.0)[0] == pytest.approx(45 / 120)


def test_registry_round_trip(tmp_path):
    df = synthetic()
    rep, model = train(df)
    window = (df["decision_time"].min(), df["decision_time"].max())
    mid = save_model(model, rep, tmp_path / "models", window, ["run-a"])
    again = load_model(tmp_path / "models", mid)
    assert np.allclose(again.probability(df.head(20)), model.probability(df.head(20)))
    import json

    meta = json.loads((tmp_path / "models" / mid / "meta.json").read_text())
    db = SQLiteStore(tmp_path / "j.sqlite")
    register(db, mid, meta)
    row = decode_json(db.read("models"), "models")[0]
    assert (row["model_id"], row["role"]) == (mid, "challenger")
