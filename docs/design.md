# moon-ai — Design

Status: agreed in grilling session, 2026-10-31. Research backing: [ict-ml-trading-bot.md](research/ict-ml-trading-bot.md), [prop-firms-and-order-routing.md](research/prop-firms-and-order-routing.md).

## Goal

An autonomous, self-improving ICT trading bot for CME micro futures. Prove it on paper, then run it on a prop-firm account so the maximum loss is the evaluation fee.

## Market & setups

- **MNQ first.** The engine is multi-instrument so MES or crypto can be added later.
- **Initial setups (4–5):** NY AM Silver Bullet, NY PM Silver Bullet, London sweep-and-reverse, OTE pullback, 2022 model.
- Each setup is backtested on 5+ years of official CME data from Databento.
- **Only setups that beat a random-entry baseline after costs go forward.**
- **Setup library:**
  - One self-contained file per setup.
  - A new setup goes from a plain-English description, to code, to one command or button that runs the backtest, the baseline comparison and the overfitting checks, and produces a report card.
- **Monthly ICT watcher:** new uploads on the InnerCircleTrader YouTube channel are summarised into candidate setups. The user approves them before they are coded and tested.

## How it learns

- Fixed ICT rules generate candidate trades.
- An ML filter (LightGBM meta-labeler, triple-barrier labels) learns which candidates to take, using every logged factor.
- **Retraining:** every weekend, followed by one week in shadow mode.
- **Promotion:** a challenger is promoted only if both hold:
  - it beats the current model on expectancy (in R) with a 95% CI excluding zero
  - it passes the untouched holdout
- **No model promotions during an active evaluation.**
- Proposed changes to ICT rules or risk parameters go to the user for approval. They are never self-applied.

## Verifiability

- **Ground-truth set:** about 50 hand-checked days of setups. The user spot-checks them on TradingView. Detectors must match them exactly, or CI fails.
- **Frozen replay:** a fixed historical period must reproduce identical results after every code change unless the change is intentional.
- **Untouched holdout:** the most recent 6 months, used only for sign-off.
- **Versioned models:** each version is reproducible from its data, code commit and parameters.
- **Overfitting checks:** every trial is logged, and reports show the Deflated Sharpe Ratio and the Probability of Backtest Overfitting.
- **Mandatory baselines:** random entries in the same windows with the same stops and targets, and the rules with no ML filter. If the ML does not beat rules-only, it is disabled.

## Trade journal & metrics

- **Each trade records:**
  - a chart snapshot and the full feature vector
  - which rules passed and failed
  - the ML probability
  - planned entry, stop and target
  - fills and slippage
  - MAE/MFE, R result and exit reason
- **Claude review per trade,** one of four buckets:
  - good setup / good result
  - good setup / unlucky loss
  - rule break or execution error
  - bad setup the filter should have rejected
- Weekly report.
- **Dashboard:** win rate, profit factor, expectancy, average R, drawdown, Sharpe/Sortino, per setup and per model version.
- **Claude never places trades or changes rules.**

## Backtest realism

