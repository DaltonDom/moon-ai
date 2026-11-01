"""Training rows from a backtest run: one per labelled candidate.

Every candidate the trader saw is a row, taken or skipped, because labels
ignore portfolio state. Candidates skipped for the session calendar are left
out, since they were never tradeable, and so are unfilled limit entries, which
get no label. Rows carry the feature vector, the label, net R and the
entry-to-exit span (for purged cross-validation).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl

from moon_ai.config import Config, load_config
from moon_ai.data.news import NEWS_CSV, Blackout, load_events
from moon_ai.data.store import BarStore
from moon_ai.journal import decode_json, read_run
from moon_ai.ml.features import FEATURE_SET, build, daily_from_bars
from moon_ai.ml.labels import label_candidate
from moon_ai.sessions import NY, to_ny, window_bounds
from moon_ai.setups import load_setup_defaults
from moon_ai.setups.base import Candidate

LOOKBACK = timedelta(days=32)  # 20 sessions of same-minute history, plus weekends


def candidate_from_row(row: dict[str, Any], config: Config) -> Candidate:
    params = load_setup_defaults()[row["setup"]].params
    window = config.sessions.windows[params.window]
    _, deadline = window_bounds(to_ny(row["decision_time"]).date(), window)
    return Candidate(
        setup=row["setup"],
        symbol=row["symbol"],
        side=row["side"],
        decision_time=row["decision_time"],
        entry_type=row["entry_type"],
        entry=row["entry"],
        stop=row["stop"],
        target=row["target"],
        timeout=row["timeout"],
        entry_deadline=deadline if deadline > row["decision_time"] else None,
        rule_results=row["rule_results"] or {},
        features=row["features"] or {},
        feature_set=row["feature_set"] or "",
        tags=tuple(row["tags"] or ()),
    )


def build_dataset(
    folder: Path,
    store_root: Path | None = None,
    config: Config | None = None,
    news_csv: Path = NEWS_CSV,
) -> pl.DataFrame:
    config = config or load_config()
    store = BarStore(store_root or config.data.store_root, config.data.dataset)
    events = load_events(news_csv) if news_csv.exists() else []
    blackout = Blackout(events, config.ict)
    rows = [
        r
        for r in decode_json(read_run(folder, "candidates"), "candidates")
        if r["status"] != "skipped:session"
    ]
    by_month: dict[tuple[int, int, str], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        d = r["decision_time"]
        by_month[(d.year, d.month, r["symbol"])].append(r)
    out = []
    for (y, m, symbol), group in sorted(by_month.items()):
        start = datetime(y, m, 1, tzinfo=NY) - LOOKBACK
        end = max(r["timeout"] for r in group) + timedelta(minutes=5)
        bars = store.load(symbol, start, end)
        daily = daily_from_bars(
            store.load(symbol, start - timedelta(days=400), start)
        ) + daily_from_bars(bars)
        for r in group:
            cand = candidate_from_row(r, config)
            lab = label_candidate(
                cand,
                [
                    b
                    for b in bars
                    if b.ts_close >= cand.decision_time
                    and b.ts_open < cand.timeout + timedelta(minutes=2)
                ],
                config,
                blackout,
            )
            if lab is None:
                continue
            window = config.sessions.windows[load_setup_defaults()[cand.setup].params.window]
            feats = build(cand, bars, daily, events, config, window)
            out.append(
                {
                    "candidate_id": r["candidate_id"],
                    "setup": cand.setup,
                    "side": cand.side,
                    "decision_time": cand.decision_time,
                    "exit_time": lab.exit_time,
                    "label": lab.label,
                    "net_r": lab.net_r,
                    "status": r["status"],
                    "feature_set": FEATURE_SET,
                    **{f"f_{k}": v for k, v in feats.items()},
                }
            )
    return pl.DataFrame(out, infer_schema_length=None) if out else pl.DataFrame()
