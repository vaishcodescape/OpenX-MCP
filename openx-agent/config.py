"""Central configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    github_token: str | None = os.getenv("GITHUB_TOKEN")
    github_base_url: str | None = os.getenv("GITHUB_BASE_URL")
    anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-3-opus-latest")
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
