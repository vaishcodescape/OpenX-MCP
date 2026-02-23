from __future__ import annotations

from dotenv import load_dotenv

from fastapi import FastAPI

load_dotenv()
from pydantic import BaseModel

from .mcp import MCPRequest, MCPResponse, call_tool, list_tools


class RunBody(BaseModel):
    command: str = ""


# Conversation ID used for programmatic /run calls (separate from TUI chat).
RUN_CONVERSATION_ID = "run-default"

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
    except Exception as exc:   
        return MCPResponse(id=request.id, error={"message": str(exc)})


@app.post("/run")
async def run_raw(body: RunBody) -> dict:
    """Run a command via the LLM agent (same workflow as /chat). Returns { should_continue, output }."""
    from .langchain_agent import chat as agent_chat, reset_conversation

    msg = (body.command or "").strip()
    if not msg:
        return {"should_continue": True, "output": None}

    msg_lower = msg.lower()
    if msg_lower in ("quit", "exit"):
        return {"should_continue": False, "output": "Goodbye."}
    if msg_lower == "reset":
        reset_conversation(RUN_CONVERSATION_ID)
        return {
            "should_continue": True,
            "output": "Conversation reset. You can continue with a fresh context.",
        }

    try:
        response = agent_chat(msg, RUN_CONVERSATION_ID)
        return {"should_continue": True, "output": response, "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"should_continue": True, "output": None, "error": str(exc)}


# ---------------------------------------------------------------------------
# LangChain Agent endpoints
# ---------------------------------------------------------------------------


class ChatBody(BaseModel):
    message: str
    conversation_id: str = "default"


class IndexBody(BaseModel):
    repo_full_name: str


@app.post("/chat")
async def chat_endpoint(body: ChatBody) -> dict:
    """Send a message to the LangChain ReAct agent. Handles /reset locally."""
    from .langchain_agent import chat as agent_chat, reset_conversation

    msg = (body.message or "").strip()
    if msg.lower() == "reset":
        reset_conversation(body.conversation_id)
        return {
            "response": "Conversation reset. You can continue with a fresh context.",
            "conversation_id": body.conversation_id,
        }

    try:
        response = agent_chat(body.message or "", body.conversation_id)
        return {"response": response, "conversation_id": body.conversation_id}
    except Exception as exc:  # noqa: BLE001
        return {"response": None, "conversation_id": body.conversation_id, "error": str(exc)}


@app.post("/index")
async def index_endpoint(body: IndexBody) -> dict:
    """Index a GitHub repository into the RAG knowledge base."""
    from .rag import index_repo

    try:
        result = index_repo(body.repo_full_name)
        return result
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "message": str(exc)}
