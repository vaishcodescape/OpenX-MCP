"""AI-powered code review using the Anthropic Claude API.

Sends a compact JSON summary of static findings and architecture to Claude and
returns its structured feedback.  When ``ANTHROPIC_API_KEY`` is absent the
function returns a graceful no-op response so the rest of the analysis still
works.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import anthropic

from ..config import settings

logger = logging.getLogger(__name__)

_MAX_USER_CONTENT_CHARS = 6_000
_MAX_FINDINGS_PER_CATEGORY = 5

_SYSTEM_PROMPT = (
    "You are a senior software engineer reviewing code. "
    "Identify bugs or logic errors, performance bottlenecks, and redundant or duplicated logic. "
    "Flag AI-generated or boilerplate patterns and poor coding practices. "
    "Assess the overall architecture for design inefficiencies or flaws. "
    "Provide concise, actionable feedback on both immediate code issues and higher-level design concerns."
)


def _compact_summary(summary: dict) -> dict:
    """Trim per-category findings and strip absolute paths to basenames."""
    out: dict = {}
    for key, val in summary.items():
        if not isinstance(val, dict):
            out[key] = val
            continue
        trimmed: dict = {}
        for cat, items in val.items():
            if not isinstance(items, list):
                trimmed[cat] = items
                continue
            capped = [
                {**item, "file": os.path.basename(item["file"])} if "file" in item else item
                for item in items[:_MAX_FINDINGS_PER_CATEGORY]
            ]
            trimmed[cat] = capped
            if len(items) > _MAX_FINDINGS_PER_CATEGORY:
                trimmed[f"{cat}_total"] = len(items)
        out[key] = trimmed
    return out


def _serialize(summary: dict) -> str:
    text = json.dumps(summary, default=str)
    if len(text) > _MAX_USER_CONTENT_CHARS:
        text = text[: _MAX_USER_CONTENT_CHARS - 50] + '... "[truncated]"'
    return text


def analyze_with_ai(summary: dict) -> dict[str, Any]:
    """Send *summary* to Claude and return its code-review findings.

    Returns ``{"enabled": False, ...}`` when the API key is missing.
    Returns ``{"enabled": True, "message": <text>}`` on success or API error.
    """
    if not settings.anthropic_api_key:
        return {
            "enabled": False,
            "message": "ANTHROPIC_API_KEY not set. Add it to .env to enable AI code analysis.",
            "findings": [],
        }

    model = settings.anthropic_model or "claude-3-opus-latest"
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    try:
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _serialize(_compact_summary(summary))}],
        )
    except Exception as exc:
        logger.exception("Claude request failed (model=%s)", model)
        return {
            "enabled": True,
            "message": f"LLM request failed: {exc!s}. Check ANTHROPIC_API_KEY and ANTHROPIC_MODEL.",
        }

    text = (response.content[0].text if response.content else "").strip()
    return {
        "enabled": True,
        "message": text or "The model returned no text. Verify ANTHROPIC_MODEL is set correctly.",
    }
