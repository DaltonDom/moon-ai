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

## ML filter: features and labels

Decided in [#9](https://github.com/DaltonDom/moon-ai/issues/9). Terms are defined in [GLOSSARY.md](../GLOSSARY.md).

**Labels**

- **Triple barrier on the candidate's own plan.** The barriers are the candidate's planned stop and target, plus its setup's time-out. Label = 1 if the target is hit first, otherwise 0, so a time-out counts as a loss. Net R is stored next to the label.
- **Labels come from the engine's own simulated trade,** with the same fills, costs and same-bar rule as the backtest ([#8](https://github.com/DaltonDom/moon-ai/issues/8)), so a label can never disagree with the journal.
- **Time-outs (pre-registered in `defaults.yaml`):**
  - 15:55 ET for NY AM SB, NY PM SB, OTE pullback and the 2022 model
  - 09:30 ET for London sweep-and-reverse, whose one variant is 16:00
- **Labels ignore portfolio state.** Each candidate is labelled as if it were taken on its own, including `skipped:cap` candidates and those after the daily stop. Unfilled limit entries get no label and are left out of training. A candidate whose entry falls in the news blackout is labelled only if it still qualifies from +15 minutes.

**Features**

- **Frozen at decision time:** the close of the bar that completes the setup and places the order, not the fill.
- **Feature set v1.** Sizes are in ticks and as multiples of ATR(14), never absolute prices.
  - **Context:** setup type, killzone, minutes since the window opened, time of day, day of week.
  - **Bias:** each of the five bias proxies as aligned / against / none relative to the trade direction, and how many agree.
  - **Setup geometry:** sweep depth, FVG size, displacement body and range, stop distance, distance to target, planned R:R.
  - **Liquidity:** distance to the nearest opposing level by source (swing, Asian, prior day), and which kind of level was swept.
  - **SMT:** an MNQ vs MES divergence flag in the setup window, using the same swing rules.
  - **Volatility regime:**
    - 1-minute ATR(14) ÷ its 20-session median at the same time of day
    - prior-day range ÷ daily ATR(14)
    - daily ATR percentile over the trailing 252 days
  - **News:** minutes to the next and since the last scheduled high-impact event, plus event-day flags (FOMC / CPI / NFP / other).
  - **Prior sessions:** Asian, London and prior-day ranges in ATR, and where the entry sits in the prior-day range (premium/discount %).
  - **Volume:** displacement-bar volume ÷ the 20-session median for that minute.
- **Not features:** today's P&L, the earlier trade's result and how many trades are already taken. That is portfolio state, which the risk rules handle.
- **Versioned.** Any change to the feature set ships as a new model version and counts as a trial.
- **Banned (look-ahead):**
  - anything known after decision time: fill, slippage, MAE/MFE, bars to fill, exit and outcome fields
  - unconfirmed swings
  - the current session's or day's high, low and range, and today's daily bar
  - ATR that includes the forming bar
  - unscheduled news events
  - released economic values or surprises
  - absolute price levels, because unadjusted rolls make them jump
- **Enforced in CI.** The feature builder only receives primitives whose `known_at` is at or before decision time. A truncation test extends the ICT look-ahead test to the whole feature vector: cutting the bars at decision time must give an identical vector.

**Training**

- **One pooled model** across all go-forward setups, with setup type as a feature, trained only on setups that passed the go-forward bar. A per-setup split is a challenger like any other.
- **Minimum data:** at least 500 labelled candidates pooled, and at least 100 for each included setup. Below that, setups trade rules-only and the ML filter is off. The holdout never enters training.
- **Cross-validation:** walk-forward folds that purge any candidate whose entry-to-exit window overlaps a test fold, plus a 1-session embargo after each test fold.
- **Overlapping candidates:** each setup's candidate is its own row. Rows are weighted by average uniqueness (López de Prado, ch. 4): a candidate overlapping k others gets a weight of about 1/k.

**Take or skip**

- Take a candidate when its expected R is above zero, which means `p > 1 / (1 + net R:R)`, with p calibrated on out-of-fold predictions by isotonic regression.
- The cut comes from each candidate's own R:R, so there is no tuned threshold.
- The probability never changes position size; risk stays at 1%.

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

## News blackout

Agreed in the grilling session for [#15](https://github.com/DaltonDom/moon-ai/issues/15), 2026-10-31. Events come from our own versioned `news_events.csv`, built from BLS, BEA and Federal Reserve records ([news-calendar research](https://github.com/DaltonDom/moon-ai/blob/research/news-calendar/docs/research/news-calendar.md)). Backtests, paper replay and live trading read the same file. Defaults live in `IctConfig` (`news_handling`, `news_blackout_minutes`, `fomc_blackout_end`).

- **Blocking events (±15 minutes):** CPI, Employment Situation (NFP), PPI, GDP and PCE (08:30 ET); FOMC statement and minutes (14:00 ET); FOMC press conferences, the Chair's congressional testimony (Humphrey-Hawkins) and the Jackson Hole speech.
- **FOMC statement days:** blocked from 13:45 to **15:30 ET**, through the end of the press conference. The NY PM Silver Bullet does not trade on those days.
- **Recorded, not blocking:** other Chair speeches, ISM manufacturing and services (10:00), retail sales, jobless claims, JOLTS and consumer sentiment. They are ML features and the "news inside the killzone" trigger the 2022 model needs.
- **Unscheduled events** (e.g. the Mar 2020 emergency cuts): not blocked in backtests, because live trading could not have known 15 minutes ahead. They carry `scheduled=false`, so results can be reported with and without those days. The daily stop is the protection.
- **History records actual releases:** rows hold the time a release actually came out; cancelled releases (e.g. the Oct 2025 jobs report) have no row. Live and paper use the daily-refreshed official schedule; a release cancelled at short notice still blocks its planned time.
- **Entries only:** the blackout blocks entries, not setups ([setup testing protocol](https://github.com/DaltonDom/moon-ai/blob/claude/zealous-heisenberg-s13jgm/docs/design.md#setup-testing-protocol), #16). A setup may form during it and enter from the end of the blackout.
- **Open trades** are held through the news with their broker-side stop and target. A gap through the stop fills at the worse price in the simulator.
- **Unfilled entry orders** are cancelled when a blackout starts. After it ends, the setup may place the order again if it is still valid (stop not hit, window still open).

## Hard risk rules (ML cannot override)

- 1% risk per trade.
- At most 2 trades per session.
- Daily stop at −2%.
- Flat by 16:00 ET.
- No trading from 15 minutes before to 15 minutes after high-impact news (see [News blackout](#news-blackout)).
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
