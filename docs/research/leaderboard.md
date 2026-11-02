# Strategy leaderboard (untouched quarters, Nov 2023 – Oct 2025)

Every row is walk-forward:
- each quarter is traded with choices made only from the 12 months before it
- the prop business simulation runs on 3 copy-traded 50K accounts, after evaluation fees
- evaluation spending is capped at $500 a month

| Rank | Strategy | Avg/month (3 accts) | Profitable quarters | Best quarter | Notes |
|---|---|---|---|---|---|
| 1 | **Top 3 rules by Sharpe, MNQ+MES** (mostly first-hour momentum) | **+$331** | 3 of 8 | +$6,049 | `walkforward.py --top 3` |
| 2 | **First-hour momentum, fixed**: at 10:30 trade the first hour's direction if it moved > 0.25 ATR; stop 0.25 ATR; target 2R; MNQ+MES | **+$315** | 2 of 8 | +$9,783 | `--fixed "time_mom m=60 th=0.25 k=0.25 t=2.0"` |
| 3 | Top 3 within first-hour momentum only | +$106 | 2 of 8 | +$6,049 | `--family time_mom --top 3` |
| 4 | First-hour momentum, fixed, any move | +$83 | 2 of 8 | +$7,324 | |
| 5 | Top 7 across 7 markets | −$106 | 1 of 8 | +$3,745 | |
| … | 15 other settings, the ML model, 7-market per-market picks | −$20 to −$1,133 | 0–1 | | see `walkforward-2026-11-02.md` |

**Best strategy so far: first-hour momentum on MNQ and MES.** It is the most consistent pattern in every test since round 1.
- Its money comes in bursts. Aug–Oct 2024 paid +$6–10k, and most other quarters lost $400–1,200, mostly in evaluation fees.
- It doesn't yet reach $2,000 a month (about $315–330), or 6 profitable quarters out of 8.
