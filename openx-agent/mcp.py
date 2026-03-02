"""MCP server — FastMCP-based tool registry with backward-compatible API.

Tools are registered via FastMCP ``@mcp.tool`` for native MCP protocol support
(stdio, HTTP/SSE) and simultaneously stored in a lightweight compat layer so
that ``langchain_agent``, ``command_router``, and ``main`` can keep using
``TOOLS``, ``call_tool()``, and ``list_tools()`` unchanged.
"""

from __future__ import annotations

import inspect
import types
from dataclasses import dataclass, field
from typing import Any, Callable, get_type_hints

from fastmcp import FastMCP

from .analysis.ai_analysis import analyze_with_ai
from .analysis.architecture import summarize_architecture
from .analysis.format_report import format_analysis_report
from .analysis.static_analysis import analyze_static
from .config import config_settings, resolve_repo
from .gh_cli import run_gh_command, run_in_background
from .workspace import (
    git_add,
    git_commit,
    git_current_branch,
    git_push,
    git_status,
    list_dir as ws_list_dir,
    read_file as ws_read_file,
    write_file as ws_write_file,
)
from .github_client import (
    analyze_ci_failure as gh_analyze_ci_failure,
    apply_fix_to_pr as gh_apply_fix_to_pr,
    close_issue,
    comment_issue,
    comment_pr,
    create_issue,
    create_pull,
    generate_fix_patch as gh_generate_fix_patch,
    get_ci_logs as gh_get_ci_logs,
    get_failing_prs as gh_get_failing_prs,
    get_issue,
    get_pr,
    get_readme as gh_get_readme,
    get_repo,
    heal_failing_pr as gh_heal_failing_pr,
    get_workflow_run,
    list_issues,
    list_open_prs,
    list_repos,
    list_workflow_runs,
    list_workflows,
    locate_code_context as gh_locate_code_context,
    merge_pr,
    rerun_ci as gh_rerun_ci,
    trigger_workflow,
    update_readme as gh_update_readme,
)

# ---------------------------------------------------------------------------
# FastMCP server instance
# ---------------------------------------------------------------------------

mcp = FastMCP("OpenX")

# ---------------------------------------------------------------------------
# Backward-compat layer (consumed by langchain_agent / command_router / main)
# ---------------------------------------------------------------------------


@dataclass
class ToolCompat:
    """Minimal mirror of the old ``Tool`` Pydantic model so existing consumers
    can keep reading ``.name``, ``.description``, and ``.input_schema``."""

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)


TOOLS: dict[str, ToolCompat] = {}
_HANDLERS: dict[str, Callable[..., Any]] = {}


def _py_to_json_type(tp: Any) -> str:
    """Map a Python type annotation to its JSON-Schema string."""
    if tp is int:
        return "integer"
    if tp is float:
        return "number"
    if tp is bool:
        return "boolean"
    if tp is str:
        return "string"
    origin = getattr(tp, "__origin__", None)
    if tp is list or origin is list:
        return "array"
    if tp is dict or origin is dict:
        return "object"
    # Union / Optional — pick the first non-None branch.
    if origin is types.UnionType or origin is type(int | str):
        args = [a for a in tp.__args__ if a is not type(None)]
        return _py_to_json_type(args[0]) if args else "string"
    return "string"


