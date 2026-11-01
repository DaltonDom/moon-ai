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

- Each setup has one locked default config in a committed `config/defaults.toml`, written before any backtest runs. The commit is the pre-registration record.
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
- **Promotion:** a challenger is promoted only if it beats the current model on expectancy (in R) and passes the untouched holdout. Exact rules are in [Model promotion and rollback](#model-promotion-and-rollback).
- **No model promotions during an active evaluation.**
- Proposed changes to ICT rules or risk parameters go to the user for approval. They are never self-applied.

## ML filter: features and labels

Decided in [#9](https://github.com/DaltonDom/moon-ai/issues/9). Terms are defined in [GLOSSARY.md](../GLOSSARY.md).

**Labels**

- **Triple barrier on the candidate's own plan.** The barriers are the candidate's planned stop and target, plus its setup's time-out. Label = 1 if the target is hit first, otherwise 0, so a time-out counts as a loss. Net R is stored next to the label.
- **Labels come from the engine's own simulated trade,** with the same fills, costs and same-bar rule as the backtest ([#8](https://github.com/DaltonDom/moon-ai/issues/8)), so a label can never disagree with the journal.
- **Time-outs (pre-registered in `config/defaults.toml`):**
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
- **Drift alarms (ADWIN)** watch the per-candidate Brier score and the take rate. An alarm freezes refreshes and promotions, runs the rolling check immediately and notifies the user. An alarm never disables the model on its own.
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
- **Claude review per trade** and a weekly report (see [Claude trade review](#claude-trade-review)).
- **Dashboard:** win rate, profit factor, expectancy, average R, drawdown, Sharpe/Sortino, per setup and per model version.
- **Claude never places trades or changes rules.**

### Journal storage

Decided in [Journal storage and data model](https://github.com/DaltonDom/moon-ai/issues/24).

- **Two stores, one schema:**
  - **Paper, shadow and later live trading** go in one SQLite file, `data/journal/journal.sqlite`, in WAL mode. Rows change after they are written (a trade closes, a review arrives), and the dashboard reads while the nightly job writes. SQLite handles both and is in Python's standard library.
  - **Backtests and baselines** are large and never change, so each run is written once as Parquet under `data/runs/<run id>/`.
  - Both use the same tables and columns, so the same code (Polars) reads either.
- **Tables:**

  | Table | One row per | Key fields |
  |---|---|---|
  | `runs` | backtest, baseline or paper/shadow stream | run id, kind (`backtest`, `baseline_random`, `baseline_rules`, `paper`, `shadow`, later `live`), code commit, `config/defaults.toml` hash, model id, data range, account size and risk per trade |
  | `candidates` | candidate | id, run, setup, side, decision time, planned entry/stop/target, time-out, rule results, feature vector, feature-set version, ML probability and threshold, **status** (`taken`, `skipped:ml`, `skipped:cap`, `skipped:blackout`, `skipped:london_min_stop`, `skipped:daily_stop`, `skipped:session` (holiday, early close, roll or degraded day), `skipped:busy` (a trade on that symbol is already open or working), `skipped:kill_switch`, `skipped:size` (the stop is too wide for 1 contract at 1% risk), `unfilled`), label, other matching setups (tags) |
  | `orders` / `fills` | order / fill | candidate, type, prices, quantity, times, slippage in ticks, commission |
  | `trades` | taken candidate | entry and exit fills, exit reason, MAE/MFE, R, net $, chart path |
  | `reviews` | taken trade | status (`pending`, `done`, `failed`), attempts, bucket, the validated review fields, model used, cost |
  | `models` | model version | id, recipe, training window, role (`champion`, `challenger`, `retired`), promotion and rollback records, holdout checks used |
  | `events` | health event | nightly step results, alarms, fallbacks. This is what the dashboard's status strip and "Needs you" read |
- **Rules:**
  - **Ids are deterministic:** a candidate id is `<run>:<setup>:<decision time>:<side>`, so two runs of the same code compare row by row. The frozen replay relies on this.
  - **Kinds are never mixed.** Every row carries its run, and the Today page reads only the `paper` run. Backtest numbers can't leak into the go-live bar.
  - **Append-only, with two exceptions:** a trade's exit fields are filled when it closes, and a review's fields arrive later. Nothing else is edited; a correction is a new run.
  - **Money:** prices are stored in points, with R and net $ (after commission and slippage) computed once at close.
- **Feature vectors** (and other nested fields: rule results, tags, review fields) are canonical JSON text in both stores, so a round-trip is exact, tagged with a feature-set version. Training expands them into columns, and a feature-set change is a new version, never an edit.
- **Charts:** one PNG per taken trade at `data/charts/<candidate id>.png`, rendered at close for the Claude review and the dashboard. Skipped candidates get no chart.
- **Schema versions:** a `schema_version` table and numbered migrations in code. Each Parquet run records the schema version it was written with.
- **Backups:** the nightly job copies `journal.sqlite` to `data/backups/` and keeps the last 14. Time Machine covers the rest.

## Backtest realism

Agreed in the grilling session for [#8](https://github.com/DaltonDom/moon-ai/issues/8), 2026-10-31. Backtests and the nightly paper replay use exactly the same rules, so their results stay comparable. Defaults live in `BrokerConfig` in `src/moon_ai/config.py`.

- **Commission:** $1.00 per contract per side ($2.00 round trip), a deliberately pessimistic generic rate. Swap in the chosen prop firm's real rate once a firm is picked.
- **Slippage:** applied to market orders, stop entries and bracket stop exits. Limit entries and targets never slip. Numbers come from the [London liquidity research](https://github.com/DaltonDom/moon-ai/blob/research/london-liquidity/docs/research/london-liquidity.md) (Databento tick data, Oct 2026):

  | Window (time the fill's bar opens, New York) | Entry | Stop exit |
  |---|---:|---:|
  | London 02:00–05:00 | 2 ticks | 2 ticks |
  | London, more than 10 contracts | 3 ticks | 3 ticks |
  | Everything else (NY AM measured; NY PM and other windows reuse it) | 1 tick | 3 ticks |

- **No volatility model.** Instead, every setup that passes the [setup testing protocol](#setup-testing-protocol) (#16) is re-run once with **double slippage** (`slippage_multiplier = 2.0`) and goes forward only if it is still profitable.
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
- **Entries only:** the blackout blocks entries, not setups ([setup testing protocol](#setup-testing-protocol), #16). A setup may form during it and enter from the end of the blackout.
- **Open trades** are held through the news with their broker-side stop and target. A gap through the stop fills at the worse price in the simulator.
- **Unfilled entry orders** are cancelled when a blackout starts. After it ends, the setup may place the order again if it is still valid (stop not hit, window still open).

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

**Inputs:** the full journal entry (plan, fills, rule checks, ML probability, feature vector, MAE/MFE, R and exit reason), the setup's pinned rules from `config/defaults.toml`, and one chart image of the setup window and the trade.

**Output, per trade** (stored with the trade in the journal, validated against a fixed schema; an invalid response is rejected, not stored):

| Field | Content |
|---|---|
| `bucket` | one of the five above |
| `code_flags` | copied from the code's checks; read-only for Claude |
| `summary` | 2–3 plain-English sentences |
| `reasons` | list; each cites a feature by name and value (e.g. `sweep_depth_ticks = 3`) or a rule in `config/defaults.toml`. Only features present in the journal entry may be cited |
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
- **Stages are labels** on the issue, set by the dashboard's buttons (or by hand on GitHub): `proposal` (approve test) → `approved` (testing) → `test-passed` (approve change) → `adopted` (live). A failed test gets `test-failed` and is closed; "No" adds `rejected` and closes the issue as not planned. The dashboard needs a fine-grained `GITHUB_TOKEN` with issue access to this repository only.

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

## Nightly run

Decided in [Nightly run on the Mac: schedule, steps, and how the user knows it worked](https://github.com/DaltonDom/moon-ai/issues/25).

**Schedule**

- **A launchd agent runs the job every day at 18:30 New York time.** It is the user's own LaunchAgent, so it needs no admin password.
- **The job catches up and is idempotent.** Each run replays every completed CME session whose data Databento will serve and that hasn't been replayed yet, oldest first, then stops. Missing a night is harmless: the next run does both sessions. The same code works whether Databento serves yesterday's session at T+1 (the research's plan) or sooner.

  The embargo a usage-only account actually sees is still UNVERIFIED: on 2026-10-31, `get_dataset_range` reported data up to 8 hours old, but the market was closed. The first week's runs record it.
- **The Mac doesn't have to stay awake.** If it is asleep at 18:30, launchd runs the job when it wakes; if it was off, the next day's run catches up. `doctor` warns when no run has finished in 36 hours.
- **The dashboard is installed as a second agent** that keeps `http://localhost:8000` up, so it is always one bookmark away.
- **Dashboard API** (`moon-ai dashboard`, `src/moon_ai/dashboard/`): read-only JSON for the six pages under `/api/`, plus two actions, queueing a backtest (a JSON file in `data/jobs/`, run one at a time by a worker thread as `moon-ai backtest`) and approving or rejecting a proposal. It binds to 127.0.0.1, answers only `Host: localhost`/`127.0.0.1`, and every write needs an `X-Moon-AI: 1` header, so a web page on another site can't trigger one.
- **After 2027-04-30, nightly pulls are pay-as-you-go,** about $0.45/month. That is when the Databento credit expires, and Databento needs a card on file then. The dashboard warns 30 days before.

**Steps** (each writes a pass/fail `events` row with a plain-language message)

1. **Preflight:** disk space, keys, network, and a lock so only one run happens at a time.
2. **Pull bars** for the sessions to replay, with a $1-per-night cost cap. Also pull 1-second bars for any minute where a stop and target could both have been hit.
3. **Check the data:**
   - bar counts against the CME calendar
   - gaps
   - Databento's `get_dataset_condition` (degraded days are flagged, and their replay is held)
   - contract rolls
4. **Refresh the news calendar.**
5. **Replay each session** through the `Trader` with the champion model, and the challenger in shadow if one is in tryout. Everything is journaled.
6. **Render charts, then reviews:** submit Claude reviews as a Batch, and collect the previous night's batch.
7. **Model checks:**
   - the rolling 60-session comparison with rules-only
   - the drift monitors
   - on Saturday, the weekly report and proposals
   - at the weekend, the weekly model refresh, with guardrails
8. **Housekeeping:** back up the journal (keep 14), rotate logs, and write a one-line summary.

When a step fails, the steps that depend on it are skipped and marked "skipped". The next run retries, and nothing half-written is kept, because a session's replay is committed in one transaction.

**How the user knows it worked**

- **Dashboard:** the Today page's "Last night" card shows the run and each step, from the `events` table. A failed step turns the card red and explains what happened and whether anything is needed.
- **Notifications:** a macOS notification on failure, and when something lands in "Needs you". The last line of the summary always says which model is in charge and how it compares with rules-only over the last 60 sessions. Optional phone push via a free ntfy.sh topic (`NTFY_TOPIC` in `~/.config/moon-ai/.env`).
- **`uv run moon-ai nightly status`:** the last 7 runs in plain language, from the terminal.

**Commands**

| Command | Does |
|---|---|
| `nightly install` | writes and loads both launch agents, runs `doctor`, and does a dry run on the last available session |
| `nightly status` | the last 7 runs and their steps |
| `nightly run [--session YYYY-MM-DD]` | runs now, or re-runs one session into a new run |
| `nightly uninstall` | removes both agents; data stays |

## Code layout and commands

Decided in [Repo layout, engine interfaces and the Mac dev setup](https://github.com/DaltonDom/moon-ai/issues/23).

**Packages** (`src/moon_ai/`, existing modules kept as they are):

| Package | Holds |
|---|---|
| `bars.py`, `sessions.py`, `config.py`, `engine.py`, `broker.py` | existing foundation |
| `data/` | Databento download (exists), the Parquet bar store and `ParquetBarFeed`, 1-second bar lookup, CME holiday / early-close / roll calendar, `news_events.csv` builder and loader, degraded-day list |
| `ict/` | ICT primitives (exist) |
| `setups/` | one module per setup plus a registry; each setup turns primitives into `Candidate`s |
| `trader.py` | the one `Strategy`: setups → dedupe by priority → news blackout → ML gate → hard risk rules → bracket orders |
| `risk.py` | hard risk rules (session cap, daily stop, flat time, London minimum stop); the ML can't bypass it |
| `journal/` | storage and schema (see the journal ticket) |
| `backtest/` | runner, random-entry and rules-only baselines, statistics (DSR, PBO, bootstrap), report card |
| `ml/` | features, labels, training, model registry (champion/challenger), drift monitors |
| `review/` | Claude trade reviews and the weekly report |
| `nightly/` | the nightly job and its launchd install (see the nightly-run ticket) |
| `dashboard/` | FastAPI app plus the built React files, so the Mac needs no Node |
| `watcher/` | the monthly ICT watcher |
| `bridge/` | Phase 3 Python side of the NinjaTrader link; the C# add-on lives in `ninjatrader/` at the repo root |

**Interfaces.** The existing `BarFeed`, `Broker`, `Strategy` and `Journal` protocols stay. What changes:

- `BarFeed`: `ParquetBarFeed` serves both backtest and nightly replay; a live feed comes in Phase 3.
- `Broker`: `SimBroker` now, and a NinjaTrader broker in Phase 3 behind the same protocol.
- New `Setup` protocol: `scan(ctx) -> list[Candidate]`. A setup never places orders.
- A `Candidate` carries:
  - setup id, side, entry type and price, stop, target, time-out
  - rule results, and the feature vector frozen at placement

  The `Trader` decides what becomes an order. That makes every skip (cap, blackout, ML, London minimum stop) a journaled candidate.
- No module reads the wall clock. Time is `ctx.now` from the bar feed, so backtest and replay behave the same.

**Files on disk**

- **Committed:**
  - `config/defaults.toml`: the pre-registered setup defaults, read by the existing strict TOML loader, so there is no YAML dependency
  - `reports/weekly/`
  - `data_public/news_events.csv`: public government release times
  - `tests/fixtures/`: synthetic bars, plus the ground-truth days' real 1-minute bars and verdicts
  - `tests/frozen/expected.json`: the frozen-replay results
- **Ground-truth and frozen-replay bars are committed** as small Parquet slices so CI can run both checks. This is allowed only because the repo is private and the use is personal; remove them before the repo is ever made public.
- **Not committed, under the gitignored `data/` in the repo folder on the Mac:**
  - `bars/` (exists) and `bars_1s/`
  - `journal/`
  - `models/<model id>/`
  - `runs/<run id>/`, holding each backtest's trades, report card and charts
  - `logs/`

**Tests**

- unit tests per module
- a look-ahead test for every setup, like the existing one for primitives
- the ground-truth check against the user's marked days, both ways
- the frozen replay: a fixed four-week window whose trades must match `tests/frozen/expected.json` exactly. An intentional change updates the file in the same commit, so the diff shows what moved.

**Commands the user runs on the Mac** (all `uv run moon-ai …`, from the repo folder):

| Command | Does |
|---|---|
| `doctor` | checks Python, keys, data, disk and the nightly job, in plain language, and says what to fix |
| `download …` | exists; buys and stores bars |
| `backtest <setup>` / `backtest --all` | runs the full protocol and opens the report card in the browser |
| `review-days <setup>` | opens the ground-truth review page |
| `verify` | runs the tests plus the frozen replay on the real data |
| `dashboard` | serves the dashboard at `http://localhost:8000` |
| `train` | trains the ML filter once the data minimums are met |
| `nightly install / status / run` | defined in the nightly-run ticket |

**Dev setup on a Mac:**

```bash
uv sync
uv run moon-ai doctor
```

uv supplies Python 3.12. Keys live in `~/.config/moon-ai/.env`, as the Databento key already does.

## Stack

- **Engine:** a lean custom Python event loop on Polars + `databento`, behind `BarFeed` / `Broker` / `Journal` interfaces. When a stop and a target are both hit in the same bar, the stop is assumed to fill first unless 1-second bars resolve which came first. NautilusTrader is re-evaluated at Phase 3 ([engine-choice research](https://github.com/DaltonDom/moon-ai/blob/research/engine-choice/docs/research/engine-choice.md)).
- **ML:** gradient-boosted trees via scikit-learn's `HistGradientBoostingClassifier` (the LightGBM algorithm; chosen over the LightGBM package because its Mac wheel needs a separate libomp install), isotonic calibration; ADWIN drift detection written in `ml/promotion.py` (River has no Apple Silicon wheel for its current version).
- **Live connection:** our own NinjaTrader 8 add-on passes bars and orders between the Python engine and NinjaTrader on the Windows PC. NinjaTrader connects to the firm over the firm's own connection: CQG/Tradovate for Lucid, Rithmic for Bulenox, Tradovate for MyFundedFutures ([NinjaTrader automation research](research/ninjatrader-automation.md)).
- **Data:** Databento `GLBX.MDP3`.
- **Dashboard:** FastAPI + React.
- **Charts:** TradingView for viewing and verification.
- **Reviews:** Claude API with structured outputs, run nightly through the Batch API.
- **Alerts:** a single safety alert, live accounts only, sent when the kill switch fires or the connection is lost with a position open.
