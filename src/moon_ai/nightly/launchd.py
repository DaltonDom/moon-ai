"""Install the nightly job as the user's own launchd agent (no admin password).

launchd wakes `moon-ai nightly run --scheduled` every hour at :35. The job
itself decides whether to run: after 18:30 New York, once a day. That keeps
it right whatever the Mac's time zone, and through daylight-saving changes.
If the Mac is asleep, launchd runs it on wake.
"""

from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
from pathlib import Path

LABEL = "com.moonai.nightly"
AGENTS = Path.home() / "Library" / "LaunchAgents"
REPO = Path(__file__).resolve().parents[3]


def plist(repo: Path = REPO, uv: str | None = None) -> dict:
    uv = uv or shutil.which("uv") or "uv"
    logs = repo / "data" / "logs"
    return {
        "Label": LABEL,
        "ProgramArguments": [
            uv,
            "run",
            "--project",
            str(repo),
            "moon-ai",
            "nightly",
            "run",
            "--scheduled",
        ],
        "WorkingDirectory": str(repo),
        "StartCalendarInterval": {"Minute": 35},
        "StandardOutPath": str(logs / "nightly.log"),
        "StandardErrorPath": str(logs / "nightly.log"),
        "EnvironmentVariables": {"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
    }


DASHBOARD_LABEL = "com.moonai.dashboard"


def dashboard_plist(repo: Path = REPO, uv: str | None = None) -> dict:
    """Keeps `moon-ai dashboard` up at http://localhost:8000: started at login,
    restarted if it stops."""
    uv = uv or shutil.which("uv") or "uv"
    logs = repo / "data" / "logs"
    return {
        "Label": DASHBOARD_LABEL,
        "ProgramArguments": [uv, "run", "--project", str(repo), "moon-ai", "dashboard"],
        "WorkingDirectory": str(repo),
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 30,
        "StandardOutPath": str(logs / "dashboard.log"),
        "StandardErrorPath": str(logs / "dashboard.log"),
        "EnvironmentVariables": {"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
    }


def install(
    agents: Path = AGENTS, repo: Path = REPO, load: bool = True, label: str = LABEL
) -> Path:
    agents.mkdir(parents=True, exist_ok=True)
    (repo / "data" / "logs").mkdir(parents=True, exist_ok=True)
    path = agents / f"{label}.plist"
    with path.open("wb") as fh:
        plistlib.dump(dashboard_plist(repo) if label == DASHBOARD_LABEL else plist(repo), fh)
    if load:
        uid = os.getuid()
        subprocess.run(["launchctl", "bootout", f"gui/{uid}", str(path)], capture_output=True)
        subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(path)], check=True)
    return path


def uninstall(agents: Path = AGENTS, unload: bool = True, label: str = LABEL) -> bool:
    path = agents / f"{label}.plist"
    if not path.exists():
        return False
    if unload:
        subprocess.run(
            ["launchctl", "bootout", f"gui/{os.getuid()}", str(path)], capture_output=True
        )
    path.unlink()
    return True
