"""Compare the running build against the latest commit on GitHub.

Backs the Software Updates admin page. The running build is stamped into the
Docker image by CI (``APP_GIT_SHA`` / ``APP_BUILD_TIME``); the latest version is
the head commit of the repo's default branch, fetched from the GitHub API and
cached briefly. Network/JSON failures degrade to an ``error`` state — callers
never see an exception.
"""

import logging
from datetime import datetime, timezone

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
DEFAULT_BRANCH = "main"
CACHE_KEY = "software_update_latest"
CACHE_TTL = 300  # seconds
REQUEST_TIMEOUT = 5


def _short(sha):
    return sha[:7] if sha else ""


def _headers():
    headers = {"Accept": "application/vnd.github+json"}
    token = getattr(settings, "GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def get_running_version():
    """Version baked into the running image, or None if unknown (e.g. dev)."""
    sha = getattr(settings, "APP_GIT_SHA", "") or ""
    if not sha:
        return None
    return {
        "sha": sha,
        "short_sha": _short(sha),
        "build_time": getattr(settings, "APP_BUILD_TIME", "") or "",
    }


def _fetch_latest():
    repo = settings.GITHUB_REPO
    url = f"{GITHUB_API}/repos/{repo}/commits/{DEFAULT_BRANCH}"
    resp = requests.get(url, headers=_headers(), timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    commit = data.get("commit", {})
    message = (commit.get("message") or "").split("\n", 1)[0]
    committer = commit.get("committer") or {}
    author = commit.get("author") or {}
    return {
        "sha": data["sha"],
        "short_sha": _short(data["sha"]),
        "message": message,
        "date": committer.get("date") or author.get("date") or "",
        "html_url": data.get("html_url", ""),
    }


def get_latest_version(force_refresh=False):
    """Latest commit on the default branch (cached ~5 min). Raises on failure."""
    if force_refresh:
        cache.delete(CACHE_KEY)
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached
    latest = _fetch_latest()
    cache.set(CACHE_KEY, latest, CACHE_TTL)
    return latest


def _behind_count(running_sha, latest_sha):
    """How many commits the running build is behind (best-effort, None on error)."""
    repo = settings.GITHUB_REPO
    url = f"{GITHUB_API}/repos/{repo}/compare/{running_sha}...{latest_sha}"
    try:
        resp = requests.get(url, headers=_headers(), timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json().get("ahead_by")
    except (requests.RequestException, ValueError):
        return None


def get_update_status(force_refresh=False):
    """Running vs latest, as a template-friendly dict that never raises.

    state is one of: up_to_date, update_available, unknown (running build not
    stamped), error (GitHub unreachable).
    """
    running = get_running_version()
    checked_at = datetime.now(timezone.utc)

    try:
        latest = get_latest_version(force_refresh=force_refresh)
    except (requests.RequestException, ValueError, KeyError) as exc:
        logger.warning("Software update check failed: %s", exc)
        return {
            "state": "error",
            "running": running,
            "latest": None,
            "behind_count": None,
            "checked_at": checked_at,
            "error": "Could not reach GitHub to check for updates.",
        }

    if running is None:
        state, behind = "unknown", None
    elif running["sha"] == latest["sha"]:
        state, behind = "up_to_date", 0
    else:
        state, behind = "update_available", _behind_count(running["sha"], latest["sha"])

    return {
        "state": state,
        "running": running,
        "latest": latest,
        "behind_count": behind,
        "checked_at": checked_at,
        "error": None,
    }
