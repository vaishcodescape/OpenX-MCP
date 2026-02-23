"""Local workspace: read/write files and git operations for modify-commit-push automation."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from .config import settings


def _workspace_root() -> Path:
    return Path(settings.workspace_root).resolve()


def _resolve(repo_path: str, *parts: str) -> Path:
    """Resolve path under workspace root. Disallow escaping (..)."""
    root = _workspace_root()
    if repo_path:
        base = (root / repo_path).resolve()
    else:
        base = root
    for p in parts:
        if p:
            base = (base / p).resolve()
    try:
        base.relative_to(root)
    except ValueError:
        raise PermissionError(f"Path must be under workspace root: {root}")
    return base


def read_file(repo_path: str, path: str) -> str:
    """Read a file from the local workspace. repo_path: subdir of workspace or '' for root."""
    full = _resolve(repo_path, path)
    if not full.is_file():
        raise FileNotFoundError(f"Not a file: {path}")
    return full.read_text(encoding="utf-8", errors="replace")


def write_file(repo_path: str, path: str, content: str) -> dict[str, Any]:
    """Write content to a file. Creates parent dirs. Best practice: preserve style and add tests if needed."""
    full = _resolve(repo_path, path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    return {"path": path, "wrote": len(content)}


def list_dir(repo_path: str, subdir: str = "") -> list[dict[str, Any]]:
    """List files and dirs under repo_path/subdir. Entries have name, type (file|dir)."""
    full = _resolve(repo_path, subdir)
    if not full.is_dir():
        raise NotADirectoryError(f"Not a directory: {subdir or repo_path or '.'}")
    result: list[dict[str, Any]] = []
    for p in sorted(full.iterdir()):
        if p.name.startswith(".") and p.name != ".git":
            continue
        result.append({"name": p.name, "type": "dir" if p.is_dir() else "file"})
    return result


def _git(repo_path: str, *args: str, capture: bool = True) -> str:
    root = _resolve(repo_path) if repo_path else _workspace_root()
    if not (root / ".git").exists():
        raise RuntimeError(f"Not a git repository: {root}")
    cmd = ["git", "-C", str(root)] + list(args)
    r = subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        timeout=60,
    )
    if r.returncode != 0 and capture:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr or r.stdout or 'failed'}")
    return (r.stdout or "").strip() if capture else ""


def git_status(repo_path: str = "") -> str:
    """Return git status (short) and diff stat for the workspace."""
    out = _git(repo_path, "status", "--short")
    diff = _git(repo_path, "diff", "--stat")
    if diff:
        out += "\n\n" + diff
    return out or "Clean working tree."


def git_add(repo_path: str, paths: list[str]) -> dict[str, Any]:
    """Stage paths. Use ['.'] for all."""
    root = _resolve(repo_path) if repo_path else _workspace_root()
    for p in paths:
        _resolve(repo_path, p)  # validate
    _git(repo_path, "add", "--", *paths)
    return {"staged": paths}


def git_commit(repo_path: str, message: str) -> dict[str, Any]:
    """Commit staged changes. Message should be clear and conventional (e.g. fix: ..., feat: ...)."""
    out = _git(repo_path, "commit", "-m", message)
    return {"message": message, "output": out}


def git_push(repo_path: str, remote: str = "origin", branch: str | None = None) -> dict[str, Any]:
    """Push to remote. If branch omitted, push current branch."""
    args = ["push", remote]
    if branch:
        args.append(branch)
    out = _git(repo_path, *args)
    return {"remote": remote, "branch": branch, "output": out}


def git_current_branch(repo_path: str = "") -> str:
    """Return current branch name."""
    return _git(repo_path, "rev-parse", "--abbrev-ref", "HEAD") or "HEAD"
