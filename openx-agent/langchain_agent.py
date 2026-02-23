"""LangChain ReAct agent — wraps MCP tools for autonomous multi-step reasoning.

Uses a TEXT-BASED ReAct loop (not OpenAI function-calling) because the
HuggingFace Inference API providers don't all support the `tools` parameter.

Optimised for HuggingFace free-tier rate limits:
  - Capped iterations (max 5 LLM round-trips)
  - Retry with exponential back-off on 429 / 5xx
  - Detailed tool descriptions to minimise wasted calls
  - Per-conversation memory with a sliding window (last 8 turns)
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import StructuredTool

from .config import settings
from .mcp import TOOLS as MCP_TOOLS, call_tool
from .rag import index_repo, search_github_knowledge

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LangSmith tracing setup
# ---------------------------------------------------------------------------


def _configure_langsmith() -> None:
    if settings.langsmith_api_key:
        os.environ.setdefault("LANGCHAIN_API_KEY", settings.langsmith_api_key)
    if settings.langsmith_tracing:
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    if settings.langsmith_project:
        os.environ.setdefault("LANGCHAIN_PROJECT", settings.langsmith_project)


_configure_langsmith()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_RETRIES = 3
_BACKOFF_BASE = 2.0
_MAX_ITERATIONS = 5

# ---------------------------------------------------------------------------
# Tool registry (LangChain StructuredTools wrapping MCP tools + RAG)
# ---------------------------------------------------------------------------


def _wrap_mcp_tool(name: str, description: str, input_schema: dict) -> StructuredTool:
    properties = input_schema.get("properties", {})
    required = set(input_schema.get("required", []))

    def handler(**kwargs: Any) -> str:
        try:
            result = call_tool(name, kwargs)
            if isinstance(result, str):
                return result
            return json.dumps(result, indent=2, default=str)
        except Exception as exc:
            return f"Error calling {name}: {exc}"

    param_hints = []
    for pname, pschema in properties.items():
        ptype = pschema.get("type", "any")
        req = " (required)" if pname in required else ""
        desc = pschema.get("description", "")
        param_hints.append(f"  {pname} ({ptype}{req}): {desc}")

    full_desc = description
    if param_hints:
        full_desc += "\nParameters:\n" + "\n".join(param_hints)

    return StructuredTool.from_function(
        func=handler,
        name=name.replace(".", "_"),
        description=full_desc,
    )


def _build_tools() -> dict[str, StructuredTool]:
    tools: dict[str, StructuredTool] = {}
    for mcp_tool in MCP_TOOLS.values():
        t = _wrap_mcp_tool(mcp_tool.name, mcp_tool.description, mcp_tool.input_schema)
        tools[t.name] = t

    tools["search_github_knowledge"] = search_github_knowledge

    def _index_tool(repo_full_name: str) -> str:
        """Index a GitHub repository into the knowledge base."""
        try:
            result = index_repo(repo_full_name)
            return json.dumps(result, indent=2)
        except Exception as exc:
            return f"Error indexing {repo_full_name}: {exc}"

    idx = StructuredTool.from_function(
        func=_index_tool,
        name="index_github_repo",
        description="Index a GitHub repo into the RAG knowledge base.\nParameters:\n  repo_full_name (string, required): e.g. 'owner/repo'",
    )
    tools[idx.name] = idx
    return tools


# Build once at module level.
_TOOLS = _build_tools()

# ---------------------------------------------------------------------------
# Text-based ReAct prompt
# ---------------------------------------------------------------------------

_TOOL_LIST = "\n".join(f"- {t.name}: {t.description.split(chr(10))[0]}" for t in _TOOLS.values())

_REACT_PROMPT = f"""\
You are OpenX, an AI DevOps assistant. Answer the user's question using the available tools.

AVAILABLE TOOLS:
{_TOOL_LIST}

Use this format EXACTLY:

Thought: <your reasoning>
Action: <tool_name>
Action Input: <JSON arguments>

After receiving the observation, continue with more Thought/Action steps if needed.
When you have enough information to answer, respond with:

Thought: I have enough information to answer.
Final Answer: <your answer>

