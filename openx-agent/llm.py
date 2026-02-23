"""Shared LLM and embeddings factory for LangChain components."""

from __future__ import annotations

import logging
from functools import lru_cache

from langchain_huggingface import (
    ChatHuggingFace,
    HuggingFaceEndpoint,
    HuggingFaceEmbeddings,
)

from .config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Embedding model (small, fast, free — runs locally via sentence-transformers)
# ---------------------------------------------------------------------------
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
# Chat LLM (HuggingFace Inference API)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_llm() -> ChatHuggingFace:
    """Return a cached ChatHuggingFace LLM for LangChain agents/chains."""
    if not settings.huggingface_api_key:
        raise RuntimeError("HUGGINGFACE_API_KEY is required. Set it in .env.")

    model = settings.huggingface_model or "Qwen/Qwen2.5-Coder-32B-Instruct"

    # Use repo_id only — let the library handle routing.
    # This avoids the mutual-exclusivity issue between repo_id/endpoint_url.
    endpoint = HuggingFaceEndpoint(
        repo_id=model,
        huggingfacehub_api_token=settings.huggingface_api_key,
        temperature=0.2,
        max_new_tokens=1024,
        task="text-generation",
    )
    return ChatHuggingFace(llm=endpoint, model_id=model)
