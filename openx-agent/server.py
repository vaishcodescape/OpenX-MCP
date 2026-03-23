"""OpenX MCP Server — GitHub automation, CI/CD healing, and code analysis.

A pure MCP server exposing tools, resources, and prompts via the Model Context
Protocol.  Any MCP-compatible client (Claude Desktop, Cursor, etc.) can connect
and use the full OpenX toolset.

"""

from __future__ import annotations

import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from .tools.analysis import register as register_analysis_tools
from .tools.github import register as register_github_tools
from .tools.workspace_tools import register as register_workspace_tools

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(server: FastMCP):
    logger.info("OpenX MCP server starting")
    yield {}
    logger.info("OpenX MCP server shutting down")
    try:
        from .github_client import _http_client

        if _http_client is not None:
            _http_client.close()
    except Exception:
        pass

mcp = FastMCP(
    name="OpenX",
    instructions=(
        "OpenX is an AI-powered GitHub automation server. "
        "Use github_* tools for repository, PR, issue, and CI/CD operations. "
        "Use workspace_* tools for local file and git operations. "
        "Use analysis_* tools for code analysis. "
        "For autonomous CI self-healing, call github_heal_failing_pr with the "
        "repo name — it will detect failures, analyze logs, generate a patch, "
        "commit the fix, and re-run CI automatically."
    ),
    lifespan=lifespan,
)
register_github_tools(mcp)
register_workspace_tools(mcp)
register_analysis_tools(mcp)

@mcp.resource("openx://config")
def server_config() -> str:
    """Current OpenX server configuration (secrets redacted)."""
    from .config import settings

    return json.dumps(
        {
            "github_base_url": settings.github_base_url or "https://api.github.com",
            "anthropic_model": settings.anthropic_model,
            "workspace_root": settings.workspace_root,
            "active_repo": settings.active_repo,
            "github_token_configured": bool(settings.github_token),
            "anthropic_key_configured": bool(settings.anthropic_api_key),
        },
        indent=2,
    )

@mcp.resource("openx://help")
def server_help() -> str:
    """OpenX usage guide and full tool reference."""
    return _HELP_TEXT

@mcp.resource("github://{owner}/{repo}/readme")
def repo_readme(owner: str, repo: str) -> str:
    """README content for a GitHub repository."""
    from .github_client import get_readme

    result = get_readme(f"{owner}/{repo}")
    return result.get("content", "")

@mcp.resource("github://{owner}/{repo}/prs")
def repo_open_prs(owner: str, repo: str) -> str:
    """Open pull requests for a GitHub repository."""
    from .github_client import list_open_prs

    return json.dumps(list_open_prs(f"{owner}/{repo}"), indent=2, default=str)

@mcp.resource("github://{owner}/{repo}/issues/{state}")
def repo_issues(owner: str, repo: str, state: str = "open") -> str:
    """Issues for a GitHub repository (state: open, closed, all)."""
    from .github_client import list_issues

    return json.dumps(list_issues(f"{owner}/{repo}", state), indent=2, default=str)

@mcp.prompt()
def analyze_repository(repo_path: str = "") -> str:
    """Comprehensive code analysis prompt for a repository."""
    target = f" at `{repo_path}`" if repo_path else ""
    return (
        f"Analyze the repository{target} using the analysis_analyze_repo tool. "
        "Review the results and provide:\n"
        "1. Key risks and bugs found\n"
        "2. Architecture overview and quality assessment\n"
        "3. Performance concerns\n"
        "4. Actionable recommendations for improvement"
    )

@mcp.prompt()
def heal_ci(repo: str, pr_number: int | None = None) -> str:
    """Step-by-step CI/CD self-healing workflow prompt."""
    target = f" PR #{pr_number}" if pr_number else " the first failing PR"
    return (
        f"Heal{target} in `{repo}` using github_heal_failing_pr. "
        "This will automatically: detect the failing PR, fetch CI logs, "
        "analyze the error, generate a fix patch, commit it to the PR branch, "
        "and re-run CI. Report what was fixed and the outcome."
    )

@mcp.prompt()
def github_workflow(task: str) -> str:
    """General GitHub automation task prompt."""
    return (
        f"Task: {task}\n\n"
        "Use the available GitHub tools to complete this task. "
        "Available operations include: list/get/create repos, PRs, and issues; "
        "manage workflows and CI; read/update README; run gh CLI commands. "
        "For local changes: read/write files, then git add/commit/push."
    )

@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})

_HELP_TEXT = """\
OpenX — AI-Powered GitHub Automation MCP Server

GitHub Tools:
  github_list_repos           List repositories
  github_list_prs             List open pull requests
  github_get_pr               Get PR details with diff and CI status
  github_create_pr            Create a new pull request
  github_comment_pr           Comment on a PR
  github_merge_pr             Merge a PR (merge/squash/rebase)
  github_get_readme           Get README content
  github_update_readme        Create or update README
  github_list_issues          List issues
  github_get_issue            Get issue details
  github_create_issue         Create a new issue
  github_comment_issue        Comment on an issue
  github_close_issue          Close an issue
  github_list_workflows       List GitHub Actions workflows
  github_trigger_workflow     Trigger a workflow dispatch
  github_list_workflow_runs   List workflow runs
  github_get_workflow_run     Get workflow run details
  github_run_gh_command       Run a raw gh CLI command

CI/CD Self-Healing:
  github_get_failing_prs      List PRs with failed CI
  github_get_ci_logs          Fetch CI logs for a workflow run
  github_analyze_ci_failure   Analyze CI logs for error patterns
  github_locate_code_context  Find relevant code for an error
  github_generate_fix_patch   Generate a unified diff fix
  github_apply_fix_to_pr      Apply patch to PR branch
  github_rerun_ci             Re-run a CI workflow
  github_heal_failing_pr      Auto-heal a failing PR (end-to-end)

Workspace:
  workspace_read_file         Read a file from the workspace
  workspace_write_file        Write content to a file
  workspace_list_dir          List files and directories
  workspace_git_status        Show git status
  workspace_git_add           Stage files
  workspace_git_commit        Commit staged changes
  workspace_git_push          Push to remote

Analysis:
  analysis_analyze_repo       Run full code analysis

Resources:
  openx://config              Server configuration
  openx://help                This help text
  github://{owner}/{repo}/readme    README content
  github://{owner}/{repo}/prs      Open pull requests
  github://{owner}/{repo}/issues/{state}  Issues (open/closed/all)
"""

def main() -> None:
    """CLI entry point for the OpenX MCP server."""
    transport = "stdio"
    host = "127.0.0.1"
    port = int(os.environ.get("PORT", 8000))

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("--http", "--streamable-http"):
            transport = "streamable-http"
        elif arg == "--sse":
            transport = "sse"
        elif arg == "--stdio":
            transport = "stdio"
        elif arg == "--host" and i + 1 < len(args):
            i += 1
            host = args[i]
        elif arg == "--port" and i + 1 < len(args):
            i += 1
            port = int(args[i])
        i += 1

    mcp.settings.host = host
    mcp.settings.port = port
    mcp.run(transport=transport)

if __name__ == "__main__":
    main()
