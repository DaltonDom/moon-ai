"""Backtest jobs queued from the dashboard's "Run backtest" button.

A job is one JSON file in `data/jobs/`, so a queued job survives a restart and
`ls` shows what's waiting. One worker thread runs them in order, each as
`moon-ai backtest <setup> --from --to --no-open` in a child process, with its
output in `<job id>.log` beside it.

A backtest never changes the live rules: it only writes a new run folder and
report card.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from moon_ai.setups import load_setup_defaults

STATES = ("queued", "running", "done", "failed")


@dataclass
class Job:
    job_id: str
    setup: str
    start: str
    end: str
    trial: str | None
    state: str
    queued_at: str
    started_at: str | None = None
    finished_at: str | None = None
    exit_code: int | None = None
    report: str | None = None


Runner = Callable[[Job, Path], tuple[int, str | None]]  # -> (exit code, report path)


def cli_runner(job: Job, log: Path) -> tuple[int, str | None]:
    cmd = [
        sys.executable,
        "-m",
        "moon_ai.cli",
        "backtest",
        job.setup,
        "--from",
        job.start,
        "--to",
        job.end,
        "--no-open",
    ]
    if job.trial:
        cmd += ["--trial", job.trial]
    with log.open("w") as out:
        code = subprocess.call(cmd, stdout=out, stderr=subprocess.STDOUT)
    report = None
    for line in log.read_text().splitlines():
        if line.startswith("report card: "):
            report = line.removeprefix("report card: ").strip()
    return code, report


class JobQueue:
    def __init__(
        self,
        folder: Path,
        runner: Runner = cli_runner,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self.folder = Path(folder)
        self.runner = runner
        self.now = now
        self._lock = threading.Lock()
        self._wake = threading.Event()

    def submit(self, setup: str, start: date, end: date, trial: str | None = None) -> Job:
        defaults = load_setup_defaults()
        if setup not in defaults:
            raise ValueError(f"unknown setup {setup!r}")
        if trial and trial not in {t.name for t in defaults[setup].all_trials}:
            raise ValueError(f"{setup} has no pre-registered retest {trial!r}")
        if end <= start:
            raise ValueError("the end date must be after the start date")
        now = self.now()
        job = Job(
            job_id=f"{now:%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:6]}",
            setup=setup,
            start=start.isoformat(),
            end=end.isoformat(),
            trial=trial,
            state="queued",
            queued_at=now.isoformat(),
        )
        self._save(job)
        self._wake.set()
        return job

    def list(self) -> list[Job]:
        if not self.folder.exists():
            return []
        jobs = [Job(**json.loads(p.read_text())) for p in self.folder.glob("*.json")]
        return sorted(jobs, key=lambda j: j.job_id, reverse=True)

    def get(self, job_id: str) -> Job | None:
        path = self.folder / f"{job_id}.json"
        if path.parent != self.folder or not path.exists():
            return None
        return Job(**json.loads(path.read_text()))

    def log(self, job_id: str) -> str | None:
        path = self.folder / f"{job_id}.log"
        return path.read_text() if self.get(job_id) and path.exists() else None

    def run_next(self) -> Job | None:
        """Run the oldest queued job, if any. Returns it once finished."""
        with self._lock:
            queued = [j for j in reversed(self.list()) if j.state == "queued"]
            if not queued:
                return None
            job = queued[0]
            job.state, job.started_at = "running", self.now().isoformat()
            self._save(job)
        try:
            code, report = self.runner(job, self.folder / f"{job.job_id}.log")
        except Exception as exc:  # a crashed runner must not kill the worker
            (self.folder / f"{job.job_id}.log").write_text(f"crashed: {exc!r}\n")
            code, report = -1, None
        job.state = "done" if code == 0 else "failed"
        job.exit_code, job.report, job.finished_at = code, report, self.now().isoformat()
        self._save(job)
        return job

    def recover(self) -> None:
        """A job left `running` by a restart is failed: its process is gone."""
        for j in self.list():
            if j.state == "running":
                j.state, j.finished_at = "failed", self.now().isoformat()
                self._save(j)

    def worker(self, stop: threading.Event) -> None:
        self.recover()
        while not stop.is_set():
            if self.run_next() is None:
                self._wake.wait(timeout=5)
                self._wake.clear()

    def _save(self, job: Job) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        tmp = self.folder / f"{job.job_id}.json.tmp"
        tmp.write_text(json.dumps(asdict(job), indent=1) + "\n")
        tmp.replace(self.folder / f"{job.job_id}.json")

    @staticmethod
    def as_dict(job: Job) -> dict[str, Any]:
        return asdict(job)
