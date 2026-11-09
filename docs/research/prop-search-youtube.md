# Prop-search 2: strategies from YouTube

Pre-registered 2026-11-09, before any result. The user asked for strategies found on YouTube.

## Sourcing

- **Search.** YouTube Data API, 8 queries on mechanical NQ/MNQ day trading and passing prop firms, videos since 2023. About 60 results.
- **Selection.** 13 full-length videos that claim backtested rules (no shorts, no mindset videos).
- **Extraction.** Gemini (`gemini-3.5-flash`) watched each video and reported only what it states ([notes](prop-search/youtube-notes/)). 11 of the 13 were read; `SrV2ALXeglM` and `Y0qANs6tdcY` failed with 503s. Captions couldn't be read directly, because YouTube blocks this server.

| Video | Gemini verdict | Used |
|---|---|---|
| The Rumers, "20 Years Backtested" (8vufTzGZqiI) | mostly mechanical | ✅ opening range reversal |
| TOS Indicators, "1,178,668 ORB trades" (MOG-DbgmzzI) | fully mechanical | ✅ 5-min ORB brackets |
| Jesse Rogers, "Works Everyday" (mzFXoK2pbNE) | mostly mechanical | ✅ 5-min ORB + FVG, 2R |
| Trader Tips, "BEST ORB" (F3dCfO6ME7M) | mostly mechanical | ❌ stop and target left to judgement |
| Trade with Pat ×2, Scarface, TMA, Lance Breitstein, Aval, JackTrades | discretionary | ❌ |

## Configurations (5 trials; DSR counts 29 with prop-search 1)

Code: `opening_range_reversal`, `orb_bracket` and `orb_fvg` in [strategies.py](../../scripts/research/strategies.py). Each docstring says which details the video left open and how they were fixed.

| Name | Rule |
|---|---|
| `yt_orr_50pct` | Opening move against the 50-day-SMA bias is at least 20% of daily ATR. A stop order one tick past the first 5-minute reversal candle enters. Stop at the low/high of day; target 50% retracement of the move. |
| `yt_orr_100pct` | Same, target 100% retracement (the video's extended target). |
| `yt_orb5_full_full` | Break of the 5-minute range; target and stop 1× range width from entry (the video's best EV). |
| `yt_orb5_half_full` | Same, target 0.5× (the video's 69% win-rate version). |
| `yt_orb5_fvg_2R` | First 1-minute close beyond the 5-minute range, then an FVG on that candle or the next two. Enter at the next open; stop at the break candle's far extreme; 2R target. |

## Fill fix made before scoring

The random-walk check found that stop entries were filled at the level plus 1 tick while their coin-flip twin traded back at the level. That handed the original the price's overshoot through the level (z up to +3.9 on noise). Stop entries now pay the repo's 3-tick stop slippage, and the twin trades at the same fill. On a path-consistent random walk, z for these 5 is now −0.8 to +1.4. The 5-minute brackets still lean slightly positive, so read their edge as possibly a little flattered.

## Bar

- **Research** (2019-06 to 2025-10): the same go-forward bar as prop-search 1 (100+ trades, edge CI excludes 0, DSR > 0.95 over 29 trials, both halves > 0, both prop pass rates above the coin flip's 95th percentile). A configuration that clears everything but DSR may still go to the holdout as a finalist, named in `finalists-youtube.json` before the look, as in prop-search 1.
- **Holdout** (2025-11 to 2026-11, one look, trial `prop-search-2`): the same four pass criteria as prop-search 1.
- **Caveat.** These exact rules never saw the holdout. But I did see related ORB variants' holdout results (prop-search 1 addendum), so a pass on the 5-minute ORB rules is a little less independent than a clean one.
