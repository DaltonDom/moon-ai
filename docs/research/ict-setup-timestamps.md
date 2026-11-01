# Research: Timestamps for the remaining ICT setup rules

Resolves [#21](https://github.com/DaltonDom/moon-ai/issues/21) (child of the map [#1](https://github.com/DaltonDom/moon-ai/issues/1); follows [#18](https://github.com/DaltonDom/moon-ai/issues/18) and [#20](https://github.com/DaltonDom/moon-ai/issues/20)). Compiled 2026-10-31. Proposes changes to [`ict-setup-definitions.md`](https://github.com/DaltonDom/moon-ai/blob/research/ict-setup-definitions/docs/research/ict-setup-definitions.md) (branch `research/ict-setup-definitions`), listed as a patch list in §3. That branch was not edited.

> **How to read this document.**
>
> - **Sources.** Only Michael J. Huddleston's (ICT's) own output: videos on his YouTube channel (`UCtjxa77NqamhVC8atV85Rog`, checked with the YouTube Data API) and posts by `@I_Am_The_ICT` on X.
> - **Read paths.** YouTube Data API v3 (search, playlistItems, videos); Gemini (`gemini-flash-latest`) with the YouTube URL as input, clipped with `start_offset`/`end_offset` at `MEDIA_RESOLUTION_LOW`; X posts through the official oEmbed endpoint (`publish.twitter.com/oembed`). No transcript scrapers, caption downloads or page scraping.
> - **Verdicts.**
>   - **Confirmed (post read)**: the post text came back from X's oEmbed, i.e. a primary read.
>   - **Confirmed (Gemini transcription)**: Gemini's transcription is the only evidence, but **two independent passes** (a coarse pass over the whole video or a long range, then a narrow clip) returned the same wording. Treat the quote as near-verbatim, not as a certified transcript.
>   - **Single pass**: one Gemini pass only. Lower confidence.
>   - **Still unverified**: no ICT source was read that states it.
> - **Timestamps.** `mm:ss` from the start of the video, taken from the narrow check pass where one was run. Gemini's coarse-pass timestamps were sometimes far off (one quote was placed at 24:39 in the coarse pass and found at 42:38 in narrow passes), so only check-pass timestamps are given as firm. Expect ±10 s.
> - Nothing here is financial advice.

## 1. Verdicts

