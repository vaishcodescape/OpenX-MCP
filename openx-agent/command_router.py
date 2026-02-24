"""CLI command router: parse text tokens and dispatch to MCP tools.

`run_command` is the single entry point — it interprets the first token as a
command name (or alias) and calls the appropriate MCP tool, returning a
`CommandResult` with the output and a `should_continue` flag.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .mcp import TOOLS, call_tool, list_tools

# ---------------------------------------------------------------------------
# Aliases and command registry
# ---------------------------------------------------------------------------

ALIASES: dict[str, str] = {
    "h": "help", "?": "help", "ls": "tools",
    "gh":       "run_gh",
    "repos":    "list_repos",
    "prs":      "list_prs",
    "pr":       "get_pr",
    "issues":   "list_issues",
    "issue":    "get_issue",
    "cpr":      "comment_pr",
    "mpr":      "merge_pr",
    "wfs":      "list_workflows",
    "twf":      "trigger_workflow",
    "runs":     "list_workflow_runs",
    "run":      "get_workflow_run",
    "analyze":  "analyze_repo",
    "heal":     "heal_ci",
    "failing":  "get_failing_prs",
    "cilogs":   "get_ci_logs",
    "analyzeci":"analyze_ci_failure",
    "locate":   "locate_code_context",
    "patch":    "generate_fix_patch",
    "applyfix": "apply_fix_to_pr",
    "rerun":    "rerun_ci",
    "ask":      "chat",
    "q":        "quit",
}

COMMANDS: list[str] = [
    "help", "tools", "schema", "call",
    "run_gh", "list_repos", "list_prs", "get_pr", "comment_pr", "merge_pr",
    "list_issues", "get_issue", "create_issue", "comment_issue", "close_issue",
    "list_workflows", "trigger_workflow", "list_workflow_runs", "get_workflow_run",
    "heal_ci", "get_failing_prs", "get_ci_logs", "analyze_ci_failure",
    "locate_code_context", "generate_fix_patch", "apply_fix_to_pr", "rerun_ci",
    "analyze_repo", "chat", "index", "reset", "quit", "exit",
]

HELP_TEXT = """\
OpenX — GitHub AI Agent

Core commands:
  help                             Show this message.
  tools                            List all registered MCP tools.
  schema <tool>                    Show input schema for a tool.
  call <tool> <json>               Call a tool with raw JSON arguments.

GitHub shortcuts:
  list_repos [org]                 List repositories.
  list_prs <repo>                  List open pull requests.
  get_pr <repo> <number>           Show pull request details.
  comment_pr <repo> <n> <body>     Add a PR comment.
  merge_pr <repo> <n> [method]     Merge a PR (merge|squash|rebase).
  gh <gh-cli-args>                 Run a raw GitHub CLI command.
  list_issues <repo> [state]       List issues (open|closed|all).
  get_issue <repo> <n>             Show issue details.
  create_issue <repo> <title> [body]
  comment_issue <repo> <n> <body>
  close_issue <repo> <n>
  list_workflows <repo>
  trigger_workflow <repo> <id> <ref> [json_inputs]
  list_workflow_runs <repo> <id>
  get_workflow_run <repo> <run_id>
  analyze_repo [path]

Self-healing CI:
  heal_ci <repo> [pr_number]       Auto-heal failing PR (end-to-end pipeline).
  get_failing_prs <repo>
  get_ci_logs <repo> <run_id>
  get_ci_logs, analyze_ci_failure, locate_code_context,
  generate_fix_patch, apply_fix_to_pr, rerun_ci — use 'call' for these.

Agent (LangChain):
  chat <message>                   Ask the AI agent (multi-step reasoning).
  index <repo>                     Index a repo into the RAG knowledge base.
  reset                            Clear conversation memory.

Session:
  quit | exit

Aliases: h/?→help  ls→tools  repos/prs/pr/issues/issue  cpr/mpr
         wfs/twf/runs/run  analyze  heal/failing/cilogs  ask  q→quit
