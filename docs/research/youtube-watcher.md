# Research: ICT YouTube Watcher (API, Transcript Access, Terms)

*Compiled 2026-10-31. Answers ticket [#6](https://github.com/DaltonDom/moon-ai/issues/6) under the map [#1](https://github.com/DaltonDom/moon-ai/issues/1). Backs the "Monthly ICT watcher" line in [`../design.md`](../design.md): new uploads on youtube.com/@InnerCircleTrader are summarised into candidate setups, and the user approves them before they are coded.*

> **How this was sourced.** The research sandbox's network blocked direct fetches of `developers.google.com`, `www.youtube.com` and `ai.google.dev`. Those first-party pages were read **through search-engine excerpts restricted to each domain**, not by opening the page. Quotes and figures below are excerpt text attributed to the cited URL. The `youtube-transcript-api` repository was cloned and read directly (commit `b5c3339`, 2026-10-30, version 1.2.4). Anything not backed by a first-party source is marked **UNVERIFIED**. Quotas and the Gemini YouTube-URL feature are both described by Google as subject to change. Re-check them before building.

## Table of contents

1. [Bottom line](#1-bottom-line)
2. [Finding new uploads: YouTube Data API v3 and quota](#2-finding-new-uploads-youtube-data-api-v3-and-quota)
3. [Getting transcripts: what is and isn't allowed](#3-getting-transcripts-what-is-and-isnt-allowed)
4. [Terms of Service implications](#4-terms-of-service-implications)
5. [Live streams and long videos](#5-live-streams-and-long-videos)
6. [Recommended pipeline](#6-recommended-pipeline)
7. [Fallback](#7-fallback)
8. [Open questions](#8-open-questions)
- [Sources](#sources)

---

## 1. Bottom line

- **Finding new uploads is easy and free.** A monthly run with an API key costs about 3 to 5 quota units against a default of 10,000 units per day [Q1]. Use `channels.list?forHandle=@InnerCircleTrader` to get the uploads playlist, then `playlistItems.list` and `videos.list`. Each costs 1 unit [Q2][Q3][Q4]. Avoid `search.list`, which has its own small bucket of about 100 calls per day [Q1].
- **The official `captions.download` endpoint can't be used on ICT's videos.** It needs OAuth, and the signed-in user must have permission to edit the video [C1]. Without that, it returns 403 `forbidden` [C1].
- **`youtube-transcript-api` and similar scrapers are not terms-compliant.** The library calls an undocumented YouTube web-client endpoint [L1]. The YouTube ToS bans automated access without written permission [T1]. The API Developer Policies ban scraping YouTube or using scraped YouTube data [P1]. YouTube also actively blocks it: the README says cloud IPs are mostly blocked and recommends rotating residential proxies to get around the bans [L2]. Downloading audio (for example with yt-dlp) and running Whisper on it is ruled out for the same reason: the ToS bans downloading Content unless YouTube authorises it [T1].
- **Recommended terms-compliant route: the Gemini API's YouTube URL input.** Google's own API takes a public YouTube URL directly [G1]. The pipeline asks Gemini for a timestamped transcript or structured notes, then passes that text to Claude for the setup summary the design already calls for. It is in preview and free; the free tier allows 8 hours of YouTube video per day [G1]. ICT's monthly volume fits comfortably (**UNVERIFIED**: no count of ICT's monthly upload hours was made).
- **Fallback:** a human-in-the-loop step. The watcher still detects new videos via the API and opens a review item. The user reads or watches the video and pastes notes or YouTube's own on-page transcript into an inbox file, and Claude summarises from there. Whether copying the on-page transcript for personal use fits the ToS is **UNVERIFIED** (see §7).

## 2. Finding new uploads: YouTube Data API v3 and quota

| Call | Purpose | Quota cost | Source |
|---|---|---|---|
| `channels.list` `part=contentDetails`, `forHandle=@InnerCircleTrader` | Resolve the handle to the channel and its `relatedPlaylists.uploads` playlist ID | 1 unit | [Q3][Q5] |
| `playlistItems.list` `playlistId=<uploads>`, `maxResults=50` | List uploads newest first; page with `nextPageToken` | 1 unit per page | [Q2][Q5] |
| `videos.list` `id=<≤50 ids>`, `part=snippet,contentDetails,liveStreamingDetails` | Title, description, duration, live status, captions flag | 1 unit | [Q4] |
| `search.list` | Not needed | Its own bucket of 100 calls/day (formerly 100 units per call) | [Q1] |
| `captions.list` | Lists caption tracks (`trackKind`: `ASR`, `standard`, `forced`) | 50 units | [Q6][Q7] |
| `captions.download` | Download a track | 200 units; needs edit rights on the video | [C1] |

Facts that shape the design:

- **Default quota:** "10,000 units per day combined for all other endpoints", with `search.list` and `videos.insert` in their own buckets of 100 calls per day. Quotas reset at midnight Pacific Time. Getting more requires an API Compliance Audit [Q1]. A June 2026 revision says the API is moving to granular quota buckets, starting with `videos.insert` and `search.list` [Q1]. Older guides that quote "search costs 100 units" are out of date [Q1].
- **Handle lookup:** `forHandle` was added on 2024-01-31. It accepts the value with or without the `@` [Q3].
- **Uploads playlist:** `contentDetails.relatedPlaylists.uploads` is "the ID of the playlist containing the channel's uploaded videos" [Q5]. The UC→UU prefix swap seen in samples is a pattern, not a documented guarantee. Read the ID from the response [Q5].
- **Duration** is ISO 8601, for example `PT15M51S` [Q7].
- **Auth:** all three calls read public data, so an API key is enough. No OAuth consent screen is needed for this half (**UNVERIFIED** as a direct quote; it follows from the methods' auth tables showing that public reads don't need user authorisation).
- **Monthly cost:** about 1 + 1 to 2 + 1 units. That is effectively free.

## 3. Getting transcripts: what is and isn't allowed

### 3.1 Official `captions` endpoint: not usable for a third-party channel

- `captions.download` "requires the user to have permission to edit the video". Its scopes are `youtube.force-ssl` and `youtubepartner` [C1].
- Without that permission it returns 403 `forbidden`: "The permissions associated with the request are not sufficient to download the caption track" [C1].
- We aren't editors of ICT's channel, so this route is closed. `captions.list` (50 units) still shows **whether** a track exists and whether it is ASR [Q6][Q7], but not its text. `videos.list` `contentDetails.caption` gives the same yes/no answer for 1 unit [Q7].

### 3.2 `youtube-transcript-api` (jdepoix): works technically, not compliant

From the repository source (commit `b5c3339`, v1.2.4, MIT licence):

- **Undocumented endpoint:** "This code uses an undocumented part of the YouTube API, which is called by the YouTube web-client. So there is no guarantee that it won't stop working tomorrow" [L1]. The code scrapes `INNERTUBE_API_KEY` out of the watch page and posts to `https://www.youtube.com/youtubei/v1/player` while posing as the `ANDROID` client [L3].
- **Blocking:** "YouTube has started blocking most IPs that are known to belong to cloud providers … you will most likely run into `RequestBlocked` or `IpBlocked` exceptions". The README recommends rotating residential proxies "to work around these IP bans" [L2].
- **Terms:** this is automated access to the Service outside the official API, which the YouTube ToS bans without written permission [T1]. The Developer Policies separately ban scraping YouTube and obtaining scraped YouTube data [P1]. Rotating proxies to evade IP bans also arguably breaks the ToS clause against circumventing YouTube's technical limits [T1] (**UNVERIFIED** whether IP blocks count as such a "feature").
- **Verdict:** don't use it in the pipeline. Running from the user's Mac would avoid the cloud-IP block in practice, but that doesn't change the terms.

### 3.3 Download plus local speech-to-text (yt-dlp + Whisper): not compliant

- The ToS bans you to "access, reproduce, download … any Content except: (a) as expressly authorized by the Service; or (b) with prior written permission from YouTube and, if applicable, the respective rights holders" [T1].
- Ruled out for the same reason as §3.2.

### 3.4 Gemini API with a YouTube URL: the compliant route

- The Gemini API accepts a public YouTube URL as video input. The feature is in **preview** and "available at no charge", and pricing and rate limits may change [G1].
- **Limits:** only public videos (not private or unlisted). The free tier allows 8 hours of YouTube video per day; the paid tier has "no limit based on video length". Gemini 2.5 and later models accept up to 10 videos per request [G1].
- **Why it is compliant:** YouTube's ToS allows access "as expressly authorized by the Service" [T1]. Here Google itself fetches the video, through a feature Google documents and offers. Nothing is scraped or downloaded on our side.
- **Caveat:** a Google developer-forum thread asks which document governs passing YouTube URLs to Gemini in a commercial app, and the docs don't answer it explicitly [G4]. This project is personal and non-commercial, which lowers the risk. Which terms govern is still **UNVERIFIED**. The Gemini API Additional Terms are the likely answer.
- **Effect on the design:** this brings in a second AI vendor (Google) next to Claude. Gemini only turns video into text; Claude still does the ICT-concept summary and the comparison with the setup library, as design.md says.

## 4. Terms of Service implications

| Rule | What it says | Effect on the watcher | Source |
|---|---|---|---|
| YouTube ToS: downloading | No accessing, reproducing or downloading Content except as the Service expressly authorises or with written permission | Rules out yt-dlp and audio download | [T1] |
| YouTube ToS: automated access | No automated access (robots, scrapers) except public search engines that follow robots.txt, or with written permission | Rules out `youtube-transcript-api` and HTML scraping | [T1] |
| YouTube ToS: circumvention | Don't circumvent features that prevent or limit copying or use of Content | Rotating proxies to beat blocks is risky | [T1] |
| API Developer Policies: scraping | Don't scrape YouTube or Google apps, or obtain scraped YouTube data | The API client must not mix in scraped transcripts | [P1] |
| API Developer Policies: storage | Keep API data no longer than needed and **at most 30 calendar days**, then delete or refresh it | Store only video IDs plus our own derived notes; refresh or drop API metadata (titles, descriptions) after 30 days | [P1][P2] |
| API Developer Policies: penalties | Violations may lead to quota cuts or termination of API access | Keep the API key's project clean | [P1] |

Whether our own **derived summaries** (Claude's notes on setup concepts) count as "API data" under the 30-day rule is **UNVERIFIED**. The safe reading is to store our notes with the video ID only, not copied titles or descriptions, and to re-check the video ID through `videos.list` (1 unit) at least every 30 days if any metadata is kept.

The ToS copy read via search excerpt was an older snapshot; the excerpt flagged it as about three years old. Re-read the live ToS page before relying on exact wording [T1].

## 5. Live streams and long videos

- **Detecting live videos:** `snippet.liveBroadcastContent` is `live`, `upcoming` or `none`. `liveStreamingDetails` (requested via `part`) appears only for upcoming, live or completed broadcasts. It carries `actualStartTime` and `actualEndTime` [Q4].
- **Rule:** skip videos that are `live` or `upcoming`, or that have `liveStreamingDetails` without `actualEndTime`. Leave them for the next run. A finished stream is treated like a normal upload.
- **Captions on finished streams:** live automatic captions do not stay on the video. "New automatic captions will be generated based on the VOD process" after the stream ends [H1]. So right after a stream ends there may be no captions yet. Another reason to wait for the next monthly run.
- **Auto-captions can be missing:** YouTube lists video length, poor audio, unsupported language, long initial silence and overlapping speakers as reasons [H2]. `contentDetails.caption=false` flags this cheaply [Q7]. The Gemini route doesn't depend on YouTube captions, because Gemini processes the audio and video itself [G1].
- **Long videos and Gemini:** about 300 tokens per second at default media resolution and about 100 at low. A 1M-token context fits about 1 hour at default or about 3 hours at low resolution [G2]. For transcript-style output, ask for **low media resolution**, since the frames hardly matter. Split videos over about 3 hours into time ranges. Gemini supports clipping a video to start and end offsets (**UNVERIFIED** this session; documented on the video-understanding page in earlier versions [G1]).
- **Daily cap:** the free tier's 8 hours per day [G1] means a backlog run (first run, or a month of long streams) should spread across days, or use the paid tier.
- **ICT's video lengths:** ICT's live sessions often run 1 to 3+ hours (**UNVERIFIED**; no measurement made).

## 6. Recommended pipeline

Runs monthly on the user's Mac (launchd or cron), as design.md puts everything on the Mac where possible.

1. **Load state:** `last_seen_published_at` and a set of processed video IDs (local SQLite or JSON).
2. **Resolve the channel** once and cache it: `channels.list?part=contentDetails&forHandle=@InnerCircleTrader` with an API key → uploads playlist ID [Q3][Q5]. (1 unit)
3. **List new uploads:** `playlistItems.list?playlistId=…&maxResults=50`. Stop paging at the first item older than the watermark [Q2]. (1 unit per page)
4. **Classify:** `videos.list?part=snippet,contentDetails,liveStreamingDetails&id=…` in batches of 50 [Q4]. (1 unit)
   - Skip `live` and `upcoming` videos, and streams with no `actualEndTime`. Keep them pending.
   - Record the duration. If the total is over 8 hours, queue the rest for later days (free tier) [G1].
5. **Video → text (Gemini, YouTube URL input)** [G1][G2]:
   - Low media resolution. One video per request. Videos over about 3 hours are split into time ranges.
   - Prompt: "Produce a timestamped transcript of the speech" (or structured notes). Ask for JSON output so it can be parsed.
   - Keep the Gemini output locally as working text. Don't publish or redistribute it.
6. **Text → candidate setups (Claude):** structured-output call that compares the text with the current setup library. Output: new concepts, changed rules for existing setups, and timestamps as evidence. The Batch API fits, because the job isn't time-critical (design.md already uses it for reviews).
7. **User approval:** write a report (Markdown or dashboard card) with links to `https://www.youtube.com/watch?v=<id>&t=<s>` for each claim. Nothing is coded until the user approves (design.md).
8. **Housekeeping for API data:** store video ID, processed date and our notes. Drop copied titles and descriptions after 30 days, or refresh them via `videos.list` [P1].

**Expected cost:** YouTube quota is about 5 units per month (free). Gemini is $0 while the preview is free and within 8 hours per day [G1]. Claude costs a few cents per video via Batch (**UNVERIFIED** estimate).

## 7. Fallback

Use the fallback when Gemini can't process a video: the preview is withdrawn or priced out, the video is over the limits, or the request fails.

1. **The watcher still detects and classifies** the video (steps 2 to 4 above, official API only).
2. **It opens a review item** for the user: video link, duration and a "needs notes" flag.
3. **The user supplies the text** by dropping one of these into `watcher/inbox/<video_id>.md`:
   - their own notes from watching, or
   - the text from YouTube's on-page "Show transcript" panel, copied by hand. This is a feature the Service offers to viewers. Whether copying it for personal analysis counts as "expressly authorized by the Service" [T1] is **UNVERIFIED**. The user should decide.
4. **Claude summarises from the inbox file** exactly as in step 6.

**Not used as a fallback:** `youtube-transcript-api`, yt-dlp plus Whisper, or `captions.download`. See §3.

A further option, for completeness: email ICT's team and ask for written permission to use transcripts. The ToS allows that route ("prior written permission … and … the respective rights holders") [T1]. Low odds, but it would make the scraping libraries usable.

## 8. Open questions

- **Second vendor:** is the user OK adding a Google Gemini API key (free tier) to the stack, only for video → text? If not, the fallback becomes the main path.
- **Manual-transcript copy:** does the user accept the ToS reading in §7.3, or keep the fallback to their own notes only?
- **Backlog:** should the first run cover only new uploads from now on, or a back-catalogue? A back-catalogue would take many days at 8 hours per day on the free tier, or need the paid tier.

---

## Sources

First-party pages marked † were read through search excerpts restricted to that domain, because direct fetches were blocked.

- [Q1] † YouTube Data API, Quota Calculator / quota costs and Revision History: https://developers.google.com/youtube/data/determine_quota_cost ; https://developers.google.com/youtube/data/revision_history ; https://developers.google.com/youtube/v3/docs/search/list
- [Q2] † PlaylistItems: list: https://developers.google.com/youtube/v3/docs/playlistItems/list
- [Q3] † Channels: list (`forHandle`, 1 unit): https://developers.google.com/youtube/v3/docs/channels/list
- [Q4] † Videos: list and Videos resource (`liveBroadcastContent`, `liveStreamingDetails`): https://developers.google.com/youtube/v3/docs/videos/list ; https://developers.google.com/youtube/v3/docs/videos
- [Q5] † Channels resource (`relatedPlaylists.uploads`) and Implementation guides: https://developers.google.com/youtube/v3/docs/channels ; https://developers.google.com/youtube/v3/guides/implementation/channels
- [Q6] † Captions: list (50 units): https://developers.google.com/youtube/v3/docs/captions/list
- [Q7] † Captions resource (`trackKind`) and Videos resource (`contentDetails.duration`, `contentDetails.caption`): https://developers.google.com/youtube/v3/docs/captions ; https://developers.google.com/youtube/v3/docs/videos
- [C1] † Captions: download (200 units, edit permission, 403 text) and Errors: https://developers.google.com/youtube/v3/docs/captions/download ; https://developers.google.com/youtube/data/reference/rest/v3/errors
- [P1] † YouTube API Services Developer Policies (scraping, 30-day storage, penalties): https://developers.google.com/youtube/terms/developer-policies
- [P2] † Additional policies for derived metrics and data storage: https://developers.google.com/youtube/terms/derived-metrics-policy ; YouTube API Services Terms of Service: https://developers.google.com/youtube/terms/api-services-terms-of-service
- [T1] † YouTube Terms of Service, Permissions and Restrictions: https://www.youtube.com/static?template=terms
- [H1] † YouTube Help, Use automatic captioning (live captions replaced after stream): https://support.google.com/youtube/answer/6373554
- [H2] † YouTube Help, automatic-caption troubleshooting: https://support.google.com/youtube/answer/6373554 ; https://support.google.com/youtube/answer/7296221
- [G1] † Gemini API, Video understanding (YouTube URL preview, 8 h/day free, public only, 10 videos/request): https://ai.google.dev/gemini-api/docs/video-understanding
- [G2] † Gemini API, Video understanding and Media resolution (tokens per second, hours per 1M context): https://ai.google.dev/gemini-api/docs/video-understanding ; https://ai.google.dev/gemini-api/docs/media-resolution
- [G4] Google AI Developers Forum, "Terms for passing public YouTube URLs to Gemini API in a commercial app": https://discuss.ai.google.dev/t/terms-for-passing-public-youtube-urls-to-gemini-api-in-a-commercial-app-which-document-governs-this/189597 (community thread; context only)
- [L1] jdepoix/youtube-transcript-api README, "Warning" section (commit b5c3339): https://github.com/jdepoix/youtube-transcript-api/blob/b5c3339ddb7ed41851b770dac25c2025d2b07a82/README.md#warning
- [L2] Same README, "Working around IP bans": https://github.com/jdepoix/youtube-transcript-api/blob/b5c3339ddb7ed41851b770dac25c2025d2b07a82/README.md#working-around-ip-bans-requestblocked-or-ipblocked-exception
- [L3] Same repo, `youtube_transcript_api/_settings.py` (InnerTube player URL, ANDROID client) and `_transcripts.py` (API-key scrape): https://github.com/jdepoix/youtube-transcript-api/blob/b5c3339ddb7ed41851b770dac25c2025d2b07a82/youtube_transcript_api/_settings.py
