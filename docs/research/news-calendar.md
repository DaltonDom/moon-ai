# Research: Free Calendar of High-Impact US News Events, Live and Back to 2019

*Compiled 2026-10-31. Resolves [#5](https://github.com/DaltonDom/moon-ai/issues/5), a child of the map [#1](https://github.com/DaltonDom/moon-ai/issues/1). It backs the hard risk rule in [`../design.md`](../design.md): "No trading from 15 minutes before to 15 minutes after high-impact news". The rule applies live, on paper and in backtests over 5+ years of history.*

> **How this was sourced.** This session's network blocked direct fetches of every relevant domain: bls.gov, bea.gov, federalreserve.gov, fred.stlouisfed.org, finnhub.io, tradingeconomics.com, forexfactory.com and nfs.faireconomy.media all failed DNS or proxy CONNECT. First-party pages were therefore read **through search-engine excerpts restricted to each publisher's own domain**. Claims below are excerpt text attributed to the cited URL. Anything not backed by a first-party excerpt is marked **UNVERIFIED**. The calendar builder script will need those three government domains allowed in the network settings of whichever environment runs it.

## Table of contents

1. [Bottom line](#1-bottom-line)
2. [Events and their usual times](#2-events-and-their-usual-times)
3. [Official sources (BLS, BEA, Federal Reserve)](#3-official-sources)
4. [FRED / ALFRED](#4-fred--alfred)
5. [Third-party APIs](#5-third-party-apis)
6. [Comparison table](#6-comparison-table)
7. [Recommendation](#7-recommendation)
8. [Time-zone handling](#8-time-zone-handling)
9. [Edge cases the calendar must carry](#9-edge-cases-the-calendar-must-carry)
10. [Open questions](#10-open-questions)
- [Sources](#sources)

---

## 1. Bottom line

- **No free API gives exact release times for these events back to 2019 under terms that allow caching it and using it in ML.**
  - FRED/ALFRED gives dates only, and its API terms ban caching and ML use (§4).
  - Finnhub's economic calendar is a premium endpoint, and its history is Enterprise-only (§5.1).
  - Trading Economics has no free tier (§5.2).
  - Forex Factory's feed covers only the current week, and its terms restrict non-interface access (§5.3).
- **The official publishers give everything needed, free and public domain.** They are BLS (CPI, NFP, PPI), BEA (GDP, PCE) and the Federal Reserve Board (FOMC statements, minutes, press conferences, Chair speeches and testimony). Each publishes past-year schedules with times back past 2019 and a live schedule for the year ahead.
- **Recommendation:** build our own versioned calendar file, `news_events.csv`, from the official sources. That is roughly 90–100 rows a year, about 750 rows for 2019–2026, which is small enough to hand-check. A small refresh script keeps it current from the live official schedules (BLS `.ics`, BEA schedule, Fed calendars). Third-party feeds are at most an optional live cross-check, never the source of truth.
- **Why that fits the design:** the backtest and the live rule then read the same file. A frozen replay stays identical because the calendar is versioned with the code, and nothing depends on a vendor whose terms or history could change.

## 2. Events and their usual times

All times are US Eastern (America/New_York). "Usual" means the publisher's standard time. The exceptions are listed in §9.

| Event | Publisher | Usual time (ET) | Per year | Evidence |
|---|---|---|---|---|
| CPI | BLS | 08:30 | 12 | BLS CPI schedule lists 08:30 AM releases through Dec 2027 ([cpi.htm](https://www.bls.gov/schedule/news_release/cpi.htm)) |
| Employment Situation (NFP) | BLS | 08:30 | 12 | 2019 and 2026 schedules show 08:30 AM ([2019](https://www.bls.gov/schedule/2019/home.htm), [2026](https://www.bls.gov/schedule/2026/home.htm)); BLS 2019 RSS stamps 08:30:00 ([RSS](https://www.bls.gov/schedule/news_release/content/2019/2019news_releases_public.rss)) |
| PPI | BLS | 08:30 | 12 | Shown on the BLS selected-releases schedules ([2026](https://www.bls.gov/schedule/2026/home.htm)). The per-release PPI time excerpt was not retrieved: **UNVERIFIED**, but it is standard 08:30 |
| GDP (advance, second, third) | BEA | 08:30 | 12 | "BEA news releases are posted at 8:30 a.m. Eastern time" ([2021 schedule](https://apps.bea.gov/scb/issues/2020/12-december/pdf/1220-news-releases-2021.pdf)); "EMBARGOED UNTIL RELEASE AT 8:30 A.M. EST" ([GDP Q4 2019 adv.](https://www.bea.gov/sites/default/files/2020-01/gdp4q19_adv_0.pdf)) |
| Personal Income and Outlays (PCE) | BEA | 08:30 | 12 | BEA moved PIO to the **same day and time as GDP** from Feb 20, 2026 ([BEA blog](https://www.bea.gov/index.php/news/blog/2026-02-09/faster-release-personal-income-outlays-same-time-gdp)). Before that it came out on a separate day, also at 8:30 a.m. under BEA's general rule |
| FOMC statement | Fed Board | 14:00 | 8 + unscheduled | 2019 statements at 2:00 p.m. ([2019 page](https://www.federalreserve.gov/monetarypolicy/fomchistorical2019.htm)); Oct 28, 2026 statement at 2:00 p.m. ([meeting page](https://www.federalreserve.gov/monetarypolicy/fomcpresconf20261028.htm)) |
| FOMC press conference | Fed Board | 14:30 (**UNVERIFIED**) | 8 | Every meeting has a transcript ([2019 page](https://www.federalreserve.gov/monetarypolicy/fomchistorical2019.htm)), but the start time was not shown in any excerpt |
| FOMC minutes | Fed Board | 14:00 | 8 | About 21 days after the decision. Sep 15–16, 2026 minutes released Oct 7 at 2:00 p.m. ([press release](https://www.federalreserve.gov/newsevents/pressreleases/monetary20261007a.htm)) |
| Fed Chair speeches and testimony | Fed Board | varies | ~10–30 (**UNVERIFIED** count) | Monthly Board calendars list date, time, speaker and venue ([Oct 2026](https://www.federalreserve.gov/newsevents/2026-october.htm)). The Chair is now Kevin Warsh: Jackson Hole keynote Aug 2026, Humphrey-Hawkins testimony Jul 14–15, 2026 ([Aug 2026](https://www.federalreserve.gov/newsevents/2026-august.htm)). For history, Powell's entries run to late 2025 ([Dec 2025](https://www.federalreserve.gov/newsevents/2025-december.htm)) |

**How this meets the design's sessions.** The 08:30 releases fall an hour before the NY open. They overlap the London setup's tail and any pre-open trades. The 14:00 FOMC statement and minutes fall in or next to the NY PM Silver Bullet window, so FOMC days block 13:45–14:15. A 14:30 press conference would be a second window (§10).

## 3. Official sources

### 3.1 BLS (CPI, NFP, PPI)

- **Live:**
  - The schedule pages list date and 08:30 AM time per release ([2026 schedule](https://www.bls.gov/schedule/2026/home.htm), [monthly pages](https://www.bls.gov/schedule/2026/11_sched.htm)).
  - An iCalendar feed at `https://www.bls.gov/schedule/news_release/bls.ics` "contains publication dates for most news releases scheduled by the BLS national office" and "is updated as needed, usually at least a week before each scheduled date" ([BLS schedule](https://www.bls.gov/schedule/2026/home.htm)).
  - Per-release pages run further ahead. The CPI schedule runs through Dec 2027 ([cpi.htm](https://www.bls.gov/schedule/news_release/cpi.htm)).
- **History:**
  - Per-year schedule pages exist for 2019 onward ([2019](https://www.bls.gov/schedule/2019/home.htm), [2025](https://www.bls.gov/schedule/2025/home.htm)).
  - Per-year RSS archives carry exact timestamps. For example, the 2019 feed stamps Employment Situation releases at 08:30:00 ([2019 RSS](https://www.bls.gov/schedule/news_release/content/2019/2019news_releases_public.rss)).
  - Archived releases list every actual edition ([Employment Situation archive](https://www.bls.gov/bls/news-release/empsit.htm)). Use the archive to confirm the *actual* dates rather than the planned ones.
- **Schedule changes:** BLS keeps a page of dates revised by the 2025 and 2026 funding lapses ([revised dates](https://www.bls.gov/bls/2025-lapse-revised-release-dates.htm)):
  - The Sep 2025 Employment Situation moved from Oct 3 to Nov 20, 2025.
  - No Oct 2025 Employment Situation release was published.
  - The Jan 2026 Employment Situation moved from Feb 6 to Feb 11, 2026.
  - The Jan 2026 CPI moved from Feb 11 to Feb 13, 2026.
- **Terms:** BLS publications are public domain, except previously copyrighted photos and illustrations. Credit to BLS is requested ([BLS copyright](https://www.bls.gov/opub/copyright-information.htm)). BLS blocks robots it considers "excessive or malicious" and may block robots that carry no owner contact information, sometimes in real time ([BLS terms](https://www.bls.gov/bls/blsterms.htm)). The script must therefore send a descriptive User-Agent with contact details and fetch rarely, for example once a day.
- **Time zone:** times are given in ET wall-clock ("08:30 AM"). They are not UTC.

### 3.2 BEA (GDP, PCE)

- **Live:** the release schedule at [bea.gov/news/schedule](https://www.bea.gov/news/schedule) lists the next dates. For example, Nov 25, 2026 at 8:30 AM brings PIO for Oct, GDP Q3 second estimate and corporate profits. Dec 23, 2026 at 8:30 AM brings PIO for Nov and GDP Q3 third estimate.
- **History:**
  - BEA publishes each year's schedule in the December *Survey of Current Business*. The 2019, 2020 and 2021 issues were found ([2019](https://apps.bea.gov/scb/issues/2018/12-december/pdf/1218-news-releases-2019.pdf), [2020](https://apps.bea.gov/scb/issues/2019/12-december/1219-news-releases-2020.htm), [2021](https://apps.bea.gov/scb/issues/2020/12-december/pdf/1220-news-releases-2021.pdf)). The 2022–2025 issues are presumed to follow the same pattern: **UNVERIFIED**.
  - Each release page carries the embargo time, for example "EMBARGOED UNTIL RELEASE AT 8:30 A.M. EST, THURSDAY, JANUARY 30, 2020" ([GDP Q4 2019](https://www.bea.gov/sites/default/files/2020-01/gdp4q19_adv_0.pdf)). Use release pages to confirm *actual* dates.
  - Planned schedules move. The 2019 schedule itself flags dates changed by the 2018–19 shutdown, and later releases were rescheduled again ([2019 trade release](https://www.bea.gov/news/2019/us-international-trade-goods-and-services-december-2018)). BEA also posted schedule updates for GDP and PIO after the 2025 shutdown ([BEA blog, Jan 2026](https://www.bea.gov/news/blog/2026-01-07/economic-release-schedule-updates-gdp-personal-income-and-outlays)).
- **Terms:** BEA is a federal agency, so its content is presumed public domain as a work of the US Government. A BEA-specific copyright statement was not retrieved: **UNVERIFIED**.
- **Time zone:** ET wall-clock ("8:30 a.m. EST/EDT").

### 3.3 Federal Reserve Board (FOMC, Chair)

- **FOMC, live and recent:** the [meeting calendars](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm) page lists the eight scheduled meetings a year, with links to statements and minutes. Per-meeting pages give the statement time, for example 2:00 p.m. on [Oct 28, 2026](https://www.federalreserve.gov/monetarypolicy/fomcpresconf20261028.htm).
- **FOMC, history:** per-year historical pages, such as [2019](https://www.federalreserve.gov/monetarypolicy/fomchistorical2019.htm) and [2020](https://www.federalreserve.gov/monetarypolicy/fomchistorical2020.htm), list every meeting including unscheduled ones. The 2019 page includes an unscheduled Oct 4 meeting. Statements, minutes and press-conference transcripts are linked from each.
- **Chair speeches and testimony:** the monthly Board calendars at `federalreserve.gov/newsevents/<year>-<month>.htm` give date, time, speaker and venue ([Oct 2026](https://www.federalreserve.gov/newsevents/2026-october.htm), [Jun 2025](https://www.federalreserve.gov/newsevents/2025-june.htm)). A per-year speeches index also exists ([2025 speeches](https://www.federalreserve.gov/newsevents/speech/2025-speeches.htm)). Gaps:
  - Whether monthly calendar pages exist back to 2019: **UNVERIFIED**.
  - Whether the listed times are always ET: **UNVERIFIED**. The Oct 2026 Bangkok entry shows a late-night time, which suggests conversion to ET.
- **Terms:** Federal Reserve Board website content is presumed public domain. A Board-specific copyright statement was not retrieved: **UNVERIFIED**.
- **Time zone:** ET wall-clock ("2:00 p.m.").

## 4. FRED / ALFRED

- **What it offers:** `fred/releases/dates` and `fred/release/dates` return release **dates**, which come from the data sources. The default `include_release_dates_with_no_data=false` drops future dates. Setting it to `true` adds them ([releases/dates docs](https://fred.stlouisfed.org/docs/api/fred/releases_dates.html), [release/dates docs](https://fred.stlouisfed.org/docs/api/fred/release_dates.html)). The `realtime_start`/`realtime_end` parameters scope the results to what FRED knew in a date window ([real-time periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html)).
- **Release times:** no excerpt showed a release *time* field. The endpoint is documented as returning `release_date` values only, so it **cannot drive a ±15-minute window** by itself. That FRED never carries a time: **UNVERIFIED**, but no excerpt showed one.
- **Terms: disqualifying for our use.**
  - The St. Louis Fed's June 2024 terms update bars using the FRED API "in connection with the development or training of any software program or system or machine learning". It also bars storing, caching or archiving FRED content, including adding it to a database ([St. Louis Fed notice, 2024-06-18](https://news.research.stlouisfed.org/2024/06/weve-updated-our-terms-of-use-action-requested/), [FRED legal](https://fred.stlouisfed.org/legal/), [API terms](https://fred.stlouisfed.org/docs/api/terms_of_use.html)).
  - Free use is aimed at non-commercial, educational and personal purposes, and other uses are subject to additional restrictions ([API terms](https://fred.stlouisfed.org/docs/api/terms_of_use.html)).
  - Our calendar *is* a cached database that feeds an ML pipeline.
- **Verdict:** do not use it as a data source. Read the FRED/ALFRED release calendar by hand, if at all, as a sanity check. Take everything we store directly from BLS, BEA and the Fed.

## 5. Third-party APIs

### 5.1 Finnhub

- `/calendar/economic` sits under "Economic Calendar **Premium**". It returns `actual`, `estimate`, `previous`, `impact`, `country`, `event`, `time` and `unit`. "Historical events and surprises are available for **Enterprise** clients" ([Finnhub docs](https://finnhub.io/docs/api/market-news)). Which paid tier unlocks the live calendar was not readable on the [pricing page](https://api.finnhub.io/pricing): **UNVERIFIED**.
- **Verdict:** not free for live use, and history back to 2019 needs an Enterprise contract.
- **Time zone:** the `time` field's zone (UTC or otherwise): **UNVERIFIED**.

### 5.2 Trading Economics

- Pricing "is adjusted accordingly to the features you use, to your volume of requests and to the distribution you make". Trials are capped at 100,000 data points and 100 requests, the trial fee is non-refundable, and trials auto-convert to paid ([TE pricing](https://tradingeconomics.com/api/pricing.aspx)). A calendar-by-country endpoint exists ([TE docs](https://docs.tradingeconomics.com/economic_calendar/country/)).
- The long-standing `guest:guest` free key is reported as discontinued. That report comes from a third-party profile ([api-evangelist/tradingeconomics](https://github.com/api-evangelist/tradingeconomics)), not Trading Economics itself, so it is **UNVERIFIED** from a first-party source.
- **Verdict:** paid only.

### 5.3 Forex Factory

- The calendar page offers a **weekly export** in ICS, CSV, JSON and XML ([FF calendar](https://www.forexfactory.com/calendar)), served from `nfs.faireconomy.media`.
  - Requests over a limit get an HTML "Request Denied" page instead of data ([FF forum](https://www.forexfactory.com/thread/1311021-mql45-programmers-this-weekly-news-download-code-solves)).
  - The feed is reported to carry only the current week, with no history. That report is a forum post from about 2020 ([FF forum](https://www.forexfactory.com/thread/567937-how-can-i-get-news-history-data-from)): **UNVERIFIED** today.
- **Terms:** users may not access the services "using a method other than the interface and the instructions that FEI provides" ([FF notices](https://www.forexfactory.com/notices)). The official weekly export arguably is such an instruction. Scraping calendar history pages for 2019 onward arguably is not.
- **Verdict:** possible as a live cross-check through the official weekly export. Not a lawful or reliable history source.
- **Time zone:** the export's zone: **UNVERIFIED**. The FF web calendar shows times in a user-selected zone.

## 6. Comparison table

| Source | Cost | Events covered | Exact time? | History to 2019? | Terms fit (cache + ML) | Time zone | Role |
|---|---|---|---|---|---|---|---|
| **BLS schedules, `.ics`, RSS archives** | Free | CPI, NFP, PPI | Yes (08:30) | Yes: per-year pages and RSS from 2019 | Public domain; polite bot rules | ET wall-clock | **Primary** |
| **BEA schedule + SCB annual schedules + release pages** | Free | GDP, PCE | Yes (08:30) | Yes: SCB 2019–2021 found; later years **UNVERIFIED** | Presumed public domain (**UNVERIFIED**) | ET wall-clock | **Primary** |
| **Fed Board FOMC calendars + historical pages** | Free | FOMC statement, minutes, presser | Yes (14:00; presser **UNVERIFIED**) | Yes: per-year pages | Presumed public domain (**UNVERIFIED**) | ET wall-clock | **Primary** |
| **Fed Board monthly calendars** | Free | Chair speeches, testimony | Yes | **UNVERIFIED** before 2025 | Presumed public domain | ET (**UNVERIFIED**) | **Primary** (speeches) |
| FRED/ALFRED API | Free key | All data releases | **No** (dates only) | Yes | **No**: bans caching and ML use | n/a | Manual sanity check only |
| Finnhub | Premium; history Enterprise | Global calendar | Yes | Enterprise only | Paid licence | **UNVERIFIED** | Not used |
| Trading Economics | Paid; trial auto-bills | Global calendar | Yes | Paid | Paid licence | **UNVERIFIED** | Not used |
| Forex Factory weekly export | Free | Global calendar, impact tags | Yes | **No** (this week only, **UNVERIFIED**) | Terms restrict non-interface access | **UNVERIFIED** | Optional live cross-check |

## 7. Recommendation

**Use one source of truth, `data/calendar/news_events.csv`, versioned in the repo and built from official publishers only.**

1. **Schema:** one row per event.

   ```
   event_id, event_type, publisher, local_time_et, utc_time, scheduled, source_url, verified_by
   ```

   - `event_type` is one of `CPI | NFP | PPI | GDP | PCE | FOMC_STATEMENT | FOMC_MINUTES | FOMC_PRESSER | FED_CHAIR`.
   - `local_time_et` is an ISO local time, for example `2019-01-04T08:30`.
   - `utc_time` is derived from `local_time_et`.
   - `scheduled` is a bool, false for emergency actions.
   - `source_url` is the official page that confirms the actual time.
2. **History back to 2019:** a one-off build of about 750 rows.
   - **BLS:** per-year schedule pages, checked against the per-year RSS archives and the archived-release lists, so the rows record *actual* dates including shutdown moves and cancellations.
   - **BEA:** the December SCB annual schedules, checked against the embargo line on each release.
   - **FOMC:** the per-year historical pages, including unscheduled meetings.
   - **Chair:** the monthly Board calendars.
   - Spot-check a sample by hand, as with the ground-truth set.
3. **Live and paper:** a daily refresh job.
   - It pulls the BLS `.ics`, the BEA schedule page, the FOMC calendar page and the current and next month of Board calendars. It shows changes as a diff, which is committed after review.
   - The rule engine reads the file. It never calls a vendor at trade time.
   - Because BLS updates the `.ics` "usually at least a week" ahead, a daily refresh gives plenty of notice.
4. **Optional cross-check:** compare the coming week against the Forex Factory weekly export and log any disagreement. Never block or unblock trades from it.
5. **Do not use** the FRED API (terms), Finnhub or Trading Economics (cost, and history is paywalled).

**Why not a vendor:** design.md wants frozen replays and reproducible models. A committed calendar file makes the news rule part of the reproducible inputs. If a vendor revises or removes history later, a past backtest would silently change.

## 8. Time-zone handling

- All three official publishers state times as **US Eastern wall-clock**, switching between EST and EDT (BEA's embargo lines say "EST" or "EDT" explicitly). Store the ET local time as published. Derive UTC with the IANA `America/New_York` zone (Python `zoneinfo`) rather than a fixed offset.
- The project stores all timestamps in UTC and computes session logic in `America/New_York` (see [`ict-ml-trading-bot.md`](./ict-ml-trading-bot.md)). Compare in UTC. The window is `[utc_time − 15 min, utc_time + 15 min]`.
- DST mismatch weeks matter for the London setup, not for these US events: the US and UK switch clocks on different dates. ET-anchored US events stay at 08:30 ET either way.

## 9. Edge cases the calendar must carry

- **Unscheduled FOMC actions:**
  - Mar 3, 2020: statement at **10:00 a.m.** ([meeting page](https://www.federalreserve.gov/monetarypolicy/fomcpresconf20200303.htm)).
  - Sunday, Mar 15, 2020: statement at **5:00 p.m.** ([meeting page](https://www.federalreserve.gov/monetarypolicy/fomcpresconf20200315.htm), [minutes](https://www.federalreserve.gov/monetarypolicy/files/fomcminutes20200315.pdf)).
  - Oct 4, 2019: unscheduled meeting ([2019 page](https://www.federalreserve.gov/monetarypolicy/fomchistorical2019.htm)).
  - These must be in history with `scheduled=false`. A live bot could not have known about them 15 minutes ahead (§10).
- **Shutdown moves and cancellations:** the 2018–19, 2025 and 2026 lapses moved or cancelled releases (§3.1, §3.2). Build history from *actual* release records, not the planned schedule.
- **Format change:** from Feb 20, 2026, PIO/PCE comes out alongside GDP ([BEA](https://www.bea.gov/index.php/news/blog/2026-02-09/faster-release-personal-income-outlays-same-time-gdp)). That gives one window, not two.
- **Chair change:** Powell up to late 2025, Warsh in 2026 (§2). Key the `FED_CHAIR` rows to the office, not the person.
- **Overseas Chair events:** for example the Oct 2026 Bangkok event, which falls at night ET. Rows still go in. They rarely overlap NY sessions.

## 10. Open questions

1. **Exact event list and windows.**
   - Does the FOMC press conference (about 14:30, **UNVERIFIED**) get its own ±15 window, or does the whole 14:00–15:00 span block on FOMC days? This decides whether the NY PM Silver Bullet ever trades on FOMC days.
   - Are all Chair speeches "high-impact", or only testimony, Jackson Hole and pressers?
2. **Unscheduled events in backtests.** Should backtests block emergency actions such as Mar 2020? A live bot could not have known 15 minutes ahead. Options:
   - (a) include them, which is conservative and slightly optimistic about the rule;
   - (b) exclude them, which matches what live would do;
   - (c) block only the 15 minutes *after* the event.
3. **Network access.** Whichever environment runs the refresh script must allow bls.gov, bea.gov and federalreserve.gov. This research session could not reach them.

## Sources

Every URL below was read via domain-restricted search excerpts (direct fetch blocked), 2026-10-31.

- BLS: [CPI schedule](https://www.bls.gov/schedule/news_release/cpi.htm) · [2026 schedule](https://www.bls.gov/schedule/2026/home.htm) · [2025 schedule](https://www.bls.gov/schedule/2025/home.htm) · [2019 schedule](https://www.bls.gov/schedule/2019/home.htm) · [2019 RSS](https://www.bls.gov/schedule/news_release/content/2019/2019news_releases_public.rss) · [Employment Situation archive](https://www.bls.gov/bls/news-release/empsit.htm) · [Revised dates after 2025/2026 lapses](https://www.bls.gov/bls/2025-lapse-revised-release-dates.htm) · [Copyright](https://www.bls.gov/opub/copyright-information.htm) · [Terms of use](https://www.bls.gov/bls/blsterms.htm)
- BEA: [Release schedule](https://www.bea.gov/news/schedule) · [2019 schedule (SCB)](https://apps.bea.gov/scb/issues/2018/12-december/pdf/1218-news-releases-2019.pdf) · [2020 schedule (SCB)](https://apps.bea.gov/scb/issues/2019/12-december/1219-news-releases-2020.htm) · [2021 schedule (SCB)](https://apps.bea.gov/scb/issues/2020/12-december/pdf/1220-news-releases-2021.pdf) · [GDP Q4 2019 advance](https://www.bea.gov/sites/default/files/2020-01/gdp4q19_adv_0.pdf) · [PIO with GDP, Feb 2026](https://www.bea.gov/index.php/news/blog/2026-02-09/faster-release-personal-income-outlays-same-time-gdp) · [Schedule updates, Jan 2026](https://www.bea.gov/news/blog/2026-01-07/economic-release-schedule-updates-gdp-personal-income-and-outlays) · [2019 trade release (shutdown reschedule)](https://www.bea.gov/news/2019/us-international-trade-goods-and-services-december-2018)
- Federal Reserve Board: [FOMC calendars](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm) · [2019 FOMC](https://www.federalreserve.gov/monetarypolicy/fomchistorical2019.htm) · [2020 FOMC](https://www.federalreserve.gov/monetarypolicy/fomchistorical2020.htm) · [Mar 3, 2020](https://www.federalreserve.gov/monetarypolicy/fomcpresconf20200303.htm) · [Mar 15, 2020](https://www.federalreserve.gov/monetarypolicy/fomcpresconf20200315.htm) · [Mar 15, 2020 minutes](https://www.federalreserve.gov/monetarypolicy/files/fomcminutes20200315.pdf) · [Oct 28, 2026 meeting](https://www.federalreserve.gov/monetarypolicy/fomcpresconf20261028.htm) · [Sep 2026 minutes release](https://www.federalreserve.gov/newsevents/pressreleases/monetary20261007a.htm) · [Calendar Oct 2026](https://www.federalreserve.gov/newsevents/2026-october.htm) · [Calendar Aug 2026](https://www.federalreserve.gov/newsevents/2026-august.htm) · [Calendar Dec 2025](https://www.federalreserve.gov/newsevents/2025-december.htm) · [Calendar Jun 2025](https://www.federalreserve.gov/newsevents/2025-june.htm) · [2025 speeches](https://www.federalreserve.gov/newsevents/speech/2025-speeches.htm)
- FRED/ALFRED: [releases/dates](https://fred.stlouisfed.org/docs/api/fred/releases_dates.html) · [release/dates](https://fred.stlouisfed.org/docs/api/fred/release_dates.html) · [Real-time periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html) · [API terms](https://fred.stlouisfed.org/docs/api/terms_of_use.html) · [Legal](https://fred.stlouisfed.org/legal/) · [June 2024 terms notice](https://news.research.stlouisfed.org/2024/06/weve-updated-our-terms-of-use-action-requested/)
- Finnhub: [API docs](https://finnhub.io/docs/api/market-news) · [Pricing](https://api.finnhub.io/pricing)
- Trading Economics: [API pricing](https://tradingeconomics.com/api/pricing.aspx) · [Calendar by country docs](https://docs.tradingeconomics.com/economic_calendar/country/) · third-party: [api-evangelist profile](https://github.com/api-evangelist/tradingeconomics)
- Forex Factory: [Calendar](https://www.forexfactory.com/calendar) · [Notices / terms](https://www.forexfactory.com/notices) · [Forum: download limit](https://www.forexfactory.com/thread/1311021-mql45-programmers-this-weekly-news-download-code-solves) · [Forum: no history in XML](https://www.forexfactory.com/thread/567937-how-can-i-get-news-history-data-from)
