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
- **Promotion:** a challenger is promoted only if it beats the current model on expectancy (in R) and passes the untouched holdout. Exact rules are in [Model promotion and rollback](#model-promotion-and-rollback).
- **No model promotions during an active evaluation.**
- Proposed changes to ICT rules or risk parameters go to the user for approval. They are never self-applied.

## Model promotion and rollback

Decided in [#10](https://github.com/DaltonDom/moon-ai/issues/10). These numbers make "improving" verifiable, so they are fixed before any model trains.

**Who competes**

- **Rules-only is the starting champion** and the permanent fallback. The first ML model must beat it under the same test.
- **Refresh vs challenger.**
  - A *refresh* is the champion's recipe (features, hyperparameters, model type, training rules) retrained on the latest data. It is adopted automatically if its last-fold Brier score is no worse than the current version's, its shadow week is not below the current version's beyond bootstrap noise, and it is reproducible from its data, commit and parameters.
  - A *challenger* is a changed recipe. It must win the full test below.
- **One challenger at a time**; others queue. A challenger without enough evidence after its walk-forward history plus 12 shadow weeks is dropped as "no detectable difference", with the reason recorded. Every challenger tried counts as a trial in the DSR.

**The test**

- **Paired, on disagreements.** Both recipes score the same rule-generated candidates. Only candidates where one takes and the other skips are compared; each candidate's R comes from the engine's simulated trade, so a skipped trade's R is still known.
- **Evidence is out-of-sample for both.** Both recipes are refit walk-forward on the same folds, each fold trained only on earlier data, and forward shadow decisions are added as they arrive. The shadow period must not show the challenger losing.
- **Session-block bootstrap** of the paired R differences: one-sided 95% (challenger better), 10,000 resamples, resampling whole sessions.
- **Minimum evidence:** 150 disagreements over at least 30 sessions. Below that, the result is "not enough evidence yet", never pass or fail. The 150 assumes a paired-difference spread of about 1.5R and a 0.3R edge at 80% power. The spread is re-measured once after the first model, and the minimum is recomputed and logged.
- **Overfitting gates:** DSR > 0.95, counting every Optuna trial, every challenger and every holdout check, and PBO ≤ 0.25.

**Holdout**

- **Fixed and checked once per challenger.** The 6-month holdout is fixed at its creation date. Each challenger may check it once, and each check counts as a DSR trial. A new holdout is carved out on promotion or every 6 months, whichever comes first.
- **Passing** means the paired mean R difference against the champion on the holdout is ≥ 0, and the challenger's net expectancy on the trades it takes is > 0R. Superiority is proven by the main test; the holdout guards against a fluke.

**Promotion**

- **Automatic** when superiority, holdout, DSR, PBO and the shadow check all pass, with a notification and a written report. Changes to ICT rules or risk parameters still need the user's approval.

**Switching off, rollback and drift**

- **Rolling check against rules-only:** the same paired bootstrap of the live model against rules-only on the last 60 paper sessions. If the model is worse at one-sided 95%, the bot falls back to rules-only automatically. If only the latest refresh is to blame (the previous version passes the same check), it rolls back to that version. The user is notified either way.
- **Drift alarms (River ADWIN)** watch the per-candidate Brier score and the take rate. An alarm freezes refreshes and promotions, runs the rolling check immediately and notifies the user. An alarm never disables the model on its own.
- **During an active evaluation:** no promotions and no refreshes. Falling back to rules-only is allowed; rolling back to an earlier model version is not.

## Verifiability

- **Ground-truth set:** about 50 hand-checked days of setups. The user spot-checks them on TradingView. Detectors must match them exactly, or CI fails.
- **Frozen replay:** a fixed historical period must reproduce identical results after every code change unless the change is intentional.
- **Untouched holdout:** the most recent 6 months, used only for sign-off. How often it is checked and when it refreshes are in [Model promotion and rollback](#model-promotion-and-rollback).
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
