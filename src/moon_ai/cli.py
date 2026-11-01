"""Command-line entry point: `moon-ai download ...`."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path

from moon_ai.config import load_config
from moon_ai.data.download import (
    DEFAULT_ENV_FILE,
    CostCapExceeded,
    Downloader,
    DownloadRequest,
    HistoricalClient,
    MissingApiKey,
    databento_client,
    resolve_api_key,
)


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="moon-ai")
    sub = p.add_subparsers(dest="command", required=True)

    d = sub.add_parser("download", help="download Databento bars (prices the request first)")
    d.add_argument("--config", type=Path, help="TOML config overriding the defaults")
    d.add_argument("--symbols", nargs="+", help="continuous symbols, e.g. MNQ.v.0")
    d.add_argument("--start", type=date.fromisoformat, required=True, help="YYYY-MM-DD")
    d.add_argument("--end", type=date.fromisoformat, required=True, help="YYYY-MM-DD, exclusive")
    d.add_argument("--schema", help="default from config (ohlcv-1m)")
    d.add_argument("--store", type=Path, help="local bar store root")
    d.add_argument("--max-cost", type=float, help="USD cap; default from config")
    d.add_argument("--dry-run", action="store_true", help="only price the request")
    d.add_argument("--confirm", action="store_true", help="allow a download above the cap")

    v = sub.add_parser("verify", help="run the tests and the frozen replay on your own data")
    v.add_argument("--config", type=Path, help="TOML config overriding the defaults")
    v.add_argument("--store", type=Path, help="local bar store root")
    v.add_argument(
        "--update-frozen",
        action="store_true",
        help="after an intentional change: rewrite tests/frozen/expected.json",
    )

    ng = sub.add_parser("nightly", help="the nightly paper replay: install, status, run, uninstall")
    ng.add_argument("action", choices=["install", "status", "run", "uninstall"])
    ng.add_argument("--session", type=date.fromisoformat, help="run: re-run one session")
    ng.add_argument("--scheduled", action="store_true", help=argparse.SUPPRESS)
    ng.add_argument("--data", type=Path, default=Path("data"), help="data folder")

    db = sub.add_parser("dashboard", help="serve the dashboard at http://localhost:8000")
    db.add_argument("action", nargs="?", default="serve", choices=["serve", "install", "uninstall"])
    db.add_argument("--port", type=int, default=8000)
    db.add_argument("--data", type=Path, default=Path("data"), help="data folder")

    wa = sub.add_parser("watcher", help="the ICT watcher: notes on ICT's new videos")
    wa.add_argument("--month", help="re-run a past month, YYYY-MM")
    wa.add_argument("--data", type=Path, default=Path("data"), help="data folder")

    tr = sub.add_parser("train", help="train the ML filter on the go-forward setups' backtests")
    tr.add_argument("--runs", type=Path, default=Path("data/runs"), help="where backtest runs are")
    tr.add_argument("--store", type=Path, help="local bar store root")
    tr.add_argument("--models", type=Path, default=Path("data/models"))
    tr.add_argument("--journal", type=Path, default=Path("data/journal/journal.sqlite"))

    rv = sub.add_parser("review-days", help="mark sampled days so the bot matches your ICT reading")
    rv.add_argument("setup", nargs="?", help="e.g. ny_am_silver_bullet")
    rv.add_argument("--days", type=int, default=50, help="how many days to sample (default 50)")
    rv.add_argument("--from", dest="start", type=date.fromisoformat, default=date(2019, 6, 3))
    rv.add_argument("--to", dest="end", type=date.fromisoformat, default=date(2026, 5, 1))
    rv.add_argument("--seed", type=int, default=7, help="which random sample")
    rv.add_argument("--store", type=Path, help="local bar store root")
    rv.add_argument("--out", type=Path, default=Path("data/review"), help="where the page goes")
    rv.add_argument("--no-open", action="store_true")
    rv.add_argument(
        "--import",
        dest="import_file",
        type=Path,
        help="save an exported verdict file as the CI ground-truth fixture",
    )

    doc = sub.add_parser("doctor", help="check the setup and say what to fix")
    doc.add_argument("--config", type=Path, help="TOML config overriding the defaults")

    b = sub.add_parser("backtest", help="backtest one setup over a date range")
    b.add_argument("setup", nargs="?", help="e.g. ny_am_silver_bullet (or use --all)")
    b.add_argument(
        "--all",
        action="store_true",
        help="run the full protocol for every setup: defaults, rescue retests, verdicts",
    )
    b.add_argument(
        "--from",
        dest="start",
        type=date.fromisoformat,
        required=True,
        help="first trading day, YYYY-MM-DD",
    )
    b.add_argument(
        "--to",
        dest="end",
        type=date.fromisoformat,
        required=True,
        help="trading day after the last one, YYYY-MM-DD (exclusive)",
    )
    b.add_argument("--trial", help="a pre-registered rescue trial name (default: the default)")
    b.add_argument("--config", type=Path, help="TOML config overriding the defaults")
    b.add_argument("--store", type=Path, help="local bar store root")
    b.add_argument("--runs", type=Path, default=Path("data/runs"), help="where runs are written")
    b.add_argument(
        "--no-open", action="store_true", help="don't open the report card in the browser"
    )
    b.add_argument(
        "--no-news",
        action="store_true",
        help="run without the news blackout (results will be optimistic)",
    )
    return p


def main(
    argv: Sequence[str] | None = None,
    client_factory: Callable[[str], HistoricalClient] = databento_client,
) -> int:
    args = _parser().parse_args(argv)
    if args.command == "backtest":
        return _backtest(args)
    if args.command == "nightly":
        return _nightly(args)
    if args.command == "dashboard":
        return _dashboard(args)
    if args.command == "watcher":
        return _watcher(args)
    if args.command == "train":
        return _train(args)
    if args.command == "review-days":
        return _review_days(args)
    if args.command == "verify":
        return _verify(args)
    if args.command == "doctor":
        from moon_ai.doctor import report, run_checks

        text, code = report(run_checks(load_config(args.config)))
        print(text)
        return code
    cfg = load_config(args.config).data

    request = DownloadRequest(
        symbols=tuple(args.symbols or cfg.symbols),
        start=args.start,
        end=args.end,
        dataset=cfg.dataset,
        schema=args.schema or cfg.schema,
        stype_in=cfg.stype_in,
    )
    cap = args.max_cost if args.max_cost is not None else cfg.max_cost_usd

    try:
        client = client_factory(resolve_api_key(env_file=DEFAULT_ENV_FILE))
        downloader = Downloader(client, store_root=args.store or cfg.store_root, max_cost_usd=cap)
        result = downloader.download(request, confirm=args.confirm, dry_run=args.dry_run)
    except (CostCapExceeded, MissingApiKey) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2

    symbols = ", ".join(request.symbols)
    print(f"estimated cost ${result.cost_usd:.2f} (cap ${cap:.2f}) for {symbols}")
    if args.dry_run:
        print("dry run: nothing downloaded")
    for path in result.files:
        print(f"wrote {path}")
    return 0


def _watcher(args: argparse.Namespace) -> int:
    import os

    from moon_ai.watcher.run import Watcher, claude_summariser

    summarise = None
    if os.environ.get("ANTHROPIC_API_KEY"):
        import anthropic

        summarise = claude_summariser(anthropic.Anthropic())
    github = None
    if os.environ.get("GITHUB_TOKEN"):
        from moon_ai.dashboard.proposals import RestGitHub

        github = RestGitHub
    res = Watcher(
        args.data / "watcher", Path("reports/watcher"), summarise=summarise, github=github
    ).run(month=args.month)
    print(res.message())
    return 0


def _dashboard(args: argparse.Namespace) -> int:
    if args.action in ("install", "uninstall"):
        from moon_ai.nightly import launchd

        if sys.platform != "darwin":
            print(
                "refused: the dashboard agent uses macOS launchd; run this on the Mac",
                file=sys.stderr,
            )
            return 2
        if args.action == "install":
            launchd.install(label=launchd.DASHBOARD_LABEL)
            print("Installed: the dashboard stays up at http://localhost:8000. Bookmark it.")
        else:
            gone = launchd.uninstall(label=launchd.DASHBOARD_LABEL)
            print("Removed the dashboard agent." if gone else "It wasn't installed.")
        return 0
    import uvicorn

    from moon_ai.dashboard.api import create_app
    from moon_ai.nightly.job import Paths

    ui = Path(__file__).parent / "dashboard" / "ui"
    app = create_app(paths=Paths(args.data), static_dir=ui, run_worker=True)
    # 127.0.0.1 only: the dashboard is never reachable from another machine.
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
    return 0


def _nightly(args: argparse.Namespace) -> int:
    from moon_ai.nightly import launchd
    from moon_ai.nightly.job import NightlyJob, Paths
    from moon_ai.nightly.status import status_text

    paths = Paths(args.data)
    if args.action == "install":
        if sys.platform != "darwin":
            print(
                "refused: the nightly agent uses macOS launchd; run this on the Mac",
                file=sys.stderr,
            )
            return 2
        path = launchd.install()
        print(f"Installed {path}. It checks every hour and runs once a day after 6:30 pm New York.")
        print("Doing a first run now on the latest session ...")
        args.action = "run"
    if args.action == "uninstall":
        print(
            "Removed the nightly agent; your data stays."
            if launchd.uninstall()
            else "The nightly agent wasn't installed."
        )
        return 0
    if args.action == "status":
        print(status_text(paths))
        return 0
    results = NightlyJob(paths).run(only_session=args.session, scheduled=args.scheduled)
    for r in results:
        mark = {"ok": "✓", "warn": "!", "skipped": "-", "fail": "✕"}[r.status]
        print(f"{mark} {r.step}: {r.message}")
    return 1 if any(r.status == "fail" for r in results) else 0


def _train(args: argparse.Namespace) -> int:
    import json

    import polars as pl

    from moon_ai.journal import SQLiteStore
    from moon_ai.ml.dataset import build_dataset
    from moon_ai.ml.train import register, save_model, train

    verdicts = args.runs / "verdicts.json"
    if not verdicts.exists():
        print(
            "refused: run `moon-ai backtest --all` first; the filter trains only on setups "
            "that passed",
            file=sys.stderr,
        )
        return 2
    passed = [v for v in json.loads(verdicts.read_text())["setups"] if v["verdict"] == "go-forward"]
    if not passed:
        print(
            "No setup passed its backtest, so there's nothing to train on. The ML filter "
            "stays off and nothing trades."
        )
        return 0
    frames = [build_dataset(Path(v["report"]).parent, store_root=args.store) for v in passed]
    df = pl.concat([f for f in frames if f.height], how="diagonal_relaxed")
    report, model = train(df)
    if model is None:
        print("The ML filter stays off (setups trade rules-only):")
        for r in report.reasons:
            print(f"  - {r}")
        return 0
    print(f"Trained on {report.rows} candidates ({report.oof_rows} judged out of sample).")
    print(f"Taking every setup: {report.rules_only_mean_r:+.3f}R per trade.")
    print(
        f"With the filter: {report.ml_mean_r:+.3f}R per trade on {report.ml_taken} trades."
        if report.ml_mean_r is not None
        else "With the filter: it would take nothing."
    )
    print(
        "The filter beats rules-only."
        if report.ml_beats_rules_only
        else "The filter does NOT beat rules-only, so it stays off."
    )
    window = (df["decision_time"].min(), df["decision_time"].max())
    mid = save_model(model, report, args.models, window, [v["report"] for v in passed])
    meta = json.loads((args.models / mid / "meta.json").read_text())
    register(SQLiteStore(args.journal), mid, meta)
    print(f"Saved model {mid} as a challenger; promotion decides if it ever trades.")
    return 0


def _review_days(args: argparse.Namespace) -> int:
    from moon_ai.data.store import BarStore
    from moon_ai.groundtruth import import_verdicts, sample_days
    from moon_ai.groundtruth.page import build

    store = BarStore(args.store or load_config().data.store_root)
    if args.import_file:
        folder = import_verdicts(args.import_file, store)
        print(f"saved the ground truth to {folder}; commit it so CI checks it")
        return 0
    if not args.setup:
        print("refused: name a setup, or use --import FILE", file=sys.stderr)
        return 2
    days = sample_days(store, args.start, args.end, args.days, args.seed)
    if not days:
        print(f"refused: no price data in {store.root} for those dates", file=sys.stderr)
        return 2
    args.out.mkdir(parents=True, exist_ok=True)
    page = args.out / f"review-{args.setup}.html"
    page.write_text(build(args.setup, days, store))
    print(f"review page for {len(days)} days: {page}")
    if not args.no_open:
        import webbrowser

        webbrowser.open(page.resolve().as_uri())
    return 0


def _verify(args: argparse.Namespace) -> int:
    import subprocess

    from moon_ai.backtest.frozen import (
        END,
        FIXTURE_STORE,
        REPO,
        START,
        diff,
        load_expected,
        replay,
        write_expected,
    )
    from moon_ai.data.store import BarStore

    if args.update_frozen:
        write_expected(replay(FIXTURE_STORE))
        print("rewrote tests/frozen/expected.json; commit it with the change that moved it")
        return 0
    print("Running the tests ...")
    tests = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=REPO)
    ok = tests.returncode == 0
    print("✓ tests pass" if ok else "✕ some tests fail (see above)")
    store = BarStore(args.store or load_config(args.config).data.store_root)
    if all(store.covers("MNQ.v.0", d) for d in (START, END)):
        problems = diff(load_expected(), replay(store.root))
        if problems:
            ok = False
            print("✕ the frozen replay on your own data differs from the committed one:")
            for line in problems[:20]:
                print(f"    {line}")
        else:
            print("✓ the frozen replay on your own data matches exactly")
    else:
        print(f"! your data doesn't cover {START} to {END}, so only the bundled replay ran")
    return 0 if ok else 1


def _backtest(args: argparse.Namespace) -> int:
    from moon_ai.backtest.runner import NewsCalendarMissing, run_backtest

    if args.all:
        return _backtest_all(args)
    if not args.setup:
        print("refused: name a setup, or use --all", file=sys.stderr)
        return 2

    try:
        result = run_backtest(
            args.setup,
            args.start,
            args.end,
            trial=args.trial,
            store_root=args.store,
            runs_root=args.runs,
            config=load_config(args.config),
            news=not args.no_news,
        )
    except (NewsCalendarMissing, KeyError, ValueError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    print(result.line())
    print(f"wrote {result.folder}")
    from moon_ai.backtest.evaluate import evaluate

    ev = evaluate(result.folder, store_root=args.store, config=load_config(args.config))
    lo, hi = ev.edge_ci
    edge = "no trades to compare" if lo != lo else f"{lo:+.3f}R to {hi:+.3f}R per trade (95% CI)"
    print(
        f"verdict: {ev.verdict} | edge vs random entries {edge} | "
        f"not-just-luck (DSR) {ev.dsr:.2f} over {ev.n_trials} trial(s)"
    )
    for reason in ev.reasons:
        print(f"  - {reason}")
    stress = None
    if ev.verdict == "go-forward":
        from moon_ai.backtest.evaluate import stress_test

        stress = stress_test(
            args.setup,
            args.trial,
            args.start,
            args.end,
            store_root=args.store,
            runs_root=args.runs,
            config=load_config(args.config),
            news=not args.no_news,
        )
        print(
            f"double-slippage re-run: {'still profitable' if stress.net_r > 0 else 'loses money'}"
        )
    from moon_ai.backtest.report import render

    page = render(ev, result.folder, stress)
    print(f"report card: {page}")
    if not args.no_open:
        import webbrowser

        webbrowser.open(page.resolve().as_uri())
    return 0


def _backtest_all(args: argparse.Namespace) -> int:
    from moon_ai.backtest.protocol import WORDS, judge_all
    from moon_ai.backtest.runner import NewsCalendarMissing

    try:
        verdicts = judge_all(
            args.start,
            args.end,
            args.runs,
            store_root=args.store,
            config=load_config(args.config),
            news=not args.no_news,
        )
    except NewsCalendarMissing as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    for v in verdicts:
        how = "" if v.trial == "default" else f" with retest {v.trial}"
        print(f"{v.title}: {WORDS[v.verdict][0]}{how} ({len(v.trials_run)} version(s) tested)")
    summary = args.runs / "summary.html"
    print(f"summary: {summary}")
    if not args.no_open:
        import webbrowser

        webbrowser.open(summary.resolve().as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
