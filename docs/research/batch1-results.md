# Non-ICT batch 1: results (#102)

Run 2026-11-02 on the Mac on MNQ, 2019-06-01 up to 2025-11-01 (research data only), into `data/runs-batch1`. The setups and their trials were pre-registered in `config/defaults.toml` before this run (commit 81df2b0).

## Verdicts

| Setup | Verdict | Versions | Default: trades / edge vs random (95% CI) / DSR |
|---|---|---|---|
| Opening-range breakout (5 min) | retired | 5 | 1,522 / +0.085R (−0.071 to +0.254) / 0.92 |
| **Noise-area breakout** | **goes forward** | 1 | **869 / +0.121R (+0.011 to +0.222) / 0.997; +84R with double slippage** |
| Intraday momentum (last half hour) | retired | 3 | 1,502 / −0.042R / 0.00 |
| Overnight-range breakout | retired | 3 | 1,145 / +0.070R (−0.031 to +0.167) / 0.92 |
| Opening-gap fill | retired | 3 | 1,005 / +0.040R / 0.49 |

Fifteen versions ran in total. With five families and 15 versions, about 0.4 false passes are expected by chance (2.5% each). One pass is encouraging, but not proof. The lower end of its interval, +0.011R, is thin.

## Noise-area breakout by year (default, $500 risk per trade)

| Year | Trades | Win % | Avg R | Net $ | Long / short |
|---|---|---|---|---|---|
| 2019 (Jun–Dec) | 70 | 41% | −0.174 | −5,694 | 35 / 35 |
| 2020 | 134 | 50% | +0.207 | 12,601 | 69 / 65 |
| 2021 | 136 | 54% | +0.205 | 15,143 | 76 / 60 |
| 2022 | 152 | 54% | +0.183 | 19,220 | 65 / 87 |
| 2023 | 141 | 48% | +0.022 | 2,390 | 78 / 63 |
| 2024 | 135 | 51% | +0.080 | 8,355 | 69 / 66 |
| 2025 (Jan–Oct) | 101 | 50% | +0.075 | 5,531 | 52 / 49 |

- **What is good:** six of seven periods are positive. It made money in the 2022 bear market with mostly shorts, so it isn't just riding the uptrend.
- **What worries us:**
  - The edge is smaller since 2023, around +0.02 to +0.08R against about +0.2R in 2020–2022.
  - It trades about 0.55 times per trading day, below the "about one a day" aim.

## Next checks, fixed before they run (pre-registered 2026-11-02)

1. **Prop-firm replay** of the MNQ default run (`moon-ai propfirm`). The bar is the one agreed for #102: at some risk level in the LucidFlex 50K replay, under 50% of funded accounts are blown within a year, and net a month is positive.
2. **Second market (MES).** Run the same default on `MES.v.0`, 2019-06-01 to 2025-11-01, into `data/runs-mes`:
   - **Passes** if net R after costs is above 0 and the edge over random entries (point estimate) is above 0.
   - The confidence interval doesn't have to exclude zero, because this is a consistency check, not a second discovery.
   - **If it fails,** we do not spend the holdout look. The edge is treated as likely MNQ-specific luck.
3. **Sealed-year sign-off** (one look, MNQ, default, 2025-11-01 to 2026-11-01), only if checks 1 and 2 pass:
   - **Passes** if net R after costs is above 0 and the edge over random entries (point estimate) is above 0.
   - The prop-firm replay over that year is reported, but one year is too short to judge pass rates.
4. **If all pass:** 3 months of paper trading in the nightly replay, then the go-live bar in `design.md`.

## Check 1 result: prop-firm replay (2026-11-02), not passed

MNQ default run, 869 trades. At each risk per trade:

| Plan | $200 | $300 | $400 | $500 |
|---|---|---|---|---|
| LucidFlex 50K (the bar) | 36% pass, 446 days; 63% blown; +$8/mo | 62%, 267 d; 100% blown; +$52 | 39%, 108 d; 100%; +$95 | 40%, 84 d; 100%; +$185 |
| LucidPro 50K | 36%, 287 d; 18% blown; payouts $21/mo | 63%; 79% | 41%; 78% | 46%, 57 d; 76%; $183/mo |
| Tradeify Growth 50K | 36%, 287 d; 18% blown; +$8/mo | 58%; 78%; +$15 | 37%; 81%; +$31 | 45%, 55 d; 71%; +$97 |
| Tradeify Select (Flex) | 83% blown; −$22/mo | 100%; −$12 | 100%; −$124 | 100%; −$51 |
| Tradeify Select (Daily) | 18%; −$5/mo | 89%; −$18 | 100%; +$2 | 100%; +$156 |

**Verdict against the pre-registered bar:** the bar was under 50% blown within a year with positive net a month, in the LucidFlex 50K replay. **No risk level clears it.** At $200, net is positive but 63% of accounts blow. Larger risks blow every account.

Tradeify Growth at $200 technically meets both numbers, but it is not the pre-registered plan, and +$8 a month after 287 days to pass is not income.

**Why it fails:** the edge is real but small (about +0.13R per trade), and it trades about every other day. Against a $2,000 trailing drawdown:
- A size big enough to reach $3,000 in reasonable time takes drawdowns that end accounts.
- A size small enough to survive takes over a year to pass and pays almost nothing.

The prop-firm rules need a higher return per unit of risk, and steadier days.

## What next

Our version simplified the published strategy (Zarattini, Aziz & Barbon 2024) in three ways. Each likely costs return per unit of risk:

