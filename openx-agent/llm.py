"""LLM factory — provides a ChatAnthropic instance for LangGraph agents.

Uses ``ANTHROPIC_API_KEY`` and ``ANTHROPIC_MODEL`` from the environment (via
:mod:`config`).  Call :func:`get_llm` to obtain a ready-to-use chat model.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from langchain_anthropic import ChatAnthropic

from .config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_llm(
    *,
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float = 0.0,
) -> ChatAnthropic:
    """Return a cached :class:`ChatAnthropic` instance.

    Parameters
    ----------
    model:
        Override ``ANTHROPIC_MODEL`` (default ``claude-sonnet-4-20250514``).
    max_tokens:
        Override ``OPENX_LLM_MAX_TOKENS``.
    temperature:
        Sampling temperature.  ``0.0`` for deterministic tool-use.
    """
    resolved_model = model or settings.anthropic_model or "claude-sonnet-4-20250514"
    resolved_tokens = max_tokens or settings.llm_max_tokens or 4096

    if not settings.anthropic_api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is required.  Set it in .env or as an environment variable."
        )

    logger.info("Initialising ChatAnthropic  model=%s  max_tokens=%d", resolved_model, resolved_tokens)
    return ChatAnthropic(
        model=resolved_model,
        anthropic_api_key=settings.anthropic_api_key,
        max_tokens=resolved_tokens,
        temperature=temperature,
        timeout=settings.llm_timeout_sec,
    )
