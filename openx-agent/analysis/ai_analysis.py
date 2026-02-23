from __future__ import annotations

import json
import logging
from typing import Any

from huggingface_hub import InferenceClient

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


def _get_message_content(completion: Any) -> str | None:
    """Extract assistant message content from chat completion response."""
    try:
        choices = getattr(completion, "choices", None)
        if not choices:
            logger.warning("LLM completion has no choices: %s", completion)
            return None
        choice = choices[0]
        message = getattr(choice, "message", None)
        if message is None:
            logger.warning("LLM choice has no message: %s", choice)
            return None
        content = getattr(message, "content", None)
        if content is not None and isinstance(content, str):
            return content
        # Fallback for backends that use "text"
        text = getattr(message, "text", None)
        if text is not None:
            return str(text)
        logger.warning("LLM message has no content or text field: %s", message)
        return None
    except Exception:
        logger.exception("Failed to extract message content from LLM response")
        return None


def analyze_with_ai(summary: dict) -> dict[str, Any]:
    if not settings.huggingface_api_key:
        return {
            "enabled": False,
            "message": "HUGGINGFACE_API_KEY not set. Set it in .env for AI analysis.",
            "findings": [],
        }

    model = settings.huggingface_model or "Qwen/Qwen2.5-Coder-32B-Instruct"
    base_url = settings.huggingface_base_url

    if base_url:
        base_url = base_url.rstrip("/")
        if base_url.endswith("/v1"):
            base_url = base_url[:-3]

    if base_url:
        client = InferenceClient(
            base_url=base_url,
            api_key=settings.huggingface_api_key,
        )
    else:
        client = InferenceClient(
            provider="auto",
            api_key=settings.huggingface_api_key,
        )
    user_content = _serialize_summary(_compact_summary(summary))
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.2,
            max_tokens=1024,
        )
    except Exception as exc:
        logger.exception("LLM request failed (model=%s, base_url=%s)", model, base_url)
        return {
            "enabled": True,
            "message": f"LLM request failed: {exc!s}. Check HUGGINGFACE_API_KEY and HUGGINGFACE_BASE_URL. If the default model is unavailable, set HUGGINGFACE_MODEL=Qwen/Qwen2.5-7B-Instruct in .env.",
        }

    raw = _get_message_content(completion)
    message = (raw or "").strip() or (
        "The model returned no text. Try HUGGINGFACE_MODEL=Qwen/Qwen2.5-7B-Instruct in .env if the default model is unavailable."
    )
    return {"enabled": True, "message": message}
