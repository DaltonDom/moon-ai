# Why every setup lost (first full backtest, 2026-11-01)

The first full `backtest --all` ran on 2019-06-01 to 2026-04-30 MNQ 1-minute bars, after the kill-switch and zero-ATR fixes. No setup passed.

| Setup | Trades | Edge vs random (R/trade, 95% range) | DSR | Verdict |
|---|---|---|---|---|
| NY AM Silver Bullet | 258 | +0.068 (−0.166 to +0.321) | 0.20 | retired (9 retests) |
| NY PM Silver Bullet | 289 | −0.211 (−0.512 to +0.074) | 0.00 | retired (8 retests) |
| London sweep-and-reverse | 2 | — | — | insufficient (likely broken) |
| OTE pullback | 1,169 | +0.086 (−0.024 to +0.192) | 0.00 | retired (9 retests) |
| ICT 2022 model | 59 | +0.125 (−0.577 to +0.738) | 0.31 | insufficient |

**OTE pullback**
- Average −0.225R per trade, win rate 37%.
- Average win +1.48R, average loss −1.21R.
- Net −$45,918.

**ICT 2022 model**
- Average −0.110R per trade, win rate 39%.
- Net −$3,198.

**Exits:** every trade ended at its stop or its target.

## Causes (research pass)

1. **Costs.** Stops are tight (median about 35 ticks), so a 1% risk means many contracts. Commission and slippage are charged per contract, so they take about 0.15–0.2R per trade. Getting costs under 0.1R needs a risk of about 16 points or more.
2. **Reward:risk below the win rate's break-even.**
   - OTE at 62% entry and 100% stop pays 1.63:1. Before costs that needs about 38% winners; the setup won 37%.
   - ICT's own OTE primer asks for at least 2:1 to the old high/low (`Cg0-CFJOJvg` 17:17–19:30, single pass, #28).
   - The Silver Bullet and 2022 model only require 10 points of room.
3. **No daily bias on the Silver Bullet.** ICT treats the daily bias as step one. The `trade_with_bias_only` retest was registered but never built, so it never ran.
4. **Patterns read from 1-minute bars.** The default swing is 1 bar either side, so swings are tiny and stops follow suit.
5. **Outside evidence.**
   - There is no peer-reviewed test of ICT.
   - The best-controlled public FVG study, with matched placebo zones, found no significant difference.
   - Stop-run research (Osler, NY Fed Staff Report 150) and intraday-momentum papers (Gao et al. 2018; Zarattini et al. 2024) find that taking out stops tends to continue a move, not reverse it.

## Round 2: pre-registered here, before any result

Each trial changes one parameter and counts as a trial for the DSR. They run with `moon-ai backtest --round2`. That command also runs any earlier retest that was skipped because it wasn't built yet, and never repeats a logged run.

| Setup | Trial | Change | Why |
|---|---|---|---|
| NY AM / NY PM Silver Bullet, ICT 2022 model | `min_rr_2` | `min_rr = 2.0` | ICT's minimum 2:1 |
| NY AM / NY PM Silver Bullet, ICT 2022 model | `timeframe_5m` | `timeframe = 5` | wider structure and stops; costs about halve |
| NY AM / NY PM Silver Bullet | `trade_with_bias_only` | `bias_gate = true` | already registered; now built (previous-day-range bias, as OTE) |
| OTE pullback | `min_leg_30` | `min_leg_points = 30` | skips tiny legs where costs dominate |

**Not tried, by design:**
- **Partial exits at 1R, breakeven stops, day-of-week filters and long-only.** They are fishing, or they use hindsight.
- **Fib on candle bodies and the NY killzone ending at 09:00** (from #28). These are single-pass video readings and need confirmation first.
- **Trading with the 09:30 move vs. premium/discount of the overnight range.** These conflict with each other. One is chosen before its results are seen, if round 2 fails.

**If round 2 fails,** the evidence supports concluding that these mechanical ICT reversal setups lack an edge on MNQ after costs. The next step would then be continuation-style setups, which trade with a stop-run instead of against it, rather than more rescues.
