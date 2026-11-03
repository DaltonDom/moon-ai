"""Can judgment pick the winning ICT setups? Tanja-style cues + the walk-forward ML filter.

Reads the backtest runs in data/runs/judgment, builds the ML dataset for each,
adds three cues from Tanja Trades' stated method, and reports, all out of sample:

  A. taking every candidate
  B. the ML filter with the repo's v1 features
  C. the ML filter with v1 + Tanja cues
  D. Tanja's cues as fixed rules (no fitting)
"""

import pickle
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
import polars as pl

from moon_ai.backtest.stats import bootstrap_mean_ci
from moon_ai.journal import decode_json, read_run
from moon_ai.ml.dataset import build_dataset
from moon_ai.ml.train import train

RUNS = Path("data/runs/judgment")
BARS = Path("data/bars/GLBX.MDP3/ohlcv-1m")
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
OTHER = {"MNQ.v.0": "MES.v.0", "MES.v.0": "MNQ.v.0"}


def load_bars(symbol: str) -> pl.DataFrame:
    return (
        pl.concat([pl.read_parquet(p) for p in sorted((BARS / symbol).glob("*.parquet"))])
        .unique(subset=["ts_event"], keep="last")
        .sort("ts_event")
        .select("ts_event", "open", "high", "low", "close")
    )


class Px:
    def __init__(self, df: pl.DataFrame):
        self.ts = df["ts_event"].dt.epoch("ns").to_numpy()
        self.o, self.h = df["open"].to_numpy(), df["high"].to_numpy()
        self.l, self.c = df["low"].to_numpy(), df["close"].to_numpy()

    def idx_close_at(self, t_ns: int) -> int:
        """Index of the last bar that has closed by t (bar closes 1 minute after its open)."""
        return int(np.searchsorted(self.ts, t_ns - 60_000_000_000, side="right")) - 1

    def close_at(self, t_ns: int) -> float | None:
        i = self.idx_close_at(t_ns)
        return float(self.c[i]) if i >= 0 else None

    def open_at(self, t_ns: int) -> float | None:
        i = int(np.searchsorted(self.ts, t_ns, side="left"))
        return float(self.o[i]) if i < len(self.ts) and self.ts[i] - t_ns < 5 * 60e9 else None


def rel_strength(px: dict[str, Px], symbol: str, t, side: str, since) -> float | None:
    """side-signed (self return - other return) since `since`: > 0 means the trade is
    in the direction Tanja wants (long the stronger index, short the weaker)."""
    t_ns, s_ns = int(t.timestamp() * 1e9), int(since.timestamp() * 1e9)
    if s_ns >= t_ns:
        return None
    vals = []
    for sym in (symbol, OTHER[symbol]):
        a, b = px[sym].open_at(s_ns), px[sym].close_at(t_ns)
        if a is None or b is None:
            return None
        vals.append(b / a - 1)
    return (1 if side == "long" else -1) * (vals[0] - vals[1]) * 1e4  # basis points


def fvg_age_minutes(p: Px, t, fvg) -> float | None:
    """Minutes from the FVG's completing bar to the decision, searching 1-minute bars."""
    if not fvg:
        return None
    lo, hi = float(fvg[0]), float(fvg[1])
    i_end = p.idx_close_at(int(t.timestamp() * 1e9))
    for i in range(i_end, max(i_end - 600, 2), -1):
        bull = abs(p.h[i - 2] - lo) < 1e-9 and abs(p.l[i] - hi) < 1e-9
        bear = abs(p.h[i] - lo) < 1e-9 and abs(p.l[i - 2] - hi) < 1e-9
        if bull or bear:
            return (i_end - i) * 1.0
    return None


def tanja_features(folder: Path, df: pl.DataFrame, px: dict[str, Px]) -> pl.DataFrame:
    cands = {
        r["candidate_id"]: r for r in decode_json(read_run(folder, "candidates"), "candidates")
    }
    from moon_ai.sessions import NY

    major, rs_open, rs_hour, age = [], [], [], []
    for cid, side in zip(df["candidate_id"], df["side"], strict=True):
        r = cands[cid]
        rr = r["rule_results"] or {}
        t = r["decision_time"]
        sym = r["symbol"]
        pool = rr.get("swept_pool")
        major.append(None if pool is None else float(pool != "swing"))
        ny = t.astimezone(NY)
        rth_open = ny.replace(hour=9, minute=30, second=0, microsecond=0)
        rs_open.append(rel_strength(px, sym, t, side, rth_open))
        rs_hour.append(rel_strength(px, sym, t, side, t - timedelta(minutes=60)))
        age.append(fvg_age_minutes(px[sym], t, rr.get("fvg")))
    return df.with_columns(
        pl.Series("f_tj_major_sweep", major, dtype=pl.Float64),
        pl.Series("f_tj_rs_since_0930_bp", rs_open, dtype=pl.Float64),
        pl.Series("f_tj_rs_last_60m_bp", rs_hour, dtype=pl.Float64),
        pl.Series("f_tj_fvg_age_min", age, dtype=pl.Float64),
    )


