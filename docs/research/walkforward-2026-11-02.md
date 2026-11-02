# Walk-forward search 1 (2026-11-02)

`scripts/research/walkforward.py`, as agreed in design.md (Revision 2026-11-02b):
- tune on 12 months, then trade the next 3 untouched, rolling over Nov 2022 – Oct 2025
- 8 untouched quarters, Nov 2023 – Oct 2025
- 344 candidates: the 172 screen-1 rule variants, each on MNQ and MES
- in each tuning year, choose the variants, the prop plan (LucidFlex 50K, Tradeify Growth, Select Flex or Select Daily 50K) and the risk per trade ($100–500)
- a continuous business simulation (buy an evaluation, pass or blow, funded payouts, replace) across the untouched quarters, times 3 copy-traded accounts

The bar for a winner: average total of $2,000 a month or more after fees, money made in at least 6 of 8 quarters, and evaluation spending of $500 a month or less.

## Every search setting tried (all on the same 8 quarters)

| Setting | Average total a month | Quarters with money made | Most eval spending in a month | Verdict |
|---|---|---|---|---|
| top 3 by Sharpe | **+$375** | 3 | $870 | no |
| top 1 by Sharpe | −$171 | 0 | $870 | no |
| top 6 by Sharpe | −$1,133 | 0 | $3,960 | no |
| top 3, our $1,000 daily cap | +$331 | 3 | $870 | no |
| top 6, $1,000 cap | −$327 | 1 | $1,980 | no |
| top 10, $1,000 cap | −$354 | 1 | $2,175 | no |
| top 1 by tuning-year business income | −$185 | 1 | $990 | no |
| top 3 by business income | −$386 | 1 | $2,475 | no |
| top 3 by business income, $1,000 cap | −$654 | 0 | $2,475 | no |

## Reading

- **The tuning years always look good, and the untouched quarters don't.** Choosing by tuning-year income showed $500–1,400 a month per account in-sample, then lost money out of sample. These rule families' apparent edges are mostly fitted noise.
- **The best setting earned +$375 a month,** about +$9,000 over 24 months on 3 accounts. Nearby settings are negative, so even that is likely luck in which rules got picked.
- **The months that worked** (Sep–Dec 2024, Sep 2025) paid $2–4k. The goal is reachable in good stretches, but no setting got there reliably.
- **Note:** trying 9 search settings on the same quarters is itself tuning, so the best one is optimistic.

**Conclusion:** none of the simple time-of-day, breakout, gap or range rules reaches the goal under honest walk-forward testing on MNQ and MES.

## Fix: the evaluation budget is enforced (2026-11-02)

The business simulation no longer buys an evaluation that would take the month's spending over $500 across the 3 accounts. It waits for the next month instead. The best setting from search 1 (top 3 by Sharpe) re-run with the fix: **+$331 a month**, 3 of 8 quarters, at most $495 in a month. **Not a winner.**

## Machine learning (`scripts/research/ml_walkforward.py`)

A gradient-boosted classifier predicts, at six decision times, whether price will be higher at 15:55. Its features are known at the decision time:
- the move since the open
- 15- and 30-minute momentum
- the range so far, and price's position in it
- the gap and the previous day's move
- the overnight range and the open's place in it
- the volatility regime
- the day of the week and the time
- the other market's move

Inside each tuning year it trains on 9 months and picks the confidence threshold, stop, plan and risk on the last 3.

**Result:** in 6 of 8 quarters nothing made money in validation, so it sat out. It lost in the 2 quarters it traded, averaging −$151 a month. Accuracy on untouched quarters (AUC) was **0.479 on MNQ and 0.449 on MES, no better than a coin flip (0.5)**. These features don't predict the rest of the day.

## Seven markets (MNQ, MES, M2K, MYM, MGC, MCL, M6E; 2022-05 to 2025-10, data $21.52)

There are 1,204 candidates (172 variants × 7 markets). The budget is enforced.

| Setting | Average total a month | Quarters with money made |
|---|---|---|
| best 1 per market | −$399 | 0 |
| best 1 per market, $1,000 cap | −$329 | 0 |
| best 2 per market | −$403 | 0 |
| global top 3 | −$258 | 0 |
| global top 7 | −$106 | 1 |

**Reading:** spreading over more markets didn't help. Choosing per market by a training year's Sharpe picks noise in each of them.

## Where the search stands

These approaches don't reach $2,000 a month under honest walk-forward testing:
- about 270 rule variants
- 14 walk-forward search settings
- a machine-learning model
- 7 markets

The best outcome is about +$330 a month over 2 years on 3 accounts, from one setting among many tried, so it is likely optimistic.
