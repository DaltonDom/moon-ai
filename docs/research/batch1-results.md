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
