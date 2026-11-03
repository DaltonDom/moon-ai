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

