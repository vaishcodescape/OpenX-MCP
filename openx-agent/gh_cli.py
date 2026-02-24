"""Fast GitHub operations via `gh` CLI (subprocess). Used when available; falls back to PyGithub."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any, Callable, TypeVar

from .config import settings

T = TypeVar("T")

logger = logging.getLogger(__name__)

# Timeout for a single gh command (seconds).
_GH_TIMEOUT = 30
# Max workers for parallel gh calls.
_EXECUTOR = ThreadPoolExecutor(max_workers=10, thread_name_prefix="gh_cli")


# ---------------------------------------------------------------------------
# Cached env dict — avoid copying all of os.environ on every subprocess call.
# We cache on the (token, base_url) pair so a config change invalidates it.
# ---------------------------------------------------------------------------

_gh_env_cache: dict[str, str] | None = None
_gh_env_cache_key: tuple[str | None, str | None] = (None, None)
_gh_env_lock = threading.Lock()


def _gh_env() -> dict[str, str]:
    global _gh_env_cache, _gh_env_cache_key
    key = (settings.github_token, settings.github_base_url)
    # Fast path: no lock needed for a cache hit on an immutable key.
    if _gh_env_cache is not None and _gh_env_cache_key == key:
        return _gh_env_cache
    with _gh_env_lock:
        # Re-check inside lock in case another thread beat us here.
        if _gh_env_cache is not None and _gh_env_cache_key == key:
            return _gh_env_cache
        env = {**os.environ}
        if settings.github_token:
            env["GH_TOKEN"] = settings.github_token
        if settings.github_base_url:
            from urllib.parse import urlparse
            parsed = urlparse(settings.github_base_url)
            if parsed.hostname:
                env["GH_HOST"] = parsed.hostname
        _gh_env_cache = env
        _gh_env_cache_key = key
    return _gh_env_cache


def _run_gh(*args: str, timeout: int = _GH_TIMEOUT) -> str | None:
    """Run gh with args; return stdout or None on failure."""
    try:
        r = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_gh_env(),
        )
        if r.returncode != 0:
            logger.debug("gh %s failed (rc=%d): %s", " ".join(args), r.returncode, (r.stderr or "").strip())
            return None
        return (r.stdout or "").strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        logger.debug("gh %s exception: %s", " ".join(args), exc)
        return None


_gh_available: bool | None = None
_gh_available_lock = threading.Lock()


def available() -> bool:
    """Return True if gh is installed and authenticated (and we have a token)."""
    global _gh_available
    # Fast path: already resolved, no lock needed.
    if _gh_available is not None:
        return _gh_available
    if not settings.github_token:
        _gh_available = False
        return False
    with _gh_available_lock:
        # Re-check inside lock in case another thread just set it.
        if _gh_available is not None:
            return _gh_available
        try:
            r = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                text=True,
                timeout=5,
                env=_gh_env(),
            )
            out = (r.stdout or "") + (r.stderr or "")
            _gh_available = r.returncode == 0 and ("Logged in" in out or "logged in" in out)
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            _gh_available = False
    return _gh_available or False


def list_repos(org: str | None = None) -> list[dict[str, Any]] | None:
    """List repos via gh. Returns same shape as github_client.list_repos or None to fall back."""
    args = ["repo", "list", "--limit", "100", "--json", "nameWithOwner,isPrivate,defaultBranchRef,url"]
    if org:
        args.extend([org])
    out = _run_gh(*args)
    if not out:
        return None
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return None
    result = []
    for r in data:
        default_branch = "main"
        if isinstance(r.get("defaultBranchRef"), dict):
            ref = r["defaultBranchRef"].get("name")
            if ref:
                default_branch = ref
        result.append({
            "full_name": r.get("nameWithOwner", ""),
            "private": r.get("isPrivate", False),
            "default_branch": default_branch,
            "html_url": r.get("url", ""),
        })
    return result


def list_open_prs(repo_full_name: str, include_ci_status: bool = False) -> list[dict[str, Any]] | None:
    """List open PRs via gh. include_ci_status: if True we still skip (use API fallback for CI)."""
    json_fields = "number,title,author,state,url"
    if include_ci_status:
        json_fields += ",statusCheckRollup"
    out = _run_gh(
        "pr", "list",
        "--repo", repo_full_name,
        "--state", "open",
        "--limit", "100",
        "--json", json_fields,
    )
    if not out:
        return None
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return None
    result = []
    for pr in data:
        author = pr.get("author") or {}
        login = author.get("login", "") if isinstance(author, dict) else ""
        entry: dict[str, Any] = {
            "number": pr.get("number"),
            "title": pr.get("title", ""),
            "user": login,
            "state": pr.get("state", "open"),
            "html_url": pr.get("url", ""),
        }
        if include_ci_status and "statusCheckRollup" in pr:
            statuses = pr.get("statusCheckRollup") or []
            conclusions = [s.get("conclusion") for s in statuses if isinstance(s, dict) and s.get("conclusion")]
            if any(c in ("FAILURE", "ERROR", "CANCELLED", "TIMED_OUT") for c in conclusions):
                entry["ci_status"] = "failure"
            elif all(c == "SUCCESS" for c in conclusions):
                entry["ci_status"] = "success"
            else:
                entry["ci_status"] = "pending"
        result.append(entry)
    return result


def get_pr(repo_full_name: str, number: int) -> dict[str, Any] | None:
    """Get PR details via gh. Returns same shape as github_client.get_pr (best effort)."""
    out = _run_gh(
        "pr", "view", str(number),
        "--repo", repo_full_name,
        "--json", "number,title,body,state,author,url,headRefName,baseRefName,headRefOid",
        timeout=20,
    )
    if not out:
        return None
    try:
        pr = json.loads(out)
    except json.JSONDecodeError:
        return None
    author = pr.get("author") or {}
    login = author.get("login", "") if isinstance(author, dict) else ""

    diff_out = _run_gh("pr", "diff", str(number), "--repo", repo_full_name, timeout=25)
    diff_text = (diff_out or "")[:50000]

    return {
        "number": pr.get("number"),
        "title": pr.get("title", ""),
        "body": pr.get("body") or "",
        "state": pr.get("state", ""),
        "user": login,
        "html_url": pr.get("url", ""),
        "head": pr.get("headRefName", ""),
        "base": pr.get("baseRefName", ""),
        "head_sha": pr.get("headRefOid", ""),
        "files_changed": [],
        "diff": diff_text,
        "ci_checks": [],
    }


def list_issues(repo_full_name: str, state: str = "open") -> list[dict[str, Any]] | None:
    """List issues via gh."""
    out = _run_gh(
        "issue", "list",
        "--repo", repo_full_name,
        "--state", state,
        "--limit", "100",
        "--json", "number,title,state,author,url,labels",
    )
    if not out:
        return None
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return None
    result = []
    for i in data:
        author = i.get("author") or {}
        login = author.get("login") if isinstance(author, dict) else None
        labels = i.get("labels") or []
        label_names = [lb.get("name", "") for lb in labels if isinstance(lb, dict)]
        result.append({
            "number": i.get("number"),
            "title": i.get("title", ""),
            "state": i.get("state", "open"),
            "user": login,
            "html_url": i.get("url", ""),
            "labels": label_names,
        })
    return result


def get_issue(repo_full_name: str, number: int) -> dict[str, Any] | None:
    """Get one issue via gh."""
    out = _run_gh(
        "issue", "view", str(number),
        "--repo", repo_full_name,
        "--json", "number,title,body,state,author,url,labels",
    )
    if not out:
        return None
    try:
        i = json.loads(out)
    except json.JSONDecodeError:
        return None
    author = i.get("author") or {}
    login = author.get("login") if isinstance(author, dict) else None
    labels = i.get("labels") or []
    label_names = [lb.get("name", "") for lb in labels if isinstance(lb, dict)]
    return {
        "number": i.get("number"),
        "title": i.get("title", ""),
        "body": i.get("body") or "",
        "state": i.get("state", ""),
        "user": login,
        "html_url": i.get("url", ""),
        "labels": label_names,
    }


# Allowed first-level gh subcommands for run_gh_command (avoids auth, config, etc.).
_ALLOWED_GH_SUBCOMMANDS = frozenset({"pr", "issue", "repo", "run", "workflow", "api"})


def _run_gh_capture_both(*args: str, timeout: int = _GH_TIMEOUT) -> str | None:
    """Run gh; return combined stdout + stderr or None on failure (so we can parse URL from either stream)."""
    try:
        r = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_gh_env(),
        )
        if r.returncode != 0:
            logger.debug("gh %s failed (rc=%d): %s", " ".join(args), r.returncode, (r.stderr or "").strip())
            return None
        return ((r.stdout or "") + " " + (r.stderr or "")).strip() or None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        logger.debug("gh %s exception: %s", " ".join(args), exc)
        return None


# Match issue/PR URLs from any GitHub host (github.com or enterprise).
_ISSUE_URL_RE = re.compile(r"(https?://[^\s/]+/[^/]+/[^/]+/issues/(\d+))")
_PULL_URL_RE = re.compile(r"(https?://[^\s/]+/[^/]+/[^/]+/pull/(\d+))")


def create_issue(repo_full_name: str, title: str, body: str = "", labels: list[str] | None = None) -> dict[str, Any] | None:
    """Create an issue via gh. Returns dict with number, title, state, html_url or None on failure."""
    args = ["issue", "create", "--repo", repo_full_name, "--title", title]
    if body:
        args.extend(["--body", body])
    else:
        args.extend(["--body", ""])
    if labels:
        for lb in labels:
            args.extend(["--label", lb])
    out = _run_gh_capture_both(*args, timeout=15)
    if not out:
        return None
    m = _ISSUE_URL_RE.search(out)
    if not m:
        return None  # No parseable URL; fall back to API
    url, number_str = m.group(1), m.group(2)
    number = int(number_str)
    return {"number": number, "title": title, "state": "open", "html_url": url}


def create_pr(
    repo_full_name: str,
    title: str,
    head: str,
    base: str = "main",
    body: str = "",
) -> dict[str, Any] | None:
    """Create a PR via gh. Returns dict with number, title, state, html_url or None on failure."""
    args = [
        "pr", "create",
        "--repo", repo_full_name,
        "--title", title,
        "--head", head,
        "--base", base,
    ]
    if body:
        args.extend(["--body", body])
    else:
        args.extend(["--body", ""])
    out = _run_gh_capture_both(*args, timeout=20)
    if not out:
        return None
    m = _PULL_URL_RE.search(out)
    if not m:
        return None  # No parseable URL; fall back to API
    url, number_str = m.group(1), m.group(2)
    number = int(number_str)
    return {"number": number, "title": title, "state": "open", "html_url": url}


def run_gh_command(command: str, timeout: int = 25) -> str:
    """Run a gh CLI command string (e.g. 'pr list --repo owner/repo'). Returns combined stdout and stderr.
    Only allowed subcommands: pr, issue, repo, run, workflow, api. Raises ValueError if disallowed or empty.
    """
    parts = [p.strip() for p in command.split() if p.strip()]
    if not parts:
        raise ValueError("Empty gh command")
    sub = parts[0].lower()
    if sub not in _ALLOWED_GH_SUBCOMMANDS:
        raise ValueError(f"Subcommand not allowed: {sub}. Allowed: {', '.join(sorted(_ALLOWED_GH_SUBCOMMANDS))}")
    try:
        r = subprocess.run(
            ["gh", *parts],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_gh_env(),
        )
        out = (r.stdout or "").strip()
        err = (r.stderr or "").strip()
        if r.returncode != 0 and err:
            return f"{out}\n{err}" if out else err
        return out or "(no output)"
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"gh {sub} timed out after {timeout}s")
    except FileNotFoundError:
        raise RuntimeError("gh CLI is not installed. Install it from https://cli.github.com/")
    except OSError as e:
        raise RuntimeError(f"gh command failed: {e}")


def run_in_background(func: Callable[..., T], *args: Any, timeout: int | None = None, **kwargs: Any) -> T:
    """Run a callable in the thread pool; wait for result. Use for non-blocking execution vs main thread."""
    effective_timeout = timeout if timeout is not None else _GH_TIMEOUT + 5
    future = _EXECUTOR.submit(func, *args, **kwargs)
    try:
        return future.result(timeout=effective_timeout)
    except FuturesTimeoutError:
        raise TimeoutError(f"gh operation timed out after {effective_timeout}s")
