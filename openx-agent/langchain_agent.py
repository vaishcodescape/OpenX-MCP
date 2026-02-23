"""LangChain ReAct agent — all GitHub tools for PR/CI automation, fast and optimised.

- Fast path: known commands (list_prs, get_pr, list_repos, etc.) run with a direct
  tool call and no LLM round-trip for minimal latency.
- Full GitHub tool set: repos, PRs (list/get/comment/merge), workflows (list/trigger/runs),
  CI (failing PRs, logs, analyze failure, locate context, generate/apply patch, rerun).
- ReAct loop for natural language and multi-step; compact prompt and tool-name
  normalization (e.g. github.get_pr → github_get_pr) for fewer failures.
- Rate-limit retries, observation truncation, and per-conversation memory (last 8 turns).
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

from .command_router import help_text as get_help_text
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
_OBSERVATION_TRUNCATE = 3000  # chars; long CI logs truncated to save context
# Cap total prompt size for faster LLM response (fewer tokens).
_MAX_PROMPT_CHARS = 14_000

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

    def _help_tool() -> str:
        return get_help_text()

    tools["openx_help"] = StructuredTool.from_function(
        func=_help_tool,
        name="openx_help",
        description="Return OpenX help and list of all commands/shortcuts. Use when user asks for 'help', '?', 'tools', or 'schema'.",
    )
    return tools


# Build once at module level.
_TOOLS = _build_tools()

# ---------------------------------------------------------------------------
# Fast path: known commands → direct tool call (no LLM, minimal latency)
# ---------------------------------------------------------------------------

def _fast_path_parsers() -> dict[str, tuple[str, Any]]:
    """Command first-word -> (tool_name, parser). Parser: (parts: list[str]) -> dict | None."""
    def no_args(_p: list[str]) -> dict:
        return {}
    def list_repos_parser(p: list[str]) -> dict:
        return {} if not p else {"org": p[0]}
    def repo_only(p: list[str]) -> dict | None:
        return {"repo_full_name": p[0]} if len(p) >= 1 else None
    def repo_only_gh(p: list[str]) -> dict | None:
        return {"repo": p[0]} if len(p) >= 1 else None
    def repo_int(p: list[str]) -> dict | None:
        if len(p) < 2:
            return None
        try:
            return {"repo_full_name": p[0], "number": int(p[1])}
        except ValueError:
            return None
    def repo_int_body(p: list[str]) -> dict | None:
        if len(p) < 3:
            return None
        try:
            return {"repo_full_name": p[0], "number": int(p[1]), "body": " ".join(p[2:])}
        except ValueError:
            return None
    def merge_parser(p: list[str]) -> dict | None:
        if len(p) < 2:
            return None
        try:
            out = {"repo_full_name": p[0], "number": int(p[1])}
            if len(p) > 2 and p[2].lower() in ("squash", "rebase", "merge"):
                out["method"] = p[2].lower()
            return out
        except ValueError:
            return None
    def repo_workflow_id(p: list[str]) -> dict | None:
        if len(p) < 2:
            return None
        try:
            return {"repo_full_name": p[0], "workflow_id": int(p[1])}
        except ValueError:
            return None
    def repo_run_id(p: list[str]) -> dict | None:
        if len(p) < 2:
            return None
        try:
            return {"repo_full_name": p[0], "run_id": int(p[1])}
        except ValueError:
            return None
    def trigger_parser(p: list[str]) -> dict | None:
        if len(p) < 3:
            return None
        try:
            return {"repo_full_name": p[0], "workflow_id": int(p[1]), "ref": p[2]}
        except ValueError:
            return None
    def repo_workflow_run_id(p: list[str]) -> dict | None:
        if len(p) < 2:
            return None
        try:
            return {"repo": p[0], "workflow_run_id": int(p[1])}
        except ValueError:
            return None
    def heal_ci_parser(p: list[str]) -> dict | None:
        if not p:
            return None
        out: dict[str, Any] = {"repo": p[0]}
        if len(p) >= 2:
            try:
                out["pr_number"] = int(p[1])
            except ValueError:
                pass
        return out
    def path_only(p: list[str]) -> dict | None:
        return {"path": p[0]} if p else None
    def analyze_repo_parser(p: list[str]) -> dict | None:
        # Path optional: omit or "" uses workspace root in backend.
        if not p:
            return {}
        return {"path": p[0]}
    def index_parser(p: list[str]) -> dict | None:
        return {"repo_full_name": p[0]} if p else None
    def apply_fix_parser(p: list[str]) -> dict | None:
        if len(p) < 2:
            return None
        try:
            return {"repo": p[0], "pr_number": int(p[1]), "patch": " ".join(p[2:]) or ""}
        except ValueError:
            return None
    def list_issues_parser(p: list[str]) -> dict | None:
        if not p:
            return None
        state = p[1] if len(p) > 1 and p[1].lower() in ("open", "closed", "all") else "open"
        return {"repo_full_name": p[0], "state": state}
    def get_readme_parser(p: list[str]) -> dict | None:
        if not p:
            return None
        out: dict[str, Any] = {"repo_full_name": p[0]}
        if len(p) > 1:
            out["ref"] = p[1]
        return out
    def create_issue_parser(p: list[str]) -> dict | None:
        if len(p) < 2:
            return None
        return {"repo_full_name": p[0], "title": p[1], "body": " ".join(p[2:])}

    return {
        "help": ("openx_help", no_args),
        "?": ("openx_help", no_args),
        "tools": ("openx_help", no_args),
        "schema": ("openx_help", no_args),
        "list_repos": ("github_list_repos", list_repos_parser),
        "list_prs": ("github_list_prs", repo_only),
        "get_pr": ("github_get_pr", repo_int),
        "comment_pr": ("github_comment_pr", repo_int_body),
        "merge_pr": ("github_merge_pr", merge_parser),
        "list_issues": ("github_list_issues", list_issues_parser),
        "get_issue": ("github_get_issue", repo_int),
        "create_issue": ("github_create_issue", create_issue_parser),
        "comment_issue": ("github_comment_issue", repo_int_body),
        "close_issue": ("github_close_issue", repo_int),
        "get_readme": ("github_get_readme", get_readme_parser),
        "list_workflows": ("github_list_workflows", repo_only),
        "trigger_workflow": ("github_trigger_workflow", trigger_parser),
        "list_workflow_runs": ("github_list_workflow_runs", repo_workflow_id),
        "get_workflow_run": ("github_get_workflow_run", repo_run_id),
        "get_failing_prs": ("github_get_failing_prs", repo_only_gh),
        "heal_ci": ("github_heal_failing_pr", heal_ci_parser),
        "heal_failing_pr": ("github_heal_failing_pr", heal_ci_parser),
        "heal": ("github_heal_failing_pr", heal_ci_parser),
        "get_ci_logs": ("github_get_ci_logs", repo_workflow_run_id),
        "rerun_ci": ("github_rerun_ci", repo_workflow_run_id),
        "analyze_repo": ("analysis_analyze_repo", analyze_repo_parser),
        "index": ("index_github_repo", index_parser),
    }


_FAST_PATH = _fast_path_parsers()


def _try_fast_path(message: str) -> str | None:
    """If message is a known command with parseable args, run tool directly and return result. Else None."""
    msg = (message or "").strip()
    if not msg:
        return None
    parts = msg.split()
    cmd = parts[0].lower()
    rest = parts[1:] if len(parts) > 1 else []
    entry = _FAST_PATH.get(cmd)
    if not entry:
        return None
    tool_name, parser = entry
    args = parser(rest)
    if args is None:
        return None
    tool = _TOOLS.get(tool_name)
    if not tool:
        return None
    try:
        result = tool.invoke(args)
        return result if isinstance(result, str) else json.dumps(result, indent=2, default=str)
    except Exception as exc:
        return f"Error: {exc}"


# ---------------------------------------------------------------------------
# Text-based ReAct prompt (compact for speed)
# ---------------------------------------------------------------------------

# One line per tool: name + key params so the model picks and fills quickly.
_TOOL_LINES = [
    "github_list_repos(org?), github_list_prs(repo_full_name), github_get_pr(repo_full_name,number), github_comment_pr(repo_full_name,number,body), github_merge_pr(repo_full_name,number,method?)",
    "github_get_readme(repo_full_name,ref?), github_update_readme(repo_full_name,content,branch?,message?)",
    "github_list_issues(repo_full_name,state?), github_get_issue(repo_full_name,number), github_create_issue(repo_full_name,title,body?,labels?), github_comment_issue(repo_full_name,number,body), github_close_issue(repo_full_name,number)",
    "github_list_workflows(repo_full_name), github_trigger_workflow(repo_full_name,workflow_id,ref), github_list_workflow_runs(repo_full_name,workflow_id), github_get_workflow_run(repo_full_name,run_id)",
    "github_get_failing_prs(repo), github_heal_failing_pr(repo,pr_number?), github_get_ci_logs(repo,workflow_run_id), github_analyze_ci_failure(logs), github_locate_code_context(repo,error_context), github_generate_fix_patch(code_context,error), github_apply_fix_to_pr(repo,pr_number,patch), github_rerun_ci(repo,workflow_run_id)",
    "workspace_read_file(repo_path?,path), workspace_write_file(repo_path?,path,content), workspace_list_dir(repo_path?,subdir?), workspace_git_status(repo_path?), workspace_git_add(repo_path?,paths), workspace_git_commit(repo_path?,message), workspace_git_push(repo_path?,remote?,branch?)",
    "analysis_analyze_repo(path), index_github_repo(repo_full_name), search_github_knowledge(query), openx_help()",
]
_TOOL_LIST = "\n".join(_TOOL_LINES)

# Dense mapping so the model picks the right tool and args in one step.
_SHORTCUT_MAPPING = """COMMAND → tool(args): list_repos→github_list_repos; list_prs→github_list_prs(repo_full_name); get_pr→github_get_pr(repo_full_name,number); comment_pr/merge_pr→github_comment_pr/github_merge_pr; get_readme→github_get_readme(repo_full_name,ref?); update_readme→github_update_readme(repo_full_name,content,branch?,message?); list_issues→github_list_issues(repo_full_name,state?); get_issue→github_get_issue(repo_full_name,number); create_issue→github_create_issue(repo_full_name,title,body?); comment_issue/close_issue→github_comment_issue/github_close_issue; list_workflows→github_list_workflows; trigger_workflow→github_trigger_workflow(repo_full_name,workflow_id,ref); list_workflow_runs/get_workflow_run→github_list_workflow_runs/github_get_workflow_run; get_failing_prs→github_get_failing_prs; heal_ci/heal_failing_pr→github_heal_failing_pr(repo,pr_number?) auto-modifies code and reruns CI; get_ci_logs/rerun_ci→github_get_ci_logs/github_rerun_ci(repo,workflow_run_id); analyze_ci_failure→github_analyze_ci_failure(logs); locate_code_context→github_locate_code_context(repo,error_context); generate_fix_patch/apply_fix_to_pr→github_generate_fix_patch/github_apply_fix_to_pr; analyze_repo→analysis_analyze_repo(path); index→index_github_repo(repo_full_name). repo = owner/repo."""

# Automation: how to set up CI/CD, PR, workflows, issues, README, and modify-commit-push.
_AUTOMATION_PROMPT = """
AUTOMATION / SETUP (do these via tools and report back):
- CI/CD: github_list_workflows(repo); github_trigger_workflow(repo,workflow_id,ref); github_rerun_ci(repo,workflow_run_id). AUTOMATIC CI HEALING: github_heal_failing_pr(repo,pr_number?) to auto-fix a failing PR (fetches logs, analyzes, generates patch, applies to PR, reruns CI). Step-by-step: github_get_failing_prs→get_ci_logs→analyze_ci_failure→locate_code_context→generate_fix_patch→apply_fix_to_pr.
- PRs: list_prs→get_pr; comment_pr; merge_pr (merge|squash|rebase).
- Workflows: list_workflows; trigger_workflow; list_workflow_runs/get_workflow_run.
- Issues: list_issues; get_issue; create_issue(repo,title,body?); comment_issue; close_issue.
- README: github_get_readme(repo_full_name,ref?) to read; github_update_readme(repo_full_name,content,branch?,message?) to create or update README. Use when user asks to update docs, add badges, fix README, or modify readme.
- MODIFY CODE + COMMIT + PUSH: (1) workspace_read_file(repo_path,path). (2) workspace_write_file(repo_path,path,content) with best practices. (3) workspace_git_status. (4) workspace_git_add(repo_path,paths). (5) workspace_git_commit(repo_path,message). (6) workspace_git_push(repo_path,remote?,branch?). Use repo_path '' for workspace root.
"""

# When user does not provide path/repo, the agent infers or fetches automatically.
_PATH_REPO_INFERENCE = """
PATH & REPO INFERENCE (do not require the user to supply these—infer or fetch via tools):
- repo_path: Default to '' (workspace root) unless the user specifies a subdir. Never ask for it; use ''.
- path (file): If user says "readme" or "README" or "docs" without a path, use path "README.md". If user says "read the code" or "look at the project" without a file, use workspace_list_dir(repo_path '', subdir '') first to discover files, then read the relevant one. Never ask "which file?"—infer or list_dir.
- path (analyze_repo): Omit path or use '' to analyze the workspace root automatically. Call analysis_analyze_repo with {{}} or {{"path": ""}}.
- repo (owner/repo): If user says "my repo", "this repo", or doesn't name one, use github_list_repos() to list and pick the first or match by name; or use search_github_knowledge(query) to find repo context. Never ask "which repo?"—infer or list_repos.
- For workspace_read_file / workspace_write_file: path is optional; backend defaults to README.md when omitted. Use list_dir when you need to discover paths.
"""

# Orchestration and error handling: agent must check outcomes and surface errors.
_ORCHESTRATION_PROMPT = """
ORCHESTRATION & ERROR HANDLING:
- You handle every user prompt by choosing and running the right tools. No prompt is "just chat"—always use tools to fulfill the request when possible.
- After each Action, read the Observation: if it starts with "Error:" or contains "status\": \"error\" or "failed" or "not found", treat it as a failure. Report the error clearly in your Final Answer; do not assume success or continue as if the step succeeded.
- For multi-step flows (e.g. heal CI, modify README then push): if one step fails, stop and report what failed and why. Do not proceed to the next step with invalid state.
- When a tool returns JSON with a "status" field, check it: status "error", "no_fix", "no_logs" etc. mean the operation did not fully succeed—surface that to the user.
- Summarize what was done and any errors at the end (Final Answer).
"""

_REACT_PROMPT = f"""\
You are OpenX. The user's prompt is your instruction: automatically pick the right tools and run them to fulfill the request. Every request is handled by you using the tools below (repos, PRs, issues, workflows, CI healing, README, local files, git). First word of user message is often the command; parse rest as args (repo=owner/repo, numbers as int).
{_PATH_REPO_INFERENCE}
{_ORCHESTRATION_PROMPT}
{_SHORTCUT_MAPPING}
{_AUTOMATION_PROMPT}

