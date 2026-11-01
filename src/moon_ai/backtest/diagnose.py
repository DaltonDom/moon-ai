"""`moon-ai diagnose`: why a setup's backtest made or lost money.

Reads one finished backtest run (no new trading) and prints aggregate numbers
only, so the output is safe to share:

1. **Trade anatomy:** win rate, average win and loss, how much costs take per
   trade, planned reward:risk, and what happened to losers before they were
   stopped (were they ever up 0.5R or 1R, or wrong from the start?).
2. **Where it loses:** every candidate the setup produced, labelled as if it
   were taken, split by hour, weekday, side, year and by each ML feature in
   fifths. The splits with the biggest gap between best and worst come first.
3. **Can ML pick the good ones?** The ML filter's walk-forward check on these
   candidates: average R taking everything vs. only what the filter takes, all
   out of sample.

It's a research tool. Any rule it suggests is a hypothesis: it must still be
pre-registered and pass the testing protocol, which counts it as a trial.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

from moon_ai.journal import decode_json, read_run

MIN_BUCKET_SHARE = 0.05
MIN_BUCKET_ROWS = 20
TOP_SPLITS = 8


def latest_run(runs_root: Path, setup: str, trial: str = "default") -> Path | None:
    """The newest non-stress run of `setup` / `trial` in `runs_root`."""
    found = []
    for f in runs_root.glob(f"{setup}.{trial}.*"):
        if not (f / "run.json").exists():
            continue
        run = decode_json(read_run(f, "runs"), "runs")[0]
        notes = run["notes"] or {}
        if notes.get("stress") or notes.get("setup") != setup:
            continue
        found.append((run["created_at"], f))
    return max(found)[1] if found else None


def _pct(x: float) -> str:
    return f"{x:.0%}"


def anatomy(folder: Path) -> list[str]:
    trades = decode_json(read_run(folder, "trades"), "trades")
    cands = {
        c["candidate_id"]: c for c in decode_json(read_run(folder, "candidates"), "candidates")
    }
    done = [t for t in trades if t["r"] is not None]
    if not done:
        return ["No closed trades."]
    r = np.array([t["r"] for t in done])
    wins, losses = r[r > 0], r[r <= 0]
    out = [
        f"{len(done)} trades | average {r.mean():+.3f}R | win rate {_pct((r > 0).mean())}",
        f"average win {wins.mean() if len(wins) else 0:+.2f}R | "
        f"average loss {losses.mean() if len(losses) else 0:+.2f}R",
    ]
    from moon_ai.config import load_config

    config = load_config()
    ideal, stop_t, rr = [], [], []
    for t in done:
        c = cands.get(t["candidate_id"])
        if c is None or c["entry"] is None:
            continue
        sign = 1 if c["side"] == "long" else -1
        risk = abs(c["entry"] - c["stop"])
        if risk <= 0:
            continue
        raw = {"stop": c["stop"], "target": c["target"]}.get(t["exit_reason"], t["exit_price"])
        ideal.append(sign * (raw - c["entry"]) / risk)
        tick = config.instrument(c["symbol"]).tick_size
        stop_t.append(risk / tick)
        rr.append(abs(c["target"] - c["entry"]) / risk)
    if ideal:
        before = np.array(ideal)
        out.append(
            f"before costs {before.mean():+.3f}R per trade | costs take "
            f"{before.mean() - r.mean():.3f}R per trade"
        )
        out.append(
            f"stop size: median {np.median(stop_t):.0f} ticks | "
            f"planned reward:risk median {np.median(rr):.2f}"
        )
    mfe = np.array([t["mfe_r"] for t in done if t["r"] <= 0 and t["mfe_r"] is not None])
    if len(mfe):
        out.append(
            f"losers that were up at least 1R first: {_pct((mfe >= 1).mean())} | "
            f"at least 0.5R: {_pct((mfe >= 0.5).mean())} | "
            f"never up 0.25R: {_pct((mfe < 0.25).mean())}"
        )
    mae = np.array([t["mae_r"] for t in done if t["r"] > 0 and t["mae_r"] is not None])
    if len(mae):
        out.append(f"winners' worst point: median {np.median(mae):+.2f}R")
    reasons: dict[str, int] = {}
    for t in done:
        reasons[t["exit_reason"]] = reasons.get(t["exit_reason"], 0) + 1
    out.append("exits: " + ", ".join(f"{k} {v}" for k, v in sorted(reasons.items())))
    return out


def _labelled(df: pl.DataFrame) -> pl.DataFrame:
    t = df["decision_time"].dt.convert_time_zone("America/New_York")
    return df.with_columns(
        hour=t.dt.hour(),
        weekday=t.dt.weekday(),
        year=t.dt.year(),
    )


def splits(df: pl.DataFrame) -> list[str]:
    """Mean net R by group, the widest best-vs-worst gaps first."""
    df = _labelled(df)
    min_rows = max(MIN_BUCKET_ROWS, math.ceil(MIN_BUCKET_SHARE * df.height))
    results: list[tuple[float, str, list[tuple[str, int, float]]]] = []

    def add(name: str, key: pl.Expr) -> None:
        g = (
            df.with_columns(_k=key)
            .filter(pl.col("_k").is_not_null())
            .group_by("_k")
            .agg(n=pl.len(), r=pl.col("net_r").mean())
            .filter(pl.col("n") >= min_rows)
            .sort("_k")
        )
        if g.height < 2:
            return
        rows = [(str(k), int(n), float(r)) for k, n, r in g.iter_rows()]
        gap = max(r for _, _, r in rows) - min(r for _, _, r in rows)
        results.append((gap, name, rows))

    for name in ("side", "hour", "weekday", "year"):
        add(name, pl.col(name))
    for c in sorted(c for c in df.columns if c.startswith("f_")):
        if df[c].dtype not in (pl.Float64, pl.Float32, pl.Int64, pl.Int32) or c == "f_setup":
            continue
        s = df[c].drop_nulls()
        if s.n_unique() < 5:
            add(c.removeprefix("f_"), pl.col(c))
            continue
        edges = [float(s.quantile(q)) for q in (0.2, 0.4, 0.6, 0.8)]
        labels = ["1 lowest", "2", "3", "4", "5 highest"]
        add(c.removeprefix("f_") + " (fifths)", pl.col(c).cut(edges, labels=labels))
    out = []
    for gap, name, rows in sorted(results, reverse=True)[:TOP_SPLITS]:
        out.append(f"{name}: best-to-worst gap {gap:.2f}R")
        out += [f"    {k:<10} {n:>5} candidates  {r:+.3f}R" for k, n, r in rows]
    return out


def ml_check(df: pl.DataFrame) -> list[str]:
    from moon_ai.ml.train import train

    rep, _ = train(df, enforce_minimums=False)
    if rep.status != "trained":
        return ["The ML check couldn't run: " + "; ".join(rep.reasons)]
    out = [f"{rep.oof_rows} of {rep.rows} candidates judged out of sample (walk-forward)."]
    out.append(f"taking every candidate: {rep.rules_only_mean_r:+.3f}R")
    if rep.ml_mean_r is None:
        out.append("with the filter: it would take nothing")
    else:
        out.append(
            f"with the filter: {rep.ml_mean_r:+.3f}R on {rep.ml_taken} candidates "
            f"({rep.ml_taken / rep.oof_rows:.0%} kept)"
        )
    out.append(f"calibration (Brier, lower is better): {rep.brier_calibrated:.3f}")
    return out


def diagnose(
    setup: str,
    runs_root: Path,
    *,
    trial: str = "default",
    store_root: Path | None = None,
    dataset: Any = None,
    ml: bool = True,
) -> list[str]:
    folder = latest_run(runs_root, setup, trial)
    if folder is None:
        return [f"No {setup} ({trial}) run in {runs_root}. Run the backtest first."]
    lines = [f"{setup} ({trial}), run {folder.name}", "", "1. Trade anatomy"]
    lines += ["  " + ln for ln in anatomy(folder)]
    if dataset is None:
        from moon_ai.ml.dataset import build_dataset

        dataset = build_dataset(folder, store_root=store_root)
    if dataset.height == 0:
        return [*lines, "", "No labelled candidates for the splits."]
    lines += [
        "",
        f"2. Where it wins and loses ({dataset.height} candidates, each as if taken, net R)",
    ]
    lines += ["  " + ln for ln in splits(dataset)]
    if ml:
        lines += ["", "3. Can ML pick the good ones? (out of sample)"]
        lines += ["  " + ln for ln in ml_check(dataset)]
    lines += [
        "",
        "Any rule this suggests is a hypothesis: it must be pre-registered and pass",
        "the testing protocol, where it counts as one more trial.",
    ]
    return lines
