# /// script
# requires-python = ">=3.12"
# dependencies = ["mlx-whisper>=0.4", "yt-dlp>=2025.1.1", "httpx>=0.27"]
# ///
"""Turn a folder of trading videos into text and chart screenshots, on the Mac.

    uv run scripts/media/ingest.py ~/moon-ai-media

Layout (the folder lives outside the repo; none of it is ever committed):

    ~/moon-ai-media/
      videos/          your downloaded videos, any of .mp4 .mov .mkv .webm .m4v
      links.txt        optional: YouTube links, one per line (or filled by --discord)
      out/<video>/
        transcript.txt "[mm:ss] what he says", one line per segment
        frames/        a chart screenshot every 30 s, named by time, e.g. 12-30.jpg
        done           written last; a video with it is skipped next time

Steps, each skipped when already done, so it can be stopped and re-run:
1. `--discord`: read the YouTube links posted in the given channels with your own
   read-only bot (DISCORD_BOT_TOKEN in ~/.config/moon-ai/.env) into links.txt.
2. Download every link in links.txt with yt-dlp (720p at most) into videos/.
3. Transcribe each video locally with Whisper (mlx, Apple silicon). Nothing is
   uploaded anywhere.
4. Save a screenshot every 30 seconds with ffmpeg.

Needs ffmpeg (`brew install ffmpeg`).
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
FRAME_EVERY = 30  # seconds
WHISPER_MODEL = "mlx-community/whisper-large-v3-turbo"
YOUTUBE = re.compile(
    r"https?://(?:www\.|m\.)?(?:youtube\.com/(?:watch\?v=|live/|shorts/)|youtu\.be/)[\w\-?=&%.]+"
)
ENV_FILE = Path.home() / ".config" / "moon-ai" / ".env"


def mmss(seconds: float) -> str:
    s = int(seconds)
    h, m = divmod(s // 60, 60)
    return f"{h}:{m:02d}:{s % 60:02d}" if h else f"{m:02d}:{s % 60:02d}"


def transcript_lines(segments: list[dict]) -> list[str]:
    """Whisper segments -> "[mm:ss] text" lines, empty ones dropped."""
    return [f"[{mmss(s['start'])}] {s['text'].strip()}" for s in segments if s["text"].strip()]


def frame_name(index: int, every: int = FRAME_EVERY) -> str:
    """ffmpeg's 1-based frame number -> its time in the video, e.g. 12-30.jpg."""
    return mmss((index - 1) * every).replace(":", "-") + ".jpg"


def youtube_links(text: str) -> list[str]:
    """Unique YouTube links in order of appearance."""
    seen: dict[str, None] = {}
    for m in YOUTUBE.findall(text):
        seen.setdefault(m.rstrip(").,>"), None)
    return list(seen)


def safe_stem(path: Path) -> str:
    return re.sub(r"[^\w\-. ]+", "_", path.stem).strip() or "video"


# --- steps ---------------------------------------------------------------------------


def discord_links(channel_ids: list[str], token: str) -> list[str]:
    """Every YouTube link posted in these channels, oldest first, via a bot token."""
    import httpx

    headers = {"Authorization": f"Bot {token}"}
    found: list[str] = []
    with httpx.Client(base_url="https://discord.com/api/v10", headers=headers, timeout=30) as c:
        for ch in channel_ids:
            before = None
            while True:
                params = {"limit": 100, **({"before": before} if before else {})}
                r = c.get(f"/channels/{ch}/messages", params=params)
                if r.status_code == 429:
                    import time

                    time.sleep(float(r.json().get("retry_after", 2)))
                    continue
                r.raise_for_status()
                msgs = r.json()
                if not msgs:
                    break
                for m in reversed(msgs):
                    text = (
                        m.get("content", "")
                        + " "
                        + " ".join(e.get("url", "") or "" for e in m.get("embeds", []))
                    )
                    found += youtube_links(text)
                before = msgs[-1]["id"]
    return list(dict.fromkeys(found))


