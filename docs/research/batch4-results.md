# Batch 4: momentum portfolio (results)

Run 2026-11-02 in the cloud session, 2019-06-01 up to 2025-11-01. The four existing defaults were run on MNQ and MES (`data/runs-portfolio-*`) and judged by `scripts/research/portfolio_check.py`, counting 94 versions. Pre-registered in commit 82fdcf5.

| Member | MNQ | MES |
|---|---|---|
| noise_breakout | 869 trades, +92.7R | 866 trades, +70.7R |
| orb_5m | 1,522 trades, +124.4R | 1,381 trades, **−218.9R** (19% wins) |
| overnight_breakout | 1,145 trades, +63.0R | 1,007 trades, +20.6R |
| vwap_pullback | 437 trades, +29.9R | 365 trades, **−44.8R** |

**Pooled:** 7,592 trades, +0.018R per trade (CI −0.049 to +0.084), daily Sharpe 0.21 a year, DSR 0.000 counting 94 versions, −161.7R with double slippage. It made money in 2022 (+142R) but lost in 2020, 2023 and 2024. **Fails.**

**What this teaches:**
- **The opening-range breakout and VWAP pullback don't carry over to MES.** On MES the 5-minute opening range is only a few points, so costs swamp a stop that tight. The MNQ results for both are best read as instrument-specific luck or a cost artefact.
- **Only the noise breakout and the overnight breakout are positive on both markets.** The noise breakout already failed the holdout.
- **Pooling weak edges doesn't help when some of them aren't real.** Diversification only multiplies an edge that exists.
