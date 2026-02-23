from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel, Field

from .analysis.ai_analysis import analyze_with_ai
from .analysis.architecture import summarize_architecture
from .analysis.static_analysis import analyze_static
from .github_client import (
    analyze_ci_failure as gh_analyze_ci_failure,
    apply_fix_to_pr as gh_apply_fix_to_pr,
    comment_pr,
    generate_fix_patch as gh_generate_fix_patch,
    get_ci_logs as gh_get_ci_logs,
    get_failing_prs as gh_get_failing_prs,
    get_pr,
    get_repo,
    get_workflow_run,
    list_open_prs,
    list_repos,
    list_workflow_runs,
    list_workflows,
    locate_code_context as gh_locate_code_context,
    merge_pr,
    rerun_ci as gh_rerun_ci,
    trigger_workflow,
)


class MCPRequest(BaseModel):
    id: str | int | None = None
    method: str
    params: dict[str, Any] | None = None


class MCPResponse(BaseModel):
    id: str | int | None = None
    result: Any | None = None
    error: dict[str, Any] | None = None


class Tool(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    handler: Callable[[dict[str, Any]], Any]

    class Config:
        arbitrary_types_allowed = True


def _tool(name: str, description: str, input_schema: dict[str, Any]):
    def decorator(func: Callable[[dict[str, Any]], Any]):
        return Tool(name=name, description=description, input_schema=input_schema, handler=func)
    return decorator


TOOLS: dict[str, Tool] = {}


def register(tool: Tool) -> None:
    TOOLS[tool.name] = tool


@_tool(
    name="github.list_repos",
    description="List repositories for the authenticated user or an org",
    input_schema={"type": "object", "properties": {"org": {"type": "string"}}},
)

def _list_repos(params: dict[str, Any]) -> Any:
    return list_repos(params.get("org"))


@_tool(
    name="github.list_open_prs",
    description="List open pull requests in a repository",
    input_schema={
        "type": "object",
        "properties": {"repo_full_name": {"type": "string"}},
        "required": ["repo_full_name"],
    },
)

def _list_open_prs(params: dict[str, Any]) -> Any:
    return list_open_prs(params["repo_full_name"])


@_tool(
    name="github.get_pr",
    description="Get a pull request by number",
    input_schema={
        "type": "object",
        "properties": {"repo_full_name": {"type": "string"}, "number": {"type": "integer"}},
        "required": ["repo_full_name", "number"],
    },
)

def _get_pr(params: dict[str, Any]) -> Any:
    return get_pr(params["repo_full_name"], params["number"])


@_tool(
    name="github.comment_pr",
    description="Comment on a pull request",
    input_schema={
        "type": "object",
        "properties": {
            "repo_full_name": {"type": "string"},
            "number": {"type": "integer"},
            "body": {"type": "string"},
        },
        "required": ["repo_full_name", "number", "body"],
    },
)

def _comment_pr(params: dict[str, Any]) -> Any:
    return comment_pr(params["repo_full_name"], params["number"], params["body"])


@_tool(
    name="github.merge_pr",
    description="Merge a pull request",
    input_schema={
        "type": "object",
        "properties": {
            "repo_full_name": {"type": "string"},
            "number": {"type": "integer"},
            "method": {"type": "string", "enum": ["merge", "squash", "rebase"]},
        },
        "required": ["repo_full_name", "number"],
    },
)

def _merge_pr(params: dict[str, Any]) -> Any:
    return merge_pr(params["repo_full_name"], params["number"], params.get("method", "merge"))


@_tool(
    name="github.list_workflows",
    description="List GitHub Actions workflows for a repo",
    input_schema={
        "type": "object",
        "properties": {"repo_full_name": {"type": "string"}},
        "required": ["repo_full_name"],
    },
)

def _list_workflows(params: dict[str, Any]) -> Any:
    return list_workflows(params["repo_full_name"])


@_tool(
    name="github.trigger_workflow",
    description="Trigger a workflow dispatch",
    input_schema={
        "type": "object",
        "properties": {
            "repo_full_name": {"type": "string"},
            "workflow_id": {"type": "integer"},
            "ref": {"type": "string"},
            "inputs": {"type": "object"},
        },
        "required": ["repo_full_name", "workflow_id", "ref"],
    },
)

def _trigger_workflow(params: dict[str, Any]) -> Any:
    return trigger_workflow(
        params["repo_full_name"],
        params["workflow_id"],
        params["ref"],
        params.get("inputs"),
    )


@_tool(
    name="github.list_workflow_runs",
    description="List workflow runs for a workflow",
    input_schema={
        "type": "object",
        "properties": {"repo_full_name": {"type": "string"}, "workflow_id": {"type": "integer"}},
        "required": ["repo_full_name", "workflow_id"],
    },
)

def _list_workflow_runs(params: dict[str, Any]) -> Any:
    return list_workflow_runs(params["repo_full_name"], params["workflow_id"])


@_tool(
    name="github.get_workflow_run",
    description="Get a specific workflow run",
    input_schema={
        "type": "object",
        "properties": {"repo_full_name": {"type": "string"}, "run_id": {"type": "integer"}},
        "required": ["repo_full_name", "run_id"],
    },
)

def _get_workflow_run(params: dict[str, Any]) -> Any:
    return get_workflow_run(params["repo_full_name"], params["run_id"])


# --- Autonomous PR Self-Healing MCP Toolset ---


@_tool(
    name="github.get_failing_prs",
    description="List pull requests with failed CI workflows in a repository",
    input_schema={
        "type": "object",
        "properties": {"repo": {"type": "string", "description": "Repository full name (owner/repo)"}},
        "required": ["repo"],
    },
)
def _get_failing_prs(params: dict[str, Any]) -> Any:
    return gh_get_failing_prs(params["repo"])


@_tool(
    name="github.get_ci_logs",
    description="Fetch raw GitHub Actions logs for a workflow run",
    input_schema={
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository full name (owner/repo)"},
            "workflow_run_id": {"type": "integer", "description": "GitHub Actions workflow run ID"},
        },
        "required": ["repo", "workflow_run_id"],
    },
)
def _get_ci_logs(params: dict[str, Any]) -> Any:
    return gh_get_ci_logs(params["repo"], params["workflow_run_id"])


