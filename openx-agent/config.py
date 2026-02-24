"""Central configuration — loaded once from .env at import time.

All settings are read from environment variables (with sensible defaults).
The frozen dataclass prevents accidental mutation; use `resolve_repo` to
normalise the repo name from user input or the active-repo setting.
"""

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
    # GitHub — fine-grained PAT: grant Issues + Pull requests "Read and write".
    github_token: str | None = os.getenv("GITHUB_TOKEN")
    github_base_url: str | None = os.getenv("GITHUB_BASE_URL")

    # Anthropic / Claude
    anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-3-opus-latest")

    # LLM tuning — lower max_tokens = faster; tune via env vars.
    llm_max_tokens: int = int(os.getenv("OPENX_LLM_MAX_TOKENS", "768"))
    llm_timeout_sec: float = float(os.getenv("OPENX_LLM_TIMEOUT_SEC", "90"))

    # LangSmith tracing (optional)
    langsmith_api_key: str | None = os.getenv("LANGCHAIN_API_KEY")
    langsmith_tracing: bool = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
    langsmith_project: str = os.getenv("LANGCHAIN_PROJECT", "openx-agent")

    # Local workspace root for file/git operations (defaults to cwd).
    workspace_root: str = os.getenv("OPENX_WORKSPACE_ROOT", os.getcwd())

    # Active repository (owner/repo) — used when no explicit repo is given.
    active_repo: str | None = os.getenv("OPENX_ACTIVE_REPO")


settings = Settings()
# Alias kept for any legacy imports.
config_settings = settings


def resolve_repo(repo: str | None, *, required: bool = True) -> str:
    """Return a canonical owner/repo string.

    Preference order: explicit argument → OPENX_ACTIVE_REPO env var.
    Raises `ValueError` when `required` is True and nothing is available.
    """
    resolved = (repo or "").strip() or (settings.active_repo or "").strip()
    if required and not resolved:
        raise ValueError(
            "No repository specified. Set OPENX_ACTIVE_REPO (e.g. owner/repo)"
            " or pass the repo to the command."
        )
    return resolved
