from __future__ import annotations

from typing import Any

import httpx

from ..config import settings


SYSTEM_PROMPT = (
    "You are a senior reviewer. Provide concise findings about bugs, performance, "
    "duplicate code, AI-generated code, and bad practices. Provide architecture insights too."
)


def analyze_with_ai(summary: dict) -> dict[str, Any]:
    if not settings.openai_api_key:
        return {"enabled": False, "message": "OPENAI_API_KEY not set", "findings": []}

    payload = {
        "model": settings.openai_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Repository summary: {summary}"},
        ],
        "temperature": 0.2,
    }

    base_url = settings.openai_base_url or "https://api.openai.com/v1"
    url = base_url.rstrip("/") + "/chat/completions"

    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
    with httpx.Client(timeout=30) as client:
        resp = client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    message = data["choices"][0]["message"]["content"]
    return {"enabled": True, "message": message}
