"""Workspace MCP tools — local file I/O and git operations."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from ..workspace import (
    git_add as _git_add,
    git_commit as _git_commit,
    git_push as _git_push,
    git_status as _git_status,
    list_dir as _list_dir,
    read_file as _read_file,
    write_file as _write_file,
)

server = FastMCP("OpenX Workspace Tools")


@server.tool
def read_file(repo_path: str = "", path: str = "README.md") -> Any:
    """Read a file from the local workspace.

    repo_path: subdirectory of the workspace root (empty for root).
    path: file path relative to repo_path.
    """
    return _read_file(repo_path, path or "README.md")


@server.tool
def write_file(content: str, repo_path: str = "", path: str = "README.md") -> Any:
    """Write content to a file in the workspace, creating parent directories as needed."""
    return _write_file(repo_path, path or "README.md", content)


@server.tool
def list_dir(repo_path: str = "", subdir: str = "") -> Any:
    """List files and directories in the workspace."""
    return _list_dir(repo_path, subdir)


@server.tool
def git_status(repo_path: str = "") -> Any:
    """Show git status and diff stat for the local repository."""
    return _git_status(repo_path)


@server.tool
def git_add(paths: list[str], repo_path: str = "") -> Any:
    """Stage files for commit. Use paths=['.'] to stage everything."""
    return _git_add(repo_path, paths)


@server.tool
def git_commit(message: str, repo_path: str = "") -> Any:
    """Commit staged changes. Use conventional messages: fix:, feat:, refactor:, etc."""
    return _git_commit(repo_path, message)


@server.tool
def git_push(
    repo_path: str = "",
    remote: str = "origin",
    branch: str | None = None,
) -> Any:
    """Push commits to a remote. Uses the current branch when branch is omitted."""
    return _git_push(repo_path, remote, branch)
