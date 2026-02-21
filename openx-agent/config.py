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


settings = Settings()
