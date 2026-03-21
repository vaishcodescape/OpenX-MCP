"""GitHub MCP tools — repos, PRs, issues, workflows, CI healing, README."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from ..config import resolve_repo
from ..gh_cli import run_gh_command as _run_gh_command, run_in_background
from ..github_client import (
    analyze_ci_failure as _analyze_ci_failure,
    apply_fix_to_pr as _apply_fix_to_pr,
    close_issue as _close_issue,
    comment_issue as _comment_issue,
    comment_pr as _comment_pr,
    create_issue as _create_issue,
    create_pull as _create_pull,
    generate_fix_patch as _generate_fix_patch,
    get_ci_logs as _get_ci_logs,
    get_failing_prs as _get_failing_prs,
    get_issue as _get_issue,
    get_pr as _get_pr,
    get_readme as _get_readme,
    get_workflow_run as _get_workflow_run,
    heal_failing_pr as _heal_failing_pr,
    list_issues as _list_issues,
    list_open_prs as _list_open_prs,
    list_repos as _list_repos,
    list_workflow_runs as _list_workflow_runs,
    list_workflows as _list_workflows,
    locate_code_context as _locate_code_context,
    merge_pr as _merge_pr,
    rerun_ci as _rerun_ci,
    trigger_workflow as _trigger_workflow,
    update_readme as _update_readme,
)

server = FastMCP("OpenX GitHub Tools")

# ---------------------------------------------------------------------------
# Repos
# ---------------------------------------------------------------------------


@server.tool
def list_repos(org: str | None = None) -> Any:
    """List repositories for the authenticated user or an organization."""
    return _list_repos(org)


@server.tool
def list_prs(repo_full_name: str = "") -> Any:
    """List open pull requests. Omit repo_full_name to use OPENX_ACTIVE_REPO."""
    return _list_open_prs(resolve_repo(repo_full_name or ""))


@server.tool
def get_pr(number: int, repo_full_name: str = "") -> Any:
    """Get pull request details including files changed, diff, and CI checks."""
    return _get_pr(resolve_repo(repo_full_name or ""), number)


@server.tool
def create_pr(
    repo_full_name: str,
    title: str,
    head: str,
    base: str = "main",
    body: str = "",
) -> Any:
    """Create a pull request. head = source branch, base = target branch."""
    return _create_pull(repo_full_name, title, head, base, body)


@server.tool
def comment_pr(repo_full_name: str, number: int, body: str) -> Any:
    """Add a comment to a pull request."""
    return _comment_pr(repo_full_name, number, body)


@server.tool
def merge_pr(
    repo_full_name: str,
    number: int,
    method: str = "merge",
) -> Any:
    """Merge a pull request (method: merge, squash, or rebase)."""
    return _merge_pr(repo_full_name, number, method)


# ---------------------------------------------------------------------------
# README
# ---------------------------------------------------------------------------


@server.tool
def get_readme(repo_full_name: str, ref: str | None = None) -> Any:
    """Get README content for a repository. ref = branch/tag or omit for default."""
    return _get_readme(repo_full_name, ref)


@server.tool
def update_readme(
    repo_full_name: str,
    content: str,
    branch: str | None = None,
    message: str = "docs: update README",
) -> Any:
    """Create or update the README in a repository."""
    return _update_readme(repo_full_name, content, branch, message)


# ---------------------------------------------------------------------------
# Issues
# ---------------------------------------------------------------------------


@server.tool
def list_issues(repo_full_name: str, state: str = "open") -> Any:
    """List issues in a repository (state: open, closed, or all)."""
    return _list_issues(repo_full_name, state)


@server.tool
def get_issue(repo_full_name: str, number: int) -> Any:
    """Get a single issue by number."""
    return _get_issue(repo_full_name, number)


@server.tool
def create_issue(
    repo_full_name: str,
    title: str,
    body: str = "",
    labels: list[str] | None = None,
) -> Any:
    """Create a new issue in a repository."""
    return _create_issue(repo_full_name, title, body, labels)


@server.tool
def comment_issue(repo_full_name: str, number: int, body: str) -> Any:
    """Add a comment to an issue or pull request."""
    return _comment_issue(repo_full_name, number, body)


@server.tool
def close_issue(repo_full_name: str, number: int) -> Any:
    """Close an issue."""
    return _close_issue(repo_full_name, number)


# ---------------------------------------------------------------------------
# Workflows & CI
# ---------------------------------------------------------------------------


@server.tool
def list_workflows(repo_full_name: str) -> Any:
    """List GitHub Actions workflows for a repository."""
    return _list_workflows(repo_full_name)


@server.tool
def trigger_workflow(
    repo_full_name: str,
    workflow_id: int,
    ref: str,
    inputs: dict[str, Any] | None = None,
) -> Any:
    """Trigger a workflow dispatch event."""
    return _trigger_workflow(repo_full_name, workflow_id, ref, inputs)


@server.tool
def list_workflow_runs(repo_full_name: str, workflow_id: int) -> Any:
    """List recent runs for a workflow."""
    return _list_workflow_runs(repo_full_name, workflow_id)


@server.tool
def get_workflow_run(repo_full_name: str, run_id: int) -> Any:
    """Get details for a specific workflow run."""
    return _get_workflow_run(repo_full_name, run_id)


@server.tool
def run_gh_command(command: str) -> Any:
    """Run a GitHub CLI (gh) command. Allowed: pr, issue, repo, run, workflow, api.

    Pass the command without the leading 'gh', e.g. 'pr list --repo owner/repo'.
    """
    cmd = (command or "").strip()
    if not cmd:
        return {"status": "error", "message": "command is required"}
    try:
        output = run_in_background(_run_gh_command, cmd, timeout=30)
        return {"status": "ok", "output": output}
    except (ValueError, TimeoutError, RuntimeError) as e:
        return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# CI Self-Healing
# ---------------------------------------------------------------------------


@server.tool
def get_failing_prs(repo: str) -> Any:
    """List pull requests with failed CI workflows in a repository."""
    return _get_failing_prs(repo)


@server.tool
def get_ci_logs(repo: str, workflow_run_id: int) -> Any:
    """Fetch raw GitHub Actions logs for a workflow run."""
    return _get_ci_logs(repo, workflow_run_id)


@server.tool
def analyze_ci_failure(logs: str) -> Any:
    """Analyze CI log text and return structured error info (error_type, file_hint, reason)."""
    return _analyze_ci_failure(logs)


@server.tool
def locate_code_context(repo: str, error_context: dict[str, Any]) -> Any:
    """Find relevant source files and code snippets for a CI error."""
    return _locate_code_context(repo, error_context)


@server.tool
def generate_fix_patch(code_context: str, error: dict[str, Any]) -> Any:
    """Generate a unified diff patch from code context and error information."""
    return _generate_fix_patch(code_context, error)


@server.tool
def apply_fix_to_pr(repo: str, pr_number: int, patch: str) -> Any:
    """Commit a unified diff patch to a PR branch."""
    return _apply_fix_to_pr(repo, pr_number, patch)


@server.tool
def rerun_ci(repo: str, workflow_run_id: int) -> Any:
    """Re-run a GitHub Actions workflow."""
    return _rerun_ci(repo, workflow_run_id)


@server.tool
def heal_failing_pr(repo: str, pr_number: int | None = None) -> Any:
    """Auto-heal a failing PR end-to-end.

    Pipeline: detect failure -> fetch CI logs -> analyze error ->
    generate fix patch -> commit to PR branch -> re-run CI.
    If pr_number is omitted, heals the first failing PR found.
    """
    return _heal_failing_pr(repo, pr_number)
