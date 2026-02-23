from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .mcp import TOOLS, call_tool, list_tools


ALIASES: dict[str, str] = {
    "h": "help",
    "?": "help",
    "ls": "tools",
    "repos": "list_repos",
    "prs": "list_prs",
    "pr": "get_pr",
    "cpr": "comment_pr",
    "mpr": "merge_pr",
    "wfs": "list_workflows",
    "twf": "trigger_workflow",
    "runs": "list_workflow_runs",
    "run": "get_workflow_run",
    "analyze": "analyze_repo",
    "failing": "get_failing_prs",
    "cilogs": "get_ci_logs",
    "analyzeci": "analyze_ci_failure",
    "locate": "locate_code_context",
    "patch": "generate_fix_patch",
    "applyfix": "apply_fix_to_pr",
    "rerun": "rerun_ci",
    "ask": "chat",
    "q": "quit",
}

COMMANDS: list[str] = [
    "help",
    "tools",
    "schema",
    "call",
    "list_repos",
    "list_prs",
    "get_pr",
    "comment_pr",
    "merge_pr",
    "list_workflows",
    "trigger_workflow",
    "list_workflow_runs",
    "get_workflow_run",
    "get_failing_prs",
    "get_ci_logs",
    "analyze_ci_failure",
    "locate_code_context",
    "generate_fix_patch",
    "apply_fix_to_pr",
    "rerun_ci",
    "analyze_repo",
    "chat",
    "index",
    "reset",
    "quit",
    "exit",
]


@dataclass(frozen=True)
class CommandResult:
    should_continue: bool
    output: Any | None = None


def help_text() -> str:
    return """OpenX

Commands:
  help: Show available commands and usage.
  tools: List all registered MCP tools.
  schema <tool_name>: Show input schema for one tool.
  call <tool_name> <json_args>: Call a tool with raw JSON arguments.

Shortcuts:
  list_repos [org]: List repositories for the authenticated user or org.
  list_prs <repo_full_name>: List open pull requests in a repository.
  get_pr <repo_full_name> <number>: Show details for one pull request.
  comment_pr <repo_full_name> <number> <body>: Add a PR comment.
  merge_pr <repo_full_name> <number> [merge|squash|rebase]: Merge a PR.
  list_workflows <repo_full_name>: List GitHub Actions workflows.
  trigger_workflow <repo_full_name> <workflow_id> <ref> [json_inputs]: Dispatch a workflow.
  list_workflow_runs <repo_full_name> <workflow_id>: List runs for one workflow.
  get_workflow_run <repo_full_name> <run_id>: Show one workflow run.
  analyze_repo <path>: Run repository analysis (static + architecture + AI).

Self-healing (Autonomous PR):
  get_failing_prs <repo>: List PRs with failed CI.
  get_ci_logs <repo> <workflow_run_id>: Fetch raw CI logs.
  analyze_ci_failure: Use 'call github.analyze_ci_failure' with logs.
  locate_code_context: Use 'call github.locate_code_context' with repo + error_context.
  generate_fix_patch: Use 'call github.generate_fix_patch' with code_context + error.
  apply_fix_to_pr <repo> <pr_number>: Use 'call' with repo, pr_number, patch.
  rerun_ci <repo> <workflow_run_id>: Re-run a workflow run.

Session:
  quit | exit

Aliases:
  h/? -> help, ls -> tools, repos -> list_repos, prs -> list_prs, pr -> get_pr
  cpr -> comment_pr, mpr -> merge_pr, wfs -> list_workflows, twf -> trigger_workflow
  runs -> list_workflow_runs, run -> get_workflow_run, analyze -> analyze_repo, ask -> chat
  failing -> get_failing_prs, cilogs -> get_ci_logs, analyzeci -> analyze_ci_failure
  locate -> locate_code_context, patch -> generate_fix_patch, applyfix -> apply_fix_to_pr
  rerun -> rerun_ci, q -> quit

Agentic AI (LangChain):
  chat <message>: Ask the AI agent (autonomous multi-step reasoning).
  index <repo_full_name>: Index a repo into the RAG knowledge base.
  reset: Clear the current agent conversation memory.
"""


