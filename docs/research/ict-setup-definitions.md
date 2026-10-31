# Research: Codeable ICT setup definitions

Resolves [#2](https://github.com/DaltonDom/moon-ai/issues/2) (child of the map [#1](https://github.com/DaltonDom/moon-ai/issues/1)). Re-verification pass for [#18](https://github.com/DaltonDom/moon-ai/issues/18) on 2026-10-31: see [§0.1](#01-re-verification-pass-18-2026-10-31). Builds on [ict-ml-trading-bot.md](ict-ml-trading-bot.md) §1.3 and the setup list in [design.md](../design.md).

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

### 0.1 Re-verification pass (#18, 2026-10-31)

**Result: no item could be upgraded to CONFIRMED-primary. Two items changed, one attribution was corrected, and the rest stay UNVERIFIED.** The session network now reaches youtube.com and x.com, but none of the *terms-compliant* ways to read the content worked:

| Route | Outcome |
|---|---|
| Video → text via Gemini's YouTube-URL input (the only compliant transcript route in [youtube-watcher.md](https://github.com/DaltonDom/moon-ai/blob/research/youtube-watcher/docs/research/youtube-watcher.md) §3.4) | `generativelanguage.googleapis.com` refused by the egress proxy; no Gemini key in the environment. Blocked |
| YouTube Data API (video metadata) | `www.googleapis.com` refused by the proxy. Blocked |
| Transcript scrapers, caption downloads, yt-dlp + Whisper, scripted watch-page or "Show transcript" scraping | Ruled out by the project's ToS reading (youtube-watcher.md §3.2–3.3, §4). Not attempted |
| YouTube oEmbed (`youtube.com/oembed`, official) | Works, but returns only title and channel. Used to check which cited videos are ICT's own uploads |
| ICT's posts on x.com | WebFetch gets HTTP 402. The plain HTML only serves the page shell; reading the post text would need a spoofed browser user-agent, which was not done. `publish.twitter.com` oEmbed refused by the proxy. Blocked |
| Third-party transcript of the 2023 lecture (glasp.co) | Host not allowed. Read only through a search-engine summary |

So the evidence below is still **search-engine excerpts**, now checked a second time with new queries. A second excerpt that matches the first raises confidence a little, but it is not a primary read. What it takes to close the remaining items is in §5.

**Item-by-item status**

| Item ([#18](https://github.com/DaltonDom/moon-ai/issues/18)) | Status | What the second pass found |
|---|---|---|
| Killzone edges (London 02:00–05:00, NY 07:00–10:00 / 08:30–11:00, Asian, London close, NY PM) | **Still UNVERIFIED** | No ICT post or video timestamp stating London, Asian or London-close edges turned up. The secondary consensus is unchanged: London 02:00–05:00, NY 07:00–10:00, London close 10:00–12:00, Asian 20:00–00:00 ([Trader Theory, X](https://x.com/trader_theory/status/1548247537634537473), [Trader Theory, X](https://x.com/Trader_Theory/status/1596195780095668225)). One fan post gives NY AM as 08:30–11:00 and London 02:00–05:00 with "3:30 sweet spot" ([TheHunterSetup, X](https://x.com/TheHunterSetup/status/1877496736333066321)). ICT's own "7am–10am is technically NY Killzone" post (§1.1) is still the only primary line, and it is still excerpt-only |
| SB windows 03:00–04:00 / 10:00–11:00 / 14:00–15:00 | **Still UNVERIFIED-primary, better supported** | A search summary of a third-party transcript of the **2023 Mentorship "ICT Silver Bullet Time Based Trading Model" lecture (13 May 2023)** says the lecture gives **3–4 AM, 10–11 AM and 2–3 PM New York local time** ([glasp.co transcript page](https://glasp.co/youtube/p/2023-ict-mentorship-ict-silver-bullet-time-based-trading-model), not opened; host blocked). No timestamp. This is the first source that ties all three windows to the lecture itself rather than to fan posts. The official upload's video ID was not found |
| PM SB 14:00–15:00 | **Still UNVERIFIED-primary** | As above. Same three-window set repeated by many fan accounts ([fx4_living](https://x.com/fx4_living/status/1663059633836007424), [Liq_Sniper](https://x.com/Liq_Sniper/status/1716480689766547932), [TraderDiegoX](https://x.com/TraderDiegoX/status/2085271406565310773)). No conflicting PM window found |
| Extra SB window 07:00–08:30 ("added in 2023") | **Still UNVERIFIED; changed in detail** | Search summaries date the claim to a fan post of **28 Sep 2023** ("new official silver bullet time window of 7 am to 8:30 am"), crediting @I_Am_The_ICT. A Jan 2024 post calls it the "final" window and ties it to ICT's **90-minute cycles** ([Frank369, X](https://x.com/FrankOf369/status/1746238304377311662), [Frank369, X](https://x.com/FrankOf369/status/1765444311100096583)). No ICT post or video was found stating it. Note it is a **90-minute** window, not 1 hour, and it overlaps the 08:30 data release, so it collides with the news blackout. Keep it off by default |
| OTE levels 62 / 70.5 / 79 | **Still UNVERIFIED; 70.5 weakened** | No ICT post states the levels. 62% and 79% are consistent across secondary sources ([The_ICT_mentor, X](https://x.com/The_ICT_mentor/status/1876999073061900692): "0.62 and 0.79 of the current Dealing Range"). Per the search summary, **70.5% appeared in only one secondary source** (a The5ers article), and no ICT-attributed source gave it. **Change:** default entry moves from 70.5% to the **62% zone edge** (the level every source agrees on), with 70.5% and 79% kept as variants |
| "First FVG tethered to the Dealing Range" test | **Still UNVERIFIED; changed in detail** | A second independent search excerpt reproduces ICT's post: "When you are selecting FVGs, the first one that is tethered to the Dealing Range, as I define them, whether a Hexadecant, Octant or Quadrant…", and says this "increases the Silver Bullet framework beyond your reports and my initial claims" ([ICT, X](https://x.com/I_Am_The_ICT/status/2091492182007906623)). A **reply** in the thread (not ICT) defines a hexadecant as 1/16 of the range, i.e. levels at multiples of 0.0625. **Change:** the tethered test is now a concrete rule with a grid parameter (§1.2) |
| 15–20 handle minimum target | **Still UNVERIFIED; changed in detail** | A second search excerpt again quotes ICT's thread: "Running on a 1min basis, use a 15 - 20 handle objective" ([X](https://x.com/I_Am_The_ICT/status/2091492182007906623)). Separately, the search summary of the 2023 lecture transcript says the **minimum target is 10 points for index futures** (15 pips for forex). These two may both hold: 10 points as the 2023 baseline for any SB, and 15–20 handles for the 2026 "tethered FVG on 1m" refinement. **Change:** the 10-point value now has a lecture-level source and becomes the default; 15 and 20 stay as variants tied to the tethered-FVG mode |

**Attribution correction (from oEmbed).** The "ICT's official episode 7" link in §1.3 (`QK8LUY-lgSA`) is a **re-upload by the SirTrader channel**, not ICT's. Also re-uploads: `WpWEXpVsPS4` and `4Lfj0v6XhsY` (Melody Fx Academy). Confirmed on ICT's own channel (@InnerCircleTrader) via oEmbed: the 2022 Mentorship playlist `PLVgHx4Z63paYiFGQ56PjTF1PGePL3r69s`, the Introduction (`kt6V4ai60fI`), Episode 3 (`nQfHZ2DEJ8c`) and Episode 6 (`Bkt8B3kLATQ`).

---

## 1. Shared definitions (used by every setup)

### 1.1 Time windows (`America/New_York`, DST-aware)

| Window | Default | Variants to test (*param*) | Evidence |
|---|---|---|---|
| Asian range | 20:00–00:00 | 19:00–00:00; 18:00–00:00 (from the CME reopen) | Secondary consensus ([The_ICT_Academy, X](https://x.com/The_ICT_Academy/status/1758524491724919242), [Trader Theory, X](https://x.com/tradertheory/status/1548247537634537473)). UNVERIFIED-primary |
| London Open Killzone | 02:00–05:00 | 02:00–04:00 | Secondary consensus (same sources). UNVERIFIED-primary (#18: still unverified) |
| NY AM Killzone | **07:00–10:00** (forex framing); **08:30–11:00** (index framing) | 07:00–09:00; 07:00–09:30 | ICT, 2025: "Anytime between 7am and 10am is technically NY Killzone… the question is are you able [to trade it all]" ([X](https://x.com/I_Am_The_ICT/status/1903822271514284280)). The same search excerpt says a user cited ICT's 2022 mentorship as placing it at 08:30–11:00, and ICT's reply treats sub-windows as personal "operating hours". 08:30–11:00 / 13:30–16:00 for index futures is a secondary claim ([TradingView killzone script listing](https://in.tradingview.com/scripts/ictkillzones/), [backtrex](https://backtrex.com/en/blog/ict-kill-zone-times-sessions)) |
| London Close Killzone | 10:00–12:00 | — | Secondary consensus. UNVERIFIED-primary |
| NY PM session | 13:30–16:00 | 13:00–16:00 | Secondary ([TradingView killzone listing](https://in.tradingview.com/scripts/ictkillzones/)). UNVERIFIED-primary |
| **London Silver Bullet** | **03:00–04:00** | 02:00–03:00 (likely a mix-up with the London killzone start or a UTC conversion) | Fan-account posts crediting ICT's Silver Bullet lesson ([fx4_living, X](https://x.com/fx4_living/status/1663059633836007424), [Liq_Sniper, X](https://x.com/Liq_Sniper/status/1716480689766547932)). A search summary found **no source at all** for 02:00–03:00 as a Silver Bullet hour. The 2023 lecture's third-party transcript also gives 3–4 AM (§0.1). UNVERIFIED-primary but no conflicting evidence (#18: still unverified, better supported) |
| **NY AM Silver Bullet** | **10:00–11:00** | — | ICT: "If it fails to fill that number, use 10:00 am ET Silver Bullet to ORG C.E. long" ([X](https://x.com/I_Am_The_ICT/status/1897984651186114746)). The start time is primary; the 1-hour length is secondary |
| **NY PM Silver Bullet** | **14:00–15:00** | — | Secondary consensus (same fan posts), and a search summary of a third-party transcript of the 2023 Silver Bullet lecture lists 3–4 AM, 10–11 AM and 2–3 PM NY time (§0.1). UNVERIFIED-primary (#18: still unverified, better supported) |
| Extra Silver Bullet windows | off | 07:00–08:30; 15:00–16:00 | Fan accounts report ICT adding a 07:00–08:30 window, first reported 28 Sep 2023, tied to his 90-minute cycles ([Frank369, X](https://x.com/FrankOf369/status/1746238304377311662), per search summary). Overlaps the 08:30 release, so the news blackout cuts into it. UNVERIFIED (#18: still unverified) |

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
| **Which FVG** | The **first** FVG after the MSS that is "tethered to the Dealing Range". Codeable test (#18): the FVG zone `[lo, hi]` contains, or lies within *t* ticks of, a level `range_low + j/G · (range_high − range_low)` for integer `j`, where *G* is the grid (4 = quadrant, 8 = octant, 16 = hexadecant). Uses the dealing range frozen at the decision time (§3 trap 7). | first FVG only; first tethered FVG; any FVG; grid *G* = 4 / 8 / 16; tolerance *t* = 0 / 2 ticks | ICT: "When you are selecting FVGs, the first one that is tethered to the Dealing Range, as I define them, whether a Hexadecant, Oct[ant]…" ([X](https://x.com/I_Am_The_ICT/status/2091492182007906623); the rest of the text is from a search summary). "1st Presented FVG" posts ([X](https://x.com/I_Am_The_ICT/status/1988248421438746984)). The exact "tethered" test is UNVERIFIED. #18: a second excerpt matches the post text; the 1/16 hexadecant definition comes from a reply, not ICT. The grid-overlap test above is our reading |
| **Dealing range, premium/discount** | Range = the swing low→high (or high→low) of the leg that includes the sweep and the displacement. Long entries must be in discount (< 50%), shorts in premium. | range anchor | Secondary ([LuxAlgo](https://www.luxalgo.com/library/concept/premium-and-discount/)). UNVERIFIED-primary |
| **OTE** | Retracement into **62%–79%** of the dealing range; **62%** (the zone edge) as the single-price entry (changed in #18 from 70.5%). | 62/70.5/79; 50–79 | Fib levels are secondary only ([The_ICT_mentor, X](https://x.com/The_ICT_mentor/status/1876999073061900692) "0.62 and 0.79 of the current Dealing Range"; [Trader Theory, X](https://x.com/tradertheory/status/1572935415283290113)). No ICT post found stating them. 70.5% has the weakest support (one secondary article, per search summary). UNVERIFIED-primary (#18: still unverified) |
| **Power of 3 (AMD)** | See §1.3 | — | — |
| **Daily bias** | See §1.4 | — | — |

### 1.3 Power of 3: best available written definition

- **What ICT has published on it.** No primary written definition was found. ICT teaches it inside the 2022 Mentorship; re-uploads label Episode 7 as "Power Of 3" ([YouTube](https://www.youtube.com/watch?v=4Lfj0v6XhsY)), while another re-upload titles episode 7 "Daily Bias & Consolidation Hurdles" ([SirTrader's no-rant cut, YouTube](https://www.youtube.com/watch?v=QK8LUY-lgSA)). Correction (#18): both are third-party re-uploads, per YouTube oEmbed; ICT's own episode 7 title was not checked.
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
| Target | Next opposing pool (`DOL`). **Skip if the distance to the `DOL` is below the minimum objective (default 10 NQ points).** | min objective NQ: **10** / 15 / 20 pts. 10 pts for index futures is from the 2023 SB lecture (third-party transcript, search summary only; #18). 15–20 handles on 1m is from ICT's 2026 thread, tied to the tethered-FVG selection (two matching search excerpts; #18). Test 15/20 together with "first tethered FVG". Secondary claims: 10 pts ES and 20 pts NQ ([studocu notes](https://www.studocu.com/row/document/orta-dogu-teknik-universitesi/numerical-methods/silver-bullet-hour-ict-concepts/65223591)), or 5 handles ([SirPickle, X](https://x.com/SirPickle_/status/1652344208080945153)) |
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
| Entry | Limit at the **62%** retracement (zone edge; changed in #18 from 70.5%), or at 70.5% / 79%, or scale across 62–79%. Prefer an overlap with an FVG or order block inside the zone ([The_ICT_mentor, X](https://x.com/The_ICT_mentor/status/1876999073061900692)). | 62 / 70.5 / 79; overlap required or not |
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
| Tethered grid *G* (only with first-tethered) | 8, 4, 16 |
| Tethered tolerance *t* (ticks) | 0, 2 |
| SB minimum objective (NQ points) | **10**, 15, 20 (15/20 paired with first-tethered) |
| OTE entry | **62**, 70.5, 79 |
| Bias proxy | prev-day range, weekly expansion, nearest pool, premium/discount, midnight open, none |
| PO3 ref open | 00:00, 08:30, 09:30, 18:00 |
| News handling (2022 model) | blackout blocks the setup; blackout blocks entry only |

Changes from #18: OTE default moved from 70.5 to 62; SB minimum objective default fixed at 10 (it was the first value already, now with a lecture-level source); the tethered test gained the grid and tolerance dimensions; the 07:00–08:30 window is noted as 90 minutes long and overlapping the 08:30 release. Nothing was removed.

Every one of these counts as a trial for the Deflated Sharpe Ratio and Probability of Backtest Overfitting in design.md. A full grid is thousands of trials, so a small, pre-registered default set (the bold/first value in each row) should be tested first.

---

## 5. What is still UNVERIFIED and how to close it

After #18, every item below is still open. Allowing `youtube.com` and `x.com` was not enough: the blocker is now a **compliant read path**, not the domain list (§0.1).

- **Primary video timestamps** for killzone edges, Silver Bullet windows (incl. 07:00–08:30), OTE levels, the minimum objective, Power of 3 and daily bias. Fix, either:
  1. allow `generativelanguage.googleapis.com` in the MoonAI environment and add a Gemini API key as an environment secret (the decision is in [#14](https://github.com/DaltonDom/moon-ai/issues/14)), then run Gemini's YouTube-URL input over the 2022 Mentorship playlist (`PLVgHx4Z63paYiFGQ56PjTF1PGePL3r69s`) and the 2023 "ICT Silver Bullet Time Based Trading Model" lecture (13 May 2023; official video ID still to find); or
  2. the user watches the specific segments and writes timestamped notes into the repo (the youtube-watcher fallback).
  Allowing `www.googleapis.com` too would let the Data API list the official uploads and find the lecture's video ID.
- **Full text of ICT's posts.** x.com answers WebFetch with 402 and serves no post text to plain requests. Fix: allow `publish.twitter.com` (the official oEmbed endpoint returns post text), or the user pastes the post texts.
- **The "tethered to the Dealing Range" test, and the 15–20 handle objective.** Now two matching search excerpts of one thread ([X](https://x.com/I_Am_The_ICT/status/2091492182007906623)); still not read on the page.

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

Primary-adjacent (YouTube titles; content not viewed). Channel checked with YouTube oEmbed in #18:

- 2022 ICT Mentorship playlist (ICT's channel) — https://www.youtube.com/playlist?list=PLVgHx4Z63paYiFGQ56PjTF1PGePL3r69s
- ICT Mentorship 2022 Introduction (ICT's channel) — https://www.youtube.com/watch?v=kt6V4ai60fI
- 2022 ICT Mentorship Episode 3 (ICT's channel) — https://www.youtube.com/watch?v=nQfHZ2DEJ8c
- 2022 ICT Mentorship Episode 6 (ICT's channel) — https://www.youtube.com/watch?v=Bkt8B3kLATQ
- Episode 7 no-rant cut (re-upload, SirTrader) — https://www.youtube.com/watch?v=QK8LUY-lgSA
- Episode 2 and Episode 7 "Power Of 3" (re-uploads, Melody Fx Academy) — https://www.youtube.com/watch?v=WpWEXpVsPS4, https://www.youtube.com/watch?v=4Lfj0v6XhsY

Added in #18 (search-engine summaries only, not opened):

- 2023 Silver Bullet lecture, third-party transcript (glasp.co, host not allowed) — https://glasp.co/youtube/p/2023-ict-mentorship-ict-silver-bullet-time-based-trading-model
- Trader Theory killzone posts — https://x.com/trader_theory/status/1548247537634537473, https://x.com/Trader_Theory/status/1596195780095668225
- TheHunterSetup (time elements) — https://x.com/TheHunterSetup/status/1877496736333066321
- TraderDiegoX (SB windows incl. premarket 07:00–08:30) — https://x.com/TraderDiegoX/status/2085271406565310773
- Frank369 (90-minute cycles) — https://x.com/FrankOf369/status/1765444311100096583
- ICT, 1st Presented FVG short — https://x.com/I_Am_The_ICT/status/1857446886002553100

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
