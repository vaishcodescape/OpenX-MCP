"""Shared LLM and embeddings factory for all LangChain components.

Both factories are cached with `@lru_cache` so the expensive initialisation
(model download for embeddings, API key validation for Claude) only ever
happens once per process.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from langchain_anthropic import ChatAnthropic
from langchain_huggingface import HuggingFaceEmbeddings

from .config import settings

logger = logging.getLogger(__name__)

_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def get_embeddings() -> HuggingFaceEmbeddings:
    """Return the cached sentence-transformer embedding model for RAG."""
    logger.info("Loading embedding model: %s", _EMBEDDING_MODEL)
    return HuggingFaceEmbeddings(
        model_name=_EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


@lru_cache(maxsize=1)
def get_llm() -> ChatAnthropic:
    """Return the cached Claude chat model.

    Raises `RuntimeError` if `ANTHROPIC_API_KEY` is not configured.
    """
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is required. Set it in .env.")

    model = settings.anthropic_model or "claude-3-5-sonnet-latest"
    logger.info(
        "Initialising LLM: model=%s max_tokens=%d timeout=%.1fs",
        model,
        settings.llm_max_tokens,
        settings.llm_timeout_sec,
    )
    return ChatAnthropic(
        model=model,
        api_key=settings.anthropic_api_key,
        temperature=0.2,
        max_tokens=settings.llm_max_tokens,
        default_request_timeout=settings.llm_timeout_sec,
    )
