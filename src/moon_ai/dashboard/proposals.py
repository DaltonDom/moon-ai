"""Proposals: the weekly report's suggested changes, as GitHub issues.

docs/design.md, "Weekly report and proposals". Each proposal is an issue
labelled `proposal` and needs the user's OK twice. Its stage is read from its
labels, and the dashboard's buttons set them:

| stage | labels | the button does |
|---|---|---|
| 0. approve test | `proposal` | "Yes, test it" adds `approved` |
| 1. testing | + `approved` | (the test runs as a trial) |
| 2. approve change | + `test-passed` | "Yes, use it" adds `adopted` |
| 3. live | + `adopted` | |

A test that fails gets `test-failed` and is closed. "No" closes the issue as
not planned with a `rejected` label, at any stage.
"""

from __future__ import annotations

import os
from typing import Any, Protocol

import httpx

REPO = "DaltonDom/moon-ai"
LABEL = "proposal"
API = "https://api.github.com"


class GitHub(Protocol):
    def proposals(self) -> list[dict[str, Any]]: ...
    def create_issue(self, title: str, body: str, labels: list[str]) -> dict[str, Any]:
        r = self.http.post(
            f"/repos/{self.repo}/issues", json={"title": title, "body": body, "labels": labels}
        )
        r.raise_for_status()
        return r.json()

    def add_label(self, number: int, label: str) -> None: ...
    def comment(self, number: int, body: str) -> None: ...
    def close(self, number: int, reason: str) -> None: ...


class NoGitHub(Exception):
    """No token, so proposals can't be read or acted on."""


class RestGitHub:
    """The GitHub REST API with a token from `GITHUB_TOKEN` (fine-grained,
    issues read and write on this repository only)."""

    def __init__(
        self, token: str | None = None, repo: str = REPO, client: httpx.Client | None = None
    ):
        token = token or os.environ.get("GITHUB_TOKEN")
        if not token:
            raise NoGitHub(
                "Set GITHUB_TOKEN to a fine-grained token with issue access to "
                f"{repo} to see and approve proposals here."
            )
        self.repo = repo
        self.http = client or httpx.Client(
            base_url=API,
            timeout=15,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

    def proposals(self) -> list[dict[str, Any]]:
        r = self.http.get(
            f"/repos/{self.repo}/issues", params={"labels": LABEL, "state": "all", "per_page": 50}
        )
        r.raise_for_status()
        return [i for i in r.json() if "pull_request" not in i]

    def add_label(self, number: int, label: str) -> None:
        self.http.post(
            f"/repos/{self.repo}/issues/{number}/labels", json={"labels": [label]}
        ).raise_for_status()

    def comment(self, number: int, body: str) -> None:
        self.http.post(
            f"/repos/{self.repo}/issues/{number}/comments", json={"body": body}
        ).raise_for_status()

    def close(self, number: int, reason: str) -> None:
        self.http.patch(
            f"/repos/{self.repo}/issues/{number}", json={"state": "closed", "state_reason": reason}
        ).raise_for_status()


STAGES = ("approve test", "testing", "approve change", "live")
FOOTER = "\n\n---\n_Sent from the moon-ai dashboard._"


def stage(issue: dict[str, Any]) -> str:
    labels = {lb["name"] for lb in issue.get("labels", [])}
    if (
        "rejected" in labels
        or "test-failed" in labels
        or (issue.get("state") == "closed" and "adopted" not in labels)
    ):
        return "closed"
    if "adopted" in labels:
        return "live"
    if "test-passed" in labels:
        return "approve change"
    if "approved" in labels:
        return "testing"
    return "approve test"


def summarize(issue: dict[str, Any]) -> dict[str, Any]:
    return {
        "number": issue["number"],
        "title": issue["title"],
        "body": issue.get("body") or "",
        "url": issue.get("html_url"),
        "stage": stage(issue),
        "needs_you": stage(issue) in ("approve test", "approve change"),
    }


def approve(gh: GitHub, issue: dict[str, Any]) -> str:
    """The stage's "yes". Returns the new stage; refuses when no OK is due."""
    s = stage(issue)
    n = issue["number"]
    if s == "approve test":
        gh.add_label(n, "approved")
        gh.comment(
            n, "Approved for testing. It runs as a trial under the setup testing protocol." + FOOTER
        )
        return "testing"
    if s == "approve change":
        gh.add_label(n, "adopted")
        gh.comment(n, "Test result approved: use this change." + FOOTER)
        return "live"
    raise ValueError(f"proposal #{n} is at '{s}'; there's nothing to approve")


def reject(gh: GitHub, issue: dict[str, Any]) -> str:
    s = stage(issue)
    n = issue["number"]
    if s in ("live", "closed"):
        raise ValueError(f"proposal #{n} is already {s}")
    gh.add_label(n, "rejected")
    gh.comment(n, f"Rejected at '{s}'." + FOOTER)
    gh.close(n, "not_planned")
    return "closed"