RULES:
1. Always start with a Thought.
2. Action Input MUST be valid JSON (use {{}}).
3. Do NOT guess — use tools to get real data.
4. Be concise and actionable.
5. If a tool fails, report the error — do NOT retry with the same args.
"""

# ---------------------------------------------------------------------------
# Per-conversation memory
# ---------------------------------------------------------------------------

_MEMORIES: dict[str, list[tuple[str, str]]] = {}
_MEMORY_WINDOW = 8


def _get_history(cid: str) -> list[tuple[str, str]]:
    return _MEMORIES.setdefault(cid, [])


def _trim_history(cid: str) -> None:
    h = _MEMORIES.get(cid, [])
    if len(h) > _MEMORY_WINDOW:
        _MEMORIES[cid] = h[-_MEMORY_WINDOW:]


# ---------------------------------------------------------------------------
# ReAct loop (text-based, no function-calling required)
# ---------------------------------------------------------------------------

_ACTION_RE = re.compile(r"Action:\s*(.+)", re.IGNORECASE)
_ACTION_INPUT_RE = re.compile(r"Action Input:\s*(.+)", re.IGNORECASE | re.DOTALL)
_FINAL_ANSWER_RE = re.compile(r"Final Answer:\s*(.+)", re.IGNORECASE | re.DOTALL)


def _call_llm(messages: list[dict[str, str]]) -> str:
    """Call the LLM with retry on rate limits."""
    from .llm import get_llm

    llm = get_llm()
    last_exc: Exception | None = None

    for attempt in range(_MAX_RETRIES):
        try:
            result = llm.invoke(
                [HumanMessage(content=m["content"]) if m["role"] == "user"
                 else AIMessage(content=m["content"]) for m in messages]
            )
            return result.content
        except Exception as exc:
            err = str(exc).lower()
            is_transient = any(
                kw in err for kw in ("429", "rate limit", "too many", "503", "502", "retry")
            )
            if not is_transient or attempt == _MAX_RETRIES - 1:
                raise
            wait = _BACKOFF_BASE * (2 ** attempt)
            logger.warning("Rate limited (attempt %d), retrying in %.1fs", attempt + 1, wait)
            last_exc = exc
            time.sleep(wait)
    raise last_exc  # type: ignore


def _run_react(user_message: str, history: list[tuple[str, str]]) -> str:
    """Execute the text-based ReAct loop."""

    # Build conversation context from history.
    history_text = ""
    for role, content in history[-_MEMORY_WINDOW:]:
        history_text += f"\n{role}: {content}"

    scratchpad = ""
    messages = [{"role": "user", "content": _REACT_PROMPT + history_text + f"\n\nUser: {user_message}\n\n{scratchpad}"}]

    for _iteration in range(_MAX_ITERATIONS):
        response = _call_llm(messages)
        scratchpad += response + "\n"

        # Check for Final Answer.
        final_match = _FINAL_ANSWER_RE.search(response)
        if final_match:
            return final_match.group(1).strip()

        # Check for Action.
        action_match = _ACTION_RE.search(response)
        if not action_match:
            # No action and no final answer — treat as final answer.
            return response.strip()

        tool_name = action_match.group(1).strip()
        input_match = _ACTION_INPUT_RE.search(response)
        raw_input = input_match.group(1).strip() if input_match else "{}"

        # Parse JSON arguments.
        try:
            args = json.loads(raw_input)
        except json.JSONDecodeError:
            # Maybe the model put the arg as a plain string.
            args = {"input": raw_input.strip('"').strip("'")}

        # Execute the tool.
        tool = _TOOLS.get(tool_name)
        if tool is None:
            observation = f"Error: Unknown tool '{tool_name}'. Available: {', '.join(_TOOLS.keys())}"
        else:
            try:
                if isinstance(args, dict):
                    observation = tool.invoke(args)
                else:
                    observation = tool.invoke({"input": str(args)})
            except Exception as exc:
                observation = f"Tool error: {exc}"

        # Truncate long observations.
        if len(str(observation)) > 3000:
            observation = str(observation)[:3000] + "\n... [truncated]"

        scratchpad += f"Observation: {observation}\n"
        messages = [{"role": "user", "content": _REACT_PROMPT + history_text + f"\n\nUser: {user_message}\n\n{scratchpad}"}]

    return "I reached the maximum number of steps. Here's what I found so far:\n" + scratchpad


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def chat(message: str, conversation_id: str = "default") -> str:
    """Send a message to the ReAct agent and get a response."""
    history = _get_history(conversation_id)

    try:
        answer = _run_react(message, history)
    except Exception as exc:
        logger.exception("Agent execution failed")
        answer = f"Agent error: {exc}"

    history.append(("User", message))
    history.append(("Assistant", answer))
    _trim_history(conversation_id)

    return answer


def reset_conversation(conversation_id: str = "default") -> None:
    """Clear conversation memory for a given ID."""
    _MEMORIES.pop(conversation_id, None)
