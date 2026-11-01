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

    doc = sub.add_parser("doctor", help="check the setup and say what to fix")
    doc.add_argument("--config", type=Path, help="TOML config overriding the defaults")

    b = sub.add_parser("backtest", help="backtest one setup over a date range")
    b.add_argument("setup", help="e.g. ny_am_silver_bullet")
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


if __name__ == "__main__":
    raise SystemExit(main())
