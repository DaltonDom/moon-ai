# Research: Autonomous ICT-Based Trading System with ML Self-Improvement

*Research date: 2026-10-31. Scope: CME index futures (ES/NQ/MES/MNQ) and/or crypto, ICT ("Inner Circle Trader", Michael Huddleston) concepts, paper trading first, full trade journaling, ML-driven improvement.*

> **How to read this document.** Every factual claim has a link. Items marked **UNVERIFIED** could not be confirmed against a primary source during this research (several vendor sites, e.g. databento.com, interactivebrokers.com, help.topstep.com and tradingview.com, could not be fetched directly from the research environment and were only seen through search-result excerpts). Package versions come from the PyPI JSON API as queried on 2026-10-31. Nothing here is financial or legal advice.

---

## Table of contents

1. [ICT concepts formalized for code](#1-ict-concepts-formalized-for-code)
2. [Market data & brokers with paper trading APIs](#2-market-data--brokers-with-paper-trading-apis)
3. [Backtesting / trading frameworks](#3-backtesting--trading-frameworks)
4. [ML approaches for self-improvement](#4-ml-approaches-for-self-improvement)
5. [Trade journaling & metrics](#5-trade-journaling--metrics)
6. [App architecture options](#6-app-architecture-options)
7. [Risk, legal & regulatory notes](#7-risk-legal--regulatory-notes)
8. [Recommended stack (opinion)](#8-recommended-stack-opinion)
9. [Sources](#sources)

---

## 1. ICT concepts formalized for code

### 1.1 Provenance and the definition problem

- ICT's primary material is video (YouTube channel [@InnerCircleTrader](https://www.youtube.com/@InnerCircleTrader)) and paid mentorships, not a written specification. Third-party educators credit Huddleston as the originator ([BabyPips](https://www.babypips.com/trading/what-is-ict-trading-the-most-accurate-strategy-in-forex)).
- Definitions **vary between implementations**. For example, killzone hours differ between indicator scripts (one LuxAlgo script uses NY AM 07:00–10:00, another 07:00–09:00) ([LuxAlgo killzones concept](https://www.luxalgo.com/library/concept/killzones/), [LuxAlgo ICT Killzone](https://www.luxalgo.com/library/indicator/gLHqnxvc-ict-killzone/)), and breaker/MSS rules differ between TradingView open scripts ([ICT Concepts [LuxAlgo]](https://in.tradingview.com/script/ib4uqBJx-ICT-Concepts-LuxAlgo/), [ICT Ultimate Algorithmic Engine](https://it.tradingview.com/script/u2ItPJf6-ICT-Ultimate-Algorithmic-Engine/)).
- Practical consequence: the bot must treat every ICT concept as a **parameterized detector** (lookbacks, tolerances, ATR multiples, time windows) and record the parameter set in each trade log, so ML can learn which variants matter.

### 1.2 Reference open-source implementations

| Implementation | What it gives you | License / status |
|---|---|---|
| [`smartmoneyconcepts`](https://github.com/joshyattridge/smart-money-concepts) (PyPI [`smartmoneyconcepts`](https://pypi.org/project/smartmoneyconcepts/)) | Python/pandas functions: `fvg`, `swing_highs_lows`, `bos_choch`, `ob`, `liquidity`, `previous_high_low`, `sessions`, `retracements` | MIT (repo); v0.0.27 released 2026-04-03 (PyPI). Pre-1.0, small project. |
| [ICT Concepts [LuxAlgo]](https://in.tradingview.com/script/ib4uqBJx-ICT-Concepts-LuxAlgo/) (TradingView, Pine Script, open source) | MSS & BOS, order blocks, breakers, imbalances, buyside/sellside liquidity, displacement, killzones | Open-source script on TradingView; license terms on the page **UNVERIFIED** (tradingview.com not fetchable) |
| [ICT Ultimate Algorithmic Engine](https://it.tradingview.com/script/u2ItPJf6-ICT-Ultimate-Algorithmic-Engine/) (TradingView) | Alternative rules, e.g. MSS requires candle body > 1.5×ATR; OB that swept liquidity then broken becomes breaker/mitigation block | Open-source script |
| [SMT Divergence 3-Way](https://www.tradingview.com/script/Q322Hy2o-SMT-Divergence-3-Way-Key-Levels-Killzones-Structure/) (TradingView) | Cross-instrument SMT detection | Open-source script |

The `smartmoneyconcepts` README (fetched 2026-10-31) defines its functions as follows ([repo](https://github.com/joshyattridge/smart-money-concepts)):

- **FVG**: "when the previous high is lower than the next low if the current candle is bullish" (and the mirror for bearish). Returns `FVG` (±1), `Top`, `Bottom`, `MitigatedIndex`; `join_consecutive` merges adjacent gaps.
- **Swing highs/lows**: "the current high is the highest high out of the `swing_length` amount of candles" on each side (default 50).
- **BOS/CHoCH**: computed from the swing series; `close_break=True` requires a close beyond the level (else wick).
- **Order blocks**: derived from swings; returns `Top`, `Bottom`, `OBVolume`, `Percentage` (strength); `close_mitigation` toggles close vs wick mitigation.
- **Liquidity**: "multiple highs within a small range of each other" with `range_percent` tolerance (default 0.01); returns `Level`, `End`, `Swept` index.
- **Sessions**: built-in "Asian kill zone", "London open kill zone", "New York kill zone", "london close kill zone" plus Custom, with a `time_zone` argument.

### 1.3 Formal definitions to implement

Notation: bar index `i`, OHLC arrays `o,h,l,c`, `ATR(n)` = average true range. All timestamps stored in UTC; session logic computed in `America/New_York` so daylight-saving shifts are handled (a vendor script explicitly warns that wrong DST/offset settings shift zones by an hour: [search excerpt of TradingView killzone scripts](https://kr.tradingview.com/script/WMbmcs4m-ICT-Killzones-Pivots-JB)).

| Concept | Implementable definition (parameters in *italics*) | Source / basis |
|---|---|---|
| **Swing high / low (fractal)** | Swing high at `i` if `h[i] = max(h[i-N..i+N])`; swing low mirror. *N* = 2–5 intraday is common (smc default 50). **Confirmed only at bar `i+N`** — use the confirmation time, not `i`, in backtests to avoid look-ahead bias. | [smc README](https://github.com/joshyattridge/smart-money-concepts) |
| **Break of Structure (BOS)** | In an uptrend (last structure higher-highs), a *close* (or wick, configurable) above the most recent confirmed swing high = bullish BOS (continuation). Mirror for bearish. | [smc `bos_choch`, `close_break`](https://github.com/joshyattridge/smart-money-concepts) |
| **Market Structure Shift (MSS) / CHoCH** | Break of the most recent confirmed swing *against* the prevailing trend (e.g. in an uptrend, close below the last higher-low). ICT calls this MSS; generic SMC calls it CHoCH. Many implementations additionally require **displacement** on the breaking leg. | [ICT Concepts [LuxAlgo]](https://in.tradingview.com/script/ib4uqBJx-ICT-Concepts-LuxAlgo/); ATR-body filter in [ICT Ultimate Algorithmic Engine](https://it.tradingview.com/script/u2ItPJf6-ICT-Ultimate-Algorithmic-Engine/) |
| **Displacement** | Strong, impulsive candle(s). Practical rule: candle body `|c-o| > k·ATR(n)` (*k* ≈ 1.5 in one open script) and/or the leg leaves an FVG. No canonical threshold exists. | [ICT Ultimate Algorithmic Engine](https://it.tradingview.com/script/u2ItPJf6-ICT-Ultimate-Algorithmic-Engine/) (1.5×ATR); LuxAlgo exposes displacement as a toggle without a published rule ([LuxAlgo script](https://in.tradingview.com/script/ib4uqBJx-ICT-Concepts-LuxAlgo/)) |
| **Fair Value Gap (FVG) — 3-candle** | With candles `i-1, i, i+1` (middle `i`): **bullish FVG** if `l[i+1] > h[i-1]`, zone = `[h[i-1], l[i+1]]`; **bearish FVG** if `h[i+1] < l[i-1]`, zone = `[h[i+1], l[i-1]]`. Optional: middle candle direction must match, minimum gap size *≥ x ticks or y·ATR*. **Mitigated** when price later trades into the zone (first touch, 50% "consequent encroachment", or full fill — choose and log). Known only after bar `i+1` closes. | [smc README](https://github.com/joshyattridge/smart-money-concepts); 3-candle description in [MQL5 SMC guide](https://www.mql5.com/en/blogs/post/772364) |
| **Order block (OB)** | **Bullish OB** = last down-close candle (c<o) before a displacement leg up that produces a BOS/MSS; zone = that candle's range (or open–low body variant). Bearish mirror. Invalidated when price closes through it. | [MQL5 SMC guide](https://www.mql5.com/en/blogs/post/772364); swing-based variant in [smc `ob`](https://github.com/joshyattridge/smart-money-concepts) |
| **Breaker block** | An OB that fails: price closes through it (often after it swept liquidity), after which the zone's polarity flips (failed bullish OB becomes bearish resistance). | [ICT Concepts [LuxAlgo]](https://in.tradingview.com/script/ib4uqBJx-ICT-Concepts-LuxAlgo/) ("When price mitigates (breaks out) an order block, a breaker block is confirmed"); sweep-then-break variant in [ICT Ultimate Algorithmic Engine](https://it.tradingview.com/script/u2ItPJf6-ICT-Ultimate-Algorithmic-Engine/) |
| **Buy-side / sell-side liquidity** | Buy-side liquidity (BSL) = resting stops above swing highs / equal highs / previous day/week highs; sell-side (SSL) = below lows. Implement as a set of candidate levels: confirmed swing highs/lows, previous session/day/week H/L (smc `previous_high_low`), and equal-high/low clusters. | [smc `liquidity`, `previous_high_low`](https://github.com/joshyattridge/smart-money-concepts); [LuxAlgo script](https://in.tradingview.com/script/ib4uqBJx-ICT-Concepts-LuxAlgo/) |
| **Equal highs / lows** | ≥2 swing highs (lows) within tolerance *ε* (e.g. `range_percent` or *n ticks*). | [smc `liquidity` `range_percent`](https://github.com/joshyattridge/smart-money-concepts) |
| **Liquidity sweep / raid** | Bar trades beyond a liquidity level (`h > level` for BSL) but **closes back inside** (`c < level`) within *m* bars; vs. a *break* where it closes beyond and holds. | Derived from smc `Swept` index ([repo](https://github.com/joshyattridge/smart-money-concepts)); exact close-back rule is an implementation choice |
| **Dealing range, premium / discount** | Dealing range = most recent significant swing low→swing high. Equilibrium = 50%. Above = premium (prefer shorts), below = discount (prefer longs). | [LuxAlgo premium & discount](https://www.luxalgo.com/library/concept/premium-and-discount/) |
| **OTE (Optimal Trade Entry)** | Retracement into 62%–79% (61.8–78.6) of the impulse leg; 70.5% midpoint often used as the entry. In a bullish leg this zone sits inside discount. | [LuxAlgo OTE](https://www.luxalgo.com/library/concept/optimal-trade-entry/), [chartinglens OTE](https://chartinglens.com/blog/ict-optimal-trade-entry-ote) — sources note there is no published OTE win-rate evidence |
| **Killzones (New York time)** | Commonly: **London 02:00–05:00**, **NY AM 07:00–10:00**, **NY PM 13:30–16:00**; Asian and London-close windows also used. Variants exist (e.g. NY AM 07:00–09:00 or 08:30–11:00). | [LuxAlgo killzones concept](https://www.luxalgo.com/library/concept/killzones/), [LuxAlgo silver bullet × macro × killzone](https://www.luxalgo.com/library/indicator/st4mz5Vn-silver-bullet-x-macro-x-killzone/). Exact ICT-original hours **UNVERIFIED** against ICT's own videos. |
| **Silver Bullet windows** | One-hour windows, NY time: **03:00–04:00**, **10:00–11:00** (the original/most cited), **14:00–15:00**. Rule commonly taught: in the window, trade the first FVG in the direction of HTF bias toward a liquidity target; an FVG is mandatory. Some scripts put the London window at 02:00–03:00. | [therighttrader Silver Bullet](https://therighttrader.com/learn/smart-money-concepts/silver-bullet-strategy), [LuxAlgo ICT Silver Bullet](https://www.luxalgo.com/library/indicator/ICT-Silver-Bullet), [TradingView Silver Bullet script](https://jp.tradingview.com/script/yxRodYFg-ICT-Silver-Bullet/) |
| **Power of 3 / AMD** | Session/daily candle modeled as **Accumulation** (range near the open, e.g. midnight or 18:00 open), **Manipulation** (a "Judas swing": false move away from the open that sweeps liquidity), **Distribution** (the real expansion opposite the manipulation). Code as: reference open → detect sweep of an opposing level → MSS + FVG in opposite direction. | Midnight-open/Judas-swing framing in indicator descriptions ([TradingView NQ Bias script listing](https://il.tradingview.com/scripts/search/bear/page-35)). A primary written definition was **not found — UNVERIFIED**. |
| **Daily bias** | Discretionary in ICT. Codable proxies: HTF (daily/4H) structure direction; price vs. midnight open / 18:00 open; which side of prior-day range is the nearer "draw on liquidity"; premium/discount of the weekly range. Treat as *features*, not a fixed rule. | [Indicator descriptions on midnight-open bias](https://il.tradingview.com/scripts/search/bear/page-35); otherwise **UNVERIFIED** |
| **SMT divergence (ES vs NQ)** | Within the **same session/window**, one index makes a new swing high (low) beyond a reference level while the correlated index fails to. NQ higher-high + ES lower-high = bearish SMT (and mirror). Requires time-aligned bars for both instruments. | [SMT divergence NQ/ES explainer](https://www.eltraderfinanciado.com/zh/blog/smt-divergence) (also notes the predictive claim "has not been measured"); [TradingView SMT 3-way script](https://www.tradingview.com/script/Q322Hy2o-SMT-Divergence-3-Way-Key-Levels-Killzones-Structure/) |

### 1.4 Evidence of edge (honest summary)

- **No peer-reviewed study testing ICT/SMC concepts was found** in this research (searches of arXiv/SSRN-style queries returned only vendor and indicator pages). One 2026 article reports its own Crossref search found no journal article testing SMC/ICT terms ([fxnx](https://fxnx.com/en/blog/smart-money-concepts-work-backtest-evidence)) — that is a secondary source, not an independent review.
- Base rates matter: the same source reports that in a 1,000,000-bar random walk, 3-candle gaps form on ~29.8% of bars, so "FVGs get filled" says nothing about direction without a random-baseline comparison ([fxnx](https://fxnx.com/en/blog/smart-money-concepts-work-backtest-evidence)). Vendor fill-rate claims conflict (e.g. 64.8% vs 92%) and are unverified.
- General technical-analysis literature is mixed: Lo, Mamaysky & Wang found some chart patterns carry incremental information ([NBER w7613](https://www.nber.org/papers/w7613)); Park & Irwin's survey found many positive results but flagged data-snooping and cost problems ([Journal of Economic Surveys, 2007](https://doi.org/10.1111/j.1467-6419.2007.00519.x)). Neither tests ICT specifically.
- **Implication for the project:** treat ICT as a *feature-generation hypothesis*. The ML layer's first job is to measure whether any ICT feature beats a matched random/naive baseline after costs, out of sample (Section 4).

---

## 2. Market data & brokers with paper trading APIs

### 2.1 Futures (CME) brokers / platforms

| Provider | Asset classes | Paper / sim | API style | Historical data | Cost notes | US | Python |
|---|---|---|---|---|---|---|---|
| **Interactive Brokers** (TWS API) | Futures, stocks, options, FX, some crypto | Yes — paper account; default ports TWS live 7496 / paper 7497, IB Gateway live 4001 / paper 4002 ([IBKR TWS API docs](https://www.interactivebrokers.com/docs/tws-api/doc/synchronous-api/connect-start-connection)) | Proprietary socket API via locally running TWS or IB Gateway; "Read-Only API" must be unchecked to place orders ([IBKR Campus](https://www.interactivebrokers.com/campus/trading-lessons/installing-configuring-tws-for-the-api/)) | Yes (bars, ticks; pacing limits) | Exchange data subscriptions extra | Yes | [`ib_async`](https://github.com/ib-api-reloaded/ib_async) v2.1.0 (2025-12-08), BSD, Python ≥3.10, successor to `ib_insync` ([PyPI](https://pypi.org/project/ib-async/)) |
| **Tradovate** (NinjaTrader group) | CME futures | Demo/sim environment `demo.tradovateapi.com` ([Tradovate partner docs](https://partner.tradovate.com/resources/reference/environments)) | REST + WebSocket, JSON ([partner docs](https://partner.tradovate.com/overview/welcome/introduction-to-tradovate-partner-api.md)) | Via market-data WebSocket | API access reportedly requires a funded live account and ~$25/mo add-on — **UNVERIFIED** (vendor blog [PickMyTrade](https://blog.pickmytrade.trade/tradovate-api-access-without-1000-minimum-2026-options/); community [forum](https://community.tradovate.com/t/could-i-user-api-access-the-simulation-env-by-a-simulation-account/4033)) | Yes | No official SDK; community wrappers |
| **NinjaTrader 8** | Futures | Built-in `Sim101` simulation account with queue-aware fill model ([NT8 help: Simulator](https://static.ninjatrader.com/support/helpGuides/nt8/simulation.htm)) | NinjaScript (C#) strategies inside the desktop app ([NT8 help: Account](https://ninjatrader.com/support/helpGuides/nt8/strategy_account.htm)) | Via connected feed | Platform licence/broker fees | Yes | Not native (C#; Windows desktop) |
| **Rithmic** (R\|Protocol API) | CME futures (common for prop firms) | "Rithmic Test" gateway; test env has **no historical data** ([async_rithmic PyPI](https://pypi.org/project/async-rithmic/1.3.2/)) | Protocol Buffers over WebSocket | Yes in production | Via FCM/prop firm | Yes | [`async_rithmic`](https://pypi.org/project/async-rithmic/) v1.6.6 (2026-08-21), MIT (community) |
| **TopstepX / ProjectX Gateway API** | CME futures (Topstep sim/funded) | API is for the **simulated environment only**; not available on Live funded accounts ([Topstep help](https://help.topstep.com/en/articles/11187768)) | REST + real-time hubs (SignalR) — protocol detail **UNVERIFIED** | Bars endpoint (rate-limited 50 req/30 s per third-party guide — **UNVERIFIED**) | $29/mo, 50% off with Topstep code, billed separately ([Topstep help, via search excerpt](https://help.topstep.com/en/articles/14289835)) | Yes | [`project-x-py`](https://project-x-py.readthedocs.io/en/latest/authentication.html) v4.4.2 (2026-10-29), MIT (third-party) |

Corporate context: Kraken announced acquiring NinjaTrader (a CFTC-registered FCM) for ~$1.5B on 2025-03-20 ([FinTech Futures](https://www.fintechfutures.com/m-a/kraken-bolsters-multi-asset-strategy-with-1-5bn-ninjatrader-acquisition)); NinjaTrader Group lists Tradovate and Kraken Derivatives US among affiliates ([Tradovate partner docs](https://partner.ninjatrader.com/eval/overview/core-concepts/architecture-overview.md)).

### 2.2 Crypto venues

| Provider | Products | Paper / sandbox | API | US availability | Python |
|---|---|---|---|---|---|
| **Alpaca** | US stocks/options + **spot crypto** (no crypto futures found) | Paper trading simulates crypto fills from real-time quotes ([Alpaca docs](https://docs.alpaca.markets/us/docs/paper-trading)) | REST + WebSocket; crypto supports market/limit/stop-limit, `gtc`/`ioc` ([crypto docs](https://docs.alpaca.markets/us/docs/crypto-trading-1)) | All US states except New York per Alpaca ([support](https://alpaca.markets/support/alpaca-cryptocurrency)) | `alpaca-py` |
| **Coinbase Advanced Trade** | Spot; US CFTC-regulated perpetual-style futures (nano BTC/ETH, launched 2025-07-21) ([FOW](https://www.fow.com/app/insights/coinbase-hails-arrival-of-perpetual-style-futures-in-us)) | Sandbox at `api-sandbox.coinbase.com` returns **static, pre-defined mock responses**; only Accounts/Orders endpoints ([Coinbase docs](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/sandbox)) — not usable for realistic paper trading | REST + WebSocket ([SDK overview](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/sdk)) | Yes (US futures stay on Advanced Trade API per [perpetuals guide](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/guides/perpetual)) | Official `coinbase-advanced-py` |
| **Kraken** (spot + futures) | Spot; Kraken Derivatives (non-US); **Kraken Derivatives US** with CME-listed futures, USD collateral ([Kraken eligibility](https://support.kraken.com/articles/360023786632-kraken-derivatives-eligibility)) | Futures demo `demo-futures.kraken.com` described as self-service in dev docs ([Kraken futures intro](https://docs.kraken.com/api/docs/guides/futures-introduction/)), but a support article says it was decommissioned and restricted to qualified clients ([Kraken support](https://support.kraken.com/articles/360024809011-api-testing-environment-derivatives)) — **status conflicting/UNVERIFIED**; demo resets periodically ([quickstart](https://docs.kraken.com/home/guides/quickstart)) | REST + WebSocket | Not available to NY or Maine residents ([Kraken US quick start](https://support.kraken.com/articles/quick-start-for-clients-in-the-united-states)) | Via CCXT / community |
| **Binance (.com)** | Spot, futures; testnets exist | Testnets exist (endpoint/status not verified here) | REST/WS | **Not available to US persons** per its terms ([The Block](https://www.theblock.co/post/85589/binance-blocking-us-users-14-day-deadline-new-email)); US users directed to Binance.US | CCXT |
| **Bybit** | Spot, perps; testnet exists | Testnet | REST/WS | US listed as excluded jurisdiction (Service Agreement §11.3) ([Bybit help center](https://bybit.com/en/help-center/article/Service-Restricted-Countries)). Whether testnet use is covered by the restriction is **UNVERIFIED**. | CCXT |
| **CCXT** (library) | Unified API over 100+ exchanges | `set_sandbox_mode(True)` where the exchange provides a sandbox; sandbox keys needed ([CCXT manual](https://github-redirect.dependabot.com/ccxt/ccxt/wiki/Manual)) | — | — | `ccxt` v4.5.91 (2026-10-29), MIT ([repo](https://github.com/ccxt/ccxt)) |

### 2.3 Market-data vendors

| Vendor | Coverage | Access | Pricing (as found) |
|---|---|---|---|
| **Databento** | CME Globex MDP 3.0 (`GLBX.MDP3`) tick/MBO/MBP/OHLCV; many other venues | Python client [`databento`](https://github.com/databento/databento-python) v0.89.0 (2026-10-28), Apache-2.0; historical `timeseries.get_range(dataset="GLBX.MDP3", schema="ohlcv-1m", ...)` ([Databento example](https://databento.com/docs/examples/basics-historical/custom-ohlcv)); continuous symbols like `ES.c.0` (calendar `c`, open-interest `n`, volume `v` roll) ([Nautilus Databento tutorial](https://nautilustrader.io/docs/latest/tutorials/databento_overview)) | Historical usage-based "from $0.50/GB"; CME subscription plans repriced on 2026-06-22 to $199 / $1,750 / $4,500 per month ([Databento blog](https://databento.com/blog/updates-to-subscription-pricing), [CME plans blog](https://databento.com/blog/introducing-new-cme-pricing-plans)). Which tier name maps to which price and what live-data licensing applies: **UNVERIFIED**. |
| **Massive (formerly Polygon.io)** | Stocks, options, indices, FX, crypto, CME-group futures | REST/WebSocket; `api.polygon.io` still supported alongside `api.massive.com` | Rebrand date conflicting (Oct 2025 vs 2026) ([FISD notice](https://fisd.net/polygon-io-is-now-massive)); futures coverage per [edgeful comparison](https://www.edgeful.com/blog/posts/futures-data-api-polygon-databento-edgeful-comparison) — **pricing UNVERIFIED** |
| **Broker feeds** (IBKR, Tradovate, Rithmic) | Real-time for trading | Via broker APIs | CME exchange fees apply (Section 7.5) |

---

## 3. Backtesting / trading frameworks

Versions/licenses from PyPI JSON API (queried 2026-10-31) unless noted.

| Framework | Language | Live + paper | Futures (CME) | Crypto | ML integration | Engine type | License | Maintenance (latest release) |
|---|---|---|---|---|---|---|---|---|
| **NautilusTrader** | Rust core, Python control plane (PyO3) | Yes; same strategy code in backtest and live ([repo](https://github.com/nautechsystems/nautilus_trader)) | Yes via **Interactive Brokers** and **Databento** adapters | Binance, Bybit, Coinbase, Kraken, OKX, dYdX, Hyperliquid, Deribit… | "Fast enough to train AI trading agents (RL/ES)" but built-in ML tooling out of scope ([repo](https://github.com/nautechsystems/nautilus_trader)) | Event-driven, nanosecond, order-book aware | LGPL-3.0-or-later | 1.231.0 (2026-08-02); Python 3.12–3.14 |
| **Freqtrade** (+ FreqAI) | Python | Dry-run (paper) and live ([repo](https://github.com/freqtrade/freqtrade)) | No (crypto only) | Spot: Binance, Bybit, Kraken, OKX, Gate, HTX, Hyperliquid…; futures: Binance, Bybit, Gate, Hyperliquid, Kraken, OKX | **FreqAI**: sliding-window retraining (`train_period_days`, `backtest_period_days`), LightGBM/XGBoost/PyTorch, RL via stable-baselines3 ([FreqAI docs](https://www.freqtrade.io/en/stable/freqai-running/), [RL](https://www.freqtrade.io/en/stable/freqai-reinforcement-learning/)) | Candle-based, event loop | GPL-3.0 | 2026.10 (2026-10-30) |
| **backtesting.py** | Python | No live | Generic OHLC | Generic OHLC | Manual; SAMBO optimizer ([repo](https://github.com/kernc/backtesting.py)) | Bar-by-bar `next()` | AGPL-3.0 | 0.6.6 (2026-07-22) |
| **vectorbt** (OSS) | Python + Numba | No live order execution | Generic arrays | Generic | Excellent for parameter sweeps/feature research | **Vectorized** | Apache-2.0 **with Commons Clause** ([repo](https://github.com/polakowo/vectorbt)); PRO is commercial | 1.2.0 (2026-10-19) |
| **Backtrader** | Python | Historical IB/Oanda live stores | Yes (via IB) | Community | Manual | Event-driven | GPL-3.0+ | 1.9.78.123 (**2023-04-19**); Snyk rates maintenance "Inactive" ([Snyk](https://snyk.io/advisor/python/backtrader)) |
| **LEAN / QuantConnect** | C# engine, Python or C# algorithms | Yes; local via `lean live` (Docker) ([repo](https://github.com/QuantConnect/Lean)); QC paper brokerage supports equities, FX, crypto, **futures** ([QC docs](https://www.quantconnect.com/docs/v2/lean-cli/live-trading/quantconnect-paper-trading)) | Yes; IB brokerage (local IB module needs paid org subscription) ([QC IB docs](https://www.lean.io/docs/lean-cli/live-trading/interactive-brokers)); Tradovate not found | Coinbase, Kraken, Alpaca… ([QC brokerages](https://www.lean.io/docs/v2/lean-cli/live-trading/brokerages)) | Python ML libs in research/algos | Event-driven, mature fill/fee models | Apache-2.0 | engine actively developed; `lean` CLI 1.0.233 (2026-10-27) |
| **Jesse** | Python (Rust indicators) | Paper + live ([repo](https://github.com/jesse-ai/jesse)) | No (crypto) | Spot/futures/DEX | Built-in gather → `train_model()` (scikit-learn) → `ml_predict()` pipeline ([repo](https://github.com/jesse-ai/jesse)) | Event-driven candles | MIT | 3.5.4 (2026-10-30) |

**Takeaways**
- For **CME futures + crypto in one codebase with live/paper parity**, NautilusTrader and LEAN are the only two strong candidates. Nautilus is Python-first with Databento/IB adapters; LEAN is C#-centric but has the broadest brokerage list.
- For **crypto-only with built-in adaptive ML**, Freqtrade/FreqAI is the most turnkey, but GPL-3.0 and its continual-learning mode is described by its own docs as "a naive approach… high probability of overfitting" ([FreqAI docs](https://www.freqtrade.io/en/stable/freqai-running/)).
- For **research and feature discovery** (sweeping ICT parameters), vectorbt or plain pandas/Polars is fastest; validate winners in an event-driven engine.
- Note TopstepX/ProjectX and Tradovate are **not** native adapters in Nautilus or LEAN (none found); they would need a custom adapter.

---

## 4. ML approaches for self-improvement

### 4.1 Recommended core: supervised "meta-model" over ICT features

1. **Primary model = deterministic ICT rules** produce candidate setups (side, entry, stop, target).
2. **Label each candidate with the triple-barrier method**: upper barrier (profit-take), lower barrier (stop), vertical barrier (time-out); label = first barrier touched (+1 / −1 / 0 or sign of return) — López de Prado, *Advances in Financial Machine Learning*, Wiley 2018, ch. 3 ([O'Reilly listing](https://oreilly.com/library/view/advances-in-financial/9781119482086); summary in [study notes](https://reasonabledeviations.com/notes/adv_fin_ml); reference implementation in [fynance](https://fynance.readthedocs.io/en/latest/features.labels.html)).
3. **Meta-labeling**: a secondary classifier predicts whether the primary signal will hit the profit barrier; its probability drives *take/skip* and position size (AFML ch. 3; [study notes](https://reasonabledeviations.com/notes/adv_fin_ml)).
4. **Model**: gradient-boosted trees — LightGBM 4.7.0 ([docs](https://lightgbm.readthedocs.io/en/latest/)) or XGBoost 3.4.1 (Apache-2.0) — well suited to tabular, mixed-type, modest-size data. Features: ICT detectors (FVG size in ATR, OB age, sweep depth, MSS displacement multiple, killzone/silver-bullet flag, premium/discount %, SMT flag, HTF bias), plus volatility, time-of-day, day-of-week, distance to prior day H/L, news-day flags.
5. **Calibrate** probabilities and use them for sizing (e.g. fractional Kelly capped by risk limits).

### 4.2 Validation that does not lie

- **Purged k-fold CV with embargo**: remove training samples whose label windows overlap the test fold; add an embargo gap after each test fold (AFML ch. 7; [study notes](https://reasonabledeviations.com/notes/adv_fin_ml)). Standard scikit-learn `KFold` leaks with overlapping labels.
- **Walk-forward**: train on window *T*, trade the next window, slide forward — same concept FreqAI implements with `train_period_days`/`backtest_period_days` ([FreqAI docs](https://www.freqtrade.io/en/stable/freqai-running/)).
- **Deflated Sharpe Ratio (DSR)** — corrects Sharpe for selection bias across many trials and non-normal returns (skew/kurtosis): Bailey & López de Prado, *JPM* 40(5), 2014 ([SSRN 2460551](https://papers.ssrn.com/abstract=2460551)). **Log the number of configurations tried** so DSR can be computed.
- **Probability of Backtest Overfitting (PBO)** via combinatorially symmetric cross-validation (CSCV): Bailey, Borwein, López de Prado & Zhu, *Journal of Computational Finance* ([SSRN 2326253](https://papers.ssrn.com/abstract=2326253), [Risk.net](https://www.risk.net/journal-of-computational-finance/2471206/the-probability-of-backtest-overfitting)); R package [`pbo`](https://packages.oit.ncsu.edu/cran/web/packages/pbo/readme/README.html).
- **Hyperparameter search**: Optuna 5.0.0 (MIT) — samplers incl. TPE/CMA-ES/NSGA-II, trial pruning, SQLite storage, `optuna-dashboard` ([repo](https://github.com/optuna/optuna), [docs](https://optuna.readthedocs.io)). Every Optuna trial counts toward the DSR trial count.

### 4.3 Online learning & drift

- **River** 0.26.1 (BSD-3) — incremental `learn_one`/`predict_one`, drift detection family ([repo](https://github.com/online-ml/river)); ADWIN detector (Bifet & Gavaldà 2007) usable standalone or in Adaptive Random Forest ([River ADWIN usage, via search excerpt](https://frouros.readthedocs.io/en/latest/api_reference/detectors/concept_drift/auto_generated/frouros.detectors.concept_drift.streaming.window_based.ADWIN.html)).
- Use online learning for **monitoring and gating** (detect regime change → reduce size / retrain) rather than letting the live model rewrite itself unsupervised.

### 4.4 Reinforcement learning — use cautiously

- **FinRL** (MIT): education/benchmarking framework; trains A2C/DDPG/PPO/TD3/SAC with stable-baselines3; explicitly "academic purposes", live trading not the focus ([repo](https://github.com/AI4Finance-Foundation/FinRL)); latest PyPI release 0.3.7 (2024-04-12).
- **stable-baselines3** 2.9.2 (MIT, 2026-10-26) — the RL algorithm library FreqAI also uses ([FreqAI RL](https://www.freqtrade.io/en/stable/freqai-reinforcement-learning/)).
- Pitfalls documented by FinRL's own authors: low signal-to-noise, survivorship bias, **backtest overfitting** ([FinRL-Meta, NeurIPS 2022](https://arxiv.org/abs/2211.03107)); repeated hyper-tuning on backtests, information leakage and sim-to-real gap ([arXiv 2304.13174](https://arxiv.org/pdf/2304.13174)).
- Recommendation: RL is a later-phase experiment for *execution/exit management* only, after the supervised pipeline is validated.

### 4.5 LLM "reasoning layer" (Claude API) for journaling and review

Use an LLM to **explain and review**, never to place orders directly:
- **Pre-trade rationale**: given detector outputs, produce a structured rationale record (setup type, confluences, invalidation, target liquidity).
- **Post-trade review**: compare rationale vs. outcome, MAE/MFE, rule adherence; tag mistakes; weekly summaries that propose *hypotheses* for the quantitative pipeline to test.

Relevant Anthropic docs:
- **Structured outputs** — JSON outputs constrained to a JSON Schema (`output_config.format`) and **strict tool use** (`strict: true`) guaranteeing schema-valid tool inputs ([Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)). Pydantic/Zod SDK helpers work with JSON outputs ([same page](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)).
- **Tool use** — define tools with `input_schema` ([Define tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools), [Implement tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/implement-tool-use)) — e.g. a read-only `query_trades` tool over the journal DB.
- **Message Batches API** — 50% discount, results within 24h, suited to nightly reviews ([Batch processing](https://platform.claude.com/docs/en/build-with-claude/batch-processing)); **prompt caching** (cache reads 0.1× base input price; stacks with batch discount) for the repeated rulebook/system prompt ([Prompt caching](https://docs.claude.com/en/docs/build-with-claude/prompt-caching)).
- Python SDK `anthropic` 2.3.0 (Apache-2.0, 2026-10-23) ([PyPI](https://pypi.org/project/anthropic/)).

---

## 5. Trade journaling & metrics

### 5.1 Metrics and formulas

Let trade P&L be `p_k` (net of fees/slippage), initial risk `R_k = |entry − initial_stop| × point_value × qty`, period returns `r_t`, risk-free `r_f`.

| Metric | Formula | Reference |
|---|---|---|
| Win rate | `#(p_k > 0) / N` | standard |
| Profit factor | `Σ p_k⁺ / |Σ p_k⁻|` | standard |
| Expectancy ($) | `WR · avgWin − (1−WR) · avgLoss` | [Van Tharp (traders.com)](https://www.traders.com/Documentation/FEEDbk_docs/2007/01/Abstracts_new/Tharp/tharp.html) |
| R-multiple | `R-mult_k = p_k / R_k`; **expectancy in R** = mean R-multiple | Tharp: "the average R-multiple produced by the system is… the expectancy" ([Van Tharp Institute](https://vantharp.com/Weekly_update/Weekly_273_May_31_2006.htm)) |
| Max drawdown | `max_t (peak_t − equity_t) / peak_t`, `peak_t = max_{s≤t} equity_s` | standard |
| Sharpe (ex post) | `mean(r_t − r_f) / std(r_t − r_f) × √periods_per_year` | [Sharpe 1994, *JPM*](https://web.stanford.edu/~wfsharpe/art/sr/sr.htm) |
| Sortino | `(mean(r_t) − MAR) / DD`, `DD = √(mean(min(0, r_t − MAR)²))` | Sortino & Price 1994, *Journal of Investing* ([PerformanceAnalytics docs](https://rdrr.io/cran/JFE/man/SortinoRatio.html)) |
| Calmar | `annualized return / |max drawdown|` (often over 36 months) | standard; Young (1991) — original citation **UNVERIFIED** |
| MAE / MFE | MAE = worst unrealized P&L during the trade; MFE = best unrealized P&L; analyze in R units to tune stops/targets | Sweeney's MAE framework ([TradesViz glossary](https://www.tradesviz.com/glossary/maximum-adverse-excursion/), [LuxAlgo MAE/MFE](https://www.luxalgo.com/library/concept/mae-mfe-distributions/)) |
| Deflated Sharpe, PBO | see Section 4.2 | [SSRN 2460551](https://papers.ssrn.com/abstract=2460551), [SSRN 2326253](https://papers.ssrn.com/abstract=2326253) |

Library options: `quantstats` 0.0.86 (Apache-2.0) for tearsheets ([PyPI](https://pypi.org/project/quantstats/)).

Note on sizing: CME Micro E-mini Nasdaq-100 (MNQ) is $2 × index, 0.25-pt tick = $0.50 ([CME FAQ](https://www.cmegroup.com/articles/faqs/micro-e-mini-equity-index-futures-frequently-asked-questions.html), [CME MNQ specs](https://www.cmegroup.com/markets/equities/nasdaq/micro-e-mini-nasdaq-100.contractSpecs.html)); MES is $5 × index so a 0.25-pt tick = $1.25 (derived; confirm on CME MES spec page).

### 5.2 Trade log record (proposed schema)

Each trade (and each *skipped* candidate — needed for unbiased ML) should store:

- **Identity**: `trade_id`, `strategy_version` (git SHA), `detector_params_hash`, `model_version`, `mode` (backtest / paper / live), `account`, `venue`.
- **Instrument**: symbol, contract month, point value, tick size, session (Asia/London/NY), killzone/silver-bullet flag.
- **Signal context (features snapshot at decision time)**: HTF bias, structure state, MSS/BOS levels, FVG zone & size (ticks, ATR), OB/breaker zone, liquidity target & swept level, premium/discount %, OTE flag, SMT flag, ATR, spread, volume, time-of-day, news flag.
- **Plan**: side, entry type & price, initial stop, targets, planned R, size and risk $.
- **Model output**: meta-model probability, threshold, decision (take/skip) and reason.
- **Execution**: order IDs, submit/fill timestamps (UTC, ns), fill prices, slippage vs. intended, fees/commissions, partial fills.
- **Management**: stop/target modifications with timestamps and reason.
- **Outcome**: exit price/time/reason (stop/target/time/manual), gross & net P&L, R-multiple, MAE, MFE (price & R), bars in trade, triple-barrier label.
- **Narrative**: LLM-generated pre-trade rationale and post-trade review (structured JSON + text), rule-violation tags.
- **Environment**: data feed, latency, connectivity incidents.

---

## 6. App architecture options

### 6.1 UI / shell

| Option | Pros | Cons | Fit |
|---|---|---|---|
| **Pure Python service + CLI/logs** | Simplest; one language; runs headless on a server | No visual review | Engine core (always) |
| **Local web dashboard: FastAPI + React** | Clean separation (engine API ↔ UI); works locally or remotely; FastAPI 0.162.0 (MIT) ([PyPI](https://pypi.org/project/fastapi/), [docs](https://fastapi.tiangolo.com/)) | Two stacks to maintain | Best long-term |
| **Streamlit** | Fastest to build analytics dashboards in pure Python; 1.66.1 (Apache-2.0) ([PyPI](https://pypi.org/project/streamlit/), [docs](https://docs.streamlit.io/)) | Rerun model awkward for real-time control | Good v1 for journal/analytics |
| **Tauri 2** desktop | Uses OS webview (WebView2 / WebKit), minimal app < 600 KB; can bundle external "sidecar" binaries ([Tauri: What is Tauri](https://v2.tauri.app/start/), [sidecar guide](https://v2.tauri.app/learn/sidecar-nodejs/)) | Python sidecar packaging (e.g. PyInstaller) not documented by Tauri — **UNVERIFIED**; webview differences per OS | Optional later wrapper |
| **Electron** | Mature; bundles Chromium so consistent rendering ([Electron docs](https://www.electronjs.org/docs/latest/)) | Larger footprint than Tauri (Tauri docs say its model avoids bundling a browser engine — [Tauri security](https://v2.tauri.app/security/)) | Not needed if web dashboard exists |

A desktop wrapper adds little for a system whose engine should run 24/7 on a server: the web dashboard is reachable from anywhere (over VPN/SSH tunnel).

### 6.2 Where the engine runs

- **CME equity-index futures** trade Sunday 6:00 p.m. – Friday 5:00 p.m. ET with a daily 5:00–6:00 p.m. ET halt ([CME Micro E-mini page](https://www.cmegroup.com/markets/equities/micro-emini-equity.html), [CME options FAQ](https://www.cmegroup.com/articles/faqs/e-mini-s-p-500-tuesday-and-thursday-options-frequently-asked-questions.html)) — effectively 23×5; ICT killzones span 02:00–16:00 ET.
- **Crypto** trades 24/7.
- Therefore a **always-on host** (cloud VM/VPS, ideally in or near Chicago/Aurora for CME or near the exchange region for crypto) is preferable to a laptop. Latency is not critical for minute-bar ICT setups, but uptime and reconnect logic are.
- IB's TWS API requires a running TWS or IB Gateway process ([IBKR Campus](https://www.interactivebrokers.com/campus/trading-lessons/installing-configuring-tws-for-the-api/)), i.e. a headless Gateway on the server (with periodic re-auth). NinjaTrader requires a Windows desktop app. Tradovate/ProjectX/Databento/crypto APIs are pure network APIs (easiest to host).

### 6.3 Storage

| Store | Use | Notes |
|---|---|---|
| **Parquet files** | Raw/normalized historical bars & ticks (immutable, partitioned by symbol/date) | Columnar, cheap; queried directly by DuckDB/Polars |
| **DuckDB** 2.0.0 (MIT) | Analytical queries, feature engineering, backtest result analysis | Embedded, reads Parquet natively ([DuckDB Parquet docs](https://duckdb.org/docs/stable/data/parquet/overview)) |
| **SQLite** | Single-host transactional store for orders, fills, trade journal (WAL mode for concurrent readers) | Zero-ops ([SQLite WAL](https://www.sqlite.org/wal.html)) |
| **PostgreSQL (+ TimescaleDB)** | Multi-process/multi-host journal + time-series with hypertables | TimescaleDB has an Apache-2 edition and a Community edition under the Tiger Data License with more features ([TimescaleDB editions](https://www.tigerdata.com/docs/get-started/choose-your-path/timescaledb-editions)) |

Pattern: **Parquet + DuckDB for research**, **SQLite (→ Postgres later) for the live journal**, Optuna studies in the same DB.

---

## 7. Risk, legal & regulatory notes

*(Factual pointers only; consult a qualified attorney for your situation.)*

### 7.1 CFTC / NFA — trading your own account

- A **CTA** is someone who, "for compensation or profit, advises others" on trading futures/options/swaps ([NFA: CTA registration](https://www.nfa.futures.org/registration-membership/who-has-to-register/cta.html)). An individual running a bot solely on their own account is not advising others; by that definition CTA registration should not apply (inference from the definition; NFA does not state it explicitly in the pages found). **Selling signals, managing others' money, or selling the bot as advice can trigger CTA/CPO obligations**; exemptions are in [17 CFR 4.14](https://www.law.cornell.edu/cfr/text/17/4.14).
- **Regulation AT** (which would have imposed registration/controls on algorithmic traders) was **withdrawn** by the CFTC on 2020-06-25 and replaced with exchange-level electronic trading risk principles ([CFTC Release 8188-20](https://www.cftc.gov/PressRoom/PressReleases/8188-20), [Morgan Lewis](https://www.morganlewis.com/pubs/farewell-reg-at-hello-electronic-trading-principles)).
- **Exchange conduct rules apply to everyone, including bots**: CME Rule 575 prohibits spoofing (orders entered with intent to cancel before execution), messages that mislead or overload systems, and reckless disruption; it covers "any person" and all market states ([CME Rule 575 PDF](https://www.cmegroup.com/rulebook/files/cme-group-Rule-575.pdf), [CME FAQ](https://www.cmegroup.com/education/courses/market-regulation/disruptive-practices-prohibited/disruptive-practice-prohibited-frequently-asked-questions)). Engineering implications: order-rate limits, no layering logic, kill switch, cancel-on-disconnect.

### 7.2 Pattern Day Trader rule

- The PDT rule was a FINRA Rule 4210 margin rule for **securities** margin accounts; it never applied to futures accounts.
- Further, the SEC approved FINRA's amendment eliminating the PDT designation and the $25,000 minimum on 2026-04-14, replaced by intraday margin standards, effective 2026-06-04 per FINRA (with possible extended adoption to 2027-10-20 for some firms) ([Schwab summary](https://international.schwab.com/story/sec-approves-scrapping-25000-day-trader-minimum), [E*TRADE](https://us.etrade.com/knowledge/library/margin/pattern-day-trading-rule-change)). Primary documents (FINRA Regulatory Notice 26-10; SEC Rel. 34-105226) were cited in coverage but **not read directly — UNVERIFIED**.

### 7.3 Crypto availability for US residents

- **Binance.com**: does not serve US persons ([The Block](https://www.theblock.co/post/85589/binance-blocking-us-users-14-day-deadline-new-email)).
- **Bybit**: US is an excluded jurisdiction ([Bybit help center](https://bybit.com/en/help-center/article/Service-Restricted-Countries)).
- **Kraken**: not available in NY and ME; US derivatives via Kraken Derivatives US (CME-listed futures) ([Kraken US](https://support.kraken.com/articles/quick-start-for-clients-in-the-united-states), [eligibility](https://support.kraken.com/articles/360023786632-kraken-derivatives-eligibility)).
- **Coinbase**: US CFTC-regulated perpetual-style futures via Coinbase Financial Markets since 2025-07-21 ([FOW](https://www.fow.com/app/insights/coinbase-hails-arrival-of-perpetual-style-futures-in-us)).
- **Alpaca**: spot crypto in all states except NY ([Alpaca support](https://alpaca.markets/support/alpaca-cryptocurrency)).
- Using VPNs to access restricted venues violates their terms; design around US-available venues.

### 7.4 Prop-firm automation rules

> **Correction (2026-10-31):** see [`prop-firms-and-order-routing.md`](./prop-firms-and-order-routing.md) for the full prop-firm study. Updates to the items below and in Section 2.1:
> - **Apex:** now confirmed on Apex's own help center (no longer UNVERIFIED), and it is stricter than stated: "The use of automation is strictly prohibited on all account types", which covers evaluations too, not only funded accounts ([Prohibited Activities](https://support.apextraderfunding.com/hc/en-us/articles/40463668243099-Prohibited-Activities)).
> - **Topstep:** in addition to the API being sim-only on Live Funded accounts, "the use of VPS, VPNs, and remote servers is prohibited", and "all trading activity must originate from your personal device". A cloud-hosted bot therefore cannot trade Topstep accounts at all ([TopstepX API Access](https://help.topstep.com/en/articles/11187768-topstepx-api-access)).
> - **Tradovate API (Section 2.1):** the $1,000 live-account minimum and the $25/mo API Access add-on are confirmed by Tradovate's support article, which also states "prop firm and evaluation accounts are not eligible for API access" ([Tradovate API Access](https://support.tradovate.com/s/article/Tradovate-API-Access?language=en_US)).
> - **ProjectX:** ProjectX wound down its third-party service for most partner firms, with support ending 2026-02-28. TopstepX is effectively the only remaining ProjectX venue ([projectx.com](https://www.projectx.com/)).
> - **Firms that do allow bots in funded accounts** (subject to conditions): Lucid Trading, Tradeify, Bulenox and MyFundedFutures, plus FundedNext Futures with conditions. A personal IBKR account is no longer the only route for a fully autonomous bot.

- **Topstep**: bots/custom automation **allowed via the TopstepX (ProjectX) API**, subject to platform rules and a ban on HFT; API is sim-only and **not available on Live Funded accounts** ([Topstep help](https://help.topstep.com/en/articles/11187768)).
- **Apex Trader Funding**: secondary sources consistently report automation permitted in evaluations but **fully automated trading prohibited on funded (Performance/Live) accounts**, semi-automated with active oversight allowed ([TradersPost](https://blog.traderspost.io/article/automate-apex-trader-funding-with-traderspost), [PickMyTrade](https://blog.pickmytrade.io/5-prop-firm-automation-rules-before-you-run-a-bot-2026/)) — Apex's own rule page was not retrieved: **UNVERIFIED**.
- Prop rules change frequently; re-check before connecting any bot.

### 7.5 Exchange data licensing (CME)

- CME non-professional fees (June 2026 list): **top of book $1.55/exchange/month**, depth $12.10; all-four-DCM bundle $4.65 TOB / $36.50 depth; January 2027 list raises to $1.60 / $12.50 / $4.80 / $37.75 ([CME June 2026 fee list](https://www.cmegroup.com/market-data/files/june-2026-market-data-fee-list.pdf), [CME Jan 2027 list](https://www.cmegroup.com/market-data/files/january-2027-market-data-fee-list.pdf)). Brokers/vendors mark these up (e.g. AMP lists $5/exchange L1) ([AMP](https://www.ampfutures.com/trading-info/platform-data-fees/)).
- Non-professional status must match exchange criteria; a bot trading your own money doesn't by itself make you professional, but check the subscriber agreement wording.
- Historical data from vendors (Databento) carries its own license terms — research/personal use vs. redistribution; displaying it in a shared dashboard may count as redistribution (**UNVERIFIED**, read the vendor agreement).

---

## 8. Recommended stack (opinion)

> **This section is a recommendation, not a fact.** It optimizes for: one language (Python), paper-first, honest validation, and a credible path to live CME micros and US-legal crypto.

**Phase 0 – Research harness (weeks 1–4)**
- Data: **Databento** `GLBX.MDP3` 1-minute (and later tick) history for ES/NQ/MES/MNQ, stored as **Parquet**, queried with **DuckDB/Polars**. For crypto, CCXT OHLCV from Coinbase/Kraken.
- ICT detectors: write our own, test-covered, parameterized implementations, using `smartmoneyconcepts` and the LuxAlgo scripts only as cross-checks (the package is pre-1.0 and definitions differ).
- Fast exploration with **vectorbt** (note Commons Clause is fine for personal use).
- Baseline experiment first: does any ICT setup beat a random-entry baseline with identical stops/targets/time windows, after costs?

**Phase 1 – Event-driven backtest + paper trading**
- Engine: **NautilusTrader** (LGPL; Python strategies; IB + Databento adapters for CME; Coinbase/Kraken for crypto; backtest/live parity).
  - *Tradeoff*: steeper learning curve than Freqtrade; no Tradovate/ProjectX adapter (custom work if you want Topstep).
  - *Alternative*: LEAN if you are comfortable with C#/Docker and want QC's paper brokerage for futures.
- Paper venue: **IBKR paper account** (CME futures, real market data, decent sim fills) via IB Gateway on a VPS. Crypto paper: Alpaca paper (spot) or the engine's own simulated venue with live Coinbase/Kraken data (Coinbase's sandbox is static mocks and Kraken's demo status is unclear).

**Phase 2 – ML layer**
- Triple-barrier labels → **LightGBM** meta-labeler → purged/embargoed walk-forward CV → **Optuna** (trial counts logged) → report **DSR + PBO** before any promotion.
- **River** drift detectors to gate/reduce size; scheduled (weekly) retrain with human approval of promotions. Defer RL.

**Phase 3 – Journal, review, dashboard**
- Journal in **SQLite** (→ Postgres when multi-process), schema per Section 5.2, including skipped candidates.
- **Claude API** with structured outputs for pre-trade rationale and post-trade reviews; nightly **Message Batches** for cost; the LLM proposes hypotheses, the quant pipeline tests them; the LLM never sends orders.
- **FastAPI + React** dashboard (or **Streamlit** for v1). Skip Electron/Tauri unless a desktop app is a hard requirement.

**Phase 4 – Live (only after ≥3 months of paper results that survive DSR/PBO)**
- Start with **MES/MNQ** (small tick values), hard daily loss limit, kill switch, cancel-on-disconnect, max order rate (CME Rule 575 hygiene).
- If using a prop firm, Topstep's API is sim-only and Apex reportedly bans full automation on funded accounts — so a personal futures account (IBKR) is the cleanest route for a fully autonomous bot.

**Biggest risks**: (1) ICT edge is unproven — the project may correctly conclude there is none; (2) overfitting via many detector variants (mitigate with DSR/PBO and a frozen holdout); (3) look-ahead bias from swing confirmation and FVG timing; (4) operational risk (disconnects, rollovers, DST).

---

## Sources

**ICT / SMC concepts**
- ICT YouTube channel — https://www.youtube.com/@InnerCircleTrader
- BabyPips, What is ICT trading — https://www.babypips.com/trading/what-is-ict-trading-the-most-accurate-strategy-in-forex
- smartmoneyconcepts (GitHub) — https://github.com/joshyattridge/smart-money-concepts
- smartmoneyconcepts (PyPI) — https://pypi.org/project/smartmoneyconcepts/
- ICT Concepts [LuxAlgo] (TradingView) — https://in.tradingview.com/script/ib4uqBJx-ICT-Concepts-LuxAlgo/
- ICT Ultimate Algorithmic Engine (TradingView) — https://it.tradingview.com/script/u2ItPJf6-ICT-Ultimate-Algorithmic-Engine/
- SMT Divergence 3-Way (TradingView) — https://www.tradingview.com/script/Q322Hy2o-SMT-Divergence-3-Way-Key-Levels-Killzones-Structure/
- ICT Silver Bullet (TradingView) — https://jp.tradingview.com/script/yxRodYFg-ICT-Silver-Bullet/
- ICT Killzones & Pivots (TradingView) — https://kr.tradingview.com/script/WMbmcs4m-ICT-Killzones-Pivots-JB
- NQ Bias script listing (TradingView) — https://il.tradingview.com/scripts/search/bear/page-35
- LuxAlgo killzones concept — https://www.luxalgo.com/library/concept/killzones/
- LuxAlgo ICT Killzone indicator — https://www.luxalgo.com/library/indicator/gLHqnxvc-ict-killzone/
- LuxAlgo Silver Bullet × Macro × Killzone — https://www.luxalgo.com/library/indicator/st4mz5Vn-silver-bullet-x-macro-x-killzone/
- LuxAlgo ICT Silver Bullet — https://www.luxalgo.com/library/indicator/ICT-Silver-Bullet
- LuxAlgo premium & discount — https://www.luxalgo.com/library/concept/premium-and-discount/
- LuxAlgo OTE — https://www.luxalgo.com/library/concept/optimal-trade-entry/
- chartinglens OTE — https://chartinglens.com/blog/ict-optimal-trade-entry-ote
- therighttrader Silver Bullet — https://therighttrader.com/learn/smart-money-concepts/silver-bullet-strategy
- MQL5 SMC guide — https://www.mql5.com/en/blogs/post/772364
- SMT divergence NQ/ES — https://www.eltraderfinanciado.com/zh/blog/smt-divergence
- fxnx, SMC backtest evidence — https://fxnx.com/en/blog/smart-money-concepts-work-backtest-evidence
- Lo, Mamaysky, Wang, Foundations of Technical Analysis (NBER w7613) — https://www.nber.org/papers/w7613
- Park & Irwin (2007), Journal of Economic Surveys — https://doi.org/10.1111/j.1467-6419.2007.00519.x

**Brokers, venues, data**
- IBKR TWS API connect (ports) — https://www.interactivebrokers.com/docs/tws-api/doc/synchronous-api/connect-start-connection
- IBKR Campus, configuring TWS for API — https://www.interactivebrokers.com/campus/trading-lessons/installing-configuring-tws-for-the-api/
- ib_async — https://github.com/ib-api-reloaded/ib_async ; https://pypi.org/project/ib-async/
- Tradovate partner API — https://partner.tradovate.com/overview/welcome/introduction-to-tradovate-partner-api.md ; environments https://partner.tradovate.com/resources/reference/environments
- NinjaTrader partner architecture — https://partner.ninjatrader.com/eval/overview/core-concepts/architecture-overview.md
- Tradovate community forum — https://community.tradovate.com/t/could-i-user-api-access-the-simulation-env-by-a-simulation-account/4033
- PickMyTrade on Tradovate API access — https://blog.pickmytrade.trade/tradovate-api-access-without-1000-minimum-2026-options/
- NinjaTrader 8 Simulator — https://static.ninjatrader.com/support/helpGuides/nt8/simulation.htm ; Strategy Account https://ninjatrader.com/support/helpGuides/nt8/strategy_account.htm
- async_rithmic — https://pypi.org/project/async-rithmic/ ; https://pypi.org/project/async-rithmic/1.3.2/
- Topstep API policy — https://help.topstep.com/en/articles/11187768 ; pricing https://help.topstep.com/en/articles/14289835
- project-x-py docs — https://project-x-py.readthedocs.io/en/latest/authentication.html
- Kraken–NinjaTrader deal — https://www.fintechfutures.com/m-a/kraken-bolsters-multi-asset-strategy-with-1-5bn-ninjatrader-acquisition
- Alpaca paper trading — https://docs.alpaca.markets/us/docs/paper-trading ; crypto https://docs.alpaca.markets/us/docs/crypto-trading-1 ; support https://alpaca.markets/support/alpaca-cryptocurrency
- Coinbase Advanced Trade sandbox — https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/sandbox ; SDK https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/sdk ; perpetuals https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/guides/perpetual
- FOW on Coinbase US perpetual-style futures — https://www.fow.com/app/insights/coinbase-hails-arrival-of-perpetual-style-futures-in-us
- Kraken futures intro — https://docs.kraken.com/api/docs/guides/futures-introduction/ ; testing env https://support.kraken.com/articles/360024809011-api-testing-environment-derivatives ; quickstart https://docs.kraken.com/home/guides/quickstart ; derivatives eligibility https://support.kraken.com/articles/360023786632-kraken-derivatives-eligibility ; US quick start https://support.kraken.com/articles/quick-start-for-clients-in-the-united-states
- Binance US block (The Block) — https://www.theblock.co/post/85589/binance-blocking-us-users-14-day-deadline-new-email
- Bybit restricted countries — https://bybit.com/en/help-center/article/Service-Restricted-Countries
- CCXT — https://github.com/ccxt/ccxt ; manual https://github-redirect.dependabot.com/ccxt/ccxt/wiki/Manual
- Databento python — https://github.com/databento/databento-python ; pricing update https://databento.com/blog/updates-to-subscription-pricing ; CME plans https://databento.com/blog/introducing-new-cme-pricing-plans ; OHLCV example https://databento.com/docs/examples/basics-historical/custom-ohlcv
- Nautilus Databento tutorial — https://nautilustrader.io/docs/latest/tutorials/databento_overview
- Polygon → Massive — https://fisd.net/polygon-io-is-now-massive ; https://www.edgeful.com/blog/posts/futures-data-api-polygon-databento-edgeful-comparison

**Frameworks**
- NautilusTrader — https://github.com/nautechsystems/nautilus_trader
- Freqtrade — https://github.com/freqtrade/freqtrade ; FreqAI https://www.freqtrade.io/en/stable/freqai-running/ ; RL https://www.freqtrade.io/en/stable/freqai-reinforcement-learning/
- backtesting.py — https://github.com/kernc/backtesting.py
- vectorbt — https://github.com/polakowo/vectorbt
- Backtrader Snyk — https://snyk.io/advisor/python/backtrader
- LEAN — https://github.com/QuantConnect/Lean ; brokerages https://www.lean.io/docs/v2/lean-cli/live-trading/brokerages ; QC paper https://www.quantconnect.com/docs/v2/lean-cli/live-trading/quantconnect-paper-trading ; IB https://www.lean.io/docs/lean-cli/live-trading/interactive-brokers
- Jesse — https://github.com/jesse-ai/jesse
- PyPI JSON API (versions/licenses) — https://pypi.org/pypi/{package}/json

**ML & statistics**
- López de Prado, Advances in Financial Machine Learning (Wiley 2018) — https://oreilly.com/library/view/advances-in-financial/9781119482086 ; notes https://reasonabledeviations.com/notes/adv_fin_ml
- fynance labels — https://fynance.readthedocs.io/en/latest/features.labels.html
- Deflated Sharpe Ratio — https://papers.ssrn.com/abstract=2460551
- Probability of Backtest Overfitting — https://papers.ssrn.com/abstract=2326253 ; https://www.risk.net/journal-of-computational-finance/2471206/the-probability-of-backtest-overfitting ; R pbo https://packages.oit.ncsu.edu/cran/web/packages/pbo/readme/README.html
- LightGBM docs — https://lightgbm.readthedocs.io/en/latest/
- Optuna — https://github.com/optuna/optuna ; https://optuna.readthedocs.io
- River — https://github.com/online-ml/river
- ADWIN (Frouros docs) — https://frouros.readthedocs.io/en/latest/api_reference/detectors/concept_drift/auto_generated/frouros.detectors.concept_drift.streaming.window_based.ADWIN.html
- FinRL — https://github.com/AI4Finance-Foundation/FinRL ; FinRL-Meta https://arxiv.org/abs/2211.03107 ; arXiv 2304.13174 https://arxiv.org/pdf/2304.13174
- Claude structured outputs — https://platform.claude.com/docs/en/build-with-claude/structured-outputs
- Claude tool use — https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools ; https://platform.claude.com/docs/en/agents-and-tools/tool-use/implement-tool-use
- Claude batch processing — https://platform.claude.com/docs/en/build-with-claude/batch-processing
- Claude prompt caching — https://docs.claude.com/en/docs/build-with-claude/prompt-caching
- anthropic Python SDK — https://pypi.org/project/anthropic/

**Metrics**
- Sharpe (1994) — https://web.stanford.edu/~wfsharpe/art/sr/sr.htm
- Sortino ratio (PerformanceAnalytics/JFE docs) — https://rdrr.io/cran/JFE/man/SortinoRatio.html
- Van Tharp, R-multiples/expectancy — https://www.traders.com/Documentation/FEEDbk_docs/2007/01/Abstracts_new/Tharp/tharp.html ; https://vantharp.com/Weekly_update/Weekly_273_May_31_2006.htm
- MAE — https://www.tradesviz.com/glossary/maximum-adverse-excursion/ ; https://www.luxalgo.com/library/concept/mae-mfe-distributions/
- quantstats — https://pypi.org/project/quantstats/
- CME MNQ specs — https://www.cmegroup.com/markets/equities/nasdaq/micro-e-mini-nasdaq-100.contractSpecs.html ; Micro FAQ https://www.cmegroup.com/articles/faqs/micro-e-mini-equity-index-futures-frequently-asked-questions.html

**Architecture**
- CME Micro E-mini (hours) — https://www.cmegroup.com/markets/equities/micro-emini-equity.html ; options FAQ https://www.cmegroup.com/articles/faqs/e-mini-s-p-500-tuesday-and-thursday-options-frequently-asked-questions.html
- FastAPI — https://fastapi.tiangolo.com/ ; https://pypi.org/project/fastapi/
- Streamlit — https://docs.streamlit.io/ ; https://pypi.org/project/streamlit/
- Tauri — https://v2.tauri.app/start/ ; sidecar https://v2.tauri.app/learn/sidecar-nodejs/ ; security https://v2.tauri.app/security/
- Electron — https://www.electronjs.org/docs/latest/
- DuckDB Parquet — https://duckdb.org/docs/stable/data/parquet/overview
- SQLite WAL — https://www.sqlite.org/wal.html
- TimescaleDB editions — https://www.tigerdata.com/docs/get-started/choose-your-path/timescaledb-editions

**Regulatory**
- NFA CTA registration — https://www.nfa.futures.org/registration-membership/who-has-to-register/cta.html
- 17 CFR 4.14 — https://www.law.cornell.edu/cfr/text/17/4.14
- CFTC Release 8188-20 (Reg AT withdrawal) — https://www.cftc.gov/PressRoom/PressReleases/8188-20
- Morgan Lewis on Reg AT — https://www.morganlewis.com/pubs/farewell-reg-at-hello-electronic-trading-principles
- CME Rule 575 — https://www.cmegroup.com/rulebook/files/cme-group-Rule-575.pdf ; FAQ https://www.cmegroup.com/education/courses/market-regulation/disruptive-practices-prohibited/disruptive-practice-prohibited-frequently-asked-questions
- PDT elimination — https://international.schwab.com/story/sec-approves-scrapping-25000-day-trader-minimum ; https://us.etrade.com/knowledge/library/margin/pattern-day-trading-rule-change
- CME market data fee lists — https://www.cmegroup.com/market-data/files/june-2026-market-data-fee-list.pdf ; https://www.cmegroup.com/market-data/files/january-2027-market-data-fee-list.pdf
- AMP data fees — https://www.ampfutures.com/trading-info/platform-data-fees/
- Apex automation (secondary) — https://blog.traderspost.io/article/automate-apex-trader-funding-with-traderspost ; https://blog.pickmytrade.io/5-prop-firm-automation-rules-before-you-run-a-bot-2026/
