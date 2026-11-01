"""scripts/media/ingest.py: the parts that don't need Whisper or the network."""

import importlib.util
import shutil
import subprocess
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "ingest", Path(__file__).parents[1] / "scripts" / "media" / "ingest.py"
)
ingest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ingest)


def test_timestamps_and_frame_names():
    assert ingest.mmss(754.9) == "12:34" and ingest.mmss(3725) == "1:02:05"
    assert ingest.frame_name(1) == "00-00.jpg" and ingest.frame_name(26) == "12-30.jpg"
    segs = [{"start": 0.0, "text": " Fair value "}, {"start": 61.2, "text": "  "}]
    assert ingest.transcript_lines(segs) == ["[00:00] Fair value"]


def test_youtube_links_are_found_once_in_order():
    text = (
        "watch https://youtu.be/abcdefghijk then https://www.youtube.com/watch?v=ZYXWVUTSRQP&t=30s "
        "and again (https://youtu.be/abcdefghijk). not https://example.com/x"
    )
    assert ingest.youtube_links(text) == [
        "https://youtu.be/abcdefghijk",
        "https://www.youtube.com/watch?v=ZYXWVUTSRQP&t=30s",
    ]


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_screenshots_every_30_seconds_named_by_time(tmp_path):
    video = tmp_path / "v.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=65:size=320x240:rate=5",
            str(video),
        ],
        check=True,
    )
    ingest.screenshots(video, tmp_path)
    assert sorted(f.name for f in (tmp_path / "frames").iterdir()) == [
        "00-00.jpg",
        "00-30.jpg",
        "01-00.jpg",
    ]


def test_finished_videos_are_skipped(tmp_path, monkeypatch):
    (tmp_path / "videos").mkdir()
    (tmp_path / "videos" / "a.mp4").write_bytes(b"x")
    done = tmp_path / "out" / "a"
    done.mkdir(parents=True)
    (done / "done").write_text("")
    monkeypatch.setattr(ingest, "transcribe", lambda *a: pytest.fail("re-transcribed"))
    assert ingest.main([str(tmp_path), "--no-frames"]) == 0
