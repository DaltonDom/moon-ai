# Research: Codeable ICT setup definitions

Resolves [#2](https://github.com/DaltonDom/moon-ai/issues/2) (child of the map [#1](https://github.com/DaltonDom/moon-ai/issues/1)). Builds on [ict-ml-trading-bot.md](ict-ml-trading-bot.md) §1.3 and the setup list in [design.md](../design.md).

> **How to read this document.**
>
> - **What counts as a source.** "Primary" means Michael J. Huddleston's (ICT's) own output: posts by `@I_Am_The_ICT` on X, and videos on the InnerCircleTrader YouTube channel.
> - **How sources were reached.** This session's network blocked every primary host: youtube.com, x.com, theinnercircletrader.com, plus luxalgo.com, sozai.app and videohighlight.com, which host transcripts and summaries. So **every primary quote below comes from a search-engine excerpt restricted to that domain** (x.com/twitter.com or youtube.com). None was read on the page itself. Excerpts can be cut short, and some post texts were truncated by the search engine (marked "…").
> - **UNVERIFIED** marks any claim with no primary source, or one that only secondary sources (blogs, indicator pages, fan accounts) support.
> - **ICT does not publish written rulebooks.** His models are taught in long videos and loose posts, and he revises them (see §1.2). So the "rules" here are a **codeable reading** of his material, with each free choice exposed as a **parameter** to be tested. Treat every row marked *param* as a sweep dimension. None of them is a fact about ICT.
> - Nothing here is financial advice.

## 0. Answer in one paragraph