1. The paper **trails the stop** at the stricter of the noise boundary and VWAP, checked at each half hour. Ours holds a fixed stop at the anchor all day.
2. The paper **re-enters** at later checkpoints after an exit. Ours trades at most once a day.
3. The paper sizes by recent volatility. Ours uses a fixed dollar risk, which the replay then re-sizes.

A round 2 for this setup should implement the paper's own rules, not new ideas. It also needs trailing-stop support in the simulated broker. Separately, the pre-registered MES check (check 2) still runs, to tell whether the edge carries over to another market at all.

## Check 2 result: second market (MES), passed

Same default rules on `MES.v.0`, 2019-06-01 up to 2025-11-01: 866 trades, +70.7R net (+0.082R per trade), win rate 47%. The edge over random entries is +0.031R to +0.271R (95% CI), with DSR 0.97. It stays profitable with double slippage. That clears the full go-forward bar on its own, not just the consistency rule.

MNQ and MES are highly correlated, so this is strong support but not an independent discovery.

**MES prop-firm replay** (pass rate counted the old way, before the fix below). At $200 risk per trade:

| Plan | Passed | Days to pass | Blown in a year | Net a month |
|---|---|---|---|---|
| LucidFlex 50K | 44% | 176 | 67% | +$227 |
| LucidPro 50K | 44% | 161 | 7% | payouts $103/mo; fee unknown |
| Tradeify Growth 50K | 44% | 161 | 7% | +$89 |
| Tradeify Select (Daily) | 44% | 176 | 7% | +$145 |

Plans with a daily loss limit blow far fewer accounts. LucidFlex has none.

## Replay fixes (2026-11-02, after seeing the MES table)

- **Too-slow evaluations.** An evaluation not passed within 365 days now counts as failed ("too slow"). Before, such evaluations were dropped when the data ran out, which made the $100 row read "100% passed".
- **Our own daily cap.** `--daily-cap USD` applies our own soft daily loss cap inside the firm's limit. The guardrail was agreed in design.md before any results; only its value is set here.

## Check 1b, pre-registered 2026-11-02 before running

- **Account:** MNQ and MES default runs replayed together as one account (`propfirm --combine`), with our daily cap at $1,000 (half the $2,000 drawdown).
- **Bar:** unchanged and still on LucidFlex 50K. At some risk level, under 50% of funded accounts blown within a year and positive net a month. The other plans are reported but don't decide.
- **If it passes:** the holdout look is the noise breakout default on MNQ and on MES, one run each, logged per market. Both must clear the check-3 rule.
- **If it fails:** no holdout look. Next is round 2 with the paper's full rules (trailing stop, re-entry).

## Check 1b result: combined MNQ + MES, our $1,000 daily cap, passed (narrowly)

1,735 trades. LucidFlex 50K (the bar):

| Risk per trade | Passed (within a year) | Days to pass | Payouts a month | Blown in a year | Fees per pass | Net a month |
|---|---|---|---|---|---|---|
| **$100** | 18% | 235 | $92 | **27%** | $725 | **+$75** |
| $200 | 38% | 126 | $524 | 93% | $344 | +$448 |
| $300 | 37% | 92 | $503 | 100% | $349 | +$317 |
| $400 | 29% | 58 | $1,131 | 100% | $442 | +$931 |
| $500 | 22% | 43 | $1,299 | 100% | $590 | +$914 |

**Verdict: the pre-registered bar is met at $100,** with 27% blown and +$75 a month. The money is thin, though:
- only 18% of evaluations pass, and they take about 8 months
- each funded account costs about $725 in fees
- each funded account then nets about $75 a month

Larger sizes earn more after fees but blow nearly every account. That's a "buy evaluations, take payouts, blow, repeat" pattern. It is outside the bar and is fragile: the result is sensitive to unverified rules, to the edge persisting, and to firms' tolerance. It isn't the plan.

The other plans with our cap at $200: LucidPro blows 51%, Tradeify Growth 54% (+$221 a month), and Select Daily 59% (+$351 a month).

**What happens next, as pre-registered:** the holdout look, one run each on MNQ and MES. Separately, round 2 (the paper's trailing stop and re-entry) aims to make the economics worth it.

## Check 3 result: the holdout (2025-11-01 to 2026-11-01), failed

These were one-time looks, logged in `data/holdout_checks.jsonl` on the Mac. The rule set in advance was net R above 0 and an edge over random above 0, on both markets.

| Market | Trades | Win % | Net | Avg per trade | Edge vs random (95% CI) | DSR |
|---|---|---|---|---|---|---|
| MNQ | 107 | 41% | −11.3R (−$3,726) | −0.106R | −0.307 to +0.143R | 0.13 |
| MES | 132 | 39% | −14.2R (−$6,102) | −0.108R | −0.298 to +0.200R | 0.14 |

The combined LucidFlex replay over the year (for information only): no evaluation passes at any risk level.

**Verdict: the noise-area breakout (default) fails the holdout.** It does not go to paper trading. The edge that showed in 2020–2022 had been shrinking since 2023 (+0.02 to +0.08R per trade), and in the sealed year it turned negative on both markets. This is what the holdout is for. At 1% risk, trading it live over the last year would have lost about $10,000 across the two markets.

**Effect on later work:** we have now seen how this family did in the holdout year. Any later noise-breakout variant (the round 2 planned above) can still take its one logged look. That look is no longer a fully clean test for this family, though, so for it **3 months of paper trading on new data is the deciding test.**