@_tool(
    name="github.analyze_ci_failure",
    description="Analyze CI log text and return structured error (error_type, file_hint, reason)",
    input_schema={
        "type": "object",
        "properties": {"logs": {"type": "string", "description": "Raw CI log text"}},
        "required": ["logs"],
    },
)
def _analyze_ci_failure(params: dict[str, Any]) -> Any:
    return gh_analyze_ci_failure(params["logs"])


@_tool(
    name="github.locate_code_context",
    description="Return relevant files and code snippets for an error context in a repo",
    input_schema={
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository full name (owner/repo)"},
            "error_context": {
                "type": "object",
                "description": "Structured error from analyze_ci_failure (error_type, file_hint, reason)",
            },
        },
        "required": ["repo", "error_context"],
    },
)
def _locate_code_context(params: dict[str, Any]) -> Any:
    return gh_locate_code_context(params["repo"], params["error_context"])


@_tool(
    name="github.generate_fix_patch",
    description="Generate a unified diff patch from code context and error",
    input_schema={
        "type": "object",
        "properties": {
            "code_context": {"type": "string", "description": "JSON or string from locate_code_context"},
            "error": {
                "type": "object",
                "description": "Structured error (error_type, file_hint, reason)",
            },
        },
        "required": ["code_context", "error"],
    },
)
def _generate_fix_patch(params: dict[str, Any]) -> Any:
    return gh_generate_fix_patch(params["code_context"], params["error"])


@_tool(
    name="github.apply_fix_to_pr",
    description="Commit a unified diff patch to the PR branch",
    input_schema={
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository full name (owner/repo)"},
            "pr_number": {"type": "integer", "description": "Pull request number"},
            "patch": {"type": "string", "description": "Unified diff patch text"},
        },
        "required": ["repo", "pr_number", "patch"],
    },
)
def _apply_fix_to_pr(params: dict[str, Any]) -> Any:
    return gh_apply_fix_to_pr(params["repo"], params["pr_number"], params["patch"])


@_tool(
    name="github.rerun_ci",
    description="Trigger re-run of a GitHub Actions workflow run",
    input_schema={
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository full name (owner/repo)"},
            "workflow_run_id": {"type": "integer", "description": "Workflow run ID to re-run"},
        },
        "required": ["repo", "workflow_run_id"],
    },
)
def _rerun_ci(params: dict[str, Any]) -> Any:
    return gh_rerun_ci(params["repo"], params["workflow_run_id"])


@_tool(
    name="analysis.repo",
    description="Analyze a local repo for bugs, performance, duplicate code, AI-generated code, and bad practices",
    input_schema={
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    },
)

def _analysis_repo(params: dict[str, Any]) -> Any:
    root = params["path"]
    static_findings = analyze_static(root)
    arch = summarize_architecture(root)
    ai = analyze_with_ai({"static_findings": static_findings, "architecture": arch})
    ai_message = ai.get("message", "") if isinstance(ai, dict) else ""
    return {
        "static_findings": static_findings,
        "architecture": arch,
        "ai": ai,
        "ai_message": ai_message,
    }


def _register_all() -> None:
    for tool in list(globals().values()):
        if isinstance(tool, Tool):
            register(tool)


_register_all()


def list_tools() -> list[dict[str, Any]]:
    return [
        {"name": t.name, "description": t.description, "input_schema": t.input_schema}
        for t in TOOLS.values()
    ]


def call_tool(name: str, params: dict[str, Any]) -> Any:
    if name not in TOOLS:
        raise KeyError(f"Tool not found: {name}")
    return TOOLS[name].handler(params)
