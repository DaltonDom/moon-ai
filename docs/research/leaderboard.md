# Strategy leaderboard (untouched quarters, Nov 2023 – Oct 2025)

Every row is walk-forward:
- each quarter is traded with choices made only from the 12 months before it
- the prop business simulation runs on 3 copy-traded 50K accounts, after evaluation fees
- evaluation spending is capped at $500 a month

| Rank | Strategy | Avg/month (3 accts) | Profitable quarters | Best quarter | Notes |
|---|---|---|---|---|---|
| **★** | **Breadth-confirmed first-hour momentum, MNQ** (all four index micros agree at 10:30), Tradeify Growth, $600 per trade fixed | **+$2,308** | **6 of 8** | +$16,200 | meets the bar on these quarters, with hindsight caveats. See `candidate-breadth-first-hour.md`. The clean check is pending. |
| **1** | **First-hour momentum on MNQ only**: at 10:30 trade the first hour's direction; stop 0.25 ATR; target 2R; risk up to $1,000 tuned per quarter; our $1,000 daily cap | **+$1,079** | 4 of 8 | +$13,691 | `--markets MNQ --fixed "time_mom m=60 th=0.0 k=0.25 t=2.0" --daily-cap 1000` |
| 2 | Same, no daily cap | +$914 | 4 of 8 | +$13,691 | |
| 3 | Same rule, no target (held to 15:55) | +$813 | 2 of 8 | +$21,165 | |
| 4 | **Top 3 rules by Sharpe, MNQ+MES** (mostly first-hour momentum) | **+$331** | 3 of 8 | +$6,049 | `walkforward.py --top 3` |
| 5 | **First-hour momentum, fixed**: at 10:30 trade the first hour's direction if it moved > 0.25 ATR; stop 0.25 ATR; target 2R; MNQ+MES | **+$315** | 2 of 8 | +$9,783 | `--fixed "time_mom m=60 th=0.25 k=0.25 t=2.0"` |
| 3 | Top 3 within first-hour momentum only | +$106 | 2 of 8 | +$6,049 | `--family time_mom --top 3` |
| 4 | First-hour momentum, fixed, any move | +$83 | 2 of 8 | +$7,324 | |
| 5 | Top 7 across 7 markets | −$106 | 1 of 8 | +$3,745 | |
| … | 15 other settings, the ML model, 7-market per-market picks | −$20 to −$1,133 | 0–1 | | see `walkforward-2026-11-02.md` |

**Best strategy so far: first-hour momentum on MNQ.** MES dilutes it.

- **Signal consistency:** the raw signal (stop 0.25 ATR, target 2R) made money in 23 of 27 quarters on MNQ from 2019 to 2025.
- **Selection:** on data from before Nov 2023 alone, the 10:30 family takes 7 of the top 10 screen ranks, and this version ranks 8th. Choosing it is a mild hindsight pick. The newest year (Nov 2025 – Oct 2026, on the Mac) is the clean check.
- **Sizing:** sizing variations didn't beat a fixed risk tuned each quarter. They covered fractions of the drawdown buffer, separate evaluation and funded sizes, and tuning for steady months. Logs are in `walkforward-logs/{g,h,i,j}-*.log`.

Previous ranking: It is the most consistent pattern in every test since round 1.
- Its money comes in bursts. Aug–Oct 2024 paid +$6–10k, and most other quarters lost $400–1,200, mostly in evaluation fees.
- It doesn't yet reach $2,000 a month (about $315–330), or 6 profitable quarters out of 8.
