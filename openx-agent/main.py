from __future__ import annotations

import shlex

from fastapi import FastAPI
from pydantic import BaseModel

from .command_router import run_command
from .mcp import MCPRequest, MCPResponse, call_tool, list_tools


class RunBody(BaseModel):
    command: str = ""

app = FastAPI(title="OpenX", version="1.0")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/tools")
async def tools() -> list:
    """Return list of MCP tools for command palette (name, description)."""
    return list_tools()


@app.post("/mcp")
async def mcp(request: MCPRequest) -> MCPResponse:
    try:
        if request.method == "tools/list":
            return MCPResponse(id=request.id, result=list_tools())
        if request.method == "tools/call":
            params = request.params or {}
            name = params.get("name")
            arguments = params.get("arguments") or {}
            if not name:
                raise ValueError("Missing tool name")
            result = call_tool(name, arguments)
            return MCPResponse(id=request.id, result=result)
        raise ValueError(f"Unknown method: {request.method}")
    except Exception as exc:  # noqa: BLE001
        return MCPResponse(id=request.id, error={"message": str(exc)})


@app.post("/run")
async def run_raw(body: RunBody) -> dict:
    """Run a single command string (same as TUI input). Returns { should_continue, output }."""
    tokens = shlex.split(body.command) if (body.command or "").strip() else []
    result = run_command(tokens)
    return {"should_continue": result.should_continue, "output": result.output}