def download_links(links: list[str], videos: Path) -> None:
    for url in links:
        out = videos / "yt_%(id)s.%(ext)s"
        vid = re.search(r"(?:v=|youtu\.be/|live/|shorts/)([\w\-]{11})", url)
        if vid and any(videos.glob(f"yt_{vid[1]}.*")):
            continue
        print(f"  downloading {url}", flush=True)
        subprocess.run(
            [
                sys.executable,
                "-m",
                "yt_dlp",
                "-q",
                "--no-playlist",
                "-f",
                "bv*[height<=720]+ba/b[height<=720]/b",
                "--merge-output-format",
                "mp4",
                "-o",
                str(out),
                url,
            ],
            check=False,
        )


def transcribe(video: Path, dest: Path) -> None:
    import mlx_whisper

    result = mlx_whisper.transcribe(
        str(video), path_or_hf_repo=WHISPER_MODEL, language="en", verbose=None
    )
    (dest / "transcript.txt").write_text("\n".join(transcript_lines(result["segments"])) + "\n")


def screenshots(video: Path, dest: Path) -> None:
    frames = dest / "frames"
    frames.mkdir(exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video),
            "-vf",
            (
                f"select='isnan(prev_selected_t)+gte(t-prev_selected_t\\,{FRAME_EVERY})',"
                "scale=1280:-2"
            ),
            "-fps_mode",
            "vfr",
            "-q:v",
            "5",
            str(frames / "%05d.jpg"),
        ],
        check=True,
    )
    for f in sorted(frames.glob("[0-9][0-9][0-9][0-9][0-9].jpg")):
        f.rename(frames / frame_name(int(f.stem)))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("root", type=Path, help="e.g. ~/moon-ai-media")
    p.add_argument(
        "--discord",
        nargs="+",
        metavar="CHANNEL_ID",
        help="collect YouTube links from these channels first",
    )
    p.add_argument("--no-frames", action="store_true", help="skip screenshots")
    args = p.parse_args(argv)
    root = args.root.expanduser()
    videos, out = root / "videos", root / "out"
    videos.mkdir(parents=True, exist_ok=True)
    out.mkdir(exist_ok=True)
    if not args.no_frames and shutil.which("ffmpeg") is None:
        print("ffmpeg is missing: run `brew install ffmpeg`, or pass --no-frames", file=sys.stderr)
        return 2

    links_file = root / "links.txt"
    if args.discord:
        token = _env("DISCORD_BOT_TOKEN")
        if not token:
            print(f"DISCORD_BOT_TOKEN is missing from {ENV_FILE}", file=sys.stderr)
            return 2
        links = discord_links(args.discord, token)
        old = youtube_links(links_file.read_text()) if links_file.exists() else []
        links_file.write_text("\n".join(dict.fromkeys(old + links)) + "\n")
        print(f"links.txt: {len(dict.fromkeys(old + links))} YouTube links", flush=True)
    if links_file.exists():
        download_links(youtube_links(links_file.read_text()), videos)

    todo = sorted(v for v in videos.iterdir() if v.suffix.lower() in VIDEO_EXT)
    for i, v in enumerate(todo, 1):
        dest = out / safe_stem(v)
        if (dest / "done").exists():
            continue
        dest.mkdir(exist_ok=True)
        print(f"[{i}/{len(todo)}] {v.name}", flush=True)
        if not (dest / "transcript.txt").exists():
            transcribe(v, dest)
        if not args.no_frames:
            screenshots(v, dest)
        (dest / "source.txt").write_text(v.name + "\n")
        (dest / "done").write_text("")
    done = sum((out / safe_stem(v) / "done").exists() for v in todo)
    print(f"\n{done} of {len(todo)} videos done; output in {out}")
    return 0


def _env(key: str) -> str | None:
    import os

    if os.environ.get(key):
        return os.environ[key]
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            k, _, v = line.strip().removeprefix("export ").partition("=")
            if k.strip() == key:
                return v.strip().strip("'\"")
    return None


if __name__ == "__main__":
    raise SystemExit(main())
