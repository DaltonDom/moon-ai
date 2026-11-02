# Non-ICT batch 2: results

Run 2026-11-02 in the cloud session on MNQ, 2019-06-01 up to 2025-11-01, into `data/runs-batch2`. The setups were pre-registered in commit b88feab before the run.

| Setup | Verdict | Versions | Default: trades / edge vs random (95% CI) / DSR |
|---|---|---|---|
| Opening-range breakout, volatile markets only | retired | 2 | 718 / +0.077R (−0.162 to +0.306) / 0.83 |
| Trend-day pullback to VWAP | retired | 3 | 437 / +0.100R (−0.047 to +0.266) / 0.89 |
| VWAP reversion, quiet markets only | retired | 3 | 434 / −0.070R (−0.177 to +0.031) / 0.01 |
| Turn of the month | retired | 2 | 270 / +0.048R (−0.136 to +0.237) / 0.83 |

None passed.
- The volatility filter didn't help the opening-range breakout: +0.077R here against +0.085R unfiltered.
- The VWAP pullback had the best point estimate, but its interval is wide with only 437 trades.
- Reversion lost money, which is consistent with batch 1's gap fill. On MNQ, fading moves hasn't worked.

## Running tally (2026-11-02)

| Group | Versions tested | Passed research | Passed holdout |
|---|---|---|---|
| ICT setups, rounds 1–2 | 59 | 0 | — |
| Non-ICT batch 1 | 15 | 1 (noise breakout) | 0 |
| Noise breakout round 2 (plus one run by mistake) | 3 | 0 | — |
| Non-ICT batch 2 | 10 | 0 | — |
| **Total** | **87** | **1** | **0** |

The research section counts 59 ICT versions as 64 in places, because it counted the five defaults twice. 59 is the trial count in `verdicts.json`.
