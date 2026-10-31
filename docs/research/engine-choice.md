# Research: Is NautilusTrader the right engine on an Apple Silicon Mac?

*Compiled 2026-10-31 for [issue #4](https://github.com/DaltonDom/moon-ai/issues/4), a child of the map in [issue #1](https://github.com/DaltonDom/moon-ai/issues/1). It follows on from [ict-ml-trading-bot.md §3](./ict-ml-trading-bot.md#3-backtesting--trading-frameworks) and tests the "Engine: Python, NautilusTrader" line in [design.md](../design.md#stack) against Phases 1–2.*

> **How this was sourced.** nautilustrader.io was not fetched. Every NautilusTrader claim below comes from one of two places: the GitHub source at `develop` commit [`b60466a`](https://github.com/nautechsystems/nautilus_trader/tree/b60466a58e88789060fb7ce643328e035ad528c4) (2026-10-31), or the PyPI JSON API (queried 2026-10-31). I installed `nautilus_trader==2.0.0rc8` into a throwaway Linux venv and inspected its API. For backtesting.py 0.6.6, vectorbt 1.2.0 and databento 0.89.0, I unpacked the PyPI wheels and read the source. Nothing was run on a Mac. Anything I could not confirm is marked **UNVERIFIED**.

## 1. Answer

**Not for Phases 1–2. Build a lean custom event loop on Polars, and look at NautilusTrader again at Phase 3, once 2.0 is final.**

The deciding factors:

1. **NautilusTrader is in the middle of a major-version rewrite.**
   - `develop` is now v2 (a Rust core with PyO3 bindings), at **2.0.0rc9**.
   - The old Cython v1 lives on `develop_v1`. After the cutover, v1 gets "only critical security backports for approximately three months … no feature or parity work" ([MIGRATION_V2.md](https://github.com/nautechsystems/nautilus_trader/blob/b60466a58e88789060fb7ce643328e035ad528c4/MIGRATION_V2.md)).
   - The v2 release candidates still break things in every release. The rc9 notes list about 30 breaking changes, including **changed Databento futures instrument IDs**, which force you to "rebuild stored data" ([RELEASES.md](https://github.com/nautechsystems/nautilus_trader/blob/b60466a58e88789060fb7ce643328e035ad528c4/RELEASES.md)).
   - Starting on v1 means porting later. Starting on v2 means building on a moving API.
2. **Its bar-fill model doesn't remove our hardest realism problem.**
   - With 1-minute bars, a stop and a target in the same bar are resolved by a fixed path: `O→H→L→C` by default, or an "adaptive" heuristic. The docs describe the heuristic as "not a reconstruction of the actual trade sequence".
   - There is no "pessimistic" option.
   - The default path always fills a long's target before its stop, which biases long trades upwards (§3.3).
   - So we would write custom resolution logic either way.
3. **Most of what NautilusTrader offers, we don't use.** It is built for multi-venue, order-book, nanosecond-resolution trading. Phases 1–2 need one instrument (MNQ), 1-minute bars, bracket orders, and a rich per-candidate journal.
   - The Databento adapter is convenient, but the official `databento` Python client already writes Parquet and DataFrames (§3.2).
   - NautilusTrader's catalog needs data converted to its own Arrow schema, so it can't just read our Parquet files as they are.
4. **Installing on the Mac works, with a catch.**
   - The latest stable v1 wheel (1.231.0) is tagged **`macosx_26_0_arm64`**, so pip installs it only on macOS 26 or later.
   - The v2 release-candidate wheels are tagged `macosx_11_0_arm64`, although the docs officially support macOS 15+ only.
   - This decides nothing, but it is one more source of friction.
5. **The live path doesn't need it.** In our design, NinjaTrader 8 holds the broker-side bracket orders ([design.md](../design.md#hard-risk-rules-ml-cannot-override)). The Python side only has to:
   - send a bracket order
   - receive fills and bars

   A narrow `Broker` / `BarFeed` interface in our own loop covers this. NautilusTrader v2 *does* support custom Python live adapters (§3.7), so the door stays open.

vectorbt and backtesting.py are worse fits than either option (§4). vectorbt is still useful as a **research side tool** for parameter sweeps.

## 2. Comparison table

| Criterion | NautilusTrader | Lean custom loop (Polars) | vectorbt 1.2.0 (OSS) | backtesting.py 0.6.6 |
|---|---|---|---|---|
| **macOS arm64 install** | v1 1.231.0: wheel needs macOS 26+. v2 rc8: `macosx_11_0` wheel; docs support macOS 15+; Python 3.13–3.14 ([PyPI](https://pypi.org/project/nautilus_trader/#files), [installation.md](https://github.com/nautechsystems/nautilus_trader/blob/b60466a58e88789060fb7ce643328e035ad528c4/docs/getting_started/installation.md)) | Pure Python plus Polars and LightGBM, which both ship arm64 wheels ([polars](https://pypi.org/project/polars/#files), [lightgbm `macosx_12_0_arm64`](https://pypi.org/project/lightgbm/#files)) | Pure-Python wheel (Numba-based); Python 3.11–3.14 ([PyPI](https://pypi.org/project/vectorbt/)) | Pure-Python wheel; Python ≥3.9 ([PyPI](https://pypi.org/project/backtesting/)) |
| **Databento data** | Built-in adapter: DBN loader, historical and live clients; `GLBX.MDP3`; OHLCV-1s/1m/1h/1d → `Bar` ([databento.md](https://github.com/nautechsystems/nautilus_trader/blob/b60466a58e88789060fb7ce643328e035ad528c4/docs/integrations/databento.md)) | Official `databento` client (Apache-2.0): `DBNStore.to_df()` / `to_parquet()` / `replay()` | None; you pass arrays | None; you pass a pandas OHLC DataFrame |
| **Our own Parquet** | Only through `ParquetDataCatalog` with Nautilus Arrow schemas. The v2 catalog schema differs from v1 and needs migration ([catalog.md](https://github.com/nautechsystems/nautilus_trader/blob/b60466a58e88789060fb7ce643328e035ad528c4/docs/concepts/data/catalog.md), [MIGRATION_V2.md](https://github.com/nautechsystems/nautilus_trader/blob/b60466a58e88789060fb7ce643328e035ad528c4/MIGRATION_V2.md)) | Native: `pl.scan_parquet` | Yes, via pandas | Yes, via pandas |
| **Bar vs tick fills** | Both. Each bar becomes 4 synthetic L1 updates; tick and order-book backtests are also supported ([bar-execution.md](https://github.com/nautechsystems/nautilus_trader/blob/b60466a58e88789060fb7ce643328e035ad528c4/docs/concepts/backtesting/bar-execution.md)) | Whatever we write: 1m bars, plus a 1s drill-down where it matters (§3.3) | Bars only (vectorized) | Bars only |
| **Stop and target in the same bar** | Fixed path `O→H→L→C` (default) or adaptive "nearest extreme first". No pessimistic mode | We choose: pessimistic by default, resolved from 1s bars when available | **Stop first** ("pessimistically assume that SL comes before TP"; `signals/nb.py`) | **Stop first** ("Ensure SL orders are processed first"; `backtesting.py` L810–811) |
| **Nightly forward replay** | One-day `BacktestNode` run; same strategy code as live | One-day run through the same `BarFeed`; trivial | Re-run on one day; no event semantics | Re-run on one day |
| **LightGBM in the strategy** | Any Python inside `on_bar`. v2 strategy configs are PyO3 types, so custom fields need an explicit `__init__` ([MIGRATION_V2.md](https://github.com/nautechsystems/nautilus_trader/blob/b60466a58e88789060fb7ce643328e035ad528c4/MIGRATION_V2.md)). Built-in ML is "out of scope" ([README](https://github.com/nautechsystems/nautilus_trader/blob/b60466a58e88789060fb7ce643328e035ad528c4/README.md)) | Direct call per candidate | Only by precomputing features and probabilities in arrays | Any Python inside `next()` |
| **Journal of every candidate and decision** | Engine logs to text or **JSONL** files ([logging.md](https://github.com/nautechsystems/nautilus_trader/blob/b60466a58e88789060fb7ce643328e035ad528c4/docs/concepts/logging.md)); the candidate journal is ours to write | Ours to write; it is a first-class part of the loop | Poor fit: no per-event hook | Ours to write inside `next()` |
| **Path to a NinjaTrader bridge** | Custom Python `DataClient` / `ExecutionClient` subclasses registered on `LiveNode` ([python_adapters.md](https://github.com/nautechsystems/nautilus_trader/blob/b60466a58e88789060fb7ce643328e035ad528c4/docs/developer_guide/python_adapters.md)) | Implement the same `Broker` / `BarFeed` interface against the bridge | None (OSS has no live trading) | None |
| **Multi-instrument later** | Yes | Our design must allow it (design.md requires it) | Yes | No; one instrument per backtest |
| **Licence** | LGPL-3.0-or-later ([PyPI](https://pypi.org/project/nautilus_trader/)) | Ours | Apache-2.0 **with Commons Clause**, which bars selling a product built on it (`LICENSE.md` in the wheel) | **AGPL-3.0** ([PyPI](https://pypi.org/project/backtesting/)) |
| **Maintenance** | Very active: 613 commits on `develop` in Oct 2026, of which 482 (~79%) are by one maintainer. v1 frozen; v2 at release candidate | Ours | Active: 91 commits since 2026-05-01; last 2026-10-28 | Slow: 27 commits since 2026-05-01; last 2026-08-05 |
| **API stability, next 6 months** | **Low**: v2 rc series with breaking changes each release | High (we own it) | Medium | Medium |

Commit counts come from shallow clones of each repository on 2026-10-31.

## 3. NautilusTrader in detail

### 3.1 Platform support (macOS arm64)

- **PyPI wheels by release** (PyPI JSON API):
  - 1.213–1.219: `macosx_14_0_arm64`
  - 1.220–1.230: `macosx_15_0_arm64`
  - **1.231.0 (2026-08-02): `macosx_26_0_arm64`**
  - 2.0.0rc3–rc8 (2026-08-21 → 2026-10-29): `macosx_11_0_arm64`
- A wheel tagged `macosx_26_0` installs only on macOS 26 or newer. On an older macOS, pip falls back to the sdist, which needs the Rust toolchain. **UNVERIFIED**: I did not test this fallback on a Mac.
- The official support table lists **macOS 15.0 and later, ARM64**, Python 3.13–3.14. CI uses `macos-latest`, "so support tracks that runner image as it moves ahead" ([installation.md](https://github.com/nautechsystems/nautilus_trader/blob/b60466a58e88789060fb7ce643328e035ad528c4/docs/getting_started/installation.md)).
- v1 and v2 both import as `nautilus_trader` and must live in separate venvs ([MIGRATION_V2.md](https://github.com/nautechsystems/nautilus_trader/blob/b60466a58e88789060fb7ce643328e035ad528c4/MIGRATION_V2.md)).
- **UNVERIFIED**: the user's macOS version. If it is older than 26, the stable v1 line has no matching wheel.

### 3.2 Data: Databento and our own Parquet

- **Databento adapter.**
  - It uses the official `databento-rs` crate and provides `DatabentoDataLoader` (DBN files), a historical client, a live client and a `LiveNode` data client.
  - `GLBX.MDP3` is supported. OHLCV-1s/1m/1h/1d decode to `Bar`, timestamped at bar close by default (`bars_timestamp_on_close`).
  - Databento is "a market data provider only … no execution client".
  - Continuous symbols (`ES.c.0`) work for historical requests. Some live subscriptions accept explicit contracts only (`ESZ26.GLBX`).
  - Source: [databento.md](https://github.com/nautechsystems/nautilus_trader/blob/b60466a58e88789060fb7ce643328e035ad528c4/docs/integrations/databento.md).
- **Own Parquet.**
  - `ParquetDataCatalog` stores Nautilus types in Parquet using Nautilus Arrow schemas ([catalog.md](https://github.com/nautechsystems/nautilus_trader/blob/b60466a58e88789060fb7ce643328e035ad528c4/docs/concepts/data/catalog.md)). Arbitrary Parquet has to be converted to `Bar` objects first, for example with `BarDataWrangler`, with `ts_init` set to bar close ([bar-execution.md](https://github.com/nautechsystems/nautilus_trader/blob/b60466a58e88789060fb7ce643328e035ad528c4/docs/concepts/backtesting/bar-execution.md)).
  - The v2 catalog schema differs from v1 and needs a migration step.
  - v2 `BacktestNode` does not support "custom data, or data frames" from the catalog config ([MIGRATION_V2.md, Known limitations](https://github.com/nautechsystems/nautilus_trader/blob/b60466a58e88789060fb7ce643328e035ad528c4/MIGRATION_V2.md#known-limitations)).
- **The plain alternative.** The `databento` Python client (0.89.0, Apache-2.0) has `DBNStore.to_df()`, `to_parquet()` and `replay(callback)` (`databento/common/dbnstore.py` in the wheel). Polars reads the resulting Parquet directly.

### 3.3 Backtest realism: bars vs ticks, and the same-bar stop/target problem

From [bar-execution.md](https://github.com/nautechsystems/nautilus_trader/blob/b60466a58e88789060fb7ce643328e035ad528c4/docs/concepts/backtesting/bar-execution.md) and [fill-models.md](https://github.com/nautechsystems/nautilus_trader/blob/b60466a58e88789060fb7ce643328e035ad528c4/docs/concepts/backtesting/fill-models.md):

- **How a bar is processed.** Each external time bar becomes four synthetic L1 updates (open, high and low in the configured order, then close), and orders are matched after each one. Orders submitted from `on_bar(N)` arrive only after bar N's whole sweep.
- **`bar_adaptive_high_low_ordering`:**
  - `False` (the default) always uses `O→H→L→C`.
  - `True` visits the extreme nearer the open first. This is "a deterministic heuristic, not a reconstruction of the actual trade sequence". The only evidence cited for it is an exploratory EUR/USD gist.
  - Confirmed in the installed 2.0.0rc8 API: `BacktestEngine.add_venue(..., bar_execution=True, bar_adaptive_high_low_ordering=False, ...)`.
- **What the default does to our trades.** For a **long** bracket with the stop below and the target above, both inside one bar, `O→H→L→C` reaches the high first, so **the target always wins**. For a short, the stop always wins. This is a systematic long-side bias. There is no "stop first" setting.
- **No native next-bar-open fills.** Using the current bar's open inside `on_bar` is look-ahead.
- **Fill models.** The fill models (`prob_fill_on_limit`, one-tick `prob_slippage`, tiered synthetic books) are useful, but cover only one-tick L1 slippage.
- **Ticks and order books.** Tick-level (`TradeTick`, `QuoteTick`) and L2/L3 book backtests are supported, and would remove the same-bar ambiguity. They need Databento `trades`/`mbp-1` data for 5+ years of MNQ. **UNVERIFIED**: the cost against the $125 credit.

**Implication for us:** every engine needs an explicit policy for same-bar stop/target hits. We can write the best one ourselves:

1. Check each bar for a stop and target hit together.
2. If both are hit, look up the 1-second bars (Databento `ohlcv-1s`) for that minute and replay them.
3. If the 1-second bars are missing or still ambiguous, assume the stop filled first.
4. Log each ambiguous case in the journal.

This is about 50 lines in a custom loop. In NautilusTrader it would mean feeding 1-second bars for the whole run, or a custom matching module.

### 3.4 Paper: nightly forward replay

- Phase 2 replays that day's 1-minute bars after the close ([design.md](../design.md#phases--where-they-run)). That is just a one-day backtest with the same strategy code, so any engine can do it.
- NautilusTrader's advantage is that the *same* `Strategy` class later runs under `LiveNode`. It also has a `sandbox` adapter for simulated execution against live data (`crates/adapters/sandbox`). Neither is needed in Phase 2.
- A custom loop gets the same parity by keeping strategy code behind `BarFeed` (history file, or later the bridge) and `Broker` (simulator, or later the bridge).

### 3.5 ML: LightGBM inside a strategy

- The README says "built-in AI/ML tooling [is] out of scope" ([README](https://github.com/nautechsystems/nautilus_trader/blob/b60466a58e88789060fb7ce643328e035ad528c4/README.md)), and the [ROADMAP](https://github.com/nautechsystems/nautilus_trader/blob/b60466a58e88789060fb7ce643328e035ad528c4/ROADMAP.md) says the same.
- A Python strategy can call `booster.predict()` in `on_bar`. Nothing prevents this.
- In v2, configs are Rust/PyO3 types. Custom fields need keyword-only `__init__` arguments, and "annotated custom fields on v1 `StrategyConfig` subclasses do not carry over" ([MIGRATION_V2.md](https://github.com/nautechsystems/nautilus_trader/blob/b60466a58e88789060fb7ce643328e035ad528c4/MIGRATION_V2.md)). This is friction, not a blocker.
- **UNVERIFIED**: the per-callback overhead of Rust→Python dispatch over about 1.7M one-minute bars (5 years of MNQ). It is not benchmarked here.

### 3.6 Logging for the journal

- The engine logger writes to stdout and/or files, as plain text or **JSON (`.jsonl`)**, with daily or size-based rotation ([logging.md](https://github.com/nautechsystems/nautilus_trader/blob/b60466a58e88789060fb7ce643328e035ad528c4/docs/concepts/logging.md)).
- Order and position events can be persisted to the catalog. Note that "catalog order-event data written before `activation_price` … cannot be read by the new schema", which is another v1→v2 migration hazard ([MIGRATION_V2.md](https://github.com/nautechsystems/nautilus_trader/blob/b60466a58e88789060fb7ce643328e035ad528c4/MIGRATION_V2.md)).
- Our per-candidate record has to be written by us with any engine. It needs the feature vector, rules passed and failed, ML probability, planned prices, MAE/MFE and exit reason (see [design.md, Trade journal](../design.md#trade-journal--metrics) and [ict-ml-trading-bot.md §5.2](./ict-ml-trading-bot.md#52-trade-log-record-proposed-schema)).

### 3.7 Later live trading: custom adapter for the NinjaTrader bridge

- v2 supports custom live adapters written in Python. You subclass `DataClient` / `ExecutionClient` from `nautilus_trader.live.clients`, register a factory on `LiveNodeBuilder`, and the clients run on the node's Python event loop ([python_adapters.md](https://github.com/nautechsystems/nautilus_trader/blob/b60466a58e88789060fb7ce643328e035ad528c4/docs/developer_guide/python_adapters.md), [python.md#support-boundaries](https://github.com/nautechsystems/nautilus_trader/blob/b60466a58e88789060fb7ce643328e035ad528c4/docs/concepts/python.md)). A deterministic adapter template is provided (`examples/live/_template`).
- Contingency orders (`OCO`, `OUO`, `OTO`) are supported ([README](https://github.com/nautechsystems/nautilus_trader/blob/b60466a58e88789060fb7ce643328e035ad528c4/README.md)), so brackets could map onto NinjaTrader ATM/OCO orders. **UNVERIFIED**: no NinjaTrader adapter exists in-tree. The in-tree adapter list is `architect_ax betfair binance blockchain bybit coinapi coinbase databento deribit derive dydx hyperliquid interactive_brokers kraken lighter okx polymarket sandbox tardis`.
- The adapter API is itself v2-new and still changing. The rc9 notes include adapter config breaking changes ([RELEASES.md](https://github.com/nautechsystems/nautilus_trader/blob/b60466a58e88789060fb7ce643328e035ad528c4/RELEASES.md)).

### 3.8 Status: licence and maintenance

- **Licence: LGPL-3.0-or-later** (PyPI `license_expression`). Using it as a library in a private, undistributed bot creates no source-release obligation. LGPL obligations attach to distribution.
- **Maintenance: very active.** There were 613 commits on `develop` in October 2026, and 482 of them (about 79%) were by the lead maintainer. That is a bus-factor consideration.
- **Version state:**
  - Stable 1.231.0 (2026-08-02) is the last v1 release on PyPI.
  - v2 release candidates have shipped roughly every two weeks since 2026-08-21 (rc3→rc8). rc9 is in progress on `develop`.
  - The ROADMAP calls v2.0 "a significant milestone toward establishing a stable API" ([ROADMAP.md](https://github.com/nautechsystems/nautilus_trader/blob/b60466a58e88789060fb7ce643328e035ad528c4/ROADMAP.md)).
- **UNVERIFIED**: a release date for 2.0.0 final. None was found in the repository.

## 4. The alternatives

### 4.1 Lean custom event loop (Polars)

- **Shape:**
  - `BarFeed` (Parquet history, or later the NinjaTrader bridge)
  - setup detectors (one file per setup, as design.md requires)
  - candidate → features → LightGBM probability → hard risk rules → `Broker`
  - `Broker` is a bracket-order simulator, or later the bridge
  - the journal writer records every candidate, taken or not
- **Pros:**
  - Fill and same-bar policy are explicit and testable against the ground-truth set and frozen replay.
  - No foreign data schema.
  - No upstream breaking changes.
  - Trivially deterministic.
  - Runs anywhere Polars runs.
- **Cons:**
  - We own the order and position accounting, commissions, slippage and session/rollover handling, so there is more room for our own bugs.
  - Mitigations: the design's ground-truth CI, the frozen replay, and a small hand-checked test suite for the simulator (bracket fill cases, gaps through stops, flat-by-16:00).
  - Multi-instrument support must be designed in from the start.

### 4.2 vectorbt 1.2.0 (open-source edition)

- Vectorized and fast, which makes it excellent for sweeping detector parameters.
- Same-bar stop/target resolution: stop first ("we pessimistically assume that SL comes before TP"; `vectorbt/signals/nb.py`, `generate_ohlc_stop_ex_nb` docstring).
- Weak at path-dependent, stateful logic:
  - 2 trades per session
  - daily −2% stop
  - per-candidate ML gating with journaling
- No live trading in the open-source edition ([ict-ml-trading-bot.md §3](./ict-ml-trading-bot.md#3-backtesting--trading-frameworks)).
- **Licence:** the wheel's `LICENSE.md` is "Apache 2.0 with Commons Clause". It forbids selling a product or service whose value derives substantially from vectorbt. That is fine for private use, but it is a constraint.
- **Use:** a research side tool, not the engine.

### 4.3 backtesting.py 0.6.6

- Simple bar-by-bar `next()` API.
- Same-bar policy is pessimistic: stop-loss orders go to the front of the queue ("Ensure SL orders are processed first", `backtesting/backtesting.py` L810–811). It warns when a contingent stop or target would fill in the same bar as its entry, and defers it to the next bar (L1024–1046).
- Problems for us:
  - one instrument per backtest
  - no live path
  - pandas-only
  - **AGPL-3.0**
  - slower cadence (27 commits since 2026-05-01)
- **Use:** none for this project.

## 5. Recommendation

1. **Phases 1–2: a lean custom engine** on Polars + `databento` + LightGBM, with:
   - a `BarFeed` / `Broker` / `Journal` interface that the strategy code never sees past
   - the same-bar policy from §3.3 (1-second drill-down, otherwise stop first, logged)
   - the simulator covered by the ground-truth and frozen-replay CI that design.md already requires
2. **vectorbt (optional)** for fast parameter sweeps during setup research only. Confirm winners in the custom engine.
3. **Re-evaluate NautilusTrader at the start of Phase 3** if 2.0.0 final has shipped by then. The question at that point is whether the NinjaTrader bridge should be:
   - (a) our `Broker` / `BarFeed` implementation, or
   - (b) a NautilusTrader v2 custom Python adapter, with strategies ported to `Strategy`.

   Keep the strategy layer thin so that (b) remains possible.
4. **Update design.md's stack line** from "Engine: Python, NautilusTrader" to the above. That is the map owner's call, not this ticket's.

## Open questions

- **Databento cost check:** what do 5+ years of MNQ `ohlcv-1m`, `ohlcv-1s` and `trades` in `GLBX.MDP3` cost against the $125 credit? This decides whether the 1-second drill-down is affordable for the whole history.
- **User's macOS version:** this only matters if NautilusTrader comes back into consideration. v1 1.231 needs macOS 26 or later.
