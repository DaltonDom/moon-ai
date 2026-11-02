# Strategy search: state and next steps (living document)

**Goal** (design.md, Revision 2026-11-02b): $2,000 a month or more in total, after evaluation fees, on at most 3 copy-traded accounts; money made in at least 6 of 8 untouched walk-forward quarters (Nov 2023 – Oct 2025); evaluation spending of $500 a month or less. Then a clean check on Nov 2025 – Oct 2026 (Mac), then one live evaluation.

**Tools**
- `scripts/research/screen.py`: fast rule simulator, calibrated to the engine.
- `scripts/research/walkforward.py`: walk-forward plus the prop business simulation. It covers MNQ, MES, M2K, MYM, MGC, MCL and M6E, and has `--fixed`, `--family`, `--sizing` and `--steady`.
- `scripts/research/ml_walkforward.py`: the ML search.

**Best so far** (`leaderboard.md`): first-hour momentum on MNQ, +$1,079 a month, 4 of 8 quarters. The bottleneck is signal strength: about +0.1R a trade, about 1 trade a day. Sizing can't fix it.

**Ruled out:**
- the ICT reversal rules
- opening breakouts
- gap and VWAP fades
- the overnight drift
- turn of the month
- the plain ML on 15 price features (AUC 0.45–0.48)
- per-market rule picking across 7 markets
- buffer-fraction, split and "steady" sizing

**Next experiments (in order)** to sharpen the first-hour signal on MNQ:
1. **Filters known at 10:30:** the first hour agreeing with the overnight or gap direction; the volatility regime; relative volume in the first hour (add volume to `screen.Market`); the first hour's range against the ATR; the day of the week. Pick in walk-forward within the family only.
2. **Trade management:** stop to breakeven after +1R; take half at 1R; a time stop. These raise the win rate and smooth equity, which suits the trailing drawdown and consistency rules.
3. **Confirmation from other indices:** trade MNQ only when MES, M2K and MYM agree on the first-hour direction (breadth).
4. **More decisions a day in the same direction:** add 11:30 and 12:30 checks as adds or re-entries.

## Update (2026-11-02, later)

- **Breadth-confirmed first-hour momentum on MNQ** cleared the bar on Nov 2023 – Oct 2025, with hindsight choices. Then it **failed the clean check** on Nov 2025 – Oct 2026: −0.061R per trade and −$326 a month. It is retired. See `candidate-breadth-first-hour.md`.
- **Two holdout-year looks are spent** (the noise breakout and the breadth candidate), and both lost. Every further look at that year is a little less clean. Paper trading, or a live evaluation, on data from Nov 2026 onward is the only fully fresh test left.
- **Next:**
  1. A regime or equity-curve filter: trade only while the signal's own trailing results are positive. Judge it walk-forward on research data first.
  2. Strategies whose rules are chosen *without* hindsight filters. In walk-forward, the filter choice must also come from each tuning window.

## Honest walk-forward of the first-hour family (2026-11-02)

**Method** (`exp_first_hour.py --honest STEADY`): every choice is made inside each 12-month tuning window, with nothing chosen by hindsight. The menu was:
- the filter: none, breadth3, breadthMES, gap agree, gap disagree, range high/low, relative volume high/low, and relative volume high with breadth3
- the target: 1.5, 2 or 3R
- the equity-curve filter, on or off
- the plan, from 4
- the risk, $200–800

**Results:**

| Steady weight | Average a month (3 accounts) | Profitable quarters |
|---|---|---|
| 0 | +$206 | 3 of 8 |
| 0.5 | −$211 | 2 of 8 |
| 1.0 | +$144 | 1 of 8 (mostly sat out) |

- The volume filters were never chosen.
- breadth3 was chosen in only 1 quarter. This confirms that the earlier breadth "winner" was a hindsight pick.
- **Conclusion:** with all choices made honestly, the first-hour family makes about $0–200 a month. It doesn't reach the bar.
