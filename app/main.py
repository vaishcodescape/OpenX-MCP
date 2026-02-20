from __future__ import annotations

from fastapi import FastAPI, HTTPException

from .mcp import MCPRequest, MCPResponse, call_tool, list_tools

app = FastAPI(title="OpenX MCP Server", version="1.0")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


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