def ml(df: pl.DataFrame, drop_tanja: bool) -> str:
    d = df.drop([c for c in df.columns if c.startswith("f_tj_")]) if drop_tanja else df
    try:
        rep, _ = train(d, enforce_minimums=False)
    except ValueError as e:
        return f"couldn't train on so few rows ({e})"
    if rep.status != "trained":
        return "couldn't train: " + "; ".join(rep.reasons)
    if rep.ml_mean_r is None:
        return (
            f"{rep.oof_rows} judged out of sample; "
            f"all {rep.rules_only_mean_r:+.3f}R; filter takes nothing"
        )
    return (
        f"{rep.oof_rows} judged out of sample; take all {rep.rules_only_mean_r:+.3f}R -> "
        f"filter {rep.ml_mean_r:+.3f}R on {rep.ml_taken} ({rep.ml_taken / rep.oof_rows:.0%} kept)"
    )


def line(name: str, r: np.ndarray) -> str:
    if len(r) == 0:
        return f"    {name:<44} n=0"
    lo, hi = bootstrap_mean_ci(r)
    return f"    {name:<44} n={len(r):>4}  {r.mean():+.3f}R  (95% CI {lo:+.3f} to {hi:+.3f})"


def rules(df: pl.DataFrame) -> list[str]:
    r = df["net_r"].to_numpy()
    out = [line("take every candidate", r)]
    m = df["f_tj_major_sweep"].to_numpy()
    rs = df["f_tj_rs_since_0930_bp"].to_numpy()
    rh = df["f_tj_rs_last_60m_bp"].to_numpy()
    age = df["f_tj_fvg_age_min"].to_numpy()
    out.append(line("major-level sweep only", r[m == 1]))
    out.append(line("minor (session swing) sweep only", r[m == 0]))
    out.append(line("right index (since 09:30) only", r[rs > 0]))
    out.append(line("wrong index (since 09:30)", r[rs < 0]))
    out.append(line("right index (last 60 min) only", r[rh > 0]))
    out.append(line("fresh FVG (<= 15 min old) only", r[age <= 15]))
    out.append(line("older FVG (> 15 min)", r[age > 15]))
    out.append(line("major sweep AND right index (09:30)", r[(m == 1) & (rs > 0)]))
    return out


def main() -> None:
    px = {s: Px(load_bars(s)) for s in ("MNQ.v.0", "MES.v.0")}
    frames = []
    cached = OUT / "dataset.pkl"
    if cached.exists():
        allc = pickle.loads(cached.read_bytes())
        pools = {}
        for folder in sorted(RUNS.iterdir()):
            for r in decode_json(read_run(folder, "candidates"), "candidates"):
                pools[r["candidate_id"]] = (r["rule_results"] or {}).get("swept_pool")
        major = [
            None if pools.get(c) is None else float(pools[c] != "swing")
            for c in allc["candidate_id"]
        ]
        allc = allc.with_columns(pl.Series("f_tj_major_sweep", major, dtype=pl.Float64))
        report(allc)
        return
    for folder in sorted(RUNS.iterdir()):
        if not (folder / "run.json").exists() and not any(folder.glob("*.parquet")):
            continue
        df = build_dataset(folder)
        if df.height == 0:
            print(f"{folder.name}: no labelled candidates")
            continue
        df = tanja_features(folder, df, px).with_columns(pl.lit(folder.name).alias("run"))
        frames.append(df)
        print(f"{folder.name}: {df.height} labelled candidates", flush=True)
    allc = pl.concat(frames, how="diagonal_relaxed")
    with (OUT / "dataset.pkl").open("wb") as fh:
        pickle.dump(allc, fh)
    report(allc)


def report(allc: pl.DataFrame) -> None:
    groups = [("ALL setups, MNQ + MES pooled", allc)]
    for s in sorted(allc["setup"].unique()):
        groups.append((f"{s}, MNQ + MES", allc.filter(pl.col("setup") == s)))
    groups.append(("ALL setups, MNQ only", allc.filter(pl.col("run").str.contains("MNQ"))))
    for name, g in groups:
        g = g.sort("decision_time")
        print(f"\n=== {name} ({g.height} candidates, each as if taken, net R)")
        print("  D. Tanja's cues as fixed rules (nothing fitted):")
        print("\n".join(rules(g)))
        print("  B. ML filter, v1 features:      ", ml(g, drop_tanja=True))
        print("  C. ML filter, v1 + Tanja cues:  ", ml(g, drop_tanja=False), flush=True)


if __name__ == "__main__":
    main()
