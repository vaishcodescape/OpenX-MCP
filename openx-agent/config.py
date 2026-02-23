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
    langsmith_api_key: str | None = os.getenv("LANGCHAIN_API_KEY")
    langsmith_tracing: bool = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
    langsmith_project: str = os.getenv("LANGCHAIN_PROJECT", "openx-agent")


settings = Settings()
