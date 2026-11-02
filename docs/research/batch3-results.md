# Batch 3: overnight drift (results)

Run 2026-11-02 in the cloud session on MNQ, 2019-06-01 up to 2025-11-01, into `data/runs-batch3`. Pre-registered in commit 205dd62 before any run. Judged with the first test fixed there (`scripts/research/time_effect_check.py`).

| Setup / version | Trades | Mean R (95% CI) | DSR | 2× slippage | 2022 | Verdict |
|---|---|---|---|---|---|---|
| overnight_hold, default (stop 1 ATR) | 1,030 | +0.023 (−0.002 to +0.049) | 0.96 | +19.4R | −5.3R | fail |
| overnight_hold, stop 0.5 ATR | 1,495 | +0.025 (−0.014 to +0.062) | 0.86 | +24.8R | −17.9R | fail |
| overnight_after_down, default | 364 | +0.005 (−0.041 to +0.050) | 0.59 | −0.4R | −0.1R | fail |
| overnight_after_down, stop 0.5 ATR | 660 | +0.012 (−0.048 to +0.073) | 0.63 | +7.0R | −8.9R | fail |
| euro_open_drift, default | 1,507 | −0.035 (−0.063 to −0.008) | 0.01 | −79.6R | −9.4R | fail |
| euro_open_drift, after a down session | 686 | −14.1R net | — | — | — | fail |
| euro_open_drift, stop 0.5 ATR | 1,417 | −26.9R net | — | — | — | fail |

- **Overnight hold:** positive overall, but it loses in the 2022 bear year. It is mostly market beta, not an edge.
- **After a down session:** this conditioning (the NY Fed inventory effect) adds nothing on MNQ.
- **European-open drift:** the move is too small for MNQ's costs, and it loses in every year.
- **Sizing:** the default's 1-ATR stop skipped 495 nights as too wide for one contract at $500 risk. The 0.5-ATR version trades nearly every night, and its verdict is the same.

**All retired.** That makes 94 versions tested in total, with 1 research pass and 0 holdout passes.
