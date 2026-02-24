"""Local workspace operations: read/write files and git automation.

All paths are validated against the workspace root before any I/O so that
agents cannot escape the sandbox via path traversal.  Git subcommands run in
a dedicated thread pool to avoid blocking the FastAPI event loop.
"""

from __future__ import annotations

import subprocess
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pathlib import Path
from typing import Any

from .config import settings

# Dedicated pool for git subprocess calls.
_WS_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="workspace")


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _root() -> Path:
    """Resolved absolute workspace root (computed once per call — Path is cheap)."""
    return Path(settings.workspace_root).resolve()


def _resolve(repo_path: str, *parts: str) -> Path:
    """Return an absolute path under the workspace root.

    Resolves the root once, then joins parts with pure path arithmetic before
    a single final ``resolve()`` call — avoids one filesystem stat per part.
    Raises ``PermissionError`` on path-traversal attempts.
    """
    root = _root()
    base: Path = (root / repo_path).resolve() if repo_path else root
    for part in parts:
        if part:
            base = base / part  # pure join, no stat
    resolved = base.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        raise PermissionError(f"Path must be under workspace root: {root}")
    return resolved


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------


def read_file(repo_path: str, path: str) -> str:
    """Read *path* (relative to *repo_path*) from the local workspace."""
    full = _resolve(repo_path, path)
    if not full.is_file():
        raise FileNotFoundError(f"Not a file: {path}")
    return full.read_text(encoding="utf-8", errors="replace")


def write_file(repo_path: str, path: str, content: str) -> dict[str, Any]:
    """Write *content* to *path*, creating parent directories as needed."""
    full = _resolve(repo_path, path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    return {"path": path, "wrote": len(content)}


def list_dir(repo_path: str, subdir: str = "") -> list[dict[str, Any]]:
    """List files and directories under *repo_path/subdir*.

    Hidden entries (dot-files) are omitted except ``.git``.
    """
    full = _resolve(repo_path, subdir)
    if not full.is_dir():
        raise NotADirectoryError(f"Not a directory: {subdir or repo_path or '.'}")
    return [
        {"name": p.name, "type": "dir" if p.is_dir() else "file"}
        for p in sorted(full.iterdir())
        if not p.name.startswith(".") or p.name == ".git"
    ]


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _git(repo_path: str, *args: str) -> str:
    """Run a git command inside the workspace directory.

    Executes in the thread pool so it never blocks the event loop.
    Returns stdout as a string, or raises ``RuntimeError`` on non-zero exit.
    """
    def _run() -> str:
        root = _resolve(repo_path) if repo_path else _root()
        if not (root / ".git").exists():
            raise RuntimeError(f"Not a git repository: {root}")
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"git {' '.join(args)}: {result.stderr or result.stdout or 'failed'}"
            )
        return (result.stdout or "").strip()

    future = _WS_EXECUTOR.submit(_run)
    try:
        return future.result(timeout=65)
    except FuturesTimeoutError:
        raise TimeoutError(f"git {' '.join(args)} timed out")


def git_status(repo_path: str = "") -> str:
    """Return short git status and diff stat for the workspace."""
    status = _git(repo_path, "status", "--short")
    diff = _git(repo_path, "diff", "--stat")
    return "\n\n".join(filter(None, [status, diff])) or "Clean working tree."


def git_add(repo_path: str, paths: list[str]) -> dict[str, Any]:
    """Stage *paths*.  Pass ``['.']`` to stage everything."""
    for p in paths:
        _resolve(repo_path, p)  # path-traversal guard
    _git(repo_path, "add", "--", *paths)
    return {"staged": paths}


def git_commit(repo_path: str, message: str) -> dict[str, Any]:
    """Commit staged changes with *message* (use conventional style: fix:, feat:, …)."""
    output = _git(repo_path, "commit", "-m", message)
    return {"message": message, "output": output}


def git_push(repo_path: str, remote: str = "origin", branch: str | None = None) -> dict[str, Any]:
    """Push to *remote*.  Uses the current branch when *branch* is omitted."""
    args = ["push", remote]
    if branch:
        args.append(branch)
    output = _git(repo_path, *args)
    return {"remote": remote, "branch": branch, "output": output}


def git_current_branch(repo_path: str = "") -> str:
    """Return the current branch name (``HEAD`` if detached)."""
    return _git(repo_path, "rev-parse", "--abbrev-ref", "HEAD") or "HEAD"


def git_remote_url(repo_path: str = "", remote: str = "origin") -> str:
    """Return the URL for *remote*, or an empty string if not found."""
    try:
        return _git(repo_path, "remote", "get-url", remote)
    except RuntimeError:
        return ""
