"""Train the ML filter: purged walk-forward CV, uniqueness weights, isotonic
calibration, and the take rule (design.md, "ML filter", Training / Take or skip).

- **Model:** one pooled gradient-boosted tree model across go-forward
  setups, with the setup as a feature. It is scikit-learn's
  HistGradientBoostingClassifier (histogram GBDT, the LightGBM algorithm),
  chosen because LightGBM's Mac wheel needs a separate libomp install.
- **Minimum data:** at least 500 labelled rows, and 100 per setup. Below
  that the filter stays off and setups trade rules-only.
- **Cross-validation:** walk-forward folds in time. Training rows whose
  entry-to-exit span reaches into the test fold are purged, plus a
  1-session embargo before each test fold.
- **Weights:** average uniqueness. A row overlapping k rows (itself
  included) weighs 1/k.
- **Calibration:** isotonic regression on the out-of-fold predictions.
- **Take rule:** take when p > 1 / (1 + net R:R), with net R:R taken from
  the candidate's own stop and target after round-trip costs. There's no
  tuned threshold.
"""

from __future__ import annotations

import json
import pickle
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.isotonic import IsotonicRegression

from moon_ai.config import Config, load_config

MIN_ROWS = 500
MIN_PER_SETUP = 100
N_FOLDS = 5
EMBARGO = timedelta(days=1)
RECIPE = {
    "model": "sklearn.HistGradientBoostingClassifier",
    "max_iter": 200,
    "learning_rate": 0.05,
    "max_leaf_nodes": 15,
    "min_samples_leaf": 20,
    "l2_regularization": 1.0,
    "random_state": 0,
}


def feature_columns(df: pl.DataFrame) -> list[str]:
    return sorted(c for c in df.columns if c.startswith("f_"))


def matrix(df: pl.DataFrame, cols: list[str]) -> np.ndarray:
    return df.select([pl.col(c).cast(pl.Float64) for c in cols]).to_numpy()


def uniqueness_weights(df: pl.DataFrame) -> np.ndarray:
    starts = df["decision_time"].to_list()
    ends = df["exit_time"].to_list()
    w = np.empty(len(starts))
    for i, (s, e) in enumerate(zip(starts, ends, strict=True)):
        k = sum(1 for s2, e2 in zip(starts, ends, strict=True) if s2 < e and e2 > s)
        w[i] = 1.0 / max(k, 1)
    return w


def cost_ticks(config: Config, symbol: str = "MNQ.v.0") -> float:
    """Round-trip costs in ticks: commission both sides, entry and stop slippage."""
    spec = config.instrument(symbol)
    b = config.broker
    commission = 2 * b.commission_per_contract / spec.point_value / spec.tick_size
    return commission + b.entry_slippage_ticks


def take_threshold(stop_ticks: np.ndarray, target_ticks: np.ndarray, costs: float) -> np.ndarray:
    """p must beat 1 / (1 + net R:R) for the trade's expected R to be above zero."""
    net_rr = np.maximum(target_ticks - costs, 0.0) / (stop_ticks + costs)
    return 1.0 / (1.0 + net_rr)


def check_minimums(df: pl.DataFrame) -> list[str]:
    reasons = []
    if df.height < MIN_ROWS:
        reasons.append(f"only {df.height} labelled candidates; {MIN_ROWS} needed")
    for setup, n in df.group_by("setup").len().iter_rows():
        if n < MIN_PER_SETUP:
            reasons.append(f"{setup} has only {n} labelled candidates; {MIN_PER_SETUP} needed")
    return reasons


def walk_forward_folds(
    df: pl.DataFrame, n_folds: int = N_FOLDS
) -> list[tuple[np.ndarray, np.ndarray]]:
    """(train_idx, test_idx) with expanding training windows, purged and embargoed."""
    order = np.argsort(df["decision_time"].to_numpy())
    blocks = np.array_split(order, n_folds + 1)
    dec = df["decision_time"].to_list()
    ext = df["exit_time"].to_list()
    folds = []
    for k in range(1, n_folds + 1):
        test = blocks[k]
        t0 = min(dec[i] for i in test)
        train = np.array(
            [i for b in blocks[:k] for i in b if ext[i] < t0 - EMBARGO], dtype=int
        )  # purge + embargo
        folds.append((train, test))
    return folds


def _model() -> HistGradientBoostingClassifier:
    p = {k: v for k, v in RECIPE.items() if k != "model"}
    return HistGradientBoostingClassifier(**p)


