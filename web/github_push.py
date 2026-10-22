"""Server-side GitHub push support (Git Data API, single commit).

Used by ``POST /api/github/push`` so the browser never talks to GitHub
directly: the Personal Access Token is sent to the local FastAPI server
only, and requests to ``api.github.com`` are made from the server.

The push uses the *Git Data* flow (blobs → tree → commit → ref update),
so all files land in **one commit** instead of one commit per file.

Requires a PAT with ``Contents: Read and write`` permission (classic) or
``contents: write`` (fine-grained). No third-party dependencies — stdlib
``urllib`` only.
"""
from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.request
from typing import Dict, List, Tuple

API_ROOT = "https://api.github.com"
API_VERSION = "2022-11-28"
USER_AGENT = "Video2ArabicSubs"
TIMEOUT_SECONDS = 60

#: GitHub blocks files > 100 MB through the Git Data/Contents APIs.
MAX_FILE_BYTES = 100 * 1024 * 1024

REPO_RE = re.compile(r"^[\w.\-]+/[\w.\-]+$")


class GitHubError(Exception):
    """A user-facing error (bad repo/branch/permission, network…)."""

    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status


def env_token_configured() -> bool:
    """True when the server has a ``GITHUB_TOKEN`` env var available."""
    return bool(os.environ.get("GITHUB_TOKEN", "").strip())


def _extract_detail(raw: bytes) -> str:
    try:
        payload = json.loads(raw.decode("utf-8", "replace"))
        message = payload.get("message", "")
        errors = payload.get("errors")
        if errors:
            details = "; ".join(
                e.get("message", str(e)) if isinstance(e, dict) else str(e)
                for e in errors
            )
            message = f"{message} — {details}"
        return message or "unknown error"
    except Exception:  # noqa: BLE001
        text = raw.decode("utf-8", "replace").strip()
        return text[:300] if text else "unknown error"


def _request(token: str, method: str, path: str, payload: dict = None) -> dict:
    url = f"{API_ROOT}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", API_VERSION)
    req.add_header("User-Agent", USER_AGENT)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            body = resp.read()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        try:
            detail = _extract_detail(exc.read())
        except Exception:  # noqa: BLE001
            detail = str(exc.reason)
        raise GitHubError(f"GitHub API error ({exc.code}): {detail}", exc.code) from exc
    except urllib.error.URLError as exc:
        raise GitHubError(f"Could not reach github.com: {exc.reason}") from exc
    except TimeoutError as exc:
        raise GitHubError("GitHub request timed out") from exc


def push_files(
    token: str,
    repo: str,
    branch: str,
    message: str,
    files: List[Tuple[str, bytes]],
) -> Dict[str, object]:
    """Push ``files`` (list of ``(path, bytes)``) to ``repo`` as one commit.

    Returns ``{"commit_sha", "html_url", "files", "repo", "branch"}``.
    Raises :class:`GitHubError` with a readable message on failure.
    """
    repo = (repo or "").strip()
    if not REPO_RE.match(repo):
        raise GitHubError(f"Invalid repository name {repo!r} — expected 'owner/repo'")
    if not files:
        raise GitHubError("No files to push")
    for path, data in files:
        if len(data) > MAX_FILE_BYTES:
            raise GitHubError(
                f"{path} is {len(data) / (1024 * 1024):.0f} MB — "
                "GitHub allows at most 100 MB per file"
            )

    # 1. Resolve the branch head commit.
    ref = _request(token, "GET", f"/repos/{repo}/git/ref/heads/{branch}")
    head_sha = ref["object"]["sha"]

    # 2. Base tree of that commit.
    base = _request(token, "GET", f"/repos/{repo}/git/commits/{head_sha}")
    base_tree = base["tree"]["sha"]

    # 3. Upload blobs + build the tree.
    tree_entries = []
    for path, data in files:
        blob = _request(
            token,
            "POST",
            f"/repos/{repo}/git/blobs",
            {"content": base64.b64encode(data).decode("ascii"), "encoding": "base64"},
        )
        tree_entries.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
    tree = _request(
        token,
        "POST",
        f"/repos/{repo}/git/trees",
        {"base_tree": base_tree, "tree": tree_entries},
    )

    # 4. Commit + fast-forward the branch.
    commit = _request(
        token,
        "POST",
        f"/repos/{repo}/git/commits",
        {"message": message, "tree": tree["sha"], "parents": [head_sha]},
    )
    _request(
        token,
        "PATCH",
        f"/repos/{repo}/git/refs/heads/{branch}",
        {"sha": commit["sha"], "force": False},
    )

    return {
        "commit_sha": commit["sha"],
        "html_url": commit.get("html_url", ""),
        "files": [path for path, _ in files],
        "repo": repo,
        "branch": branch,
    }
