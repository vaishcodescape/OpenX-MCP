"""Agent MCP tools — expose the LangGraph ReAct agent to MCP clients."""

from __future__ import annotations

from fastmcp import FastMCP

from ..agent import run_agent as _run_agent

server = FastMCP("OpenX Agent Tools")


@server.tool
def chat(message: str, thread_id: str = "default") -> str:
    """Send a natural-language message to the OpenX AI agent.

    The agent (LangGraph ReAct + Claude) can autonomously plan and execute
    multi-step workflows using GitHub operations, knowledge-base search,
    local workspace I/O, and CI self-healing tools.

    Parameters
    ----------
    message:
        Your request in plain English (e.g. "List failing PRs in owner/repo
        and heal the first one").
    thread_id:
        Conversation thread for context continuity across multiple calls.
    """
    return _run_agent(message, thread_id=thread_id)
