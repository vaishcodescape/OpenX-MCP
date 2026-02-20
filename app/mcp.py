from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel, Field

from .analysis.ai_analysis import analyze_with_ai
from .analysis.architecture import summarize_architecture
from .analysis.static_analysis import analyze_static
from .github_client import (
    comment_pr,
    get_pr,
    get_repo,
    get_workflow_run,
    list_open_prs,
    list_repos,
    list_workflow_runs,
    list_workflows,
    merge_pr,
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
    return {
        "static_findings": static_findings,
        "architecture": arch,
        "ai": ai,
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
