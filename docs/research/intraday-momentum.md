# Intraday momentum (noise area) on MNQ: first backtest, 2026-11-02

**Verdict: passed in-sample, failed the holdout sign-off on statistical strength while staying profitable.** It was the first strategy to clear all four in-sample checks. Its one holdout look (2026-11-03) was profitable but didn't clear the bar; see [Holdout sign-off](#holdout-sign-off-2026-11-03).

The rules were pre-registered in [`config/families/intraday_momentum.toml`](../../config/families/intraday_momentum.toml) and committed before any run. They come from Zarattini, Aziz & Barbon (2024), "Beat the Market: An Effective Intraday Momentum Strategy for S&P500 ETF (SPY)". None of them was tuned on our data. This document reports the single default run (trial 1 of 1) and some diagnostics that changed no rule.

## The rules in one paragraph

Each session gets a "noise area" around the 09:30 open: for every minute, the average absolute move from the open at that minute over the last 14 sessions. The band is anchored to the larger (upper) or smaller (lower) of today's open and yesterday's close. Every half hour from 10:00 to 15:30, on the close of the bar ending then: if flat and above the upper band, go long; if below the lower band, go short. A long exits when price closes below the larger of the upper band and the session VWAP, and a short mirrors that. Anything still open is closed at 15:55. Size targets 2% daily volatility on $50,000, capped at 4× leverage, which averaged 2.8 MNQ.

## How it was run

- `uv run python -m moon_ai.research.intraday_momentum` (code in `src/moon_ai/research/intraday_momentum.py`, tests in `tests/test_intraday_momentum.py`).
- MNQ.v.0 1-minute bars from Databento, 2019-06-03 to 2025-11-01, in-sample only. The locked holdout (2025-11-01 to 2026-11-01) is refused by `holdout.guard`.
- The engine's conventions:
  - A decision sees only closed bars, and every order is a market order filled at the next bar's open.
  - Costs are $1 commission per contract per side plus 1 tick of slippage on every fill, about $3 per contract round trip.
  - Holidays, half days, roll days and degraded days are skipped. News blackouts block new entries.
- It runs as its own backtest, not through the bracket engine, because the bracket engine has no trailing exit.

## Results (MNQ, 2019-06 to 2025-10)

| Check | Result | Bar | Pass |
|---|---|---|---|
| Trades | 1,381 | ≥ 100 | ✅ |
| Edge over random entries (gross $/trade, 95% CI) | +$44.8 (+$24.2 to +$66.2) | CI above 0 | ✅ |
| DSR, daily returns, 1 trial | 1.00 | > 0.95 | ✅ |
| Net with double slippage | +$45,655 | > 0 | ✅ |

| | |
|---|---|
| Net P&L | +$49,693 (costs $12,114) |
| Win rate | 41% (average win $349, average loss −$181) |
| Profit factor | 1.34 |
| Sharpe (annualised, daily) | 1.39 |
| Max drawdown | $4,048 |
| Longs / shorts | +$36,102 / +$13,591 |
| Exits | 894 trailing, 487 at 15:55 |

**By year** (no losing year; 2019 is about half a year and flat):

| Year | Trades | Net | Win rate | Sharpe | Max DD |
|---|---|---|---|---|---|
| 2019 | 134 | +$14 | 36% | 0.01 | $3,632 |
| 2020 | 202 | +$9,078 | 42% | 1.45 | $1,849 |
| 2021 | 208 | +$8,289 | 43% | 1.35 | $3,922 |
| 2022 | 248 | +$5,239 | 38% | 1.13 | $2,014 |
| 2023 | 212 | +$10,531 | 47% | 2.20 | $2,525 |
| 2024 | 207 | +$10,379 | 40% | 2.19 | $2,537 |
| 2025 (to Oct) | 170 | +$6,165 | 39% | 1.01 | $4,048 |

With one fixed contract the strategy nets +$20,852, with a $1,783 max drawdown and a Sharpe of 1.29.

## Diagnostics (no rule changed; not trials)

