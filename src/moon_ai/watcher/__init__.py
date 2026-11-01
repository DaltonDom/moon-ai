"""The monthly ICT watcher (docs/design.md, "Monthly ICT watcher"; decisions in #14).

1. **Find** new uploads on ICT's channel with the YouTube Data API (a few quota
   units), and log their total hours.
2. **Transcribe to notes** with Gemini (`gemini-flash-latest`, low media
   resolution, the free tier only): timestamped notes on setups and rules.
   - At most 8 hours of video and 20 requests a day.
   - What doesn't fit waits for the next run.
   - A quota error stops the day. Nothing is ever paid.
3. **Fallback:** if Gemini fails, refuses or a video is over the limits, the
   video waits for the user's own notes. The user drops a Markdown file named
   `<video id>.md` (or any name) into `data/watcher/inbox/`.
4. **Summarise** a finished month's notes with Claude into candidate setups,
   and open one review item (a GitHub issue labelled `ict-watcher`). The user
   approves a candidate before anything is coded or tested.

The first run also queues a short targeted list (the 2022 Mentorship and the
2023 Silver Bullet lecture, plus ICT's 2017 session videos), not the back
catalogue.

State lives in `data/watcher/state.json`. Notes are kept in
`data/watcher/notes/<video id>.md`, and summaries in
`reports/watcher/<YYYY-MM>.md`.
"""
