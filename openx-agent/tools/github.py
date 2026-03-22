"""GitHub MCP tools — repos, PRs, issues, workflows, CI healing, README."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from ..config import resolve_repo
from ..gh_cli import run_gh_command as _run_gh_command
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

def list_repos(org: str | None = None) -> Any:
    """List repositories for the authenticated user or an organization."""
    return _list_repos(org)

def list_prs(repo_full_name: str = "") -> Any:
    """List open pull requests. Omit repo_full_name to use OPENX_ACTIVE_REPO."""
    return _list_open_prs(resolve_repo(repo_full_name or ""))

def get_pr(number: int, repo_full_name: str = "") -> Any:
    """Get pull request details including files changed, diff, and CI checks."""
    return _get_pr(resolve_repo(repo_full_name or ""), number)

def create_pr(
    repo_full_name: str,
    title: str,
    head: str,
    base: str = "main",
    body: str = "",
) -> Any:
    """Create a pull request. head = source branch, base = target branch."""
    return _create_pull(repo_full_name, title, head, base, body)

def comment_pr(repo_full_name: str, number: int, body: str) -> Any:
    """Add a comment to a pull request."""
    return _comment_pr(repo_full_name, number, body)

def merge_pr(
    repo_full_name: str,
    number: int,
    method: str = "merge",
) -> Any:
    """Merge a pull request (method: merge, squash, or rebase)."""
    return _merge_pr(repo_full_name, number, method)

def get_readme(repo_full_name: str, ref: str | None = None) -> Any:
    """Get README content for a repository. ref = branch/tag or omit for default."""
    return _get_readme(repo_full_name, ref)

def update_readme(
    repo_full_name: str,
    content: str,
    branch: str | None = None,
    message: str = "docs: update README",
) -> Any:
    """Create or update the README in a repository."""
    return _update_readme(repo_full_name, content, branch, message)

def list_issues(repo_full_name: str, state: str = "open") -> Any:
    """List issues in a repository (state: open, closed, or all)."""
    return _list_issues(repo_full_name, state)

def get_issue(repo_full_name: str, number: int) -> Any:
    """Get a single issue by number."""
    return _get_issue(repo_full_name, number)

def create_issue(
    repo_full_name: str,
    title: str,
    body: str = "",
    labels: list[str] | None = None,
) -> Any:
    """Create a new issue in a repository."""
    return _create_issue(repo_full_name, title, body, labels)

def comment_issue(repo_full_name: str, number: int, body: str) -> Any:
    """Add a comment to an issue or pull request."""
    return _comment_issue(repo_full_name, number, body)

def close_issue(repo_full_name: str, number: int) -> Any:
    """Close an issue."""
    return _close_issue(repo_full_name, number)

def list_workflows(repo_full_name: str) -> Any:
    """List GitHub Actions workflows for a repository."""
    return _list_workflows(repo_full_name)

def trigger_workflow(
    repo_full_name: str,
    workflow_id: int,
    ref: str,
    inputs: dict[str, Any] | None = None,
) -> Any:
    """Trigger a workflow dispatch event."""
    return _trigger_workflow(repo_full_name, workflow_id, ref, inputs)

def list_workflow_runs(repo_full_name: str, workflow_id: int) -> Any:
    """List recent runs for a workflow."""
    return _list_workflow_runs(repo_full_name, workflow_id)

def get_workflow_run(repo_full_name: str, run_id: int) -> Any:
    """Get details for a specific workflow run."""
    return _get_workflow_run(repo_full_name, run_id)

def run_gh_command(command: str) -> Any:
    """Run a GitHub CLI (gh) command. Allowed: pr, issue, repo, run, workflow, api.

    Pass the command without the leading 'gh', e.g. 'pr list --repo owner/repo'.
    """
    cmd = (command or "").strip()
    if not cmd:
        return {"status": "error", "message": "command is required"}
    try:
        output = _run_gh_command(cmd, timeout=30)
        return {"status": "ok", "output": output}
    except (ValueError, TimeoutError, RuntimeError) as e:
        return {"status": "error", "message": str(e)}

def get_failing_prs(repo: str) -> Any:
    """List pull requests with failed CI workflows in a repository."""
    return _get_failing_prs(repo)

def get_ci_logs(repo: str, workflow_run_id: int) -> Any:
    """Fetch raw GitHub Actions logs for a workflow run."""
    return _get_ci_logs(repo, workflow_run_id)

def analyze_ci_failure(logs: str) -> Any:
    """Analyze CI log text and return structured error info (error_type, file_hint, reason)."""
    return _analyze_ci_failure(logs)

def locate_code_context(repo: str, error_context: dict[str, Any]) -> Any:
    """Find relevant source files and code snippets for a CI error."""
    return _locate_code_context(repo, error_context)

def generate_fix_patch(code_context: str, error: dict[str, Any]) -> Any:
    """Generate a unified diff patch from code context and error information."""
    return _generate_fix_patch(code_context, error)

def apply_fix_to_pr(repo: str, pr_number: int, patch: str) -> Any:
    """Commit a unified diff patch to a PR branch."""
    return _apply_fix_to_pr(repo, pr_number, patch)

def rerun_ci(repo: str, workflow_run_id: int) -> Any:
    """Re-run a GitHub Actions workflow."""
    return _rerun_ci(repo, workflow_run_id)

def heal_failing_pr(repo: str, pr_number: int | None = None) -> Any:
    """Auto-heal a failing PR end-to-end.

    Pipeline: detect failure -> fetch CI logs -> analyze error ->
    generate fix patch -> commit to PR branch -> re-run CI.
    If pr_number is omitted, heals the first failing PR found.
    """
    return _heal_failing_pr(repo, pr_number)

def register(mcp: FastMCP) -> None:
    mcp.add_tool(list_repos, name="github_list_repos")
    mcp.add_tool(list_prs, name="github_list_prs")
    mcp.add_tool(get_pr, name="github_get_pr")
    mcp.add_tool(create_pr, name="github_create_pr")
    mcp.add_tool(comment_pr, name="github_comment_pr")
    mcp.add_tool(merge_pr, name="github_merge_pr")
    mcp.add_tool(get_readme, name="github_get_readme")
    mcp.add_tool(update_readme, name="github_update_readme")
    mcp.add_tool(list_issues, name="github_list_issues")
    mcp.add_tool(get_issue, name="github_get_issue")
    mcp.add_tool(create_issue, name="github_create_issue")
    mcp.add_tool(comment_issue, name="github_comment_issue")
    mcp.add_tool(close_issue, name="github_close_issue")
    mcp.add_tool(list_workflows, name="github_list_workflows")
    mcp.add_tool(trigger_workflow, name="github_trigger_workflow")
    mcp.add_tool(list_workflow_runs, name="github_list_workflow_runs")
    mcp.add_tool(get_workflow_run, name="github_get_workflow_run")
    mcp.add_tool(run_gh_command, name="github_run_gh_command")
    mcp.add_tool(get_failing_prs, name="github_get_failing_prs")
    mcp.add_tool(get_ci_logs, name="github_get_ci_logs")
    mcp.add_tool(analyze_ci_failure, name="github_analyze_ci_failure")
    mcp.add_tool(locate_code_context, name="github_locate_code_context")
    mcp.add_tool(generate_fix_patch, name="github_generate_fix_patch")
    mcp.add_tool(apply_fix_to_pr, name="github_apply_fix_to_pr")
    mcp.add_tool(rerun_ci, name="github_rerun_ci")
    mcp.add_tool(heal_failing_pr, name="github_heal_failing_pr")
