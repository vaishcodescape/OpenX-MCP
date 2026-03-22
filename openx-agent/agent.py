"""LangGraph ReAct agent — orchestrates OpenX tools via Claude.

Exposes a single :func:`run_agent` entry-point that the MCP tool layer can
call.  The agent uses ``create_react_agent`` from ``langgraph.prebuilt`` with
a ``ChatAnthropic`` model and LangChain tool wrappers around the core OpenX
business logic (GitHub operations, workspace I/O, CI healing).
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from .config import resolve_repo, settings
from .llm import get_llm

logger = logging.getLogger(__name__)

@tool
def list_repos(org: str | None = None) -> list[dict[str, Any]]:
    """List GitHub repositories for the authenticated user or an organisation."""
    from .github_client import list_repos as _list_repos
    return _list_repos(org)

@tool
def list_open_prs(repo: str) -> list[dict[str, Any]]:
    """List open pull requests in a repository (owner/repo)."""
    from .github_client import list_open_prs as _list_open_prs
    return _list_open_prs(repo)

@tool
def get_pr(repo: str, number: int) -> dict[str, Any]:
    """Get pull-request details including diff and CI status."""
    from .github_client import get_pr as _get_pr
    return _get_pr(repo, number)

@tool
def create_issue(repo: str, title: str, body: str = "", labels: list[str] | None = None) -> dict[str, Any]:
    """Create a new GitHub issue."""
    from .github_client import create_issue as _create_issue
    return _create_issue(repo, title, body, labels)

@tool
def list_issues(repo: str, state: str = "open") -> list[dict[str, Any]]:
    """List issues in a repository (state: open, closed, all)."""
    from .github_client import list_issues as _list_issues
    return _list_issues(repo, state)

@tool
def get_readme(repo: str) -> dict[str, Any]:
    """Get the README content for a repository."""
    from .github_client import get_readme as _get_readme
    return _get_readme(repo)

@tool
def heal_failing_pr(repo: str, pr_number: int | None = None) -> dict[str, Any]:
    """Auto-heal a failing PR: detect failure, generate fix, commit, re-run CI."""
    from .github_client import heal_failing_pr as _heal
    return _heal(repo, pr_number)

@tool
def read_file(path: str, repo_path: str = "") -> str:
    """Read a file from the local workspace."""
    from .workspace import read_file as _read_file
    return _read_file(repo_path, path)

@tool
def write_file(path: str, content: str, repo_path: str = "") -> dict[str, Any]:
    """Write content to a file in the local workspace."""
    from .workspace import write_file as _write_file
    return _write_file(repo_path, path, content)

@tool
def list_dir(repo_path: str = "", subdir: str = "") -> list[dict[str, Any]]:
    """List files and directories in the workspace."""
    from .workspace import list_dir as _list_dir
    return _list_dir(repo_path, subdir)

@tool
def git_status(repo_path: str = "") -> str:
    """Show git status and diff stat for the workspace."""
    from .workspace import git_status as _git_status
    return _git_status(repo_path)

AGENT_TOOLS = [
    list_repos,
    list_open_prs,
    get_pr,
    create_issue,
    list_issues,
    get_readme,
    heal_failing_pr,
    read_file,
    write_file,
    list_dir,
    git_status,
]

_SYSTEM_MESSAGE = (
    "You are OpenX, an AI-powered GitHub automation assistant. "
    "You have access to tools for GitHub operations (repos, PRs, issues, CI), "
    "local workspace file I/O, and CI self-healing capabilities.\n\n"
    "Guidelines:\n"
    "- Use the available tools to answer questions and complete tasks.\n"
    "- For CI failures, use heal_failing_pr for end-to-end automated fixing.\n"
    "- Be concise and actionable in your responses.\n"
    "- If a tool call fails, explain the error and suggest alternatives."
)

def _build_agent():
    """Construct and return the LangGraph ReAct agent graph."""
    llm = get_llm()
    return create_react_agent(
        model=llm,
        tools=AGENT_TOOLS,
        prompt=_SYSTEM_MESSAGE,
    )

_agent = None

def _get_agent():
    """Lazy-initialise the agent (avoids import-time API key checks)."""
    global _agent
    if _agent is None:
        _agent = _build_agent()
    return _agent

def run_agent(message: str, *, thread_id: str = "default") -> str:
    """Send *message* to the LangGraph agent and return the final response text."""
    agent = _get_agent()

    logger.info("Agent invocation  thread=%s  message=%s", thread_id, message[:120])
    result = agent.invoke(
        {"messages": [HumanMessage(content=message)]},
        config={"configurable": {"thread_id": thread_id}},
    )

    messages = result.get("messages", [])
    if not messages:
        return "Agent returned no response."

    final = messages[-1]
    text = getattr(final, "content", "")
    if isinstance(text, list):
        text = " ".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in text
        )
    return text or "Agent completed with no text output."
