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
- **Claude review per trade** and a weekly report (see [Claude trade review](#claude-trade-review)).
- **Dashboard:** win rate, profit factor, expectancy, average R, drawdown, Sharpe/Sortino, per setup and per model version.
- **Claude never places trades or changes rules.**

## Claude trade review

Agreed in the grilling session for [#13](https://github.com/DaltonDom/moon-ai/issues/13), 2026-10-31.

**Scope and role**

- Claude reviews **every taken trade** individually. Skipped candidates (ML skip, `skipped:cap`, news blackout, London minimum stop) get no per-candidate review; the weekly report shows them as code-computed totals (count, how many would have won, net R from their labels).
- **Reviews are commentary, never inputs.** Buckets and opinions never feed ML training, labels or model promotion. They are for the user to read and for proposals, which must then pass a real backtest.
- **Code finds the mistakes, Claude explains them.** Code computes `code_flags` deterministically: fill worse than the slippage assumption, a failed rule check, a rejected order, a missing broker-side stop or target. Claude cannot override them.

**Buckets** (exactly one per trade)

1. Rule break or execution error — set whenever `code_flags` is non-empty, checked first.
2. Good setup, won.
3. Good setup, unlucky loss.
4. Bad setup, lucky win.
5. Bad setup, lost — the filter should have rejected it.

"Good" or "bad" is Claude's judgement of whether the trade matched the setup's rules in spirit, and it must cite the feature or rule behind it.

**Inputs:** the full journal entry (plan, fills, rule checks, ML probability, feature vector, MAE/MFE, R and exit reason), the setup's pinned rules from `defaults.yaml`, and one chart image of the setup window and the trade.

**Output, per trade** (stored with the trade in the journal, validated against a fixed schema; an invalid response is rejected, not stored):

| Field | Content |
|---|---|
| `bucket` | one of the five above |
| `code_flags` | copied from the code's checks; read-only for Claude |
| `summary` | 2–3 plain-English sentences |
| `reasons` | list; each cites a feature by name and value (e.g. `sweep_depth_ticks = 3`) or a rule in `defaults.yaml`. Only features present in the journal entry may be cited |
| `setup_quality` | `good` / `bad`, with confidence `low` / `medium` / `high` |
| `execution_notes` | fills or slippage worth noting, or empty |
| `follow_up` | optional idea worth testing; it becomes a proposal only if the weekly report picks it up |
| `model`, `prompt_version`, `cost_usd` | traceability and the monthly cap |

**Model, schedule and cost**

- Claude Opus 5.5 through the Message Batches API (half price). Per-trade reviews go out as one batch right after the nightly paper replay and are back before the next session.
- The weekly report runs **Saturday**, before the weekend retraining, so proposals are queued before a new model's shadow week. It includes last week's shadow-model comparison.
- Expected cost about $1–3 a month. **Hard cap $10 a month:** when reached, reviews stop and the user is alerted.
- **Failures** (API error, invalid output, refusal, cap reached): the trade is marked `review: pending` and retried the next night, up to 3 times, then `review: failed` and listed in the weekly report. Reviews never block trading, the paper replay or retraining.

**Weekly report and proposals**

- A Markdown file in the repo (`reports/weekly/<ISO year>-W<week>.md`), also shown on the dashboard: metrics per setup and model version, bucket counts, skipped-candidate totals, the 3–5 most instructive trades, failed reviews, and proposals.
- **At most 3 proposals a week,** each opened as a GitHub issue labelled `proposal`: the exact parameter or rule change, the evidence, and the test that would decide it.
- **Two approvals.** The user adds `approved` to run the test, which is logged as a trial under the setup testing protocol (#16). The rule changes only if the test passes **and** the user approves the result.

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