| # | Item | Verdict | Evidence |
|---|---|---|---|
| 1 | SB windows 03:00–04:00, 10:00–11:00, 14:00–15:00 ET | **Confirmed (Gemini transcription)** | Title slides and speech in the 2023 lecture [`tRq1hyGGtl4`](https://www.youtube.com/watch?v=tRq1hyGGtl4) at 08:12, 12:30, 14:10 |
| 2 | SB 07:00–08:30 is ICT's own window | **Confirmed (Gemini transcription), as an optional extra** | ICT, 27 Sep 2023 PM review [`v_iJlBKYmUc`](https://www.youtube.com/watch?v=v_iJlBKYmUc&t=3243s) at 54:03: "If you really, really want it, you can do 7:00 in the morning to 8:30." |
| 3a | Minimum objective 10 points (index futures) | **Confirmed (Gemini transcription)**, with a definition change | Slide at 00:20 and speech at ~00:40 of `tRq1hyGGtl4`: "10 points or 40 ticks". It is the *framework* (best-case delivery available), not the trade's entry-to-exit range |
| 3b | 15–20 handle objective (2026 thread) | **Still unverified** | oEmbed cuts the post off before that sentence. Search excerpts only (as in #18) |
| 4 | Tethered FVG: post text | **Partly confirmed (post read)** | oEmbed returns the opening through "…whether a Hexadecant, Octant or…" ([X](https://x.com/I_Am_The_ICT/status/2091492182007906623), 23 Aug 2026). The rest is not served |
| 4b | Tethered FVG: grid test 4/8/16 | **Partly confirmed** | ICT names hexadecant (1/16) and octant (1/8) himself. "Quadrant" and the meaning of "tethered" are past the cut-off. The overlap test is still our reading |
| 5a | NY killzone, index framing 08:30–11:00 | **Confirmed (Gemini transcription)** | 2022 Mentorship Ep. 2 [`tmeCWULSTHc`](https://www.youtube.com/watch?v=tmeCWULSTHc&t=2558s) at 42:38: "I like watching it around 8:30 in the morning, New York local time, to 11:00" |
| 5b | NY killzone 07:00–10:00 | **Confirmed (post read)** | [X, 2025-03-23](https://x.com/I_Am_The_ICT/status/1903822271514284280): "Anytime between 7am and 10am is technically NY Killzone..." |
| 5c | London 02:00–05:00, Asian, London close | **Still unverified** | Not stated in the 2022 Mentorship Introduction, Ep. 2 or Ep. 4 (full passes). Candidate sources found (§4) but not read: Gemini daily quota ran out |
| 6 | OTE 62 / 70.5 / 79 | **Still unverified** | In the 2022 episodes read, ICT only uses the 50% "equilibrium" (Ep. 2 ~35:34, Ep. 4 ~02:10, single pass). Candidate: 2017 "OTE Primer" [`Cg0-CFJOJvg`](https://www.youtube.com/watch?v=Cg0-CFJOJvg), not read |

## 2. Evidence by item

### 2.1 Silver Bullet windows (item 1)

**Video:** "2023 ICT Mentorship - ICT Silver Bullet Time Based Trading Model", ID **`tRq1hyGGtl4`**, ICT's channel, published 2023-05-14 21:00 UTC (the evening of 13 May in New York), 19:16 long. This is the official upload that #18 could not find. Found with the Data API `search` on ICT's channel.

Passes: one coarse pass over the whole video, then narrow checks of 08:00–09:40 and 12:20–14:40. Both agree.

| Time | On-screen slide (check pass) | Spoken (check pass) |
|---|---|---|
| 08:12 | "SETUP TIME: 3:00 AM – 4:00 AM / \* ALWAYS NEW YORK LOCAL TIME / The London Open Silver Bullet" | "First setup time is 3:00 a.m. to 4:00 a.m. Now, we're always referring to New York local time… If we're observing Daylight Saving Time, then you observe Daylight Saving Time." |
| 12:30 | "SETUP TIME: 10:00 AM – 11:00 AM / \* ALWAYS NEW YORK LOCAL TIME / The AM Session Silver Bullet" | "The second one in our continuing list of ICT Silver Bullet setups is the AM session. Now, this one is focusing on the 10:00 a.m. to 11:00 a.m., always New York local time." |
| 14:10 | "SETUP TIME: 2:00 PM – 3:00 PM / \* ALWAYS NEW YORK LOCAL TIME / The PM Session Silver Bullet" | "And finally, we have our last ICT Silver Bullet here, which is framed on 2:00 p.m. to 3:00 p.m., New York local time, and this is the PM Session ICT Silver Bullet setup." |

Related rules from the same lecture:

- **The window gates the setup and entry, not the exit** (check pass, 13:36): "the trade is many times held in duration longer than the window that the framework and entry is derived from. So it's not a in-and-out within the same hour, it means that you're looking for the setup to form to get you into the trade within the scope of 10:00 to 11:00 New York local time." The coarse pass also has (≈11:26, single pass): "The entry is taken inside of that 60-minute window… your trade many times will be held over the 4:00 hour and into 5:00 in the morning."
- **Which FVG** (≈09:30, check pass): "what we're looking for is a classic ICT fair value gap to form between 3:00 a.m. and 4:00 a.m." The coarse pass also has (≈15:26, single pass) "taking the first Fair Value Gap that forms inside of" the 14:00–15:00 window.
- **Setup types slide** (08:00, check pass): "1) Previous Daily High/Low Draw On Liquidity. 2) Previous Session High/Low… 3) Previous Week High/Low… 4) Return To Current/Old New Week Opening Gap. 5) Expansion Away From Current/Old New Week Opening Gap. 6) Classic ICT Optimal Trade Entry. 7) Confluence Of The 2022 ICT Mentorship YouTube Model. \* The Main Emphasis Is Determining The Next Likely Draw In The Price Action." This confirms the 2022-model crossover noted in §2.5 of the definitions doc.

### 2.2 The 07:00–08:30 window (item 2)

**Video:** "ICT Mentorship 2023 - September 27, 2023 PM Session Market Review", ID **`v_iJlBKYmUc`**, ICT's channel, published 2023-09-27 20:31 UTC. That is the day before the fan post of 28 Sep 2023 that #18 traced the claim to. Found by listing ICT's uploads from 15 Sep to 15 Oct 2023 with the Data API.

Passes: a coarse pass over the whole video (73:28) found it, and a narrow check of 52:40–56:00 returned the same words.

> **53:30** "I gave you a Silver Bullet model between 10:00 in the morning and 11:00 in the morning, New York local time. That makes it so easy…"
> **53:51** "I mean, I literally made it really easy for you. You have a Silver Bullet at 2:00 to 3:00, you have a Silver Bullet at 3:00 to 4:00, New York local time. You have one at 3:00 in the morning to 4:00 in the morning, London session."
> **54:03** "If you really, really want it, you can do 7:00 in the morning to 8:30."
> **54:09** "Yep. Just love tucking them in there, real deep. Real deep in the videos."

Reading:

- 07:00–08:30 **is ICT's own window**, said live, but framed as optional ("if you really, really want it"). It is 90 minutes, not 60. The 1-hour windows from the May lecture stay the core set.
- The "3:00 to 4:00, New York local time" next to "2:00 to 3:00" at 53:51 is either a slip of the tongue or a transcription error. Both passes have it. It does not match the lecture slides, which are unambiguous (14:00–15:00). Don't add a 15:00–16:00 window on the strength of it.
- The window overlaps the 08:30 data release, so with design.md's ±15 min blackout only 07:00–08:15 is usable on days with an 08:30 release. Keep it **off by default**, as now.

### 2.3 Minimum objective (item 3)

**10 points (2023 lecture), confirmed (Gemini transcription).** `tRq1hyGGtl4`; coarse pass and a narrow 00:00–02:40 check agree.

- Slide (00:20): "The minimum Trade framework should be 10 Points [or 40 Ticks] for Indices. The minimum Trade framework should be 15 Pips for Forex pairs. \* Framework is the best case Price Delivery that you expect to see, not your actual Trade Entry to Exit range. 10 Handles for Indices is the same to me as 20 Pips in Forex. 5 Handles for Indices is the same to me as 10 Pips in Forex." (The last three lines are from the coarse pass only.)
- Speech (~00:40): "The minimum trade framework should be 10 points, or 40 ticks, for index futures or indices."
- Speech (~01:54): "the minimum framework is, it has to at least offer the potential for 10 points or 10 handles, which is equivalent to 40 ticks."
- Applied (12:51–13:36, check pass): "So it obviously meets the criteria of a minimum of 10 handles, in framework. It does not mean you're trying to get 10 handles, it just means that it offers 10 handles. So, going short here, collecting five handles…"

So the 10 points is a **filter on the distance from entry to the draw on liquidity**, not a take-profit. ICT's own example takes 5 handles. The lecture's examples are on the E-mini S&P (ES), and ICT gives one number for "indices". He does not give a separate NQ figure.

**15–20 handles (2026 thread), still unverified.** oEmbed for [status 2091492182007906623](https://x.com/I_Am_The_ICT/status/2091492182007906623) stops before "Running on a 1min basis, use a 15 - 20 handle objective", so that sentence is still known only from search excerpts. The two figures do not conflict: 10 is the 2023 floor for any SB; 15–20 is the later, tethered-FVG-on-1m refinement.

### 2.4 Tethered FVG post (item 4)

oEmbed text (primary read), posted 23 Aug 2026:

> "Reading letters mailed to me, got a note from a Quant, who ran statistics on my concepts. I will answer openly, I trust this will suffice...
>
> When you are selecting FVGs, the first one that is tethered to the Dealing Range, as I define them, whether a Hexadecant, Octant or…"

That is all oEmbed returns. X's oEmbed truncates long posts with "…", and there is no other compliant read path for the remainder. **The full text is not obtained.**

On the grid: ICT himself names **Hexadecant** (16 parts) and **Octant** (8 parts) as the dealing-range divisions. The "or…" almost certainly continues to "Quadrant" (the search excerpts in #18 say so), but that word is past the cut-off. So *G* ∈ {8, 16} is ICT's, *G* = 4 is likely, and the exact meaning of "tethered" (touching a grid level? starting from one?) is not stated in the readable text. The grid-overlap test in the definitions doc stays our reading.

### 2.5 Killzone edges (item 5)

Read with Gemini (whole video, one question covering killzone times, OTE levels and minimum targets) from the 2022 Mentorship playlist `PLVgHx4Z63paYiFGQ56PjTF1PGePL3r69s` (41 videos, listed with the Data API): the **Introduction** (`kt6V4ai60fI`), **Episode 2** (`tmeCWULSTHc`) and **Episode 4** (`L-ReMHiavPM`).

- **NY, index framing: 08:30–11:00, confirmed (Gemini transcription).** Ep. 2, 42:33–42:53 (coarse pass, then a 35:00–49:36 pass, then a narrow 42:00–43:30 check):
  > "and you can't watch the time frame around the opening of the index futures. And I like watching it around 8:30 in the morning, New York local time, to 11:00. There's usually a setup in there that I'm going to be able to find… that's like that sweet little spot in the morning that I focus on."

  Note the wording: these are the hours he *watches* index futures, not a defined "killzone".
- **08:30 as the start of the hunt (single pass).** Ep. 4 (`L-ReMHiavPM`) ≈03:02: "Previous high, short-term high, and 8:30 in the morning, that starts the hunt basically. That's what 8:30 in the morning is to me."
- **NY 07:00–10:00, confirmed (post read).** oEmbed of [status 1903822271514284280](https://x.com/I_Am_The_ICT/status/1903822271514284280) (23 Mar 2025): "If you have studied under me longer that just recently... you would understand the that I make examples of framing operating hours for unique Trader needs due to work, school, life demands. Anytime between 7am and 10am is technically NY Killzone... the question is are you able…" (truncated by oEmbed).
- **London, Asian, London close: still unverified.** Not stated in the Introduction, Ep. 2 or Ep. 4. The episodes that likely state them were not read (Gemini's free-tier quota of 20 requests per day ran out). The Data API found ICT's own dedicated 2017 videos, listed in §4 as the next pass.

### 2.6 OTE levels (item 6)

Still unverified. In the 2022 episodes read, ICT uses only the 50% level, as the premium/discount split:

- Ep. 2 ≈35:34 (single pass): "all of this can be determined by a simple 50 level on a Fibonacci… anything above that 50 level, this is referred to from an algorithmic stance as a premium market… below the 50 point, okay? 50%. Anything down here is a discount."
- Ep. 4 ≈02:10 (single pass): "below the equilibrium price point of this entire range, or 50% level on the fib… equilibrium, which is the 50 level on the Fibonacci."
- The Introduction mentions "optimal trade entry" (≈24:28) with no levels.

The 2023 lecture lists "Classic ICT Optimal Trade Entry" as an SB type but gives no levels. The Data API found ICT's 2017 "OTE Primer - Intro To ICT Optimal Trade Entry" (`Cg0-CFJOJvg`, 44:40), the most likely place for 62 / 70.5 / 79. It was not read.

### 2.7 Other ICT posts re-read with oEmbed (upgrades from excerpt-only)

| Post | Full text (oEmbed) |
|---|---|
| [1550816841110638592](https://x.com/I_Am_The_ICT/status/1550816841110638592) (2022-07-23) | "Stop listening to Goobers who say what we do is "complicated". Determine most likely expansion on the weekly candle. Find Med or High impact econ event in ICT Killzones. Wait for opposing Liquidity to be taken out. Look for displacement & FVG. Target Opposing PD Arrays." |
| [1897984651186114746](https://x.com/I_Am_The_ICT/status/1897984651186114746) (2025-03-07) | "When Indices gap lower at 9:30 am ET the first concern is the 70% odds Opening Range Gap C.E. is booked by 10:00 am ET. If it fails to fill that number, use 10:00 am ET Silver Bullet to ORG C.E. long." |
| [1640362563845095433](https://x.com/I_Am_The_ICT/status/1640362563845095433) (2023-03-27) | "ICT Silver Bullet..." plus an image. No rules in the text |
| [1988248421438746984](https://x.com/I_Am_The_ICT/status/1988248421438746984) (2025-11-11) | "ICT Opening Range Theory \ 1st Presented FVG Logic" plus a link |
| [1857446886002553100](https://x.com/I_Am_The_ICT/status/1857446886002553100) (2024-11-15) | "1st Presented FVG short has delivered nicely. I did a single nothing over the top for 1470. Only thing I would have done differently I would be short two take the 75 handles on one and let the other run til 20575." |

## 3. Proposed patch list for `ict-setup-definitions.md`

For whoever next edits branch `research/ict-setup-definitions`. Nothing here has been applied.

**Header and "How to read this document"**

1. Add a pointer: "Timestamped primary evidence for #21: [ict-setup-timestamps.md](ict-setup-timestamps.md)."
2. Replace "every primary quote below comes from a search-engine excerpt" with: quotes marked *(#21)* were read through the YouTube Data API + Gemini YouTube-URL input or X oEmbed; the rest are still search excerpts.

**§0 (one paragraph)**

3. Change the "15–20 handle" bullet to: the first FVG "tethered to the Dealing Range, … whether a Hexadecant, Octant or…" (post read via oEmbed); 15–20 handles still excerpt-only.
4. Add a bullet: the three Silver Bullet hours 03:00–04:00, 10:00–11:00, 14:00–15:00 NY local time, and the 10-point / 40-tick minimum framework, from the 2023 lecture `tRq1hyGGtl4` (08:12, 12:30, 14:10; 00:20).
5. In "Everything else is UNVERIFIED", drop "the London Silver Bullet hour" and narrow "exact killzone edges" to "London, Asian and London-close killzone edges".

**§0.1**

6. Append a sub-section "Timestamp pass (#21)" with the §1 verdict table of this file, and change these rows of the #18 table:
   - SB windows and PM SB rows → "Confirmed (Gemini transcription), `tRq1hyGGtl4` 08:12 / 12:30 / 14:10". Replace the glasp.co link with the video.
   - Extra SB window 07:00–08:30 → "ICT's own words, optional: `v_iJlBKYmUc` 54:03". Remove "No ICT post or video was found stating it".
   - 15–20 handle row → "10 pts confirmed (Gemini transcription), `tRq1hyGGtl4` 00:20 / ~00:40; it is a framework (distance to DOL), not a take-profit. 15–20 still excerpt-only."
   - Tethered row → "Post opening read via oEmbed; ICT names Hexadecant and Octant; Quadrant and the rest are cut off."
   - Killzone row → "NY 08:30–11:00 (Ep. 2 `tmeCWULSTHc` 42:38) and NY 07:00–10:00 (post, read) confirmed; London, Asian, London close still unverified."
7. Fix the route table: Gemini, Data API and oEmbed now work (#20). oEmbed truncates long posts.

**§1.1 time-window table**

8. *NY AM Killzone* evidence: add "Ep. 2 `tmeCWULSTHc` 42:38: 'I like watching it around 8:30 in the morning, New York local time, to 11:00' (Gemini transcription, 2 passes)". Mark the 07:00–10:00 quote "post read (#21)". Remove "attributed to his 2022 mentorship but not confirmed" from the bullet under the table.
9. *London Silver Bullet*: evidence → "`tRq1hyGGtl4` 08:12 slide 'SETUP TIME: 3:00 AM – 4:00 AM \* ALWAYS NEW YORK LOCAL TIME'. Confirmed (Gemini transcription)." Drop the 02:00–03:00 variant (no source, and the lecture contradicts it).
10. *NY AM Silver Bullet*: add "`tRq1hyGGtl4` 12:30 slide '10:00 AM – 11:00 AM'"; the 1-hour length is now primary.
11. *NY PM Silver Bullet*: evidence → "`tRq1hyGGtl4` 14:10 slide '2:00 PM – 3:00 PM'. Confirmed (Gemini transcription)."
12. *Extra Silver Bullet windows*: keep **off** by default. Evidence → "ICT, `v_iJlBKYmUc` 54:03 (27 Sep 2023): 'If you really, really want it, you can do 7:00 in the morning to 8:30.' Optional, 90 min." Remove the 15:00–16:00 variant or mark it "no ICT source".
13. Add a note under the table: windows gate setup and entry only; ICT holds trades past the window end (`tRq1hyGGtl4` 13:36).
14. *Asian*, *London Open KZ*, *London Close KZ*, *NY PM*: unchanged ("UNVERIFIED-primary (#21: not in Mentorship Intro/Ep. 2/Ep. 4)").

**§1.2 concept table**

15. *Which FVG*: replace the quote with the oEmbed text from §2.4 and add "(post read; text truncated by oEmbed after 'Octant or')". Keep the grid test labelled as our reading. Reorder the *G* values so 8 and 16 are named by ICT and 4 is inferred.
16. *OTE*: add "#21: 2022 Mentorship Intro/Ep. 2/Ep. 4 use only the 50% equilibrium; 62/70.5/79 still not found in ICT's own material. Next: OTE Primer `Cg0-CFJOJvg`." No default change.
17. *Dealing range, premium/discount*: evidence → add "ICT, Ep. 2 `tmeCWULSTHc` ~35:34 and Ep. 4 `L-ReMHiavPM` ~02:10: 50% of the range splits premium and discount (single Gemini pass)".

**§2 rule cards**

18. §2.1 *Target* row: reword the minimum objective as a **framework filter**: skip if the distance from entry to the DOL is under 10 NQ points; the take-profit can be smaller. Source → `tRq1hyGGtl4` 00:20 / ~00:40, 12:51–13:36. Note that ICT's lecture examples are ES and his figure is for "indices" in general.
19. §2.1 *Window* row: add "entry by window end; the position may run past it (`tRq1hyGGtl4` 13:36)".
20. §2.2: "Windows are UNVERIFIED-primary" → "Window confirmed (Gemini transcription), `tRq1hyGGtl4` 14:10". The 5-handle claim: note ICT's own 10-handle framework applies to all three windows in the lecture, so the PM minimum default should be 10, with 5 as a variant.
21. §2.5 *ICT's own crossover*: add the lecture slide at 08:00, "7) Confluence Of The 2022 ICT Mentorship YouTube Model".

**§4 sweep list**

22. *NY AM killzone*: keep 07:00–10:00, 08:30–11:00 (both now ICT-sourced), 07:00–09:00.
23. *London SB*: `03:00–04:00` only. Remove 02:00–03:00.
24. *Extra SB windows*: `off`, `07:00–08:30` (ICT, optional).
25. *SB minimum objective*: keep **10**, 15, 20; rename "minimum framework (distance to DOL)". Add PM SB minimum: **10**, 5.
26. *Tethered grid G*: keep 8, 4, 16; annotate "8/16 named by ICT".
27. *OTE entry*: unchanged (62, 70.5, 79), still unverified.
28. Change log line: "Changes from #21: London SB 02:00–03:00 dropped; minimum objective redefined as framework filter; PM SB minimum default 10; no other default changes."

**§5 and Sources**

29. §5: remove the "compliant read path" blocker; replace with the remaining reads in §4 of this file.
30. Sources: move the posts in §2.7 to "Primary (read via oEmbed)". Add `tRq1hyGGtl4`, `v_iJlBKYmUc`, `tmeCWULSTHc`, `L-ReMHiavPM`, `kt6V4ai60fI` as primary videos. Drop the glasp.co transcript link, or demote it to "superseded".

## 4. What is still open, and the next pass

Gemini's free tier also caps **requests at 20 per day** for this model. That, not the 8-hour video cap, stopped this pass. Next pass, in priority order (durations from the Data API):

| Item | Video (ICT's channel) | Length |
|---|---|---|
| London killzone | "ICT Forex - The ICT London Killzone" [`G8OEsUAoIWE`](https://www.youtube.com/watch?v=G8OEsUAoIWE) (2017) | 21:35 |
| Asian range | "ICT Forex - The ICT Asian Killzone" [`ley5HZs4bUM`](https://www.youtube.com/watch?v=ley5HZs4bUM); "Implementing The Asian Range" [`JA0mLNJeytY`](https://www.youtube.com/watch?v=JA0mLNJeytY) | 13:20; 39:09 |
| London close | "ICT Forex - The ICT London Close Killzone" [`3OEUIkkcmLE`](https://www.youtube.com/watch?v=3OEUIkkcmLE) | 9:34 |
| NY killzone (forex framing) | "ICT Forex - The ICT New York Killzone" [`plNN9n7nrxc`](https://www.youtube.com/watch?v=plNN9n7nrxc) | 15:51 |
| OTE levels | "OTE Primer - Intro To ICT Optimal Trade Entry" [`Cg0-CFJOJvg`](https://www.youtube.com/watch?v=Cg0-CFJOJvg) | 44:40 |
| 15–20 handles, rest of the tethered post | No compliant path: oEmbed truncates. The user can paste the full post text | — |

These are 2017 forex-era videos, so their times may differ from 2022+ index usage. Record them as ICT's stated edges at the time, not as current rules. About 2.4 hours of video in total, 6 requests plus check passes.

## Sources

ICT's YouTube channel (IDs and dates from the YouTube Data API v3):

- 2023 ICT Mentorship - ICT Silver Bullet Time Based Trading Model (2023-05-14) — https://www.youtube.com/watch?v=tRq1hyGGtl4
- ICT Mentorship 2023 - September 27, 2023 PM Session Market Review — https://www.youtube.com/watch?v=v_iJlBKYmUc
- 2022 ICT Mentorship playlist — https://www.youtube.com/playlist?list=PLVgHx4Z63paYiFGQ56PjTF1PGePL3r69s
- ICT Mentorship 2022 Introduction — https://www.youtube.com/watch?v=kt6V4ai60fI
- 2022 ICT Mentorship Episode 2 — https://www.youtube.com/watch?v=tmeCWULSTHc
- 2022 ICT Mentorship Episode 4 — https://www.youtube.com/watch?v=L-ReMHiavPM
- Not read (next pass): `G8OEsUAoIWE`, `plNN9n7nrxc`, `ley5HZs4bUM`, `3OEUIkkcmLE`, `JA0mLNJeytY`, `Cg0-CFJOJvg`; also "ICT Mentorship 2023 - Evolving ICT Silver Bullet Example" `DkOuO0eNwUA` (request failed on a connection reset)

ICT's posts on X (text via `publish.twitter.com/oembed`):

- Tethered FVG (truncated) — https://x.com/I_Am_The_ICT/status/2091492182007906623
- NY killzone 07:00–10:00 — https://x.com/I_Am_The_ICT/status/1903822271514284280
- 10:00 SB to ORG C.E. — https://x.com/I_Am_The_ICT/status/1897984651186114746
- 2022 model checklist — https://x.com/I_Am_The_ICT/status/1550816841110638592
- ICT Silver Bullet (image only) — https://x.com/I_Am_The_ICT/status/1640362563845095433
- 1st Presented FVG logic — https://x.com/I_Am_The_ICT/status/1988248421438746984
- 1st Presented FVG short, 75 handles — https://x.com/I_Am_The_ICT/status/1857446886002553100
