"""Shared LLM and embeddings factory for LangChain components.

Uses langchain_anthropic.ChatAnthropic for the chat model and
local sentence-transformers for embeddings.
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
    """Return a cached HuggingFace embedding model for RAG."""
    logger.info("Loading embedding model: %s", _EMBEDDING_MODEL)
    return HuggingFaceEmbeddings(
        model_name=_EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_llm() -> ChatAnthropic:
    """Return a cached chat LLM for LangChain agents/chains."""
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is required. Set it in .env.")

    model = settings.anthropic_model or "claude-3-5-sonnet-latest"

    max_tokens = getattr(settings, "llm_max_tokens", 4096)
    timeout = getattr(settings, "llm_timeout_sec", 90.0)
    logger.info("LLM: model=%s max_tokens=%s timeout=%s", model, max_tokens, timeout)
    return ChatAnthropic(
        model=model,
        api_key=settings.anthropic_api_key,
        temperature=0.2,
        max_tokens=max_tokens,
        default_request_timeout=timeout,
    )