@dataclass
class TrainReport:
    status: str  # "trained" | "off"
    reasons: list[str]
    rows: int
    oof_rows: int
    brier_raw: float | None = None
    brier_calibrated: float | None = None
    rules_only_mean_r: float | None = None  # every OOF candidate taken
    ml_mean_r: float | None = None  # only the OOF candidates the filter takes
    ml_taken: int | None = None
    ml_beats_rules_only: bool | None = None


@dataclass
class TrainedModel:
    model: HistGradientBoostingClassifier
    calibrator: IsotonicRegression
    columns: list[str]
    costs: float

    def probability(self, df: pl.DataFrame) -> np.ndarray:
        raw = self.model.predict_proba(matrix(df, self.columns))[:, 1]
        return self.calibrator.predict(raw)

    def take(self, df: pl.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        p = self.probability(df)
        thr = take_threshold(
            df["f_stop_ticks"].to_numpy(), df["f_target_ticks"].to_numpy(), self.costs
        )
        return p, thr, p > thr


def train(
    df: pl.DataFrame, config: Config | None = None, enforce_minimums: bool = True
) -> tuple[TrainReport, TrainedModel | None]:
    config = config or load_config()
    reasons = check_minimums(df)
    if reasons and enforce_minimums:
        return TrainReport("off", reasons, df.height, 0), None
    cols = feature_columns(df)
    X, y = matrix(df, cols), df["label"].to_numpy()
    w = uniqueness_weights(df)
    oof = np.full(len(y), np.nan)
    for tr, te in walk_forward_folds(df):
        if len(tr) < 20 or len(set(y[tr])) < 2:
            continue
        m = _model().fit(X[tr], y[tr], sample_weight=w[tr])
        oof[te] = m.predict_proba(X[te])[:, 1]
    have = ~np.isnan(oof)
    if have.sum() < 20 or len(set(y[have])) < 2:
        return TrainReport(
            "off", [*reasons, "too few out-of-fold predictions"], df.height, int(have.sum())
        ), None
    cal = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(oof[have], y[have])
    p = cal.predict(oof[have])
    costs = cost_ticks(config)
    thr = take_threshold(
        df["f_stop_ticks"].to_numpy()[have], df["f_target_ticks"].to_numpy()[have], costs
    )
    net = df["net_r"].to_numpy()[have]
    take = p > thr
    final = _model().fit(X, y, sample_weight=w)
    rep = TrainReport(
        "trained",
        reasons,
        df.height,
        int(have.sum()),
        brier_raw=float(np.mean((oof[have] - y[have]) ** 2)),
        brier_calibrated=float(np.mean((p - y[have]) ** 2)),
        rules_only_mean_r=float(net.mean()),
        ml_mean_r=float(net[take].mean()) if take.any() else None,
        ml_taken=int(take.sum()),
    )
    rep.ml_beats_rules_only = rep.ml_mean_r is not None and rep.ml_mean_r > rep.rules_only_mean_r
    return rep, TrainedModel(final, cal, cols, costs)


# --- registry -----------------------------------------------------------------------


def save_model(
    trained: TrainedModel,
    report: TrainReport,
    models_root: Path,
    training_window: tuple[datetime, datetime],
    sources: list[str],
) -> str:
    """Write data/models/<id>/ (model.pkl + meta.json) and return the id."""
    stamp = datetime.now(UTC)
    model_id = f"m-{stamp:%Y%m%dT%H%M%S}"
    folder = Path(models_root) / model_id
    folder.mkdir(parents=True)
    with (folder / "model.pkl").open("wb") as fh:
        pickle.dump(trained, fh)
    meta = {
        "model_id": model_id,
        "created_at": stamp.isoformat(),
        "recipe": RECIPE,
        "feature_set": "v1",
        "columns": trained.columns,
        "training_window": [t.isoformat() for t in training_window],
        "sources": sources,
        "report": asdict(report),
    }
    (folder / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    return model_id


def load_model(models_root: Path, model_id: str) -> TrainedModel:
    with (Path(models_root) / model_id / "model.pkl").open("rb") as fh:
        return pickle.load(fh)


def register(journal, model_id: str, meta: dict[str, Any], role: str = "challenger") -> None:
    """Add the model to the journal's `models` table. A new model always
    starts as a challenger; only promotion (#50) makes one champion."""
    journal.insert(
        "models",
        {
            "model_id": model_id,
            "created_at": datetime.fromisoformat(meta["created_at"]),
            "recipe": meta["recipe"],
            "train_start": datetime.fromisoformat(meta["training_window"][0]),
            "train_end": datetime.fromisoformat(meta["training_window"][1]),
            "role": role,
            "records": {"report": meta["report"]},
            "holdout_checks": 0,
        },
    )
