from __future__ import annotations

import json
import logging
from typing import Any

import anthropic

from ..config import settings


MAX_USER_CONTENT_CHARS = 6_000
MAX_FINDINGS_PER_CATEGORY = 5

SYSTEM_PROMPT = (
    "You are a senior software engineer reviewing code. "
    "Identify any bugs or logic errors, performance bottlenecks, and redundant or duplicated logic. "
    "Flag instances of AI-generated or boilerplate code patterns as well as poor coding practices or anti-patterns. "
    "Assess the overall architecture for design inefficiencies or flaws. "
    "Provide concise, actionable feedback on both immediate code issues and higher-level design concerns."
)


def _compact_summary(summary: dict) -> dict:
    """Trim the analysis summary so it stays within LLM input limits.

    - Caps findings per category to MAX_FINDINGS_PER_CATEGORY.
    - Strips absolute file paths to basenames.
    """
    import os
    out: dict = {}
    for key, val in summary.items():
        if isinstance(val, dict):
            trimmed: dict = {}
            for cat, items in val.items():
                if isinstance(items, list):
                    capped = items[:MAX_FINDINGS_PER_CATEGORY]
                    for item in capped:
                        if isinstance(item, dict) and "file" in item:
                            item["file"] = os.path.basename(item["file"])
                    trimmed[cat] = capped
                    if len(items) > MAX_FINDINGS_PER_CATEGORY:
                        trimmed[f"{cat}_total"] = len(items)
                else:
                    trimmed[cat] = items
            out[key] = trimmed
        else:
            out[key] = val
    return out


def _serialize_summary(summary: dict) -> str:
    out = json.dumps(summary, default=str)
    if len(out) > MAX_USER_CONTENT_CHARS:
        out = out[: MAX_USER_CONTENT_CHARS - 50] + '... "[truncated]"'
    return out


logger = logging.getLogger(__name__)


def analyze_with_ai(summary: dict) -> dict[str, Any]:
    if not settings.anthropic_api_key:
        return {
            "enabled": False,
            "message": "ANTHROPIC_API_KEY not set. Set it in .env for AI code analysis.",
            "findings": [],
        }

    model = settings.anthropic_model or "claude-3-opus-latest"
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    user_content = _serialize_summary(_compact_summary(summary))

    try:
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
    except Exception as exc:
        logger.exception("Claude request failed (model=%s)", model)
        return {
            "enabled": True,
            "message": f"LLM request failed: {exc!s}. Check ANTHROPIC_API_KEY and ANTHROPIC_MODEL.",
        }

    raw = response.content[0].text if response.content else ""
    message = (raw or "").strip() or (
        "The model returned no text. Check ANTHROPIC_MODEL is set correctly."
    )
    return {"enabled": True, "message": message}
