# Strategy search (started 2026-11-03)

Agreed with the user in a grilling session on 2026-11-03. Every earlier strategy
idea is dropped; the anti-self-deception rules stay. The search does not stop
until a candidate clears the whole bar below, holdout included.

## The bar

Measured only on data the candidate was never tuned on (walk-forward folds), then
once on the locked holdout (2025-11-01 to 2026-11-01).

- **Eval:** >= 75% of simulated LucidFlex 50K evaluations, one started on every
  trading day, pass within 1 month (21 trading days).
- **Funded:** >= 60% of full runs pass the eval *and then* withdraw >= $1,000 net
  (after the 90/10 split) in each of the first six 21-trading-day months without
  losing the account.
- No single trade risks more than about 15% of the drawdown allowance.
- Holds in every year separately, and with 2x slippage.
- Intraday only (flat before Lucid's 4:45 PM ET auto-close); micros or minis.

## Rules simulated

See the docstring of `src/moon_ai/lab/propfirm.py`. Lucid's help pages
(support.lucidtrading.com, intercom.help) are blocked from the research
container, so rules come from secondary sources (2026-07 to 2026-11); where they
disagree the stricter number is used:

- Eval: $3,000 target, $2,000 EOD trailing MLL locking at the start balance,
  50% consistency rule, no daily loss limit, >= 2 days, 40 micros max.
- Funded: $2,000 EOD trailing MLL (some sources say $2,500), no consistency, no
  daily limit, assumed 20-micro cap until +$2,000, payout after 5 days of
  >= $150 profit, 50% of profit, $500 min, $2,000 cap, 90% split.

## Costs

$1.00 per contract per side, slippage 1 tick on market entries, 3 ticks on stop
exits, 1 tick on time exits; limits fill only on a trade-through (design.md,
"Backtest realism").

## What the bar needs (synthetic calibration)

With normally distributed daily P&L, the bar needs a **daily Sharpe of about
0.4-0.5** (annualised about 6-8). Daily Sharpe 0.2 passes the eval about 40% of
the time and almost never survives six funded months at $1k/month. A single
intraday edge on one index rarely has that, so the search builds diversified
portfolios of many independent edges across instruments.

## Log

### Trial 1 - single classic rules (exploration, full research period)

ORB (5/15/30/60-min), overnight/session drifts on MNQ and MES. Best daily Sharpe
about 0.05 (MNQ 60-min ORB); MES lower. Far below the ~0.4 needed. Not pursued
alone.

### Trial 2 - walk-forward ML, MNQ, 15-min decisions, 30-min horizon

LightGBM on cross-asset return/VWAP/range features, trained only on prior years.
Out-of-sample IC 0.006-0.059 per year; net of costs daily Sharpe -0.03 to +0.10.
Costs (~1.1 bp a trade on micros) eat most of the edge.

### Trial 3 - walk-forward portfolio of 5,572 rule streams

Six families (window momentum/reversal, ORB, gap, VWAP distance, calendar,
previous-day levels) x params x 7 micros (MNQ, MES 2019+; MYM, M2K, MGC, MCL,
M6E 2022+). Each year picks streams by in-sample t-stat and weights them equally
by risk. Out-of-sample daily Sharpe 2021-2025: **-0.04 to +0.01** across six
selection settings. In-sample winners do not persist. Dead.

### Trial 4 - hedged NQ/ES intraday spread reversion

Fade the MNQ-vs-beta*MES spread (since the open) when it is 1-3 sigma wide,
hold 15-60 min. **Before costs** daily Sharpe 0.00-0.03; after two legs of costs
-0.3 to -1.2. Dead.

### Trial 5 - walk-forward ML on all 7 micros, 10-min decisions, 10/30/60-min horizons

Out-of-sample IC is about 0 on MES, MYM, M2K, MGC, MCL and M6E (often
negative) and 0.00-0.04 on MNQ. Net daily Sharpe: MNQ -0.02 to +0.02, all others
negative (-0.03 to -0.39). Dead.

### Trial 6 - whole-session direction at the open (LightGBM and logistic)

Overnight, European-session and 1-20 day returns of MNQ and MES, volatility
regime, weekday. A first run showed a daily Sharpe of 0.95: that was a
look-ahead bug (the "past k-day return" included today's close), caught and
fixed. Honest out-of-sample: RTH 0.03-0.04, AM 0.02-0.03, PM 0.01-0.02. Dead.

### Trial 7 - best streams through the Lucid 50K simulator (2021-2025)

| Stream | OOS daily Sharpe | Best eval pass rate (any risk level) | Full bar |
|---|---:|---:|---:|
| MNQ 60-min ORB, 2R target | 0.07 | 19.6% (bust 31%) | 0% |
| ML MNQ 30-min | 0.02 | 9.6% (bust 48%) | 0% |

Bar: 75% pass, 60% full.

## Where this stands (after 7 trials)

The bar implies a strategy with a daily Sharpe of roughly 0.3 for the
evaluation alone and 0.4-0.5 for the funded months (annualised 5-8). This is not
just a property of normal returns. By optional stopping, a 75% pass rate with a
$3,000 target and a $2,000 loss limit needs an *expected* gain of about $1,750
over the evaluation while the account's swings stay well inside $2,000. That is
roughly 0.9 Sharpe over 15-20 days, whatever the shape of the trade distribution.
A zero-edge strategy tops out near 40% pass, however it is sized.

Everything tested on 1-minute OHLCV from the 7 CME micros at realistic costs
lands at 0.00-0.07 out of sample: 5-10x short. Ideas that look better in-sample
do not survive walk-forward selection (Trial 3).
