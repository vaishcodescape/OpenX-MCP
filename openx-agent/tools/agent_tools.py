"""Agent MCP tools — expose the LangGraph ReAct agent to MCP clients."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..agent import run_agent as _run_agent

def chat(message: str, thread_id: str = "default") -> str:
    """Send a natural-language message to the OpenX AI agent."""
    return _run_agent(message, thread_id=thread_id)

def register(mcp: FastMCP) -> None:
    mcp.add_tool(chat, name="agent_chat")
