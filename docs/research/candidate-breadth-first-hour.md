# Candidate: breadth-confirmed first-hour momentum (MNQ)

## The rules (fixed 2026-11-02, before any look at Nov 2025 – Oct 2026)

- **Signal.** At 10:30 New York, take the move of each market from its 09:30 open to the 10:29 close: MNQ, MES, M2K and MYM. Trade only if **all four moved in the same direction**. The trade goes that way on MNQ, at the market (the 10:30 bar's open).
- **Stop:** 0.25 × the 14-day ATR of MNQ's cash session (finished days only).
- **Target:** 2R. Otherwise the trade is closed at the 15:55 bar.
- **At most one trade a day.** No trades on roll days, half days or broken sessions.
- **Account:** Tradeify Growth 50K, copy-traded on 3 accounts. Risk is **$600 per trade**, rounded down to whole micros. Our own soft daily loss cap is $1,000. Evaluation spending is at most $500 a month.

## Evidence so far (research data, MNQ to 2025-11-01)

- **Experiments (`walkforward-logs/exp1-filters.log`):** among 11 filters on the first-hour signal, breadth (all 3 other indices agree) doubled the edge per trade, from +0.112R to +0.208R, over 439 trades.
- **Grid (`exp2-breadth-grid.log`):** 36 variants. Only 10:30 with all 3 agreeing and a tight stop works. With per-quarter re-tuning of plan and risk, the business result is a spike: $1,726 a month for the chosen variant against −$164 to +$935 for its neighbours.
- **Fixed plan and risk, held all 8 quarters (`exp3-fixed-business.log` and the follow-up):** a broad plateau.
  - $300–800 a trade on Tradeify Growth with a 2R target: +$877 to +$2,308 a month, 4–6 of 8 quarters.
  - **$600 a trade: +$2,308 a month, 6 of 8 quarters.** 3 evaluations, 1 pass, 0 funded blown.
  - The two losing quarters are the start-up: the first evaluation hasn't passed yet.

## Caveats

1. **Hindsight.** The breadth filter, the plan and the risk were picked after looking at the 8 "untouched" quarters. They are no longer untouched for this rule.
2. **Optimism.** The fast simulator was about 20% optimistic against the engine on the opening-range breakout.
3. **Unconfirmed rules.** The Tradeify Growth payout rules were researched from search excerpts, and the withdrawal floor is assumed.

## The clean check (pre-registered here; one look)

- **Data:** Nov 2025 – Oct 2026 for MNQ, MES, M2K and MYM. This rule has never seen that year.
- **Passes if both hold:**
  1. Mean net R per trade is above 0 over the year.
  2. The business simulation from 2025-11-01 (3 accounts, the rules above, a fresh first evaluation) ends the year with net income above 0 after all fees.
- The $2k a month and 6-of-8 numbers are reported, but a single year includes the start-up quarters, so they don't decide.
- **If it passes:** confirm in the event engine with news blackouts, then one live Tradeify Growth evaluation.
- **If it fails:** the candidate is retired.

## Clean check result (2026-11-02): FAILED, candidate retired

This was one look, logged in the cloud session's `data/holdout_checks.jsonl` as `breadth_first_hour / candidate-v1 / MNQ.v.0`. The data for Nov 2025 – Oct 2026 (MNQ, MES, M2K, MYM; $5.98) was bought for this check.

| | Value |
|---|---|
| Trades | 107 |
| Mean net R per trade | **−0.061** (win rate 39%) |
| Business, 3 accounts, Tradeify Growth, $600 | **−$3,915** for the year (−$326 a month). 9 evaluations, 1 passed, 1 funded account blown |
| Quarters | −870, −1,305, −870, −870 |

Both pre-registered tests fail.

**Lesson:** the second strategy in a row that looked good on 2019–2025 has lost in Nov 2025 – Oct 2026. The noise breakout failed there too. Selecting on the research years, including the hindsight choices recorded above, again found patterns that didn't persist. The broad plateau over plan and risk didn't protect against this, because the plateau was across the *business layer*. The signal itself was the hindsight pick (the best of 11 filter experiments).