Agreed in the grilling session for [#8](https://github.com/DaltonDom/moon-ai/issues/8), 2026-10-31. Backtests and the nightly paper replay use exactly the same rules, so their results stay comparable. Defaults live in `BrokerConfig` in `src/moon_ai/config.py`.

- **Commission:** $1.00 per contract per side ($2.00 round trip), a deliberately pessimistic generic rate. Swap in the chosen prop firm's real rate once a firm is picked.
- **Slippage:** applied to market orders, stop entries and bracket stop exits. Limit entries and targets never slip. Numbers come from the [London liquidity research](https://github.com/DaltonDom/moon-ai/blob/research/london-liquidity/docs/research/london-liquidity.md) (Databento tick data, Oct 2026):

  | Window (time the fill's bar opens, New York) | Entry | Stop exit |
  |---|---:|---:|
  | London 02:00–05:00 | 2 ticks | 2 ticks |
  | London, more than 10 contracts | 3 ticks | 3 ticks |
  | Everything else (NY AM measured; NY PM and other windows reuse it) | 1 tick | 3 ticks |

- **No volatility model.** Instead, every setup that passes the [setup testing protocol](https://github.com/DaltonDom/moon-ai/blob/claude/zealous-heisenberg-s13jgm/docs/design.md#setup-testing-protocol) (#16) is re-run once with **double slippage** (`slippage_multiplier = 2.0`) and goes forward only if it is still profitable.
- **Limit fills:** a limit (e.g. an FVG-edge entry or a target) fills only when price trades **1 tick through** it; a touch is not a fill.
- **Same-bar stop and target:** the stop is assumed to fill first, unless 1-second bars for that minute (bought on demand, pennies) show the order. On the bar an entry fills, a touched stop counts and a touched target does not.
- **Skipped sessions:** no new trades on CME holiday sessions, early-close sessions, or the session in which the continuous `.v.0` contract rolls (the previous session's levels belong to the old contract). No price adjustment across rolls.
- **London minimum stop:** a London trade whose stop is under **40 ticks** (10 MNQ points) is skipped, and logged as a skipped candidate so the ML and reviews still see it (`IctConfig.london_min_stop_ticks`). At the 24-tick median of a bare one-bar sweep, costs would be about 27% of R.

## Hard risk rules (ML cannot override)

- 1% risk per trade.
- At most 2 trades per session.
- Daily stop at −2%.
- Flat by 16:00 ET.
- No trading from 15 minutes before to 15 minutes after high-impact news.
- Kill switch at 10% drawdown.
- Always stricter than the prop firm's limits, with a buffer: daily stop at no more than 50% of the firm's daily limit, and never within 25% of the firm's failure line.
- **Every entry is sent with a broker-side stop and target attached,** so the trade stays protected if the PC or internet drops.

## Phases & where they run

Everything runs on the user's **Mac** wherever possible. It moves to the user's **Windows PC** (which can stay on all day) when NinjaTrader is required. A cloud server is an optional later upgrade.

| Phase | What | Where | Cost |
|---|---|---|---|
| 1. Build & backtest | Engine, detectors, ML, journal, dashboard | Mac | $0 (Databento $125 free credit) |
| 2. Paper | Nightly forward replay of the previous session's CME 1-minute data (T+1; data under 24h old needs Databento's $199/mo plan), as if live | Mac | ~$0.42/mo |
| 3. Connection test | 14 days with real-time prices on NinjaTrader's free trial, through our NinjaScript bridge | Windows PC | $0 |
| 4. Evaluation | One prop-firm evaluation | Windows PC | ~$110 per attempt |
| 5. Funded | One funded account; copying across accounts only after 3 months meeting the bar | Windows PC | $0 + firm fees |

**Go-live bar (must be met on paper before buying an evaluation):**

- 200+ trades
- 3+ months
- profit factor ≥ 1.3
- max drawdown ≤ 10%

**Prop firm:**

- Order of preference: Lucid Trading, then Bulenox, then MyFundedFutures, or firms the user finds.
- Ruled out because their own pages ban the bot: Apex, Topstep, Alpha Futures, TradeDay, Tradeify.
- **Rules policy:**
  - Follow each firm's published rules.
  - Silence counts as allowed.
  - Where the rules explicitly require a step (for example, bot approval), flag it to the user, who decides.

## Stack

- **Engine:** a lean custom Python event loop on Polars + `databento`, behind `BarFeed` / `Broker` / `Journal` interfaces. When a stop and a target are both hit in the same bar, the stop is assumed to fill first unless 1-second bars resolve which came first. NautilusTrader is re-evaluated at Phase 3 ([engine-choice research](https://github.com/DaltonDom/moon-ai/blob/research/engine-choice/docs/research/engine-choice.md)).
- **ML:** LightGBM; Optuna for tuning; River for drift detection.
- **Live connection:** our own NinjaTrader 8 add-on passes bars and orders between the Python engine and NinjaTrader on the Windows PC. NinjaTrader connects to the firm over CQG.
- **Data:** Databento `GLBX.MDP3`.
- **Dashboard:** FastAPI + React.
- **Charts:** TradingView for viewing and verification.
- **Reviews:** Claude API with structured outputs, run nightly through the Batch API.
- **Alerts:** a single safety alert, live accounts only, sent when the kill switch fires or the connection is lost with a position open.
