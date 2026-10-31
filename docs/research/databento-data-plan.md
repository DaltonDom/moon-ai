# Databento data plan and cost: MNQ / NQ / MES / ES

Status: research note for [issue #3](https://github.com/DaltonDom/moon-ai/issues/3) (child of map #1). Written 2026-10-31.
Related: [design.md](../design.md) (Phase 1 is "$0 on the Databento $125 credit", Phase 2 is "~$0–5/mo"), [ict-ml-trading-bot.md §2.3](ict-ml-trading-bot.md#23-market-data-vendors).

## How this was researched, and what is not verified

- **databento.com could not be reached from this session.** The proxy refused every `*.databento.com` host (`CONNECT tunnel failed, response 403`), so the pricing page, the price calculator and the docs could not be opened directly. Databento facts below come from:
  1. Search-result excerpts restricted to `databento.com`, marked **(excerpt)**.
  2. Databento's own code on GitHub and PyPI: the `databento` 0.89.0 client source, the `dbn` Rust crate, and the official quickstart notebook.
  3. Captured responses from Databento's `metadata.list_unit_prices` and `metadata.get_cost` endpoints, published in third-party repos, marked **(third-party capture)**. I checked these against each other and against the record sizes in `dbn`.
- **No API key, so nothing was priced with `get_cost` here.** The ticket asks for prices confirmed in Databento's own calculator. That could not be done from this session. Every dollar figure below is **unit price × record count × record size**. The unit prices and record sizes are sourced; the record counts are my estimates. **Step 0 of the plan below runs the free `get_cost` call before anything is bought.**
- Anything I could not confirm is marked **UNVERIFIED**.

---

## 1. Short answer

| Question | Answer |
|---|---|
| What to download | **`ohlcv-1m`** for **`ES.v.0`, `NQ.v.0`** (2019-01-01 →) and **`MES.v.0`, `MNQ.v.0`** (2019-05-06 →, their launch date), plus a small **`tbbo` sample for MNQ only** to calibrate slippage. **Don't buy full-history tick data.** |
| Backfill cost | About **$39** (upper bound) for four symbols of 1-minute bars from 2019 to now, at the current list price of **$70/GB**. |
| Full-history tick data | `trades`, `tbbo` or `mbp-1` for the four symbols comes to roughly **$2k–$16k**. That is 15–130× the credit, so it's ruled out. |
| Recommended credit spend | About **$75** (bars + definitions + tick sample + on-demand 1-second bars), keeping about **$50** in reserve. |
| How long the credit lasts | It expires **6 months after signup**, however much is left. After the backfill, nightly bars cost about $0.02 a day, so the reserve covers nightly pulls until it expires. **Sign up only when the downloader is ready**, because the 6-month clock starts at signup. |
| Nightly pull after the credit | About **$0.02 per session** for four symbols of `ohlcv-1m`, so about **$0.45/month** (about $5/year). Adding a daily MNQ `tbbo` pull for the kill-zone windows only adds about $2–9/month (UNVERIFIED). This fits design.md's "~$0–5/mo". |
| Catch | **Without a subscription, only data older than 24 hours counts as "historical".** The last 24 hours is "intraday" and needs a CME plan (Standard is **$199/mo**). So the nightly job replays **yesterday's** session (T+1), not "that day's". |
| Rolls | Use **volume-ranked continuous symbols** (`.v.0`). Prices are **not back-adjusted**, so the engine has to detect rolls itself (the `instrument_id` changes). |
| Licence | Historical data for personal, non-professional use, not redistributed: **no exchange licence needed**. Redistribution needs a licence. |
| Bar timestamps | `ts_event` on `ohlcv-1m` and `ohlcv-1s` is the bar's **open** (the inclusive start of the interval). A bar stamped 09:30:00 covers [09:30:00, 09:31:00) and is **only known at 09:31:00**. The engine must re-key bars to `ts_event + interval` before any signal uses them (§2.5). |
| MNQ `ohlcv-1s` | **Whole history:** 2019-05 → now is about **$200–350**, and 5 years is about $150–250. That is 1.6–2.8× the credit, so it's not affordable. **Only the ambiguous minutes:** about **$0.0002 per minute**, so pennies in total. Compare `trades` for the whole MNQ history at about **$470–2,400** (§3.5). **Pull 1-second bars on demand.** |

---

## 2. Facts

### 2.1 Pricing model

- Historical data is billed **per byte consumed, in $/GB**. Billing uses the **uncompressed size in binary (DBN) encoding**, whatever encoding you download in (CSV or JSON cost the same) ([Databento FAQ: usage-based pricing and credits](https://databento.com/docs/faqs/usage-pricing-and-data-credits) **(excerpt)**; [Metered pricing](https://databento.com/docs/api-historical/basics/metered-pricing) **(excerpt)**).
- Price formula: `cost = unit_cost × uncompressed_size_GB` ([official quickstart notebook, databento-python](https://github.com/databento/databento-python/blob/main/notebooks/quickstart.ipynb)).
- **A request is billed once.** A batch job's files can be re-downloaded free for 30 days ([FAQ](https://databento.com/docs/faqs/usage-pricing-and-data-credits) **(excerpt)**). A second `timeseries.get_range` call for the same data is billed again (inferred from "billed per byte consumed"; **UNVERIFIED** as an explicit statement).
- Cost and size estimates come from `metadata.get_cost` and `metadata.get_billable_size`. Both take the same arguments as the data request: dataset, symbols, schema, `stype_in`, start and end ([databento-python `metadata.py`](https://github.com/databento/databento-python/blob/main/databento/historical/api/metadata.py)). Third-party code and the Nautilus docs describe `get_cost` as free of charge (**UNVERIFIED** on databento.com).
- **The $125 credit:** every new team gets $125 once. It is shared across the team and **expires after 6 months**. It can be spent on historical data or on the first month of a subscription, and it is applied automatically before any charge ([FAQ](https://databento.com/docs/faqs/usage-pricing-and-data-credits) **(excerpt)**). Payment details are required at signup ([Databento blog](https://databento.com/blog/why-payment-information-required) **(excerpt)**).

### 2.2 GLBX.MDP3 unit prices ($/GB)

| Schema | Record size (bytes) | Historical $/GB, retrieved 2026-10-26 | Historical $/GB, Aug 2023 (official notebook) |
|---|---:|---:|---:|
| `ohlcv-1m` / `ohlcv-1s` | 56 | **70.00** | 63.50 / 50.50 |
| `ohlcv-1h` / `ohlcv-1d` | 56 | 190.00 | 130 / 175 |
| `trades` | 48 | **28.00** | 24.80 |
| `tbbo` | 80 | **28.00** | 17.89 |
| `bbo-1s` / `bbo-1m` | 80 | 18.00 | n/a |
| `mbp-1` | 80 | **1.80** | 2.42 |
| `mbp-10` | 368 | 0.50 | 0.45 |
| `mbo` | 56 | 1.80 | 1.10 |
| `definition` | 520 | 1.70 | 1.66 |
| `statistics` | 80 | 1.00 | 0.80 |
| `status` | 40 | 4.00 | n/a |

Sources:
- **2026 prices:** a `list_unit_prices` response captured on 2026-10-26 in [kleithegreat/moneymachine `audit/stage8/databento-pricing.json`](https://github.com/kleithegreat/moneymachine/blob/2475e91817fc95dcf0b3fa932bb248884ac7ebad/audit/stage8/databento-pricing.json) **(third-party capture)**. A second, independent capture in [dungchu2810/gator-quant-hacks notes](https://github.com/dungchu2810/gator-quant-hacks/blob/edf9b65e56d6e8e5306013abc2091bcc8581d6db/archive/session_outputs/fedtalk/data_markets/notes.md) **(third-party capture)** gives the same values: `ohlcv-1s/1m 70, tbbo/trades 28, bbo-1s 18, mbp-1 1.8, mbp-10 0.5`. Historical and historical-streaming prices are the same; live prices are 1.2× higher.
- **2023 prices:** `client.metadata.list_unit_prices(dataset="GLBX.MDP3")` output in the [official quickstart notebook](https://github.com/databento/databento-python/blob/main/notebooks/quickstart.ipynb) (client 0.17.0, Aug 2023). These show the price direction only and are out of date.
- **Record sizes:** compile-time `size_of` assertions in [`dbn/rust/dbn/src/record.rs`](https://github.com/databento/dbn/blob/main/rust/dbn/src/record.rs): `OhlcvMsg` 56, `TradeMsg` 48, `Mbp1Msg` 80, `BboMsg` 80, `Mbp10Msg` 368, `MboMsg` 56, `InstrumentDefMsg` 520, `StatMsg` 80, `StatusMsg` 40.

**Check of the formula against real `get_cost` outputs:** the gator project's [cost_summary.txt](https://github.com/dungchu2810/gator-quant-hacks/blob/edf9b65e56d6e8e5306013abc2091bcc8581d6db/archive/session_outputs/fedtalk/data_markets/cost_summary.txt) **(third-party capture)** gives record counts and dollar figures for three schemas, and each one matches `records × record_size ÷ 2^30 × unit_price`:

| Schema | Records | Formula | `get_cost` returned |
|---|---:|---:|---:|
| `ohlcv-1m` | 83,511 | 83,511 × 56 B ÷ 2^30 × $70 = $0.305 | $0.3049 |
| `tbbo` (ES/ZN/ZT, mean per day) | 313,840 | → $0.654 | $0.6547 |
| `mbp-1` (mean per day) | 3.33 M | → $0.447 | $0.4468 |

So **"GB" here means GiB (2^30 bytes)**, and the cost tables in §3 can be trusted as long as the record counts are right.

**Why `ohlcv-1m` is "$70/GB" when Databento's marketing says "from $0.50/GB":** the $0.50 rate is `mbp-10`. Compact schemas carry a much higher price per GB, but they are tiny.

### 2.3 Dataset coverage and symbology

- `GLBX.MDP3` history starts 2010-06-06 ([GLBX.MDP3 dataset page](https://databento.com/datasets/GLBX.MDP3) **(excerpt)**). MBO starts 2017-05-21 (gator notes **(third-party capture)**).
- **MES and MNQ first traded on Monday 2019-05-06** ([CME Group press release](https://investor.cmegroup.com/news-releases/news-release-details/cme-group-makes-global-equity-benchmarks-more-accessible-active) **(excerpt)**; [CME SER #8360](https://www.cmegroup.com/notices/ser/2019/04/SER-8360.pdf) **(excerpt)**). Asking for micros "from 2019-01-01" only returns data from that date. For **January–May 2019, use NQ and ES as stand-ins for MNQ and MES**: same index and same 0.25 tick, at 1/10 the multiplier ($2 vs $20, $5 vs $50) ([CME FAQ](https://www.cmegroup.com/articles/faqs/frequently-asked-questions-micro-e-mini-equity-index-futures.html) **(excerpt)**).
- **Continuous ("smart") symbols** take the form `[ROOT].[ROLL_RULE].[RANK]`, for example `ES.c.0`, with `stype_in="continuous"` ([databento-python `validation.validate_smart_symbol`](https://github.com/databento/databento-python/blob/main/databento/common/validation.py)). `[ROOT].FUT` with `stype_in="parent"` selects every ES contract **including calendar spreads**. The quickstart example for `ES.FUT` resolved to about 37 instruments on a single day ([quickstart notebook](https://github.com/databento/databento-python/blob/main/notebooks/quickstart.ipynb)), so **never pull bars with `parent`**: it costs about 10–40× more.
- **Roll rules** ([Databento symbology docs](https://databento.com/docs/standards-and-conventions/symbology) **(excerpt)**):
  - `c` is calendar, ordered by nearest expiry.
  - `n` ranks by the previous day's open interest.
  - `v` ranks by the previous day's volume.
  - Rank 0 is the lead contract.
- **Prices are not adjusted at rolls.** Databento does not back-adjust ([symbology docs](https://databento.com/docs/standards-and-conventions/symbology) **(excerpt)**).
- **Why `.v.0` and not `.c.0`:** `c.0` stays on the expiring contract during roll week, when liquidity has already moved. A third-party measurement on 2025-09-17 found `ES.c.0` had fewer 1-second bars than `ES.v.0` (gator notes **(third-party capture)**). Because `v` ranks on the **previous day's** volume, the switch happens one session after the volume crossover. That is acceptable for a bar backtest. A community report says `.v.1` can briefly flip back to the old contract ([Databento roadmap](https://roadmap.databento.com/b/n0o5prm6/feature-ideas/improved-or-additional-roll-rule-support) **(excerpt)**), so use only rank 0.
- **No bar is emitted for a minute with no trades.** Fill gaps on the client side if a dense series is needed ([Databento OHLCV docs](https://databento.com/docs/schemas-and-data-formats/ohlcv) **(excerpt)**). `ts_event` marks the start of the bar (§2.5).

### 2.5 Bar timestamps: open or close?

- **The OHLCV `ts_event` is the bar's open.** Databento's OHLCV docs define it as "the inclusive start time of the bar aggregation period", in nanoseconds since the UNIX epoch ([Aggregate bars (OHLCV)](https://databento.com/docs/schemas-and-data-formats/ohlcv) **(excerpt)**). The same `OhlcvMsg` record and convention serve `ohlcv-1s`, `-1m`, `-1h` and `-1d` ([`dbn` record.rs, `OhlcvMsg`](https://github.com/databento/dbn/blob/main/rust/dbn/src/record.rs)).
  - So the bar stamped `14:30:00` holds trades in [14:30:00.000, 14:31:00.000). Its close, high and low are **not knowable before 14:31:00**.
- Don't confuse this with the live API's end-of-interval control message. That message's `ts_event` is the *exclusive end* of the interval: a marker stamped 14:31:00 follows the bars stamped 14:30:00 ([Databento OHLCV docs](https://databento.com/docs/schemas-and-data-formats/ohlcv) **(excerpt)**).
- **Engine rules:**
  - Convert every bar to an "available at" time of `ts_event + interval` at load time.
  - Features and signals may only use bars whose available-at time is ≤ the decision time.
  - An entry triggered by bar *t* fills no earlier than the first tick after *t*'s close, which in a bar backtest is bar *t+1*'s open.
  - When resampling 1m to higher timeframes, keep left-labelled, left-closed intervals, and apply the same `+ interval` shift to the result.
  - Add a unit test that fails if any signal reads a bar whose close time is in its future.
- Databento also says vendors build OHLCV aggregates slightly differently and suggests building your own from trades where feasible ([OHLCV docs](https://databento.com/docs/schemas-and-data-formats/ohlcv) **(excerpt)**). This matters for the TradingView spot-checks: expect occasional one-tick differences in highs and lows.

### 2.4 Historical vs intraday, and licensing

- **"Historical" means more than 24 hours old.** Databento users "don't need a license to access historical data, which we define as 24 hours into the past". A licence is needed for real-time or intraday data if you are a professional or redistribute within 24 hours ([Databento licensing FAQ / blog](https://databento.com/blog/introduction-market-data-licensing) **(excerpt)**).
- The last 24 hours are served by the **live** gateways as "intraday replay" ([Intraday historical subscription](https://databento.com/docs/api-live/message-flows/intraday-historical) **(excerpt)**). Intraday access needs a Standard, Plus or Unlimited plan ([GLBX.MDP3 dataset page](https://databento.com/datasets/GLBX.MDP3) **(excerpt)**). The historical API refuses ranges beyond what your licence covers (`data_end_after_available_end`) ([Databento issue tracker](https://issues.databento.com/) **(excerpt)**).
  - **UNVERIFIED:** the exact embargo a usage-only account sees for GLBX.MDP3, that is, what `metadata.get_dataset_range` returns as `end` without a plan. Check it on day 1 with a key. Plan for T+1.
- **CME Standard plan:** **$199/month** from 2026-06-22 (was $179; existing subscribers keep $179 for 12 months) ([Databento blog: Updates to subscription pricing](https://databento.com/blog/updates-to-subscription-pricing) **(excerpt)**). It includes live data and personal use "up to 2 devices" ([Live data guide](https://databento.com/docs/portal/live-data) **(excerpt)**).
  - How much CME history the plan includes is **UNVERIFIED**. One third-party repo lists "L0 (trades, OHLCV) 15+ years; L1 (MBP-1/TBBO/BBO) 12 months; L2/L3 1 month" ([abwagner/Magpie `docs/data/universes.md`](https://github.com/abwagner/Magpie/blob/e083baa0457cd86f299345194f71fd765c18a653/docs/data/universes.md) **(third-party, UNVERIFIED)**). If true, a single month of Standard ($199) would include the whole OHLCV backfill and 12 months of `tbbo`/`mbp-1`. That is worth checking (see §5).
- **Personal use** means use by a non-professional for their own decisions, research or education, not shared or used for profit. Non-professional users who don't redistribute sign an attestation and Databento acts as vendor of record. Redistribution always needs a licence ([Live data guide / licensing](https://databento.com/docs/portal/live-data) **(excerpt)**).
- CME's 2026 fee list charges a separate historical licence fee for *distributing* historical data by feed. That applies to vendors, not to us ([CME fee list hosted by Databento](https://api.databento.com/static/licensing/cme/cme-market-data-fee-list.pdf) **(excerpt)**).
- **Implications for moon-ai:**
  - Downloading history, storing it locally, backtesting and viewing it in our own dashboard is fine.
  - Publishing the raw data, or a dashboard others can access, is redistribution. **Don't.**
  - Databento's own Terms of Service text was not read (**UNVERIFIED**).
- **Data-quality caveat:** recent days are sometimes published degraded and regenerated later. Examples include 2026-05-30/31 channels 326/327/329, and a Saturday 00:00–07:15Z gap on 24/7 channels ([issues.databento.com](https://issues.databento.com/)). The nightly job should check `metadata.get_dataset_condition` before pulling.

---

## 3. Cost tables

Assumptions:
- **Sessions:** CME equity-index futures trade about 23 hours a day, 5 sessions a week, which is about **1,380 one-minute bars per session** if every minute trades (an upper bound).
- **Session counts:** 1,974 sessions for 2019-01-01 → 2026-10-30, and 1,888 for 2019-05-06 → 2026-10-30 (weekdays minus about 9 holidays a year).
- **Pricing:** `cost = records × size ÷ 2^30 × price`, at the 2026-10-26 prices.

### 3.1 Backfill: `ohlcv-1m`, continuous `.v.0`

| Symbol | From | Bars (upper bound) | Size (MiB, DBN) | Cost @ $70/GB |
|---|---|---:|---:|---:|
| `ES.v.0` | 2019-01-01 | 2.72 M | 145.5 | $9.95 |
| `NQ.v.0` | 2019-01-01 | 2.72 M | 145.5 | $9.95 |
| `MES.v.0` | 2019-05-06 | 2.61 M | 139.1 | $9.51 |
| `MNQ.v.0` | 2019-05-06 | 2.61 M | 139.1 | $9.51 |
| **All four** | | **10.7 M** | **569** | **≈ $38.9** |
| NQ + ES + MNQ only (MES dropped; SMT uses NQ vs ES) | | | | ≈ $29.4 |

- The real cost should be a little lower, because quiet overnight minutes produce no bar (more of them for micros in 2019–2020).
- `definition` for the same four continuous symbols: one 520-byte record per instrument per day, at $1.70/GB, so **< $0.01** in total.
- `statistics` (settlements, open interest) for the four `.v.0` symbols: well under $1 (**UNVERIFIED**, price with `get_cost`).

### 3.2 Full-history tick schemas: why not

Per symbol per session, by trade (or top-of-book update) count. The counts are **my estimates, UNVERIFIED**.

| Schema (size, $/GB) | 200k records/day | 500k/day | 1M/day | 4 symbols × ~1,930 sessions |
|---|---:|---:|---:|---:|
| `trades` (48 B, $28) | $0.25 | $0.63 | $1.25 | **≈ $1.9k – $9.7k** |
| `tbbo` (80 B, $28) | $0.42 | $1.04 | $2.09 | **≈ $3.2k – $16k** |
| `mbp-1` (80 B, $1.80), 3M / 8M / 15M records a day | $0.40 | $1.07 | $2.01 | **≈ $3.1k – $15.5k** |

- Real data point: during the 3-hour FOMC-press-conference windows, `tbbo` for ES+ZN+ZT averaged **$0.65 per window** and `mbp-1` averaged **$0.45** (gator cost_summary **(third-party capture)**). That puts a single liquid front contract's full day in the $0.3–$2 range above.
- **Even at the low end, full-history tick data costs 15× the credit or more.** The robust conclusion: backtest on 1-minute bars, and calibrate fills on a small tick sample.

### 3.3 Targeted tick and second data (affordable)

| Purpose | Request | Estimated cost |
|---|---|---|
| Slippage, spread and queue calibration | `tbbo`, `MNQ.v.0`, kill-zone windows only (London 02:00–05:00, NY AM 09:30–11:30, NY PM 13:30–16:00 ET), about 60–100 sessions spread across regimes | ~$0.15–0.60 a session, so **≈ $10–35**. **Run `get_cost` first.** |
| Same-bar stop/target ambiguity (both touched in one minute) | `ohlcv-1s`, `MNQ.v.0`, only the specific trade windows the backtest flags | ≤ $0.0002 per ambiguous minute, so **on demand, under $5**. Full detail in §3.5 |
| Spread history, cheaply | `bbo-1s`, `MNQ.v.0` | ≤ $0.11 a session (full day), so a 100-session sample is ≤ $11 |

### 3.5 MNQ `ohlcv-1s` vs `trades`, for resolving same-bar stop/target hits

The engine research chose a pessimistic same-bar rule, resolved from 1-second bars.

Formulas (sizes and prices from §2.2):
- `ohlcv-1s`: 56 B at $70/GB, so **$3.65 per million bars**. A bar exists only for a second that traded, and a session has at most 82,800 seconds.
- `trades`: 48 B at $28/GB, so **$1.25 per million trades**.

**Inputs (estimates, UNVERIFIED):**
- MNQ has trades in about **30k–50k seconds per session**: nearly every second of RTH, sparser overnight. For comparison, in the 3-hour FOMC windows the gator capture saw about 4,800 one-second bars per front contract per window, which is about 45% of seconds averaged over ES, ZN, ZT, ZF and 6E.
- MNQ trades per session are estimated at **200k–1M**.
- Measure both with `get_record_count` before buying (Step 1).

| Request | Records | Cost |
|---|---:|---:|
| `ohlcv-1s` MNQ, 1 session | 30k–50k (max 82.8k) | $0.11–0.18 (max $0.30) |
| `ohlcv-1s` MNQ, **5 years** (~1,260 sessions) | 38–63 M | **≈ $140–230** (max $380) |
| `ohlcv-1s` MNQ, **full history** 2019-05-06 → now (1,888 sessions) | 57–94 M | **≈ $205–345** (max $570) |
| `ohlcv-1s` MNQ, kill-zone windows only (≈4.5 h/session, ~85% of seconds active), full history | ≈ 26 M | ≈ $95 |
| `ohlcv-1s` MNQ, **only the ambiguous minutes** | ≤ 60 per minute | **≤ $0.0002 per minute**. 2,000 ambiguous minutes ≈ $0.45 |
| `ohlcv-1s` MNQ, whole entry→exit window of every backtest trade (≤ 3 h each) | ≤ 10.8k per trade | ≤ $0.04 per trade. 1,000 trades ≤ ~$40, typically far less |
| `trades` MNQ, 1 session | 200k–1M | $0.25–1.25 |
| `trades` MNQ, **5 years** | 0.25–1.26 B | **≈ $315–1,575** |
| `trades` MNQ, **full history** | 0.38–1.9 B | **≈ $470–2,360** |

**Verdict:**
- Whole-history `ohlcv-1s` costs 1.6–2.8× the credit. It's cheaper than `trades` (about 2–7× less) but not "cheap". So **pull 1-second bars on demand**, only for the minutes the 1-minute backtest flags as ambiguous.
- Batch them per day, one request per day covering that day's flagged minutes, so request count stays low. Cache them, because the same minutes recur across parameter sweeps.
- Total expected spend is **well under $5**.
- If a stop and target both fall inside the same *second*, the pessimistic rule still applies; 1-second bars can't order them. `trades` (or `tbbo`) would order them, but only buy those for that handful of seconds if it ever matters.
- **UNVERIFIED:** whether Databento applies any per-request minimum charge to tiny requests. None is documented in the excerpts I found. Check with `get_cost` on a 1-minute request on day 1.

### 3.6 Ongoing nightly pull (after the credit)

| Pull | Per session | Per month (~21 sessions) | Per year |
|---|---:|---:|---:|
| `ohlcv-1m`, 4 × `.v.0`, previous session | ≈ $0.020 | **≈ $0.42** | ≈ $5 |
| + `definition` | < $0.0001 | ~$0 | ~$0 |
| + optional MNQ `tbbo`, kill zones only | ~$0.15–0.60 (UNVERIFIED) | ~$3–13 | ~$40–150 |
| Alternative: CME Standard plan (needed only to get *same-day* data) | n/a | **$199** | $2,388 |

---

## 4. Recommended download plan

**Step 0: before signup**
- Write the downloader with a **cost guard**. Every request first calls `metadata.get_cost` with the exact same parameters and refuses if the result is over budget.
- Log every spend to a local ledger.
- Sign up only when the downloader is ready, because the 6-month credit clock starts at signup.

**Step 1: day 1 with a key (free metadata calls)**
- `metadata.list_unit_prices("GLBX.MDP3")`: confirm the $70 / $28 / $1.80 prices.
- `metadata.get_dataset_range("GLBX.MDP3")`: confirm how far behind "now" a usage-only account can read (the 24h embargo).
- `metadata.get_cost` for every row of §4 Step 2. **Stop if the total is over $50.**
- Ask Databento support whether CME Standard includes OHLCV history (see §5). If it does, one $199 month might beat usage pricing for the tick sample. It doesn't for bars alone.

**Step 2: backfill, about $40, one batch job per symbol**

The 6-month holdout is just the most recent part of this pull, tagged as untouched.

```python
import databento as db
client = db.Historical()  # DATABENTO_API_KEY from env; never hard-code
END = "<yesterday, UTC date>"  # never inside the last 24h
jobs = [
    ("ES.v.0",  "2019-01-01"), ("NQ.v.0",  "2019-01-01"),
    ("MES.v.0", "2019-05-06"), ("MNQ.v.0", "2019-05-06"),
]
for sym, start in jobs:
    for schema in ("ohlcv-1m", "definition"):
        args = dict(dataset="GLBX.MDP3", symbols=[sym], stype_in="continuous",
                    schema=schema, start=start, end=END)
        usd = client.metadata.get_cost(**args)          # free estimate
        assert usd < 15, (sym, schema, usd)             # hard guard
        client.batch.submit_job(**args, encoding="dbn", compression="zstd",
                                split_duration="month")  # re-downloadable free for 30 days
```

- Store the raw `.dbn.zst` files (immutable, about 0.6 GB uncompressed) and convert them to Parquet for the engine.
- Keep `instrument_id` on every bar. A change of `instrument_id` within a continuous series **marks a roll**.

**Step 3: tick sample, about $10–35, after setups first show an edge on bars**
- `tbbo` for `MNQ.v.0` in the kill-zone windows on about 60–100 sessions, stratified by year and volatility regime.
- Use it to fit the slippage and fill model the bar backtest applies (design.md: "fills and slippage" in the journal).

**Step 4: on demand, a few dollars**
- `ohlcv-1s` for `MNQ.v.0` only on the specific minutes where stop and target both fall inside one 1-minute bar. Batch one request per day and cache the results (§3.5).
- Don't buy whole-history 1-second bars (about $205–345) or whole-history `trades` (about $470–2,400).

**Step 5: nightly job (Phase 2), about $0.42/month**
- Run each night after 17:00 ET. Pull **the previous completed session** (T+1), which keeps clear of the 24-hour intraday line.
- Check `get_dataset_condition` first. If a day is degraded, re-pull it after Databento regenerates it.
- The paper replay runs one day behind real time. That is harmless for a forward test.

**Reserve:** keep about $50 of credit for mistakes, re-pulls and extensions. That covers about 6 years of nightly bars, but **any credit left at 6 months is lost**.

**Engine rules that follow from the data:**
- **Rolls.** Prices are unadjusted, so on a roll day:
  - don't let indicators, FVGs or liquidity levels span the two contracts (reset or back-adjust per setup);
  - don't hold or open trades across the switch.
- **SMT divergence.** Compare NQ with ES (or MNQ with MES) using the **same roll rule**. Both roll in the same quarterly week (H/M/U/Z), but the volume crossover can land on different days, so skip SMT signals on any day either leg rolled.
- **Missing bars.** Treat a missing minute as "no trade". Don't forward-fill volume.
- **Timestamps.** Bars are stamped at their **open**. Shift to `ts_event + interval` before any signal or feature uses them (§2.5).

---

## 5. Open questions (candidates for new tickets)

1. **Design wording: Phase 2 says "that day's" data.** Without the $199/mo Standard plan, usage-based data is available only after 24 hours. Accept a T+1 replay, which this note recommends, or budget for a plan? This needs a decision on map #1.
2. **Does CME Standard include historical OHLCV or L1?** One third-party repo says 15+ years of OHLCV/trades and 12 months of L1. If true, a single $199 month during Phase 1 would cover the `tbbo` and `mbp-1` sample for the last 12 months. Ask Databento support, or read the GLBX.MDP3 pricing tab once databento.com is reachable.
3. **Network access.** databento.com and its subdomains (`hist.databento.com`, `docs.databento.com`) are blocked from this cloud session. They need to be allowed in the environment's network settings before any download job can run here. Alternatively, downloads run on the Mac, as the design already says.
4. **Professional status as a prop-firm trader.** Does trading a prop-firm funded account make the user "professional" under CME/Databento definitions? This matters only if a live CME plan is ever bought (Phase 3+ uses NinjaTrader's feed), not for historical data. **UNVERIFIED.**
5. **Real tick counts.** Measure them with `get_record_count` for one MNQ session per year, to replace the §3.2 and §3.5 estimates (trades per session, active seconds per session) before Step 3.

---

## Sources

Databento (search excerpts only; site blocked from this session):
- Usage-based pricing and credits FAQ: https://databento.com/docs/faqs/usage-pricing-and-data-credits
- Metered pricing: https://databento.com/docs/api-historical/basics/metered-pricing
- GLBX.MDP3 dataset page: https://databento.com/datasets/GLBX.MDP3
- Symbology: https://databento.com/docs/standards-and-conventions/symbology
- OHLCV schema: https://databento.com/docs/schemas-and-data-formats/ohlcv
- Intraday historical subscription: https://databento.com/docs/api-live/message-flows/intraday-historical
- Live data guide (plans, licensing table): https://databento.com/docs/portal/live-data
- Updates to subscription pricing (2026-06-22): https://databento.com/blog/updates-to-subscription-pricing
- Introduction to market data licensing: https://databento.com/blog/introduction-market-data-licensing
- Why payment info is required: https://databento.com/blog/why-payment-information-required
- CME fee list (hosted by Databento): https://api.databento.com/static/licensing/cme/cme-market-data-fee-list.pdf
- Issue tracker: https://issues.databento.com/
- Roll-rule roadmap item: https://roadmap.databento.com/b/n0o5prm6/feature-ideas/improved-or-additional-roll-rule-support

Databento code (read directly):
- databento-python 0.89.0 (PyPI wheel; `metadata.py`, `validation.py`): https://github.com/databento/databento-python
- Official quickstart notebook (2023 unit prices, cost formula, `parent` example): https://github.com/databento/databento-python/blob/main/notebooks/quickstart.ipynb
- dbn record sizes: https://github.com/databento/dbn/blob/main/rust/dbn/src/record.rs

CME (search excerpts):
- Micro E-mini launch press release: https://investor.cmegroup.com/news-releases/news-release-details/cme-group-makes-global-equity-benchmarks-more-accessible-active
- SER #8360: https://www.cmegroup.com/notices/ser/2019/04/SER-8360.pdf
- Micro E-mini FAQ: https://www.cmegroup.com/articles/faqs/frequently-asked-questions-micro-e-mini-equity-index-futures.html

Third-party captures of Databento API responses (read directly):
- list_unit_prices GLBX.MDP3, retrieved 2026-10-26: https://github.com/kleithegreat/moneymachine/blob/2475e91817fc95dcf0b3fa932bb248884ac7ebad/audit/stage8/databento-pricing.json
- get_cost and record-count outputs: https://github.com/dungchu2810/gator-quant-hacks/blob/edf9b65e56d6e8e5306013abc2091bcc8581d6db/archive/session_outputs/fedtalk/data_markets/cost_summary.txt and notes.md in the same folder
- Plan-inclusion table (UNVERIFIED): https://github.com/abwagner/Magpie/blob/e083baa0457cd86f299345194f71fd765c18a653/docs/data/universes.md
