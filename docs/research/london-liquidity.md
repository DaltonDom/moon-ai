# Is the London session liquid enough on MNQ?

Status: research note for [issue #19](https://github.com/DaltonDom/moon-ai/issues/19) (child of map #1). Written 2026-10-31.
Related: [design.md](../design.md) (setup list, hard risk rules), `src/moon_ai/config.py` (`BrokerConfig`, killzone windows), [databento-data-plan.md](https://github.com/DaltonDom/moon-ai/blob/research/databento-data-plan/docs/research/databento-data-plan.md) (schemas, prices, roll handling).
Scripts and raw output: [`london-liquidity/`](london-liquidity/). Data bought for this note: **$4.47** of the $5.00 cap (§6).

## 1. Short answer

| Question | Answer |
|---|---|
| Keep London sweep-and-reverse? | **Keep, with caveats.** MNQ in 02:00–05:00 ET is thin by NY standards (about 1/10 the volume and 1/8 the trades, and a 2-tick spread 97% of the time), but it still trades about 900 contracts and 480 prints a minute and always shows a few lots at the touch. In ticks, the round trip costs about the same as in NY AM. The problem is that London ranges and stops are about 2.5× smaller, so the same cost is a larger share of R. |
| Caveats | (1) Use London-specific slippage in backtests (below), not the global 1-tick placeholder. (2) Add a **minimum stop of about 40 ticks (10 points)** for London. At the 24-tick median stop of a bare 1-bar sweep, costs eat 27% of R. At the ~89-tick median stop of an MSS-confirmed entry, they eat ~7%. (3) London's small stops mean 1% risk buys **10–20+ lots**, and depth-walking then adds about +1 tick. (4) Prefer limit entries (FVG edge) in London, because the market-order entry pays a 2-tick spread. (5) The design's "beat the random-entry baseline after costs" gate decides it. This note only says the costs leave room. |
| Slippage for London backtests | **Entry (market): 2 ticks. Stop exit: 2 ticks.** For more than 10 lots: entry 3, stop 3. |
| Slippage for NY AM backtests (comparison) | **Entry (market): 1 tick. Stop exit: 3 ticks.** The NY stop number rests on only 56 events from 2 days, and it has a fat tail (p90 is 10 ticks). |
| Round-trip cost (1 lot, stopped out, $0.62/side commission) | London **6.5 ticks** ($3.24). NY AM **6.5 ticks**. That is **7% of a typical London MSS stop vs 3% in NY AM**, and 4% vs 1.6% of the median 15-minute range. |

Ticks are MNQ ticks: 0.25 index points = $0.50 per contract ([CME MNQ contract specs](https://www.cmegroup.com/markets/equities/nasdaq/micro-e-mini-nasdaq-100.contractSpecs.html), matching `InstrumentSpec(tick_size=0.25, point_value=2.0)` in config.py). MNQ traded around 27,500–30,000 in the sample, so 1 tick is about 0.09 bp.

---

## 2. Method

### 2.1 Data (Databento GLBX.MDP3, `MNQ.v.0`, `stype_in="continuous"`)

| Purpose | Schema | Sample |
|---|---|---|
| Ranges, volume/min, stop-size proxies | `ohlcv-1m` | 2026-05-01 → 2026-10-30, all hours (131 weekdays per window) |
| Time-weighted spread and touch size | `bbo-1s` | 10 days (Oct 16, 19–23, 26–29), London 02:00–05:00 and NY 09:30–11:00 only |
| Trade counts, spread at trade time, stop-election slippage | `tbbo` | London: the same 10 days. NY AM 09:30–11:00: Oct 27 and 28 only (NY tbbo costs ~5× more per day) |
| Depth (10 levels), market-order walk | `mbp-10` | 2026-10-28, London 03:00–03:15 and NY 10:00–10:05 |

- Every window was requested on its own, with ET wall-clock times converted to UTC through `zoneinfo` (`windows.py`). The whole tick sample is in EDT (UTC−4). US DST ends 2026-11-01.
- **Schema semantics:**
  - `bbo-1s` gives "the last best bid, best offer, and sale at 1-second intervals". Its `ts_recv` is the interval end, and an interval with no update is skipped ([Databento: BBO on interval](https://databento.com/docs/schemas-and-data-formats/bbo)). That makes it a time-weighted view of the touch: 107,889 of 108,000 London seconds had a record.
  - `tbbo` gives "every trade event alongside the BBO immediately before the effect of each trade" ([Databento: TBBO](https://databento.com/docs/schemas-and-data-formats/tbbo)).
  - `mbp-10` gives the top ten price levels after every book event ([Databento: MBP-10](https://databento.com/docs/schemas-and-data-formats/mbp-10)).
  - OHLCV `ts_event` is the bar open (see the data-plan note).
- **Rolls:** `.v.0` switched contracts at the 18:00 ET session open on 2026-06-16 (M6→U6) and 2026-09-16 (U6→Z6). No window spans a switch. The script still drops any window, or any setup's reference range, that mixes `instrument_id`s. The tick sample (mid/late October) is clear of the September and December roll weeks.
- **`mbp-1` vs `tbbo`:** `get_cost` priced `mbp-1` at $0.23 for one London window and $0.97 for one NY window, against `tbbo` at $0.14 and $0.68. That's too much for 10 days. `bbo-1s` gives the time-weighted touch for about $0.02 per day for both windows, so I used that, plus `tbbo` where trade-level detail was needed.

### 2.2 Measurements

- **Ranges.** `1m range` = high − low of each 1-minute bar. `15m range` = high − low over clock-aligned quarter hours (02:00, 02:15, …; 09:30, 09:45, …). `Window range` = high − low of the whole window that day. All are in ticks.
- **Stop-size proxies** (`analyze.py: _scan`). These come from 1-minute bars over 131 days, using config defaults (sweep = ≥1 tick beyond the level, close back inside within 1 bar, fractal swing N=1, MSS by close within 30 bars).
  - **London:** the first sweep in 02:00–05:00 of the Asian range (20:00–00:00 ET high/low).
  - **NY AM, for comparison:** the first sweep in 09:30–11:00 of the London range.
  - **Silver Bullet:** the first sweep in 10:00–11:00 of the 09:30–10:00 range.
  - **Stop A:** enter at the close of the close-back bar, stop 1 tick beyond the sweep extreme.
  - **Stop B:** enter on the first close beyond the last fractal swing on the other side (the MSS), stop 1 tick beyond the sweep extreme. The setup is void if the extreme is exceeded first.
  - **Generic:** every 1-minute bar that takes out the prior 15-bar high/low by ≥1 tick and closes back inside. Entry at its close, stop 1 tick beyond its extreme. This is level-free and gives many samples per window.
- **Entry slippage (market order at a bar close).** The touch from `bbo-1s` at each minute boundary is compared with that bar's close and the next bar's open (what a bar backtest fills at). Pooled over buys and sells, the mean is the half-spread. The depth walk for N lots comes from `mbp-10` (each second's last book, walking real levels).
- **Stop-exit slippage** (`analyze.py: tbbo_stats`). The event is the first trade in a minute at or beyond the prior-15-bar extreme + 1 tick (= S). That is where a sweep-and-reverse stop sits: just past a fresh local extreme. The fill is modelled as a stop elected by that trade and filled against the book **after the triggering matching event is finished**: the BBO of the first `tbbo` record with a later `ts_event`. Size beyond that touch is assumed to cost 1 more tick per touch-size. Slippage = fill − S, in ticks, signed so that positive is worse. "Triggering order runs past S" = how many ticks the electing aggressor itself swept through.
- **Commission:** `BrokerConfig.commission_per_contract` = $0.62/side (placeholder, ticket #8), so 2.48 ticks per round trip.

---

## 3. Measurements

### 3.1 Liquidity per window

| | London 02:00–05:00 | NY AM 09:30–11:00 | Silver Bullet 10:00–11:00 |
|---|---:|---:|---:|
| Spread, ticks p50 / p75 / p90 / p99 (bbo-1s, time-weighted) | **2 / 3 / 3 / 3** | 2 / 2 / 2 / 3 | 2 / 2 / 2 / 3 |
| Mean spread, ticks | **2.28** | 1.82 | 1.74 |
| % of time spread > 1 tick | **97.0%** | 76.5% | 72.9% |
| Spread before trades, p50 / p90 (tbbo) | 2 / 3 | 1 / 2 | 1 / 2 |
| % of trades with spread > 1 tick | 72.7% | 43.3% | 39.1% |
| Touch size bid / ask, median (p10) | 4 (1) / 4 (1) | 4 (1) / 4 (1) | 4 (1) / 4 (1) |
| % of time touch shows < 2 / 3 / 4 / 5 lots | 15 / 29 / 45 / 61 | 18 / 34 / 49 / 63 | 15 / 29 / 43 / 57 |
| Cum. size within 1 / 3 / 5 levels, median per side (mbp-10, 1 day) | 4 / 21 / 39 | 5 / 28 / 57 | (NY row) |
| Volume/min, median (p25–p75), 6 months | **635** (412–956) | 7,576 (5,188–10,536) | 6,605 (4,660–8,898) |
| Contracts/min, mean (tbbo sample) | 940 | 7,615 | 6,206 |
| Trades/min, mean (tbbo sample) | **482** | 4,023 | 3,178 |
| Median trade size | 1 | 1 | 1 |
| 1-minute bars present | 100% | 100% | 100% |

- The surprise is the touch. At MNQ ≈ 30,000, a 0.25 tick is so fine that **the market is 2 ticks wide most of the time even in NY AM**. The difference is that NY trades happen mostly when the spread is 1 tick.
- Displayed touch size is the same in both windows (median 4 lots). NY's extra volume shows up as replenishment speed and depth behind the touch, not as size at the touch.
- The `mbp-10` cross-check agrees with `bbo-1s`: spread p50 2 in both windows, and >1 tick 94% of the time (London) vs 67% (NY), on 2026-10-28.

### 3.2 Ranges (ohlcv-1m, 131 days, 2026-05-01 → 10-30)

| Ticks, p50 / p75 / p90 | London 02:00–05:00 | NY AM 09:30–11:00 | Silver Bullet 10:00–11:00 |
|---|---:|---:|---:|
| 1-minute range | **39** / 54 / 74 | 107 / 151 / 202 | 96 / 135 / 180 |
| 15-minute range | **158** / 213 / 290 | 415 / 587 / 760 | 369 / 514 / 669 |
| Whole-window range | **588** / 752 / 1,013 | 1,023 / 1,409 / 1,770 | 736 / 1,000 / 1,311 |

### 3.3 Typical stop sizes (ticks, p50 / p75 / p90)

| Setup proxy | Days with a sweep | Sweep-bar range | Stop A: enter on close-back | MSS confirmed | Stop B: enter on MSS close |
|---|---:|---:|---:|---:|---:|
| **London:** sweep of the Asian range | 86 / 131 | 42 / 58 / 82 | **44** / 69 / 117 | 39 | **89** / 130 / 169 |
| NY AM: sweep of the London range | 98 / 131 | 154 / 215 / 289 | 174 / 254 / 322 | 28 | 239 / 354 / 418 |
| Silver Bullet: sweep of the 09:30–10:00 range | 111 / 131 | 131 / 188 / 267 | 104 / 148 / 198 | 30 | 268 / 339 / 456 |

| Generic local sweep (prior 15-bar extreme, 1-bar close-back) | Events/day | Sweep-bar range | Stop (close → extreme + 1 tick) |
|---|---:|---:|---:|
| London | 23.3 | 43 / 59 / 77 | **24** / 38 / 56 |
| NY AM | 10.8 | 103 / 146 / 194 | 56 / 91 / 131 |
| Silver Bullet | 6.4 | 94 / 134 / 178 | 51 / 79 / 120 |

A London sweep-and-reverse needs a stop of roughly **45 ticks (11 points) when entering on the close-back**, and **about 90 ticks (22 points) when waiting for the MSS**. That is about 1/4–1/3 of the NY equivalents. These are 1-minute-bar proxies. The real setup will add its own filters (bias, FVG entry), which changes the entry price but not the order of magnitude.

### 3.4 Slippage

**Market entry at a bar close** (bbo-1s, 10 days; mbp-10 walk, 1 day):

| | London | NY AM | Silver Bullet |
|---|---:|---:|---:|
| Half-spread = mean cost vs bar close / next open, ticks | 1.14 | 0.90 | 0.87 |
| One-sided p90, ticks | 3 | 2 | 2 |
| Depth walk vs touch, N = 1 / 3 / 5 / 10 / 20 lots, mean ticks | 0 / 0.13 / 0.27 / 0.61 / 1.22 | 0 / 0.16 / 0.28 / 0.53 / 0.99 | (NY row) |
| Walk p90, N = 5 / 20 | 0.8 / 1.7 | 0.8 / 1.45 | |
| **Total vs bar price, 1–5 lots (mean)** | **≈ 1.1–1.4** | **≈ 0.9–1.2** | |

**Stop exit through a fresh 15-minute extreme** (tbbo):

| | London (10 days) | NY AM (2 days) |
|---|---:|---:|
| Events | 549 | 56 |
| First trade beyond S, ticks p50 / p90 / max | 0 / 0 / 2 | 0 / 0 / 0 |
| Electing aggressor runs past S, ticks p50 / p90 / max | 1 / 3 / 13 | 2 / 10 / 21 |
| Slippage N=1, mean / p90 | **0.49 / 2** | **2.57 / 10** |
| Slippage N=3, mean / p90 | 0.78 / 2 | 2.79 / 10 |
| Slippage N=5, mean / p90 | **1.15 / 3** | **3.05 / 10** |
| % of events with < 5 lots at the post-trigger touch | 63% | 41% |

- **Stops behave better in London than in NY AM.** London breakouts are mostly 1-lot prints that tick through the level. In NY, the level is often taken by one large aggressive order that sweeps 2–20 ticks in a single matching event, and an elected stop fills behind it.
- **London's weakness is the entry spread, not the stop.**

### 3.5 Costs against stops and ranges

Round trip per contract = 2.48 (commission) + entry slippage + exit slippage, using the recommended assumptions (London 2 + 2, NY AM 1 + 3). Stopped-out trades pay both. Target hits on a resting limit pay commission + entry only.

| | London | NY AM | Silver Bullet (NY AM assumptions) |
|---|---:|---:|---:|
| Round trip, stopped out (ticks / $) | **6.5 / $3.24** | 6.5 / $3.24 | 6.5 / $3.24 |
| Round trip, limit target hit | 4.5 | 3.5 | 3.5 |
| % of median 1-minute range | 17% | 6% | 7% |
| % of median 15-minute range | 4.1% | 1.6% | 1.8% |
| % of median stop B (MSS entry) | **7.3%** | 2.7% | 2.4% |
| % of median stop A (close-back entry) | **15%** | 3.7% | 6.2% |
| % of median generic 1-bar stop | **27%** | 12% | 13% |
| Lots at 1% risk on a $50k account, median stop B / A | 11 / 22 | 4 / 5 | 3 / 9 |

- **Cost as a share of R is the deciding number.** For an MSS-confirmed London entry it is ~7% of R. That is comparable to a close-back Silver Bullet entry, and a realistic ICT edge can survive it.
- Below about 40 ticks of stop the cost is above 15% of R, and a 1:1 to 2:1 R:R system needs a noticeably higher win rate to break even. For example, at a 2R target the break-even win rate, (1 + c) / 3 for a cost of c R, goes from 33.3% to about 36% at 7% cost, about 38% at 15%, and about 42% at 27%.
- Commission sensitivity: at $1.00/side all-in (some prop and retail routes), the round trip becomes 8 ticks, which is 9% of a London stop B.

---

## 4. Recommendation

1. **London sweep-and-reverse stays in the setup list (keep, with caveats).** Liquidity is lower but continuous: every minute trades, about 480 prints a minute, and 4 lots typically at the touch. Fills of 1–5 lots are realistic. What is actually different is that the costs are a larger share of the smaller London stops.
2. **Backtest slippage** (proposed for ticket #8; a per-window override in `BrokerConfig`):

   | Window | Entry (market / stop-entry) | Stop exit | Notes |
   |---|---:|---:|---|
   | **London 02:00–05:00** | **2 ticks** | **2 ticks** | 3 / 3 above 10 lots |
   | **NY AM 09:30–11:00** (incl. Silver Bullet) | **1 tick** | **3 ticks** | Stop number from a small sample; fat tail (p90 10). Re-measure. |
   | Limit entries/targets | 0 | – | Keep `limit_fill = "trade_through"` |

   The current single `slippage_ticks = 1` is too optimistic for London entries and for NY stops.
3. **London setup guardrails** to add as parameters (proposals for the user to approve, per design.md):
   - `min_stop_ticks` ≈ 40 for London.
   - A size cap of about 20 lots, or +1 tick of slippage per 10 lots above 10.
   - Prefer limit entries at the FVG edge over market entries.
4. **Re-check later** with a wider tick sample when budget allows: more NY AM `tbbo` days (the stop-slippage estimate there rests on 2 days), London `tbbo` in winter (EST), and a roll week.

---

## 5. Caveats

- **Sample sizes.**
  - Spread, touch and London trade stats come from 10 October days. NY AM trade and stop stats come from **2 days**. Depth comes from **15 minutes (London) and 5 minutes (NY) of one day**.
  - Ranges and stop proxies come from 6 months of bars, which is a reasonable sample, but they are proxies, not the final setup code.
  - The regime is one of high index levels (MNQ ~30k) and summer/autumn 2026 volatility.
- **Model simplifications.**
  - The stop fill model treats a CME stop as filled against the book right after the electing event. Real Globex stop orders are stop-limit or stop-with-protection, which can leave part of a stop unfilled in a fast move. Not verified from CME pages in this session, because www.cmegroup.com was blocked by the proxy (403).
  - Beyond the post-trigger touch, depth is approximated as "touch size per extra tick". mbp-10 shows real London depth is thicker than that (21 lots within 3 levels), so the London N=3–5 stop numbers are, if anything, pessimistic.
  - Entry slippage is measured against the bar close / next open at a random minute boundary, not specifically after sweeps. The sweep-specific behaviour is captured on the stop side.
- **Calendar and data quality.**
  - US holidays (Memorial Day, Juneteenth, July 3, Labor Day) are in the 6-month bar sample when the window had at least 50% of its bars.
  - Databento flagged 2026-05-24 (a Sunday) as degraded. It feeds only the Asian range for 2026-05-25 (Memorial Day).
- **Not tested.**
  - London in EST months (winter): the windows sit an hour later in UTC, and Europe's open aligns differently.
  - Pre-2026 data, when MNQ traded at lower prices, where a 1-tick spread was more common.
- **Commission** is still the $0.62/side placeholder (ticket #8).

---

## 6. Paid-request ledger

Every request was priced first with the free `client.metadata.get_cost` (same arguments), and the total was checked against the $5.00 cap before anything was downloaded (`download.py`). An initial plan of $5.93 (three NY AM tbbo days, 15 minutes of NY mbp-10) was cut to fit.

- All requests: dataset `GLBX.MDP3`, symbol `MNQ.v.0`, `stype_in="continuous"`.
- Files are in `data/london-liquidity/` (git-ignored, never re-downloaded).
- The per-request CSV is [`london-liquidity/ledger.csv`](london-liquidity/ledger.csv).

| # | Schema | Range (UTC) | get_cost (USD) |
|---:|---|---|---:|
| 1 | `ohlcv-1m` | 2026-05-01 → 2026-10-31 (all hours) | 0.656046 |
| 2–21 | `bbo-1s` | 10 days × London 06:00–09:00 ($0.015232–0.015289 each) and NY 13:30–15:00 ($0.008047 each); days Oct 16, 19, 20, 21, 22, 23, 26, 27, 28, 29 | 0.233208 |
| 22 | `tbbo` | 2026-10-16 06:00–09:00 | 0.138809 |
| 23 | `tbbo` | 2026-10-19 06:00–09:00 | 0.153832 |
| 24 | `tbbo` | 2026-10-20 06:00–09:00 | 0.208355 |
| 25 | `tbbo` | 2026-10-21 06:00–09:00 | 0.175705 |
| 26 | `tbbo` | 2026-10-22 06:00–09:00 | 0.240447 |
| 27 | `tbbo` | 2026-10-23 06:00–09:00 | 0.207394 |
| 28 | `tbbo` | 2026-10-26 06:00–09:00 | 0.195400 |
| 29 | `tbbo` | 2026-10-27 06:00–09:00 | 0.159516 |
| 30 | `tbbo` | 2026-10-28 06:00–09:00 | 0.143772 |
| 31 | `tbbo` | 2026-10-29 06:00–09:00 | 0.188199 |
| 32 | `tbbo` | 2026-10-27 13:30–15:00 | 0.830284 |
| 33 | `tbbo` | 2026-10-28 13:30–15:00 | 0.680285 |
| 34 | `mbp-10` | 2026-10-28 07:00–07:15 | 0.040185 |
| 35 | `mbp-10` | 2026-10-28 14:00–14:05 | 0.223409 |
| | **Total** | | **$4.474846** |

For reference, unbought quotes (one day, `get_cost`):

| Schema | London 3 h | NY AM 90 min |
|---|---:|---:|
| `mbp-1` | $0.2345 | $0.9745 |
| `trades` | $0.0863 | $0.4082 |
| `mbp-10` (full window) | $0.4213 | $1.7234 |

## 7. Reproduce

```sh
uv sync
uv run python docs/research/london-liquidity/download.py --dry-run   # free: prices every request, checks the cap
uv run python docs/research/london-liquidity/download.py             # buys only files not already in data/london-liquidity/
uv run python -I docs/research/london-liquidity/analyze.py           # offline; output saved as london-liquidity/output.md
```

The API key is read from `DATABENTO_API_KEY` by `databento.Historical()`. No script prints or stores it.

## Sources

- Databento schema docs, read 2026-10-31:
  - [BBO on interval](https://databento.com/docs/schemas-and-data-formats/bbo) (interval semantics, `ts_recv` = interval end, skipped empty intervals)
  - [TBBO](https://databento.com/docs/schemas-and-data-formats/tbbo) (BBO immediately before each trade)
  - [MBP-10](https://databento.com/docs/schemas-and-data-formats/mbp-10)
  - [MBP-1](https://databento.com/docs/schemas-and-data-formats/mbp-1)
- Databento `metadata.get_cost` and `metadata.get_billable_size` responses, captured in this session (databento-python 0.89.0).
- Record layouts: [`dbn` record.rs](https://github.com/databento/dbn/blob/main/rust/dbn/src/record.rs). Roll and bar-timestamp conventions: [databento-data-plan.md](https://github.com/DaltonDom/moon-ai/blob/research/databento-data-plan/docs/research/databento-data-plan.md).
- MNQ contract: 0.25 index point tick, $2 multiplier ([CME contract specs](https://www.cmegroup.com/markets/equities/nasdaq/micro-e-mini-nasdaq-100.contractSpecs.html); not reachable from this session, value as already encoded in `config.py`).