All five setups share one skeleton, which ICT himself put into a single 2022 post: *weekly expansion bias → a killzone (ideally with a medium- or high-impact news event) → opposing liquidity taken out → displacement and an FVG → target the opposing PD array* ([ICT, X, 2022-07-23](https://x.com/I_Am_The_ICT/status/1550816841110638592)). What separates the setups is mainly **the time window and what the stop and target are anchored to**. Primary support exists for:

- the Silver Bullet being anchored at **10:00 ET** ([ICT, X](https://x.com/I_Am_The_ICT/status/1897984651186114746))
- ICT's own statement that **anytime 07:00–10:00 is "technically NY Killzone"** ([ICT, X, 2025-03](https://x.com/I_Am_The_ICT/status/1903822271514284280))
- the **first FVG "tethered to the Dealing Range"** being the proper Silver Bullet FVG, with a **15–20 handle objective on a 1-minute basis** ([ICT, X, 2026-08](https://x.com/I_Am_The_ICT/status/2091492182007906623); the 15–20 handle part is from a search summary of that thread and only partly verified)
- the swing high being the stop for an FVG short ([ICT, X, 2022-05](https://twitter.com/I_Am_The_ICT/status/1527291258531618816))

Everything else is UNVERIFIED against primary material and must be swept as parameters: exact killzone edges, the London Silver Bullet hour, OTE levels, displacement thresholds, written definitions of Power of 3 and daily bias. The secondary consensus on these is consistent enough to give sensible defaults.

---

## 1. Shared definitions (used by every setup)

### 1.1 Time windows (`America/New_York`, DST-aware)

| Window | Default | Variants to test (*param*) | Evidence |
|---|---|---|---|
| Asian range | 20:00–00:00 | 19:00–00:00; 18:00–00:00 (from the CME reopen) | Secondary consensus ([The_ICT_Academy, X](https://x.com/The_ICT_Academy/status/1758524491724919242), [Trader Theory, X](https://x.com/tradertheory/status/1548247537634537473)). UNVERIFIED-primary |
| London Open Killzone | 02:00–05:00 | 02:00–04:00 | Secondary consensus (same sources). UNVERIFIED-primary |
| NY AM Killzone | **07:00–10:00** (forex framing); **08:30–11:00** (index framing) | 07:00–09:00; 07:00–09:30 | ICT, 2025: "Anytime between 7am and 10am is technically NY Killzone… the question is are you able [to trade it all]" ([X](https://x.com/I_Am_The_ICT/status/1903822271514284280)). The same search excerpt says a user cited ICT's 2022 mentorship as placing it at 08:30–11:00, and ICT's reply treats sub-windows as personal "operating hours". 08:30–11:00 / 13:30–16:00 for index futures is a secondary claim ([TradingView killzone script listing](https://in.tradingview.com/scripts/ictkillzones/), [backtrex](https://backtrex.com/en/blog/ict-kill-zone-times-sessions)) |
| London Close Killzone | 10:00–12:00 | — | Secondary consensus. UNVERIFIED-primary |
| NY PM session | 13:30–16:00 | 13:00–16:00 | Secondary ([TradingView killzone listing](https://in.tradingview.com/scripts/ictkillzones/)). UNVERIFIED-primary |
| **London Silver Bullet** | **03:00–04:00** | 02:00–03:00 (likely a mix-up with the London killzone start or a UTC conversion) | Fan-account posts crediting ICT's Silver Bullet lesson ([fx4_living, X](https://x.com/fx4_living/status/1663059633836007424), [Liq_Sniper, X](https://x.com/Liq_Sniper/status/1716480689766547932)). A search summary found **no source at all** for 02:00–03:00 as a Silver Bullet hour. UNVERIFIED-primary but no conflicting evidence |
| **NY AM Silver Bullet** | **10:00–11:00** | — | ICT: "If it fails to fill that number, use 10:00 am ET Silver Bullet to ORG C.E. long" ([X](https://x.com/I_Am_The_ICT/status/1897984651186114746)). The start time is primary; the 1-hour length is secondary |
| **NY PM Silver Bullet** | **14:00–15:00** | — | Secondary consensus (same fan posts). UNVERIFIED-primary |
| Extra Silver Bullet windows | off | 07:00–08:30; 15:00–16:00 | Fan accounts report ICT adding a 07:00–08:30 window in 2023 ([Frank369, X](https://x.com/FrankOf369/status/1746238304377311662), per search summary). UNVERIFIED |

**What this resolves from `ict-ml-trading-bot.md`:**

- **Killzone hours.** ICT's own wording (2025) treats 07:00–10:00 as the NY killzone. The 08:30–11:00 index variant is attributed to his 2022 mentorship but not confirmed. London 02:00–05:00 is unanimous among secondary sources. Still UNVERIFIED against a primary video timestamp.
- **London Silver Bullet hour.** 03:00–04:00, with no conflicting source.

### 1.2 Concept definitions

| Concept | Codeable rule (default) | *param* variants | Evidence |
|---|---|---|---|
| **Swing high/low** | 3-bar fractal: `h[i] > h[i-1] and h[i] > h[i+1]`. **Known only at the close of bar `i+1`.** | N = 1 (3-bar), 2 (5-bar) | ICT's "3-candle swing" is a secondary description ([YouTube title](https://www.youtube.com/watch?v=DuVWi72h-gc)). Fractal rule from [smc](https://github.com/joshyattridge/smart-money-concepts) |
| **Liquidity pools** | BSL above / SSL below: previous day high and low, the Asian range high and low, the London session high and low, previous week high and low, **relative equal highs and lows** (≥ 2 swings within ε ticks), and confirmed intraday swings. ICT prefers relative equal highs and lows as "fresh pools". | ε = 2–8 ticks on MNQ; the pool set used | ICT: "Aim for the Draw On Liquidity of Relative Equal Lows and or Highs that would constitute a 'fresh pool of liquidity'" ([X](https://x.com/I_Am_The_ICT/status/1853419538274017361)). Pool list is secondary ([Trader Theory, X](https://x.com/tradertheory/status/1841932475054133372)) |
| **Liquidity sweep (raid / stop hunt)** | A bar trades through a pool (`h > level` for BSL) **and** price closes back on the original side within *m* bars. | *m* = 1, 3, 5; close-back required or not; minimum penetration in ticks | ICT uses "opposing Liquidity to be taken out" ([X](https://x.com/I_Am_The_ICT/status/1550816841110638592)) with no written threshold. UNVERIFIED |
| **Displacement** | The leg away from the sweep contains ≥ 1 candle with `|c−o| ≥ k·ATR(14)` **and** creates an FVG. | *k* = 1.0, 1.5, 2.0; FVG required or not | ICT's 2022 checklist: "Look for displacement & FVG" ([X](https://x.com/I_Am_The_ICT/status/1550816841110638592)). No numeric threshold in ICT's material. *k* = 1.5 is from an open script ([ICT Ultimate Algorithmic Engine](https://it.tradingview.com/script/u2ItPJf6-ICT-Ultimate-Algorithmic-Engine/)) |
| **Market structure shift (MSS)** | After the sweep, a candle **closes** beyond the most recent confirmed short-term swing on the opposite side of the sweep (sweep of highs → close below the last swing low). | close vs wick; swing N; must the displacement leg itself cause the break? | Taught as a 2022 Mentorship topic, e.g. "ICT MENTORSHIP 2022 EPISODE 2 – Market Structure Shift And Internal Range Liquidity" ([YouTube](https://www.youtube.com/watch?v=WpWEXpVsPS4), a re-upload), and Episode 6 "Deep Dive into my Fair Value Gap & Market Structure Shifts" ([YouTube](https://www.youtube.com/watch?v=Bkt8B3kLATQ)). No exact rule seen. UNVERIFIED |
| **CISD** (optional alternative to MSS) | Close beyond the opening price of the run of opposite-coloured candles that delivered the sweep. | on/off | ICT names CISD as his concept ([X](https://twitter.com/I_Am_The_ICT/status/1840447752372883706)) and links it to the breaker ([X](https://x.com/I_Am_The_ICT/status/1675266686478438402)). The codeable rule is an interpretation. UNVERIFIED |
| **FVG** | Bullish when `l[i+1] > h[i-1]`, zone `[h[i-1], l[i+1]]`; bearish mirrors. **Known at the close of bar `i+1`.** Must sit in the displacement leg. | minimum size in ticks; entry at the zone edge, at **CE (50%)**, or at the far edge | 3-candle definition is secondary but universal ([casper_smc, X](https://twitter.com/casper_smc/status/1787828626244641206), [smc](https://github.com/joshyattridge/smart-money-concepts)). ICT uses "C.E." (consequent encroachment) as the gap midpoint ([X](https://x.com/I_Am_The_ICT/status/1897984651186114746)) |
| **Which FVG** | The **first** FVG after the MSS that is "tethered to the Dealing Range" (it sits at a quadrant, octant or hexadecant level of the range). | first FVG only; first tethered FVG; any FVG | ICT: "When you are selecting FVGs, the first one that is tethered to the Dealing Range, as I define them, whether a Hexadecant, Oct[ant]…" ([X](https://x.com/I_Am_The_ICT/status/2091492182007906623); the rest of the text is from a search summary). "1st Presented FVG" posts ([X](https://x.com/I_Am_The_ICT/status/1988248421438746984)). The exact "tethered" test is UNVERIFIED |
| **Dealing range, premium/discount** | Range = the swing low→high (or high→low) of the leg that includes the sweep and the displacement. Long entries must be in discount (< 50%), shorts in premium. | range anchor | Secondary ([LuxAlgo](https://www.luxalgo.com/library/concept/premium-and-discount/)). UNVERIFIED-primary |
| **OTE** | Retracement into **62%–79%** of the dealing range; **70.5%** as the single-price entry. | 62/70.5/79; 50–79 | Fib levels are secondary only ([The_ICT_mentor, X](https://x.com/The_ICT_mentor/status/1876999073061900692) "0.62 and 0.79 of the current Dealing Range"; [Trader Theory, X](https://x.com/tradertheory/status/1572935415283290113)). No ICT post found stating them. UNVERIFIED-primary |
| **Power of 3 (AMD)** | See §1.3 | — | — |
| **Daily bias** | See §1.4 | — | — |

### 1.3 Power of 3: best available written definition

- **What ICT has published on it.** No primary written definition was found. ICT teaches it inside the 2022 Mentorship; re-uploads label Episode 7 as "Power Of 3" ([YouTube](https://www.youtube.com/watch?v=4Lfj0v6XhsY)), while ICT's official episode 7 is "Daily Bias & Consolidation Hurdles" ([YouTube no-rant cut](https://www.youtube.com/watch?v=QK8LUY-lgSA)).
- **Secondary definition (consistent across sources).**
  - Open → **accumulation** near the open.
  - **Manipulation**: a false move away from the open, called the "Judas swing", which sweeps liquidity and forms the session's low (for a bullish day) or high (for a bearish day).
  - **Distribution**: expansion the opposite way, closing far from the open.
  - The reference open is the **New York midnight open (00:00 ET)**, called "the true day open for the algorithm" ([tradngpatiently, X](https://x.com/tradngpatiently/status/1683231658747543552); [Trader Theory, X](https://x.com/tradertheory/status/1572935411164495875)).
- **ICT's own usage (primary), Judas swings at different opens.**
  - "The market created a Judas Swing Lower on the Opening at 9:30 am ET. They [sic] the Algorithm will seek Buyside Liquidity" ([X, 2023-01](https://x.com/I_Am_The_ICT/status/1616465423003705344))
  - "Price uses a Judas into the Opening Range Gap, then runs…" ([X, 2023-05](https://twitter.com/i/status/1658887499018534936))
  - "Wednesday and Thursdays are like Asian Ranges ahead of the Judas swing of NFP" ([X, 2022-08](https://x.com/I_Am_The_ICT/status/1564993821825433601))
- **Codeable form.**
  - `bullish_po3(day)` = the session low prints within *T* minutes after `ref_open` **and** below `ref_open`, then price closes the window above `ref_open`. Bearish mirrors.
  - Live, only the **first half** can be tested: price trades below `ref_open` and sweeps a pool. The distribution half is the outcome, not a filter.
  - `ref_open` ∈ {00:00, 08:30, 09:30, 18:00 prior day} *param*.

### 1.4 Daily bias: best available written definition

- **What ICT has published on it.** No procedure. ICT's posts show bias *asserted together with a draw on liquidity*, not derived by a stated rule:
  - "Do you see me only focusing on one bias per day? Do you see me pointing out the correct Draw On Liquidity each time?" ([X, 2025-05](https://x.com/I_Am_The_ICT/status/1923061526585385042))
  - "we had a Bullish Bias, targeting the Buyside Liquidity I shared yesterday" ([X, 2023-05](https://twitter.com/i/status/1658887499018534936))
- **The closest thing to a procedure is the 2022 checklist:** "Determine most likely expansion on the weekly candle" ([X](https://x.com/I_Am_The_ICT/status/1550816841110638592)).
- **Codeable proxies.** Each is a feature and each can serve as a *param* gate. All are UNVERIFIED as ICT rules.
  1. **Previous-day-range rule** (secondary, [abuaws21, X](https://x.com/abuaws21/status/1923037529218994316)):
     - yesterday closed above the prior day's high → bullish, draw = yesterday's high and beyond
     - closed below the prior day's low → bearish
     - closed inside → look for a sweep of one side, then expect the other
  2. **Weekly expansion:** the side of the previous-week range swept first this week; the draw is the opposite side.
  3. **Nearest unswept HTF pool:** whichever of PDH/PDL, PWH/PWL or a daily FVG is closer and unswept.
  4. **Premium/discount** of the 20-day dealing range ([Trader Theory summary of an ICT Charter model, X](https://x.com/tradertheory/status/1776916518720205137)).
  5. **Price vs midnight open** at the start of the killzone.

---

## 2. Setup rule cards

Shorthand: `DOL` = draw on liquidity (the target pool), `R` = initial risk. Bars are 1-minute unless stated; HTF context uses 15m/1h/daily.

### 2.1 NY AM Silver Bullet

| Field | Rule (default) | *param* |
|---|---|---|
| Window | Setup forms **and** entry fills inside 10:00–11:00 ET | must the sweep also be inside? (default: sweep may be 09:30–11:00) |
| Bias | §1.4 proxy; the trade must point at the `DOL` | which proxy; bias gate on/off (ICT trades "the" bias) |
| Timeframes | Context 15m/1h; execution 1m (ICT: "Running on a 1min basis" ([X thread](https://x.com/I_Am_The_ICT/status/2091492182007906623), summary only)) | 1m / 3m / 5m |
| Sweep | Raid of an intraday pool (09:30 opening range high/low, overnight high/low, a 09:30–10:00 swing) | pool set |
| Displacement + MSS | §1.2 | *k*, close vs wick |
| Entry | Limit at the **first** FVG after the MSS (§1.2 "which FVG"), at its near edge or CE | edge / CE; tethered test |
| Stop | Beyond the swing that made the sweep (ICT stops an FVG short above the swing high ([X](https://twitter.com/I_Am_The_ICT/status/1527291258531618816))) | swing ± *x* ticks; FVG far edge (tighter) |
| Target | Next opposing pool (`DOL`). **Skip if the distance to the `DOL` is below the minimum objective.** | min objective NQ: 10 / 15 / 20 pts (ICT thread: 15–20 handles on 1m, summary only). Secondary claims: 10 pts ES and 20 pts NQ ([studocu notes](https://www.studocu.com/row/document/orta-dogu-teknik-universitesi/numerical-methods/silver-bullet-hour-ict-concepts/65223591)), or 5 handles ([SirPickle, X](https://x.com/SirPickle_/status/1652344208080945153)) |
| Invalidation | No fill by 11:00 → cancel. Price reaches the `DOL` before the fill → cancel. A close through the FVG's far side before the fill → cancel. One trade per window. | — |
| Notable ICT variant | If the 09:30 Opening Range Gap's CE has not filled by 10:00, the 10:00 SB targets the ORG CE ([X](https://x.com/I_Am_The_ICT/status/1897984651186114746)) | `target = ORG_CE` mode |

### 2.2 NY PM Silver Bullet

Same as 2.1, with these changes:

- **Window:** 14:00–15:00 ET.
- **Sweep pools:** the AM session high/low, the 12:00–13:30 lunch range, a 13:30–14:00 swing.
- **Exit:** flat by 16:00 (hard rule in design.md).
- **Minimum objective:** smaller, *param* (5 handles is a fan claim ([SirPickle, X](https://x.com/SirPickle_/status/1652344208080945153))).
- Windows are UNVERIFIED-primary (§1.1).

### 2.3 London sweep-and-reverse

**"London sweep-and-reverse" is not an ICT model name.** It is design.md's label. The closest ICT constructs are the **London Open Killzone Judas swing** (Power of 3 at the midnight open) and the **London Silver Bullet** (03:00–04:00). Coded as:

| Field | Rule (default) | *param* |
|---|---|---|
| Window | Sweep inside 02:00–05:00. Entry by 05:00. | 03:00–04:00 SB-only variant |
| Bias | §1.4. The sweep must be **against** the bias (Judas), so the reversal points toward the bias. | gate on/off |
| Sweep | Raid of the **Asian range** high or low (20:00–00:00), or of the midnight-open side ([LumiTraders example: Asia SSL taken, London KZ Judas, target Asia high, X](https://twitter.com/LumiTraders/status/1710303108679569715)) | Asian window definition; also allow the PDH/PDL |
| PO3 filter | For longs the sweep is below the 00:00 open; for shorts above it | on/off |
| Displacement, MSS, FVG entry | §1.2, on 1m–5m | TF |
| Stop | Beyond the sweep extreme | ± *x* ticks |
| Target | The opposite side of the Asian range, then the PDH/PDL | first target only / scale-out |
| Invalidation | No MSS by 05:00 → no trade. Opposite side of the Asian range hit before entry → cancel. Exit by 08:20 (before the 08:30 data). | exit time |
| MNQ note | ICT's London material is forex-centric. London liquidity on MNQ is thinner, so slippage assumptions matter. UNVERIFIED for MNQ. | — |

### 2.4 OTE pullback

| Field | Rule (default) | *param* |
|---|---|---|
| Window | NY AM killzone (07:00–10:00 or 08:30–11:00) | window variant |
| Bias | §1.4 | proxy |
| Leg | A displacement leg in the bias direction that breaks structure (MSS/BOS) defines the dealing range: swing low → swing high for longs | swing N; minimum leg size in ATR |
| Entry | Limit at **70.5%** retracement, or scale across 62–79%. Prefer an overlap with an FVG or order block inside the zone ([The_ICT_mentor, X](https://x.com/The_ICT_mentor/status/1876999073061900692)). | 62 / 70.5 / 79; overlap required or not |
| Stop | Beyond the leg's origin (100%), or 100–110% ([fx4_living thread, per search summary](https://x.com/fx4_living/status/1680038308397604864)) | 100 / 110% |
| Target | The leg's high (0%), then the −27% / −62% extensions, or the next pool | target set |
| Invalidation | A close beyond 100% → void. The leg's extreme is exceeded before the fill → re-anchor or cancel. | re-anchor on/off |
| Primary status | The OTE zone levels are UNVERIFIED-primary; no ICT post stating them was found. Post dates in this doc are decoded from X post IDs. | — |

### 2.5 2022 model ("2022 ICT Mentorship model")

Directly from ICT ([X, 2022-07-23](https://x.com/I_Am_The_ICT/status/1550816841110638592)):

> "Determine most likely expansion on the weekly candle. Find Med or High impact econ event in ICT Killzones. Wait for opposing Liquidity to be taken out. Look for displacement & FVG. Target Opposing PD Arra[y]…"

| Field | Rule (default) | *param* |
|---|---|---|
| Window | ICT killzones (§1.1). ICT prefers days with a med/high-impact release inside the killzone. | news-day filter on/off; which windows |
| Bias | Weekly expansion direction (§1.4 proxy 2) | proxy |
| Sweep | Opposing liquidity: the pool on the *other* side from the weekly expansion | pool set |
| Displacement, MSS, FVG | §1.2. Community checklist: "Liquidity grab → Displacement → MSS → FVG/OB above or below .5 fib of the Displacement Range → Return to FVG or OB" ([X](https://x.com/gitahi_mararo/status/1592245070396260352), secondary) | require FVG in the discount half of the displacement range |
| Entry | Limit at the FVG (edge or CE) | — |
| Stop | Beyond the swing formed by the sweep ([ICT on FVG short stops, X](https://twitter.com/I_Am_The_ICT/status/1527291258531618816)) | ± ticks |
| Target | The opposing PD array / pool | — |
| Invalidation | A close through the stop swing before the fill. Window end. | — |
| ICT's own crossover | ICT says the 2022 model can be applied to the Silver Bullet (clip shared by [theAplustrades, X](https://x.com/theAplustrades/status/1662282445952098305)). So 2.1/2.2 are effectively this model gated to a 1-hour window, and the setups will overlap. Dedupe or tag one trade with multiple setups. | — |

**Conflict with design.md.**

- **The conflict.** ICT wants a news event inside the killzone. design.md bans trading from 15 minutes before to 15 minutes after high-impact news.
- **Compatible reading.** The news creates the sweep, and the MSS and FVG entry usually come after it. So the rule is compatible *if* the setup may form during the blackout and only the *entry* is blocked until +15 min.
- **Decision needed.** That reading needs a decision, because it changes which trades exist.

---

## 3. Look-ahead traps (must be enforced in detectors and tests)

1. **Swing confirmation lag.** A swing at bar `i` is known only at the close of `i+N`. MSS levels, liquidity pools and dealing-range anchors must use `confirmed_at`, not `i`.
2. **FVG known at candle-3 close.** The zone exists from the close of `i+1`. The earliest possible fill is bar `i+2`. Never fill on bar `i+1` itself, even if its low touched the zone.
3. **Sweep "close back inside".** It needs that bar's close. With *m* > 1 the sweep is confirmed only at the close-back bar.
4. **MSS on close.** Confirmed at that bar's close. A wick variant is confirmed intrabar, but its intrabar order is unknown on 1m OHLC.
5. **Daily bias from today's candle.** Bias features must use only data up to the decision time. For example, "today's daily candle is bullish" is look-ahead. So is "the session low printed before 10:00" when used as a filter at 09:45.
6. **Power of 3 distribution phase.** It is the outcome; only manipulation can be a filter.
7. **Dealing range and OTE re-anchoring.** If the leg's extreme extends after the zone is drawn, the zone moves. Freeze the anchors at the decision time and log any re-anchoring as a new signal.
8. **"First FVG" selection.** "First" must be counted in real time from the MSS. A later, better FVG can't be chosen after the fact.
9. **Bar timestamps.** Databento `ohlcv-1m` bars are stamped at the bar **open** (`ts_event`). A bar stamped 10:59 closes at 11:00. Window-membership checks must use the close time for anything confirmed on close. UNVERIFIED for this dataset; check against the Databento schema docs.
10. **Limit-fill realism.** A touch of the FVG edge is not a guaranteed fill. Make fill-on-touch versus a trade-through of ≥ 1 tick a *param*, and default to the conservative one.
11. **Same-bar stop and target.** If one 1m bar spans both the stop and the target, assume the stop was hit first (conservative) unless tick data says otherwise.
12. **DST.** All windows are in `America/New_York`. London and New York change clocks on different dates for about 2–3 weeks a year, which moves "London open" relative to NY time. The windows stay fixed in NY time.

---

## 4. Parameter sweep summary (for the setup-library config)

| Dimension | Values |
|---|---|
| NY AM killzone | 07:00–10:00, 08:30–11:00, 07:00–09:00 |
| London killzone | 02:00–05:00, 02:00–04:00 |
| London SB | 03:00–04:00 (default), 02:00–03:00 |
| Extra SB windows | off, 07:00–08:30 |
| Swing N | 1, 2 |
| Sweep close-back bars *m* | 1, 3, 5 |
| Displacement *k*·ATR | 1.0, 1.5, 2.0 |
| MSS break | close, wick |
| FVG entry | edge, CE |
| FVG selection | first, first-tethered |
| SB minimum objective (NQ points) | 10, 15, 20 |
| OTE entry | 62, 70.5, 79 |
| Bias proxy | prev-day range, weekly expansion, nearest pool, premium/discount, midnight open, none |
| PO3 ref open | 00:00, 08:30, 09:30, 18:00 |
| News handling (2022 model) | blackout blocks the setup; blackout blocks entry only |

Every one of these counts as a trial for the Deflated Sharpe Ratio and Probability of Backtest Overfitting in design.md. A full grid is thousands of trials, so a small, pre-registered default set (the bold/first value in each row) should be tested first.

---

## 5. What is still UNVERIFIED and how to close it

- **Primary video timestamps** for killzone edges, Silver Bullet windows, OTE levels, Power of 3 and daily bias. Fix: allow `youtube.com` (or a transcript source) in the session network, then pull transcripts of the 2022 Mentorship (playlist `PLVgHx4Z63paYiFGQ56PjTF1PGePL3r69s`) and the 2023 "ICT Silver Bullet Time Based Trading Model" lecture.
- **Full text of ICT's posts** quoted here from search excerpts. Fix: allow `x.com`.
- **The "tethered to the Dealing Range" test, and the 15–20 handle objective.** These come from a search summary of a single thread ([X](https://x.com/I_Am_The_ICT/status/2091492182007906623)).

## Sources

Primary (ICT's own posts; all read through search-engine excerpts only):

- 2022 model checklist — https://x.com/I_Am_The_ICT/status/1550816841110638592
- NY killzone 07:00–10:00 — https://x.com/I_Am_The_ICT/status/1903822271514284280
- 10:00 Silver Bullet / ORG CE — https://x.com/I_Am_The_ICT/status/1897984651186114746
- First FVG tethered to the dealing range — https://x.com/I_Am_The_ICT/status/2091492182007906623
- 1st Presented FVG — https://x.com/I_Am_The_ICT/status/1988248421438746984
- FVG short stop — https://twitter.com/I_Am_The_ICT/status/1527291258531618816
- Relative equal highs/lows as DOL — https://x.com/I_Am_The_ICT/status/1853419538274017361
- Judas swing at 09:30 — https://x.com/I_Am_The_ICT/status/1616465423003705344
- Judas into ORG, bias + BSL — https://twitter.com/i/status/1658887499018534936
- NFP Judas — https://x.com/I_Am_The_ICT/status/1564993821825433601
- One bias per day / DOL — https://x.com/I_Am_The_ICT/status/1923061526585385042
- CISD as ICT concept — https://twitter.com/I_Am_The_ICT/status/1840447752372883706
- Breaker / change in state of delivery — https://x.com/I_Am_The_ICT/status/1675266686478438402
- Silver Bullet post (text not retrievable) — https://x.com/I_Am_The_ICT/status/1640362563845095433

Primary-adjacent (YouTube titles; content not viewed):

- 2022 ICT Mentorship playlist — https://www.youtube.com/playlist?list=PLVgHx4Z63paYiFGQ56PjTF1PGePL3r69s
- Episode 6 — https://www.youtube.com/watch?v=Bkt8B3kLATQ
- Episode 7 (no-rant cut, "Daily Bias & Consolidation Hurdles") — https://www.youtube.com/watch?v=QK8LUY-lgSA
- Episode 2 re-upload — https://www.youtube.com/watch?v=WpWEXpVsPS4

Secondary (used only for defaults, all marked UNVERIFIED-primary):

- fx4_living (SB windows) — https://x.com/fx4_living/status/1663059633836007424
- Liq_Sniper (SB windows, types) — https://x.com/Liq_Sniper/status/1716480689766547932
- Frank369 (07:00–08:30 window) — https://x.com/FrankOf369/status/1746238304377311662
- The_ICT_Academy (killzones) — https://x.com/The_ICT_Academy/status/1758524491724919242
- Trader Theory (killzones, PO3, OTE, pools) — https://x.com/tradertheory/status/1548247537634537473, https://x.com/tradertheory/status/1572935411164495875, https://x.com/tradertheory/status/1572935415283290113, https://x.com/tradertheory/status/1841932475054133372, https://x.com/tradertheory/status/1776916518720205137
- tradngpatiently (midnight open PO3) — https://x.com/tradngpatiently/status/1683231658747543552
- abuaws21 (daily bias) — https://x.com/abuaws21/status/1923037529218994316
- The_ICT_mentor (OTE) — https://x.com/The_ICT_mentor/status/1876999073061900692
- gitahi_mararo (2022 checklist) — https://x.com/gitahi_mararo/status/1592245070396260352
- fx4_living (2022 entry thread) — https://x.com/fx4_living/status/1680038308397604864
- theAplustrades (2022 model on SB) — https://x.com/theAplustrades/status/1662282445952098305
- SirPickle (PM SB, 5 handles) — https://x.com/SirPickle_/status/1652344208080945153
- LumiTraders (London Judas example) — https://twitter.com/LumiTraders/status/1710303108679569715
- casper_smc (FVG) — https://twitter.com/casper_smc/status/1787828626244641206
- TradingView killzone scripts listing — https://in.tradingview.com/scripts/ictkillzones/
- backtrex killzone times — https://backtrex.com/en/blog/ict-kill-zone-times-sessions
- studocu SB notes — https://www.studocu.com/row/document/orta-dogu-teknik-universitesi/numerical-methods/silver-bullet-hour-ict-concepts/65223591
- smc library — https://github.com/joshyattridge/smart-money-concepts
- ICT Ultimate Algorithmic Engine — https://it.tradingview.com/script/u2ItPJf6-ICT-Ultimate-Algorithmic-Engine/
- LuxAlgo premium/discount — https://www.luxalgo.com/library/concept/premium-and-discount/
