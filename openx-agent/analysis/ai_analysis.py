from __future__ import annotations

from typing import Any

import httpx

from ..config import settings


SYSTEM_PROMPT = (
    "You are a senior software engineer reviewing code. "
    "Identify any bugs or logic errors, performance bottlenecks, and redundant or duplicated logic. "
    "Flag instances of AI-generated or boilerplate code patterns as well as poor coding practices or anti-patterns. "
    "Assess the overall architecture for design inefficiencies or flaws. "
    "Provide concise, actionable feedback on both immediate code issues and higher-level design concerns."
)


def analyze_with_ai(summary: dict) -> dict[str, Any]:
    if not settings.huggingface_api_key:
        return {
            "enabled": False,
            "message": "HUGGINGFACE_API_KEY not set",
            "findings": [],
        }

    payload = {
        "model": settings.huggingface_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Repository summary: {summary}"},
        ],
        "temperature": 0.2,
    }

    base_url = settings.huggingface_base_url or "https://router.huggingface.co/v1"
    url = base_url.rstrip("/") + "/chat/completions"

    headers = {"Authorization": f"Bearer {settings.huggingface_api_key}"}
    with httpx.Client(timeout=30) as client:
        resp = client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    message = data["choices"][0]["message"]["content"]
    return {"enabled": True, "message": message}
