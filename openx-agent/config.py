from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    github_token: str | None = os.getenv("GITHUB_TOKEN")
    github_base_url: str | None = os.getenv("GITHUB_BASE_URL")
    huggingface_api_key: str | None = os.getenv("HUGGINGFACE_API_KEY")
    huggingface_base_url: str | None = os.getenv("HUGGINGFACE_BASE_URL")
    huggingface_model: str = os.getenv(
        "HUGGINGFACE_MODEL", "Qwen/Qwen2.5-Coder-32B-Instruct"
    )
    # LLM: lower max_tokens = faster; timeout to avoid hanging. Tune via OPENX_LLM_MAX_TOKENS, OPENX_LLM_TIMEOUT_SEC.
    llm_max_tokens: int = int(os.getenv("OPENX_LLM_MAX_TOKENS", "768"))
    llm_timeout_sec: float = float(os.getenv("OPENX_LLM_TIMEOUT_SEC", "90"))
    langsmith_api_key: str | None = os.getenv("LANGCHAIN_API_KEY")
    langsmith_tracing: bool = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
    langsmith_project: str = os.getenv("LANGCHAIN_PROJECT", "openx-agent")
    # Root directory for local repo operations (read_file, write_file, git_*). Default: cwd.
    workspace_root: str = os.getenv("OPENX_WORKSPACE_ROOT", os.getcwd())


settings = Settings()