"""


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CommandResult:
    should_continue: bool
    output: Any | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require(tokens: list[str], count: int, usage: str) -> None:
    if len(tokens) < count:
        raise ValueError(f"Usage: {usage}")


def _call(tool: str, args: dict[str, Any]) -> CommandResult:
    return CommandResult(should_continue=True, output=call_tool(tool, args))


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


def run_command(tokens: list[str]) -> CommandResult:  # noqa: C901 (intentionally long switch)
    """Dispatch *tokens* to the matching tool and return a `CommandResult`."""
    if not tokens:
        return CommandResult(should_continue=True)

    cmd = ALIASES.get(tokens[0], tokens[0])

    if cmd in ("quit", "exit"):
        return CommandResult(should_continue=False)

    if cmd == "help":
        return CommandResult(should_continue=True, output=HELP_TEXT)

    if cmd == "tools":
        return CommandResult(should_continue=True, output=list_tools())

    if cmd == "schema":
        _require(tokens, 2, "schema <tool_name>")
        name = tokens[1]
        if name not in TOOLS:
            raise KeyError(f"Tool not found: {name}")
        return CommandResult(should_continue=True, output={"name": TOOLS[name].name, "input_schema": TOOLS[name].input_schema})

    if cmd == "call":
        _require(tokens, 3, "call <tool_name> <json_args>")
        return _call(tokens[1], json.loads(" ".join(tokens[2:])))

    if cmd == "run_gh":
        _require(tokens, 2, "gh <command>")
        return _call("github.run_gh_command", {"command": " ".join(tokens[1:])})

    if cmd == "list_repos":
        org = tokens[1] if len(tokens) > 1 else None
        return _call("github.list_repos", {"org": org} if org else {})

    if cmd == "list_prs":
        _require(tokens, 2, "list_prs <repo>")
        return _call("github.list_prs", {"repo_full_name": tokens[1]})

    if cmd == "get_pr":
        _require(tokens, 3, "get_pr <repo> <number>")
        return _call("github.get_pr", {"repo_full_name": tokens[1], "number": int(tokens[2])})

    if cmd == "comment_pr":
        _require(tokens, 4, "comment_pr <repo> <number> <body>")
        return _call("github.comment_pr", {"repo_full_name": tokens[1], "number": int(tokens[2]), "body": " ".join(tokens[3:])})

    if cmd == "merge_pr":
        _require(tokens, 3, "merge_pr <repo> <number> [method]")
        return _call("github.merge_pr", {"repo_full_name": tokens[1], "number": int(tokens[2]), "method": tokens[3] if len(tokens) > 3 else "merge"})

    if cmd == "list_issues":
        _require(tokens, 2, "list_issues <repo> [state]")
        return _call("github.list_issues", {"repo_full_name": tokens[1], "state": tokens[2] if len(tokens) > 2 else "open"})

    if cmd == "get_issue":
        _require(tokens, 3, "get_issue <repo> <number>")
        return _call("github.get_issue", {"repo_full_name": tokens[1], "number": int(tokens[2])})

    if cmd == "create_issue":
        _require(tokens, 3, "create_issue <repo> <title> [body]")
        return _call("github.create_issue", {"repo_full_name": tokens[1], "title": tokens[2], "body": " ".join(tokens[3:]) if len(tokens) > 3 else ""})

    if cmd == "comment_issue":
        _require(tokens, 4, "comment_issue <repo> <number> <body>")
        return _call("github.comment_issue", {"repo_full_name": tokens[1], "number": int(tokens[2]), "body": " ".join(tokens[3:])})

    if cmd == "close_issue":
        _require(tokens, 3, "close_issue <repo> <number>")
        return _call("github.close_issue", {"repo_full_name": tokens[1], "number": int(tokens[2])})

    if cmd == "list_workflows":
        _require(tokens, 2, "list_workflows <repo>")
        return _call("github.list_workflows", {"repo_full_name": tokens[1]})

    if cmd == "trigger_workflow":
        _require(tokens, 4, "trigger_workflow <repo> <workflow_id> <ref> [json_inputs]")
        inputs: dict[str, Any] = json.loads(" ".join(tokens[4:])) if len(tokens) > 4 else {}
        return _call("github.trigger_workflow", {"repo_full_name": tokens[1], "workflow_id": int(tokens[2]), "ref": tokens[3], "inputs": inputs})

    if cmd == "list_workflow_runs":
        _require(tokens, 3, "list_workflow_runs <repo> <workflow_id>")
        return _call("github.list_workflow_runs", {"repo_full_name": tokens[1], "workflow_id": int(tokens[2])})

    if cmd == "get_workflow_run":
        _require(tokens, 3, "get_workflow_run <repo> <run_id>")
        return _call("github.get_workflow_run", {"repo_full_name": tokens[1], "run_id": int(tokens[2])})

    if cmd == "analyze_repo":
        path = tokens[1] if len(tokens) > 1 else ""
        return _call("analysis.analyze_repo", {"path": path} if path else {})

    if cmd == "heal_ci":
        _require(tokens, 2, "heal_ci <repo> [pr_number]")
        payload: dict[str, Any] = {"repo": tokens[1]}
        if len(tokens) > 2:
            payload["pr_number"] = int(tokens[2])
        return _call("github.heal_failing_pr", payload)

    if cmd == "get_failing_prs":
        _require(tokens, 2, "get_failing_prs <repo>")
        return _call("github.get_failing_prs", {"repo": tokens[1]})

    if cmd == "get_ci_logs":
        _require(tokens, 3, "get_ci_logs <repo> <run_id>")
        return _call("github.get_ci_logs", {"repo": tokens[1], "workflow_run_id": int(tokens[2])})

    if cmd == "analyze_ci_failure":
        _require(tokens, 2, "analyze_ci_failure <logs>")
        return _call("github.analyze_ci_failure", {"logs": " ".join(tokens[1:])})

    if cmd == "locate_code_context":
        _require(tokens, 3, "locate_code_context <repo> <error_context_json>")
        return _call("github.locate_code_context", {"repo": tokens[1], "error_context": json.loads(" ".join(tokens[2:]))})

    if cmd == "generate_fix_patch":
        _require(tokens, 2, "generate_fix_patch '<json_with_code_context_and_error>'")
        args = json.loads(" ".join(tokens[1:]))
        code_ctx = args.get("code_context")
        error    = args.get("error")
        if code_ctx is None or error is None:
            raise ValueError("JSON must contain 'code_context' and 'error'")
        return _call("github.generate_fix_patch", {
            "code_context": json.dumps(code_ctx) if isinstance(code_ctx, dict) else code_ctx,
            "error": error,
        })

    if cmd == "apply_fix_to_pr":
        _require(tokens, 4, "apply_fix_to_pr <repo> <pr_number> <patch>")
        return _call("github.apply_fix_to_pr", {"repo": tokens[1], "pr_number": int(tokens[2]), "patch": " ".join(tokens[3:])})

    if cmd == "rerun_ci":
        _require(tokens, 3, "rerun_ci <repo> <run_id>")
        return _call("github.rerun_ci", {"repo": tokens[1], "workflow_run_id": int(tokens[2])})

    if cmd == "chat":
        _require(tokens, 2, "chat <message>")
        from .langchain_agent import chat as agent_chat
        return CommandResult(should_continue=True, output=agent_chat(" ".join(tokens[1:])))

    if cmd == "index":
        _require(tokens, 2, "index <repo_full_name>")
        from .rag import index_repo
        return CommandResult(should_continue=True, output=index_repo(tokens[1]))

    if cmd == "reset":
        from .langchain_agent import reset_conversation
        reset_conversation()
        return CommandResult(should_continue=True, output="Conversation memory cleared.")

    raise ValueError(f"Unknown command: {cmd!r}. Type 'help' for available commands.")
