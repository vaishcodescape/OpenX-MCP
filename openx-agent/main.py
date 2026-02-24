"""FastAPI application — exposes the OpenX agent over HTTP.

Endpoints
---------
GET  /health       — liveness probe.
GET  /progress     — long-running operation status (heal_ci, index).
GET  /tools        — MCP tool list for the command palette.
POST /mcp          — raw MCP protocol (tools/list, tools/call).
POST /chat         — LangChain ReAct agent conversation.
POST /run          — same as /chat, legacy format (output + should_continue).
POST /index        — index a GitHub repo into the RAG knowledge base.
"""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from .mcp import MCPRequest, MCPResponse, call_tool, list_tools

app = FastAPI(title="OpenX", version="1.0")

# Stable conversation ID for /run callers (separate from TUI sessions).
_RUN_CONVERSATION_ID = "run-default"


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ChatBody(BaseModel):
    message: str
    conversation_id: str = "default"


class RunBody(BaseModel):
    command: str = ""


class IndexBody(BaseModel):
    repo_full_name: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/progress")
async def progress(operation: str | None = None) -> dict:
    """Return current progress for a long-running operation (heal_ci, index).

    Poll this endpoint to drive progress indicators in the TUI.
    """
    from .progress import get_progress

    return {"progress": get_progress(operation)}


@app.get("/tools")
async def tools() -> list:
    """Return the registered MCP tool list for the command palette."""
    return list_tools()


@app.post("/mcp")
async def mcp(request: MCPRequest) -> MCPResponse:
    """Handle raw MCP protocol messages (tools/list and tools/call)."""
    try:
        if request.method == "tools/list":
            return MCPResponse(id=request.id, result=list_tools())

        if request.method == "tools/call":
            params = request.params or {}
            name = params.get("name")
            if not name:
                raise ValueError("Missing tool name")
            result = call_tool(name, params.get("arguments") or {})
            return MCPResponse(id=request.id, result=result)

        raise ValueError(f"Unknown MCP method: {request.method!r}")

    except Exception as exc:
        return MCPResponse(id=request.id, error={"message": str(exc)})


@app.post("/chat")
async def chat_endpoint(body: ChatBody) -> dict:
    """Send a message to the LangChain ReAct agent.

    The special message ``reset`` clears conversation memory without an LLM
    round-trip.
    """
    from .langchain_agent import chat as agent_chat, reset_conversation

    msg = (body.message or "").strip()
    if msg.lower() == "reset":
        reset_conversation(body.conversation_id)
        return {
            "response": "Conversation reset. You can continue with a fresh context.",
            "conversation_id": body.conversation_id,
        }

    try:
        response = agent_chat(msg, body.conversation_id)
        return {"response": response, "conversation_id": body.conversation_id}
    except Exception as exc:
        return {"response": None, "conversation_id": body.conversation_id, "error": str(exc)}


@app.post("/run")
async def run_raw(body: RunBody) -> dict:
    """Run a command via the agent.  Returns ``{should_continue, output}``."""
    from .langchain_agent import chat as agent_chat, reset_conversation

    msg = (body.command or "").strip()
    if not msg:
        return {"should_continue": True, "output": None}

    if msg.lower() in ("quit", "exit"):
        return {"should_continue": False, "output": "Goodbye."}

    if msg.lower() == "reset":
        reset_conversation(_RUN_CONVERSATION_ID)
        return {
            "should_continue": True,
            "output": "Conversation reset. You can continue with a fresh context.",
        }

    try:
        response = agent_chat(msg, _RUN_CONVERSATION_ID)
        return {"should_continue": True, "output": response, "error": None}
    except Exception as exc:
        return {"should_continue": True, "output": None, "error": str(exc)}


@app.post("/index")
async def index_endpoint(body: IndexBody) -> dict:
    """Index a GitHub repository into the RAG knowledge base."""
    from .rag import index_repo

    try:
        return index_repo(body.repo_full_name)
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
