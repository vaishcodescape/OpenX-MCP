from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Load .env from project root (parent of openx_agent package) so config works regardless of cwd.
_env_loaded = False


def _ensure_dotenv() -> None:
    global _env_loaded
    if _env_loaded:
        return
    try:
        from dotenv import load_dotenv
        # openx_agent/config.py -> parent = openx_agent, parent.parent = project root
        root = Path(__file__).resolve().parent.parent
        load_dotenv(root / ".env")
        _env_loaded = True
    except Exception:
        _env_loaded = True  # avoid retry


_ensure_dotenv()  # run before Settings so os.getenv below sees .env

@dataclass(frozen=True)
class Settings:
    # Fine-grained PATs work: grant Issues + Pull requests "Read and write" and add repos under Repository access.
    github_token: str | None = os.getenv("GITHUB_TOKEN")
    github_base_url: str | None = os.getenv("GITHUB_BASE_URL")
    anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY")
    anthropic_model: str = os.getenv(
        "ANTHROPIC_MODEL", "claude-3-opus-latest"
    )
    # LLM: lower max_tokens = faster; timeout to avoid hanging. Tune via OPENX_LLM_MAX_TOKENS, OPENX_LLM_TIMEOUT_SEC.
    llm_max_tokens: int = int(os.getenv("OPENX_LLM_MAX_TOKENS", "768"))
    llm_timeout_sec: float = float(os.getenv("OPENX_LLM_TIMEOUT_SEC", "90"))
    langsmith_api_key: str | None = os.getenv("LANGCHAIN_API_KEY")
    langsmith_tracing: bool = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
    langsmith_project: str = os.getenv("LANGCHAIN_PROJECT", "openx-agent")
    # Root directory for local repo operations (read_file, write_file, git_*). Default: cwd.
    workspace_root: str = os.getenv("OPENX_WORKSPACE_ROOT", os.getcwd())
    # Active repository (owner/repo) for commands that operate on "current" repo when not specified.
    active_repo: str | None = os.getenv("OPENX_ACTIVE_REPO")


def resolve_repo(repo: str | None, *, required: bool = True) -> str:
    """Resolve repo_full_name: use argument, else OPENX_ACTIVE_REPO, else raise or return None."""
    out = (repo or "").strip() or (settings.active_repo or "").strip()
    if required and not out:
        raise ValueError(
            "No repository specified. Set OPENX_ACTIVE_REPO (e.g. owner/repo) or pass repo to the command."
        )
    return out


settings = Settings()
# Alias for backward compatibility with mcp.py and other callers.
config_settings = settings
