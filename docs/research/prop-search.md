# Prop-search 1: non-ICT intraday families, scored by prop-firm survival

Run 2026-11-09. Question: is there a day-trading strategy for CME micro futures that is profitable after costs, beats a coin flip, and passes a prop-firm evaluation over the past 12 months?

**Answer: not one we found.** The best candidate from 24 configurations looked real on 2019–2025, then came out no better than a coin flip on the locked 12-month holdout. It does not go forward.

## Method

- **Data.** MNQ 1-minute bars (Databento, from `moon-ai-data`), RTH 09:30–16:00 ET. Research ran on 2019-06-01 to 2025-11-01 (1,594 clean days). The holdout, 2025-11-01 to 2026-11-01 (246 days), was loaded once, after the finalist and its pass criteria were committed (`bb9aca5`, [finalists.json](prop-search/finalists.json)).
- **Costs.** The repo's cost model: $1 per side commission, 1 tick of slippage on entries and time exits, 3 ticks on stops, stop-first when a bar holds both stop and target. The double-slippage stress test was also run.
- **Grid** ([strategies.py](../../scripts/research/strategies.py)): 24 configurations, each counted as a trial. Opening-range candle (Zarattini & Aziz 2023), opening-range breakout, noise-area momentum (Zarattini, Aziz & Barbon 2024), last-half-hour momentum (Gao et al. 2018), gap fade, VWAP reversion and overnight-range breakout.
- **Coin flip.** Each trade has a twin that enters at the same minute on the other side, with the stop and target mirrored. The strategy has to beat its twin, which measures direction skill and nothing else.
- **Prop simulator** ([prop.py](../../src/moon_ai/research/prop.py), tested). A fresh evaluation starts on every trading day. The rules are an EOD trailing max loss, checked against each trade's worst open loss, plus the profit target, the daily loss limit and the consistency rule. Accounts: Topstep 50K ($3,000 target, $2,000 trailing, $1,000 DLL, 50% consistency, $400 risk per trade) and LucidFlex 25K ($1,250, $1,000, $200 risk). A coin flip also passes some evaluations, so the strategy has to beat the random-side pass rate, not zero.
- **Harness check.** On a synthetic random walk, every family shows no edge over its twin (|z| ≤ 2.0; [null_check.py](../../scripts/research/null_check.py)).

## Research window (2019-06 to 2025-10)

No configuration cleared the full go-forward bar: **DSR > 0.95 failed for all 24.** Fades lost (VWAP reversion and gap fade had zero or negative edge). Momentum and breakout families showed a small edge, consistent with the stop-run continuation literature in [why-losing.md](why-losing.md).

The best was **`orb_break_m30_opp`**, which cleared every check except DSR (0.19):

| | Value |
|---|---|
| Trades | 1,539 |
| Mean R, net | +0.078 |
| Edge over coin flip (95% CI) | +0.066R (+0.012 to +0.121) |
| Halves | +0.036 / +0.119 |
| Long / short mean R | +0.063 / +0.097 (so not bull-market drift) |
| Topstep 50K pass rate (coin mean / p95) | 37% (24% / 34%) |
| Double slippage mean R | +0.069 |

Warning signs found before the holdout look: the same rules lost on MES, MYM and M2K, so the effect was MNQ-only.

Full rows: [research.MNQ.json](prop-search/research.MNQ.json).

## Holdout (2025-11-01 to 2026-11-01), one look

| Pre-registered criterion | Result | |
|---|---|---|
| Mean R > 0 | −0.033 (239 trades) | ❌ |
| Edge over coin flip > 0 | −0.005R (CI −0.124 to +0.114); coin p = 0.56 | ❌ |
| Topstep 50K pass rate > coin mean | 1.6% vs 12.2% (198 of 246 starts failed) | ❌ |
| LucidFlex 25K pass rate > coin mean | 37% vs 5%, **but an artifact** (below) | — |
| Mean R > 0, double slippage | −0.037 | ❌ |

**Verdict: fail.** The first half of the holdout was positive (+0.077R) and the second half negative (−0.142R).

**LucidFlex artifact.** MNQ near its 2026 levels makes the 30-minute range worth a median $361 of risk per contract, so $200 risk sized only 11 of 239 trades. Its "passes" are a handful of trades and say nothing about the strategy. A fixed-dollar risk below the stop's cost per contract silently stops trading. Any later run should report trades taken per account.

The look is logged in [holdout_checks.jsonl](prop-search/holdout_checks.jsonl) as `orb_break_m30_opp` / `prop-search-1`. Copy that line into `data/holdout_checks.jsonl` on the Mac so the one-look rule holds there too.

## What this means

- Together with rounds 1 and 2, 83 versions have now been tried on MNQ and none survives. A few hundredths of an R per trade, which is what the best in-sample families show, is too small for 12 months (~240 trades) to tell from noise. It also didn't hold up out of sample.
- Passing a prop evaluation is not evidence of an edge. A coin flip with the same stops passes Topstep 50K in 12–24% of starts, because a $3,000 target against a $2,000 trailing loss is close to a fair bet. Anyone quoting a backtest "pass" without that baseline is reporting luck.
- Per design.md, "nothing passed" is a valid answer and the bar is not lowered. The bot should not trade any of these.