def _require(tokens: list[str], count: int, usage: str) -> None:
    if len(tokens) < count:
        raise ValueError(f"Usage: {usage}")


def run_command(tokens: list[str]) -> CommandResult:
    if not tokens:
        return CommandResult(should_continue=True)

    cmd = ALIASES.get(tokens[0], tokens[0])

    if cmd in {"quit", "exit"}:
        return CommandResult(should_continue=False)

    if cmd == "help":
        return CommandResult(should_continue=True, output=help_text())

    if cmd == "tools":
        return CommandResult(should_continue=True, output=list_tools())

    if cmd == "schema":
        _require(tokens, 2, "schema <tool_name>")
        name = tokens[1]
        if name not in TOOLS:
            raise KeyError(f"Tool not found: {name}")
        return CommandResult(
            should_continue=True,
            output={"name": TOOLS[name].name, "input_schema": TOOLS[name].input_schema},
        )

    if cmd == "call":
        _require(tokens, 3, "call <tool_name> <json_args>")
        name = tokens[1]
        raw = " ".join(tokens[2:])
        args = json.loads(raw)
        return CommandResult(should_continue=True, output=call_tool(name, args))

    if cmd == "list_repos":
        org = tokens[1] if len(tokens) > 1 else None
        return CommandResult(
            should_continue=True,
            output=call_tool("github.list_repos", {"org": org} if org else {}),
        )

    if cmd == "list_prs":
        _require(tokens, 2, "list_prs <repo_full_name>")
        return CommandResult(
            should_continue=True,
            output=call_tool("github.list_open_prs", {"repo_full_name": tokens[1]}),
        )

    if cmd == "get_pr":
        _require(tokens, 3, "get_pr <repo_full_name> <number>")
        return CommandResult(
            should_continue=True,
            output=call_tool(
                "github.get_pr",
                {"repo_full_name": tokens[1], "number": int(tokens[2])},
            ),
        )

    if cmd == "comment_pr":
        _require(tokens, 4, "comment_pr <repo_full_name> <number> <body>")
        return CommandResult(
            should_continue=True,
            output=call_tool(
                "github.comment_pr",
                {
                    "repo_full_name": tokens[1],
                    "number": int(tokens[2]),
                    "body": " ".join(tokens[3:]),
                },
            ),
        )

    if cmd == "merge_pr":
        _require(tokens, 3, "merge_pr <repo_full_name> <number> [merge|squash|rebase]")
        method = tokens[3] if len(tokens) > 3 else "merge"
        return CommandResult(
            should_continue=True,
            output=call_tool(
                "github.merge_pr",
                {
                    "repo_full_name": tokens[1],
                    "number": int(tokens[2]),
                    "method": method,
                },
            ),
        )

    if cmd == "list_workflows":
        _require(tokens, 2, "list_workflows <repo_full_name>")
        return CommandResult(
            should_continue=True,
            output=call_tool("github.list_workflows", {"repo_full_name": tokens[1]}),
        )

    if cmd == "trigger_workflow":
        _require(
            tokens,
            4,
            "trigger_workflow <repo_full_name> <workflow_id> <ref> [json_inputs]",
        )
        inputs: dict[str, Any] = {}
        if len(tokens) > 4:
            inputs = json.loads(" ".join(tokens[4:]))
        return CommandResult(
            should_continue=True,
            output=call_tool(
                "github.trigger_workflow",
                {
                    "repo_full_name": tokens[1],
                    "workflow_id": int(tokens[2]),
                    "ref": tokens[3],
                    "inputs": inputs,
                },
            ),
        )

    if cmd == "list_workflow_runs":
        _require(tokens, 3, "list_workflow_runs <repo_full_name> <workflow_id>")
        return CommandResult(
            should_continue=True,
            output=call_tool(
                "github.list_workflow_runs",
                {"repo_full_name": tokens[1], "workflow_id": int(tokens[2])},
            ),
        )

    if cmd == "get_workflow_run":
        _require(tokens, 3, "get_workflow_run <repo_full_name> <run_id>")
        return CommandResult(
            should_continue=True,
            output=call_tool(
                "github.get_workflow_run",
                {"repo_full_name": tokens[1], "run_id": int(tokens[2])},
            ),
        )

    if cmd == "analyze_repo":
        _require(tokens, 2, "analyze_repo <path>")
        return CommandResult(
            should_continue=True, output=call_tool("analysis.repo", {"path": tokens[1]})
        )

    if cmd == "get_failing_prs":
        _require(tokens, 2, "get_failing_prs <repo>")
        return CommandResult(
            should_continue=True,
            output=call_tool("github.get_failing_prs", {"repo": tokens[1]}),
        )

    if cmd == "get_ci_logs":
        _require(tokens, 3, "get_ci_logs <repo> <workflow_run_id>")
        return CommandResult(
            should_continue=True,
            output=call_tool(
                "github.get_ci_logs",
                {"repo": tokens[1], "workflow_run_id": int(tokens[2])},
            ),
        )

    if cmd == "analyze_ci_failure":
        _require(tokens, 2, "analyze_ci_failure <logs> (or use: call github.analyze_ci_failure {...})")
        logs = " ".join(tokens[1:])
        return CommandResult(
            should_continue=True,
            output=call_tool("github.analyze_ci_failure", {"logs": logs}),
        )

    if cmd == "locate_code_context":
        _require(tokens, 3, "locate_code_context <repo> <error_context_json>")
        repo = tokens[1]
        ctx = json.loads(" ".join(tokens[2:]))
        return CommandResult(
            should_continue=True,
            output=call_tool(
                "github.locate_code_context",
                {"repo": repo, "error_context": ctx},
            ),
        )

    if cmd == "generate_fix_patch":
        _require(tokens, 2, "generate_fix_patch '<json_with_code_context_and_error>'")
        args = json.loads(" ".join(tokens[1:]))
        code_context = args.get("code_context")
        error = args.get("error")
        if code_context is None or error is None:
            raise ValueError("JSON must contain 'code_context' and 'error'")
        return CommandResult(
            should_continue=True,
            output=call_tool(
                "github.generate_fix_patch",
                {
                    "code_context": json.dumps(code_context) if isinstance(code_context, dict) else code_context,
                    "error": error,
                },
            ),
        )

    if cmd == "apply_fix_to_pr":
        _require(tokens, 4, "apply_fix_to_pr <repo> <pr_number> <patch>")
        return CommandResult(
            should_continue=True,
            output=call_tool(
                "github.apply_fix_to_pr",
                {
                    "repo": tokens[1],
                    "pr_number": int(tokens[2]),
                    "patch": " ".join(tokens[3:]),
                },
            ),
        )

    if cmd == "rerun_ci":
        _require(tokens, 3, "rerun_ci <repo> <workflow_run_id>")
        return CommandResult(
            should_continue=True,
            output=call_tool(
                "github.rerun_ci",
                {"repo": tokens[1], "workflow_run_id": int(tokens[2])},
            ),
        )

    # --- LangChain Agent commands ---

    if cmd == "chat":
        _require(tokens, 2, "chat <message>")
        message = " ".join(tokens[1:])
        from .langchain_agent import chat as agent_chat
        return CommandResult(should_continue=True, output=agent_chat(message))

    if cmd == "index":
        _require(tokens, 2, "index <repo_full_name>")
        from .rag import index_repo
        return CommandResult(should_continue=True, output=index_repo(tokens[1]))

    if cmd == "reset":
        from .langchain_agent import reset_conversation
        reset_conversation()
        return CommandResult(should_continue=True, output="Conversation memory cleared.")

    raise ValueError(f"Unknown command: {cmd}. Type 'help' for available commands.")