def _schema_from_sig(
    func: Callable[..., Any],
    param_descs: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build a JSON-Schema-like dict from *func*'s signature + type hints."""
    sig = inspect.signature(func)
    try:
        hints = get_type_hints(func)
    except Exception:
        hints = {}

    descs = param_descs or {}
    properties: dict[str, Any] = {}
    required: list[str] = []

    for pname, param in sig.parameters.items():
        tp = hints.get(pname)
        entry: dict[str, Any] = {"type": _py_to_json_type(tp) if tp else "string"}
        if pname in descs:
            entry["description"] = descs[pname]
        properties[pname] = entry
        if param.default is inspect.Parameter.empty:
            required.append(pname)

    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _tool(dotted_name: str, param_descs: dict[str, str] | None = None):
    """Register *func* with both FastMCP and the backward-compat ``TOOLS`` dict."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        mcp.tool(name=dotted_name)(func)

        schema = _schema_from_sig(func, param_descs)
        doc = (inspect.getdoc(func) or "").strip()
        TOOLS[dotted_name] = ToolCompat(
            name=dotted_name, description=doc, input_schema=schema,
        )
        _HANDLERS[dotted_name] = func
        return func

    return decorator


# ---------------------------------------------------------------------------
# GitHub — repos & PRs
# ---------------------------------------------------------------------------


@_tool("github.list_repos")
def _list_repos(org: str | None = None) -> Any:
    """List repositories for the authenticated user or an org"""
    return list_repos(org)


@_tool(
    "github.list_prs",
    param_descs={"repo_full_name": "owner/repo; omit for active repo"},
)
def _list_prs(repo_full_name: str = "") -> Any:
    """List open pull requests in a repository. Use repo_full_name or leave empty to use OPENX_ACTIVE_REPO."""
    repo = resolve_repo(repo_full_name or "")
    return list_open_prs(repo)


@_tool("github.get_pr")
def _get_pr(number: int, repo_full_name: str = "") -> Any:
    """Get a pull request by number (details, files changed, diff, CI checks)."""
    repo = resolve_repo(repo_full_name or "")
    return get_pr(repo, number)


@_tool(
    "github.create_pr",
    param_descs={
        "repo_full_name": "owner/repo",
        "head": "Source branch name",
        "base": "Target branch (default main)",
        "body": "PR description",
    },
)
def _create_pr(
    repo_full_name: str,
    title: str,
    head: str,
    base: str = "main",
    body: str = "",
) -> Any:
    """Create a pull request. head = source branch (the branch with your changes), base = target branch (e.g. main)."""
    return create_pull(repo_full_name, title, head, base, body)


@_tool(
    "github.run_gh_command",
    param_descs={
        "command": "The gh command without the 'gh' prefix, e.g. 'pr list --repo owner/repo'",
    },
)
def _run_gh_command(command: str) -> Any:
    """Run a GitHub CLI (gh) command in the terminal. Allowed subcommands: pr, issue, repo, run, workflow, api."""
    cmd = (command or "").strip()
    if not cmd:
        return {"status": "error", "message": "command is required"}
    try:
        output = run_in_background(run_gh_command, cmd, timeout=30)
        return {"status": "ok", "output": output}
    except (ValueError, TimeoutError, RuntimeError) as e:
        return {"status": "error", "message": str(e)}


@_tool("github.comment_pr")
def _comment_pr(repo_full_name: str, number: int, body: str) -> Any:
    """Comment on a pull request"""
    return comment_pr(repo_full_name, number, body)


@_tool("github.merge_pr")
def _merge_pr(
    repo_full_name: str,
    number: int,
    method: str = "merge",
) -> Any:
    """Merge a pull request"""
    return merge_pr(repo_full_name, number, method)


# ---------------------------------------------------------------------------
# GitHub — README
# ---------------------------------------------------------------------------


@_tool(
    "github.get_readme",
    param_descs={"ref": "Branch, tag, or SHA; omit for default branch"},
)
def _get_readme(repo_full_name: str, ref: str | None = None) -> Any:
    """Get README content for a repo (path, content, sha, html_url). ref = branch/tag or omit for default."""
    return gh_get_readme(repo_full_name, ref)


@_tool(
    "github.update_readme",
    param_descs={
        "content": "Full new README markdown content",
        "branch": "Target branch; omit for default",
        "message": "Commit message",
    },
)
def _update_readme(
    repo_full_name: str,
    content: str,
    branch: str | None = None,
    message: str = "docs: update README",
) -> Any:
    """Create or update README in the repo. Use to modify README content automatically."""
    return gh_update_readme(repo_full_name, content, branch, message)


# ---------------------------------------------------------------------------
# GitHub — Issues
# ---------------------------------------------------------------------------


@_tool("github.list_issues")
def _list_issues(repo_full_name: str, state: str = "open") -> Any:
    """List issues in a repository (state: open, closed, or all)"""
    return list_issues(repo_full_name, state)


@_tool("github.get_issue")
def _get_issue(repo_full_name: str, number: int) -> Any:
    """Get a single issue by number"""
    return get_issue(repo_full_name, number)


@_tool("github.create_issue")
def _create_issue_tool(
    repo_full_name: str,
    title: str,
    body: str = "",
    labels: list[str] | None = None,
) -> Any:
    """Create a new issue in a repository"""
    return create_issue(repo_full_name, title, body, labels)


@_tool("github.comment_issue")
def _comment_issue(repo_full_name: str, number: int, body: str) -> Any:
    """Add a comment to an issue or PR"""
    return comment_issue(repo_full_name, number, body)


@_tool("github.close_issue")
def _close_issue(repo_full_name: str, number: int) -> Any:
    """Close an issue"""
    return close_issue(repo_full_name, number)


# ---------------------------------------------------------------------------
# GitHub — Workflows & CI
# ---------------------------------------------------------------------------


@_tool("github.list_workflows")
def _list_workflows(repo_full_name: str) -> Any:
    """List GitHub Actions workflows for a repo"""
    return list_workflows(repo_full_name)


@_tool("github.trigger_workflow")
def _trigger_workflow(
    repo_full_name: str,
    workflow_id: int,
    ref: str,
    inputs: dict[str, Any] | None = None,
) -> Any:
    """Trigger a workflow dispatch"""
    return trigger_workflow(repo_full_name, workflow_id, ref, inputs)


@_tool("github.list_workflow_runs")
def _list_workflow_runs(repo_full_name: str, workflow_id: int) -> Any:
    """List workflow runs for a workflow"""
    return list_workflow_runs(repo_full_name, workflow_id)


@_tool("github.get_workflow_run")
def _get_workflow_run(repo_full_name: str, run_id: int) -> Any:
    """Get a specific workflow run"""
    return get_workflow_run(repo_full_name, run_id)


# ---------------------------------------------------------------------------
# Autonomous PR Self-Healing MCP Toolset
# ---------------------------------------------------------------------------


@_tool(
    "github.get_failing_prs",
    param_descs={"repo": "Repository full name (owner/repo)"},
)
def _get_failing_prs(repo: str) -> Any:
    """List pull requests with failed CI workflows in a repository"""
    return gh_get_failing_prs(repo)


@_tool(
    "github.get_ci_logs",
    param_descs={
        "repo": "Repository full name (owner/repo)",
        "workflow_run_id": "GitHub Actions workflow run ID",
    },
)
def _get_ci_logs(repo: str, workflow_run_id: int) -> Any:
    """Fetch raw GitHub Actions logs for a workflow run"""
    return gh_get_ci_logs(repo, workflow_run_id)


@_tool(
    "github.analyze_ci_failure",
    param_descs={"logs": "Raw CI log text"},
)
def _analyze_ci_failure(logs: str) -> Any:
    """Analyze CI log text and return structured error (error_type, file_hint, reason)"""
    return gh_analyze_ci_failure(logs)


@_tool(
    "github.locate_code_context",
    param_descs={
        "repo": "Repository full name (owner/repo)",
        "error_context": "Structured error from analyze_ci_failure (error_type, file_hint, reason)",
    },
)
def _locate_code_context(repo: str, error_context: dict[str, Any]) -> Any:
    """Return relevant files and code snippets for an error context in a repo"""
    return gh_locate_code_context(repo, error_context)


@_tool(
    "github.generate_fix_patch",
    param_descs={
        "code_context": "JSON or string from locate_code_context",
        "error": "Structured error (error_type, file_hint, reason)",
    },
)
def _generate_fix_patch(code_context: str, error: dict[str, Any]) -> Any:
    """Generate a unified diff patch from code context and error"""
    return gh_generate_fix_patch(code_context, error)


@_tool(
    "github.apply_fix_to_pr",
    param_descs={
        "repo": "Repository full name (owner/repo)",
        "pr_number": "Pull request number",
        "patch": "Unified diff patch text",
    },
)
def _apply_fix_to_pr(repo: str, pr_number: int, patch: str) -> Any:
    """Commit a unified diff patch to the PR branch"""
    return gh_apply_fix_to_pr(repo, pr_number, patch)


@_tool(
    "github.rerun_ci",
    param_descs={
        "repo": "Repository full name (owner/repo)",
        "workflow_run_id": "Workflow run ID to re-run",
    },
)
def _rerun_ci(repo: str, workflow_run_id: int) -> Any:
    """Trigger re-run of a GitHub Actions workflow run"""
    return gh_rerun_ci(repo, workflow_run_id)


@_tool(
    "github.heal_failing_pr",
    param_descs={
        "repo": "Repository full name (owner/repo)",
        "pr_number": "Specific PR to heal; omit to heal the first failing PR",
    },
)
def _heal_failing_pr(repo: str, pr_number: int | None = None) -> Any:
    """Auto-heal a failing PR: get CI logs, analyze error, generate fix patch, apply to PR branch, rerun CI. Modifies code automatically."""
    return gh_heal_failing_pr(repo, pr_number)


# ---------------------------------------------------------------------------
# Workspace — local file and git operations
# ---------------------------------------------------------------------------


@_tool(
    "workspace.read_file",
    param_descs={
        "repo_path": "Subdir of workspace or empty for root",
        "path": "File path relative to repo_path; omit for README.md",
    },
)
def _read_file(repo_path: str = "", path: str = "README.md") -> Any:
    """Read a file from the local workspace. Use repo_path '' for workspace root."""
    return ws_read_file(repo_path, path or "README.md")


@_tool(
    "workspace.write_file",
    param_descs={
        "path": "File path; omit for README.md when writing docs",
    },
)
def _write_file(content: str, repo_path: str = "", path: str = "README.md") -> Any:
    """Write content to a file. If path omitted and content looks like docs, use README.md."""
    return ws_write_file(repo_path, path or "README.md", content)


@_tool("workspace.list_dir")
def _list_dir(repo_path: str = "", subdir: str = "") -> Any:
    """List files and dirs in the workspace (repo_path + subdir)."""
    return ws_list_dir(repo_path, subdir)


@_tool("workspace.git_status")
def _git_status(repo_path: str = "") -> Any:
    """Show git status and diff stat for the local repo."""
    return git_status(repo_path)


@_tool("workspace.git_add")
def _git_add(paths: list[str], repo_path: str = "") -> Any:
    """Stage files. Use paths ['.'] to stage all."""
    return git_add(repo_path, paths)


@_tool("workspace.git_commit")
def _git_commit(message: str, repo_path: str = "") -> Any:
    """Commit staged changes. Use conventional message: fix: ..., feat: ..., refactor: ..."""
    return git_commit(repo_path, message)


@_tool("workspace.git_push")
def _git_push(repo_path: str = "", remote: str = "origin", branch: str | None = None) -> Any:
    """Push to remote. Branch optional (default current)."""
    return git_push(repo_path, remote, branch)


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------


@_tool(
    "analysis.analyze_repo",
    param_descs={"path": "Repo path; omit to use workspace root"},
)
def _analyze_repo(path: str = "") -> Any:
    """Analyze a local repo for bugs, performance, duplicate code, AI-generated code, and bad practices."""
    root = path or config_settings.workspace_root
    static_findings = analyze_static(root)
    arch = summarize_architecture(root)
    ai = analyze_with_ai({"static_findings": static_findings, "architecture": arch})
    return format_analysis_report(root, static_findings, arch, ai)


# ---------------------------------------------------------------------------
# Public backward-compat API
# ---------------------------------------------------------------------------


def list_tools() -> list[dict[str, Any]]:
    """Return the tool list in the same shape as the old ``mcp.py``."""
    return [
        {"name": t.name, "description": t.description, "input_schema": t.input_schema}
        for t in TOOLS.values()
    ]


def call_tool(name: str, params: dict[str, Any]) -> Any:
    """Call a tool by its dotted name with a dict of keyword arguments."""
    handler = _HANDLERS.get(name)
    if handler is None:
        raise KeyError(f"Tool not found: {name}")
    return handler(**params)
