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
- **Pre-registered setup rules** (decided in [#16](https://github.com/DaltonDom/moon-ai/issues/16); parameter names follow [ict-setup-definitions.md](https://github.com/DaltonDom/moon-ai/blob/research/ict-setup-definitions/docs/research/ict-setup-definitions.md) §4). See [Setup testing protocol](#setup-testing-protocol).
- **Monthly ICT watcher:** new uploads on the InnerCircleTrader YouTube channel are summarised into candidate setups. The user approves them before they are coded and tested.

## Setup testing protocol

Decided in [#16](https://github.com/DaltonDom/moon-ai/issues/16).

**Pre-registration**

- Each setup has one locked default config in a committed `defaults.yaml`, written before any backtest runs. The commit is the pre-registration record.
- Only the defaults are tested first. Every run, defaults included, is logged as a trial for the Deflated Sharpe Ratio (DSR) and the Probability of Backtest Overfitting.
- **Go-forward bar.** A setup goes forward only if all three hold on the in-sample period (the 6-month holdout stays untouched):
  1. Its mean R per trade beats the random-entry baseline (≈1,000 runs with the same windows, stops, targets and direction mix), and the bootstrap 95% CI of the difference excludes zero.
  2. DSR > 0.95, counting every trial logged for that setup.
  3. At least 100 trades. Fewer is reported as "insufficient", not "fail".
- **Rescue pass.** A setup whose default fails gets one pass of at most 12 trials. The trials are chosen in advance from that setup's UNVERIFIED parameters and change one parameter at a time, with no combinations. If none clears the bar, the setup is retired with the reason on its report card. It comes back only with new primary ICT evidence.

**Defaults**

| Parameter | Default | First variant(s) |
|---|---|---|
| NY AM killzone (OTE pullback, 2022 model) | 08:30–11:00 | 07:00–10:00 |
| London killzone / London SB | 02:00–05:00 / 03:00–04:00 | — |
| Extra SB windows | off | 07:00–08:30 |
| Swing N / sweep close-back *m* / MSS | 1 / 1 bar / on close | — |
| Displacement | body ≥ 1.5 × ATR(14) | 1.0, 2.0 |
| FVG selection / entry | first FVG after the MSS / near edge | first-tethered / CE |
| Stop | sweep extreme + 1 tick | — |
| OTE entry | 62% | 70.5%, 79% |
| SB minimum objective (AM and PM) | 10 NQ points | AM: 15, 20 (with first-tethered); PM: 5 |
| Power of 3 reference open | 00:00 ET | — |
| Limit-fill rule | set by [#8](https://github.com/DaltonDom/moon-ai/issues/8) | — |

**Daily bias**

- Bias is not a gate in the default rules. All five bias proxies are logged as ML features. "Trade only with the bias" is one rescue-pass variant per setup.
- London sweep-and-reverse uses bias to detect the Judas swing, via the previous-day range rule. On an inside day there is no bias, and either side of the Asian range qualifies.
- The 2022 model uses weekly expansion, its own checklist step.
- The ground-truth days need no bias call.

**Overlapping setups**

- Each setup is backtested in isolation, with its own report card and baseline. Within one setup, signals on the same bars are one trade.
- In portfolio runs, each trade has one owner. Priority goes NY AM SB > NY PM SB > London sweep-and-reverse > OTE pullback > 2022 model. Other matching setups are logged as tags.
- The 2-trades-per-session cap counts deduped trades. Signals blocked by the cap are logged as `skipped:cap` candidates with full features and are not traded.

**News**

- The ±15-minute blackout blocks the entry only. A setup may form during it, and entry is allowed from +15 minutes. "Blackout blocks the whole setup" is a rescue-pass variant. The blackout rules themselves are set in [#15](https://github.com/DaltonDom/moon-ai/issues/15).

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
