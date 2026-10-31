# moon-ai

Autonomous, self-improving ICT trading bot for CME micro futures (MNQ first). The design is in [`docs/design.md`](docs/design.md), and planning runs on the [wayfinder map](https://github.com/DaltonDom/moon-ai/issues/1).

This repository currently holds the **Track A foundation**: config, the Databento downloader, the event loop with a simulated broker, and the ICT primitives.

## Setup on a Mac (Apple Silicon)

1. Install [uv](https://docs.astral.sh/uv/):

   ```sh
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. From the repository root, create the environment. uv fetches Python 3.12+ if needed:

   ```sh
   uv sync
   ```

3. Run the tests and the linter:

   ```sh
   uv run pytest
   uv run ruff check
   ```

The same commands work on Linux.

## Databento downloads

Put your API key in the environment or in `~/.config/moon-ai/.env`, never in the repository:

```sh
mkdir -p ~/.config/moon-ai
echo 'DATABENTO_API_KEY=db-...' > ~/.config/moon-ai/.env
chmod 600 ~/.config/moon-ai/.env
```

**Dry run (cost check only).** This calls Databento's free `get_cost` and downloads nothing:

```sh
uv run moon-ai download --symbols MNQ.v.0 NQ.v.0 --start 2019-05-06 --end 2026-10-30 --dry-run
```

The command prints the estimated cost and the cap. Without `--dry-run`, it prices the request first and then:

- **refuses** if the estimate is above the cap (`--max-cost`, default $15 from config);
- downloads above the cap only with an explicit `--confirm`;
- writes raw Parquet to `data/bars/GLBX.MDP3/ohlcv-1m/<symbol>/<start>_<end>.parquet` (git-ignored);
- appends each paid symbol to `data/bars/ledger.jsonl` as soon as it is written, so a request that fails partway still records what was bought.

`--end` is exclusive. Without a CME subscription, keep it at least 24 hours in the past.

Defaults: dataset `GLBX.MDP3`, schema `ohlcv-1m`, `stype_in=continuous`, symbols `MNQ.v.0 MES.v.0 NQ.v.0 ES.v.0`. Override them with `--config my.toml`; see `src/moon_ai/config.py` for every key.

## Layout

```text
src/moon_ai/
├── config.py        # typed config; every unverified ICT parameter, with research defaults
├── sessions.py      # America/New_York windows (DST-safe), CME trading day
├── bars.py          # Bar (ts_open/ts_close), BarFeed interface, roll marking
├── broker.py        # Broker interface, SimBroker (brackets, pessimistic same-bar rule)
├── engine.py        # event loop: BarFeed -> Broker -> Strategy
├── journal.py       # Journal interface, in-memory journal
├── cli.py           # `moon-ai download`
├── data/download.py # cost-guarded Databento downloader
└── ict/             # primitives: swings, fvg, displacement, liquidity, structure, windows
```

## Rules the code enforces

- **Bars are stamped at their open.** A bar becomes known at `ts_open + 1 minute`, and the engine hands the strategy only closed bars.
- **Fills come after the decision.** Orders fill no earlier than the bar after the decision.
- **Same-bar stop and target.** When one bar touches both, the stop fills first, unless 1-second bars for that minute are supplied.
- **Every primitive output carries `known_at`.** `tests/test_ict_lookahead.py` proves that no primitive uses future bars.
