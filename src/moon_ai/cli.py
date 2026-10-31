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
    return p


def main(
    argv: Sequence[str] | None = None,
    client_factory: Callable[[str], HistoricalClient] = databento_client,
) -> int:
    args = _parser().parse_args(argv)
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


if __name__ == "__main__":
    raise SystemExit(main())