TOOLS (use these exact names; params in parentheses):
{_TOOL_LIST}

Format:
Thought: <brief>
Action: <tool_name>
Action Input: <JSON>

Then another Thought/Action or: Thought: Done. Final Answer: <result and any errors>

Rules: Action Input = valid JSON. One tool per Action. Always check Observation for errors; if tool failed, say so in Final Answer. Do not assume success without reading the result."""

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
    """Call the LLM with retry on rate limits and timeout. Returns non-empty string or raises."""
    from .llm import get_llm

    llm = get_llm()
    last_exc: Exception | None = None

    for attempt in range(_MAX_RETRIES):
        try:
            result = llm.invoke(
                [HumanMessage(content=m["content"]) if m["role"] == "user"
                 else AIMessage(content=m["content"]) for m in messages]
            )
            content = (result.content or "").strip() if hasattr(result, "content") else ""
            if content:
                return content
            logger.warning("LLM returned empty content (attempt %d)", attempt + 1)
            if attempt == _MAX_RETRIES - 1:
                return "I couldn't generate a response. Please try again or rephrase."
        except Exception as exc:
            err = str(exc).lower()
            is_transient = any(
                kw in err for kw in ("429", "rate limit", "too many", "503", "502", "retry", "timeout")
            )
            if not is_transient or attempt == _MAX_RETRIES - 1:
                logger.exception("LLM call failed")
                raise
            wait = _BACKOFF_BASE * (2 ** attempt)
            logger.warning("Transient error (attempt %d), retrying in %.1fs: %s", attempt + 1, wait, exc)
            last_exc = exc
            time.sleep(wait)
    raise last_exc  # type: ignore


def _truncate_prompt(fixed: str, variable: str) -> str:
    """Keep total prompt under _MAX_PROMPT_CHARS; truncate only the variable part (history + scratchpad)."""
    if len(fixed) + len(variable) <= _MAX_PROMPT_CHARS:
        return fixed + variable
    max_var = max(0, _MAX_PROMPT_CHARS - len(fixed))
    return fixed + variable[-max_var:]


def _run_react(user_message: str, history: list[tuple[str, str]]) -> str:
    """Execute the text-based ReAct loop with prompt truncation and error handling."""

    # Build conversation context from history.
    history_text = ""
    for role, content in history[-_MEMORY_WINDOW:]:
        history_text += f"\n{role}: {content}"

    scratchpad = ""
    fixed = _REACT_PROMPT + f"\n\nUser: {user_message}\n\n"

    for iteration in range(_MAX_ITERATIONS):
        variable = history_text + scratchpad
        content = _truncate_prompt(fixed, variable)
        messages = [{"role": "user", "content": content}]

        try:
            response = _call_llm(messages)
        except Exception as exc:
            logger.exception("LLM call failed in ReAct iteration %d", iteration + 1)
            return f"Agent error (LLM failed): {exc}. Please try again."

        if not (response and response.strip()):
            scratchpad += "Observation: LLM returned empty response.\n"
            continue

        scratchpad += response + "\n"

        # Check for Final Answer.
        final_match = _FINAL_ANSWER_RE.search(response)
        if final_match:
            return final_match.group(1).strip()

        # Check for Action.
        action_match = _ACTION_RE.search(response)
        if not action_match:
            return response.strip()

        tool_name = action_match.group(1).strip()
        tool_key = tool_name.replace(".", "_")
        tool = _TOOLS.get(tool_key) or _TOOLS.get(tool_name)
        input_match = _ACTION_INPUT_RE.search(response)
        raw_input = input_match.group(1).strip() if input_match else "{}"

        try:
            args = json.loads(raw_input)
        except json.JSONDecodeError:
            args = {"input": raw_input.strip('"').strip("'")}

        if tool is None:
            observation = f"Error: Unknown tool '{tool_name}'. Use one of: {', '.join(sorted(_TOOLS.keys()))}"
        else:
            try:
                observation = tool.invoke(args) if isinstance(args, dict) else tool.invoke({"input": str(args)})
            except Exception as exc:
                logger.debug("Tool %s failed: %s", tool_name, exc)
                observation = f"Tool error: {exc}"

        obs_str = str(observation)
        if len(obs_str) > _OBSERVATION_TRUNCATE:
            observation = obs_str[:_OBSERVATION_TRUNCATE] + "\n... [truncated]"

        scratchpad += f"Observation: {observation}\n"

    return "I reached the maximum number of steps. Here's what I found so far:\n" + scratchpad


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def chat(message: str, conversation_id: str = "default") -> str:
    """Send a message to the ReAct agent and get a response. Uses fast path for known commands (no LLM)."""
    # Fast path: known command + parseable args → direct tool call (no LLM round-trip).
    try:
        fast_result = _try_fast_path(message)
        if fast_result is not None:
            return fast_result
    except Exception as exc:
        logger.debug("Fast path failed: %s", exc)
        # Fall through to ReAct.

    history = _get_history(conversation_id)
    try:
        answer = _run_react(message, history)
    except TimeoutError as exc:
        logger.warning("Agent timeout: %s", exc)
        answer = "Request timed out. The model took too long to respond. Please try again or use a shorter prompt."
    except RuntimeError as exc:
        if "HUGGINGFACE_API_KEY" in str(exc):
            answer = "Configuration error: HUGGINGFACE_API_KEY is not set. Add it to .env."
        else:
            answer = f"Agent error: {exc}"
    except Exception as exc:
        logger.exception("Agent execution failed")
        answer = f"Agent error: {exc}. Please try again."

    history.append(("User", message))
    history.append(("Assistant", answer))
    _trim_history(conversation_id)

    return answer


def reset_conversation(conversation_id: str = "default") -> None:
    """Clear conversation memory for a given ID."""
    _MEMORIES.pop(conversation_id, None)