| Check | Result | What it says |
|---|---|---|
| Fills 1 minute late | Sharpe 1.13, edge CI +$17 to +$58 | The edge isn't a fill-timing artefact |
| Fills 2 minutes late | Sharpe 0.99, edge CI +$14 to +$55 | Same |
| MES (S&P, the paper's market), 2019 to 2025 | Pass: Sharpe 0.95, every year positive | Consistent with the paper |
| MYM (Dow), 2022 to 2025 | **Fail**: Sharpe −0.12 | Doesn't work on every index |
| M2K (Russell), 2022 to 2025 | **Fail**: Sharpe −0.98 | Same |

The Dow and Russell failures matter. The edge appears in the two most traded, most momentum-driven index futures, not in index futures generally. Over the same 2022–2025 window, MNQ and MES were positive every year, so the difference isn't just the shorter sample.

## Prop-firm replay (illustrative)

The firm-rules simulator from the design isn't built yet. This is a stand-in using the LucidFlex 25K rules listed in [prop-firms-and-order-routing.md](prop-firms-and-order-routing.md): $1,250 target, $1,000 end-of-day trailing max loss, no daily loss limit. Those rules come from a secondary listing and are **UNVERIFIED**. An evaluation was started on every session at a fixed number of micros. A breach is checked against each session's intraday low, taken from bar extremes.

| Micros | Pass rate | Median sessions to pass |
|---|---|---|
| 1 | 74% | 67 |
| 2 | 46% | 23 |
| 3 | 44% | 11 |
| 5 | 37% | 5 |

At 1 micro, about three in four evaluations pass, but the median pass takes about three months of monthly fees. Bigger size passes faster and fails more often. The best size needs the real rule set, including fees and the consistency rule.

## Holdout sign-off (2026-11-03)

This was the one allowed look at 2025-11-01 to 2026-11-01, with the pre-registered default unchanged. It is recorded in `data/holdout_checks.jsonl` in the data repo.

| Check | Holdout | In-sample | Bar | Pass |
|---|---|---|---|---|
| Trades | 200 | 1,381 | ≥ 100 | ✅ |
| Edge over random (gross $/trade, 95% CI) | +$22.8 (−$18.9 to +$66.5) | +$44.8 (+$24.2 to +$66.2) | CI above 0 | ❌ |
| DSR | 0.82 | 1.00 | > 0.95 | ❌ |
| Net with double slippage | +$3,562 | +$45,655 | > 0 | ✅ |

- **Overall:** net +$3,811 (Sharpe 0.91, profit factor 1.20, win rate 42%, max drawdown $4,548). With one contract it's +$3,925 (Sharpe 1.12, max drawdown $2,652).
- **Average size was lower:** 1.3 contracts, against 2.8 in-sample, because the year was more volatile.
- **Longs and shorts were both positive:** +$1,374 and +$2,437.
- **Prop replay (same UNVERIFIED 25K rules):** 45% pass at 1 micro (median 22 sessions), 40% at 2 micros, 31% at 3 micros.

**Reading.** The strategy made money on unseen data, and the edge kept its sign at about half the in-sample size. One year of about 200 trades is too little to prove that statistically: with the in-sample spread of trade results (std ≈ $400), the 95% CI on 200 trades is about ±$55. Even the full in-sample edge of $45 per trade would usually fail this check on one year. That weakness was a property of the bar, known before the look, so it doesn't change the result. By the protocol, the strategy didn't clear the holdout.

The bar must not be loosened after the fact. More evidence can only come from new data: forward paper trading, which is never seen in advance and adds to the record every day.

## Caveats

- **The holdout hasn't been looked at.** The one sign-off look is the real out-of-sample test. The user decides when to spend it.
- **It overlaps the paper's era.** The paper tested SPY from 2007 to early 2024, so our 2019–2024 sample isn't independent of what its authors saw, although MNQ wasn't their market.
- **Trailing exits are checked every 30 minutes only, as in the paper.** There is no hard intraday stop, so a fast move against the position runs until the next half hour. The intraday-low replay above includes that risk, but live trading will need a catastrophic stop. That would be a new trial.
- **The repo's per-session cap (2 trades) and 2% daily stop weren't applied.** The paper has neither. Up to 12 decisions a day can churn on choppy days. Applying the hard risk rules is also a new trial.
- **Costs are the repo's defaults.** Real fills at the 10:00 and half-hour marks should be checked in paper trading.

## Next steps

1. ~~Holdout sign-off~~: done 2026-11-03. It failed the bar while staying profitable (above).
2. Build the firm-rules replay for Lucid 50K with verified rules, and choose the size from it.
3. Paper-trade it through the nightly replay before buying an evaluation.

## Trial 2, "prop_v2": prop risk controls (2026-11-03)

Pre-registered in `config/families/intraday_momentum.toml` before it ran. The entry and exit rules are unchanged. It adds:

- a hard stop at 0.5 × the 14-day daily volatility from entry, checked on every bar, with 3 ticks of stop slippage;
- a daily stop: no new entries once the session's realised loss reaches 2 × that per-trade risk;
- a fixed size of 1 micro, scaled in the replay.

Run with `uv run python -m moon_ai.research.intraday_momentum --trial prop_v2`. It is in-sample only: the holdout was spent on the default.

| Check (1 MNQ, 2019-06 to 2025-10) | Result | Pass |
|---|---|---|
| Trades | 1,381 | ✅ |
| Edge over random (gross $/trade, 95% CI) | +$7.4 to +$26.9 | ✅ |
| DSR (2 trials counted) | 1.00 | ✅ |
| Net with double slippage | +$17,170 | ✅ |

- **Overall:** net +$18,679 per contract, Sharpe 1.16, max drawdown $1,800.
- **By year:** every full year is positive (2020–2025: +$2.7k to +$3.7k per contract).
- **Exits:** 128 trades hit the hard stop.
- **Cost of the stop:** it costs about 10% of per-contract profit against the default ($20,852). In exchange it caps any single trade's loss, which a prop account needs.

### LucidFlex 50K replay

The rules are from secondary sources and **UNVERIFIED**: $3,000 target, $2,000 end-of-day trailing max loss locking at start + $100, 40% consistency in the evaluation, minimum 2 days, no daily loss limit. An evaluation was started on every session. A pass opens a funded account, followed for 6 months. Breaches are checked against intraday lows.

| Micros | Pass rate | Median sessions to pass | Funded bust within 6 months | Funded median 6-month profit |
|---|---|---|---|---|
| 1 | 100%* | 216 (~10 months) | 0% | $1,101 |
| 2 | 66% | 108 (~5 months) | 17% | $2,915 |
| 3 | 39% | 57 | 44% | $3,675 |
| 4 | 35% | 45 | 47% | $2,106 |
| 5 | 27% | 38 | 62% | $85 |

\*At 1 micro, evaluations started late in the sample never finish and aren't counted, so the 100% is optimistic.

**Reading.** The edge is real but modest, so size is the main decision. 2 micros gives the best balance: two in three evaluations pass, in about 5 months, and most funded accounts survive. Larger sizes pass faster but bust much more often. Payouts and the 90/10 split aren't modelled.
