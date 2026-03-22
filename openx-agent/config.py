"""Central configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

def _load_dotenv() -> None:
    """Load .env from the project root (parent of this package directory)."""
    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    except Exception:
        pass  # dotenv not installed or .env absent — env vars still work

_load_dotenv()

@dataclass(frozen=True)
class Settings:
    github_token: str | None = os.getenv("GITHUB_TOKEN")
    github_base_url: str | None = os.getenv("GITHUB_BASE_URL")
    anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-3-opus-latest")
    llm_max_tokens: int = int(os.getenv("OPENX_LLM_MAX_TOKENS", "768"))
    llm_timeout_sec: float = float(os.getenv("OPENX_LLM_TIMEOUT_SEC", "90"))
    langsmith_api_key: str | None = os.getenv("LANGCHAIN_API_KEY")
    langsmith_tracing: bool = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
    langsmith_project: str = os.getenv("LANGCHAIN_PROJECT", "openx-agent")
    workspace_root: str = os.getenv("OPENX_WORKSPACE_ROOT", os.getcwd())
    active_repo: str | None = os.getenv("OPENX_ACTIVE_REPO")

settings = Settings()
config_settings = settings

def resolve_repo(repo: str | None, *, required: bool = True) -> str:
    """Return a canonical owner/repo string."""
    resolved = (repo or "").strip() or (settings.active_repo or "").strip()
    if required and not resolved:
        raise ValueError(
            "No repository specified. Set OPENX_ACTIVE_REPO (e.g. owner/repo)"
            " or pass the repo to the command."
        )
    return resolved
