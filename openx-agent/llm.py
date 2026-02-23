"""Shared LLM and embeddings factory for LangChain components.

Uses huggingface_hub.InferenceClient directly (the same approach that
works reliably in ai_analysis.py) wrapped as a LangChain BaseChatModel,
instead of ChatHuggingFace/HuggingFaceEndpoint which hang on certain providers.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, List, Optional

from huggingface_hub import InferenceClient
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_huggingface import HuggingFaceEmbeddings

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
# Custom Chat Model using InferenceClient (proven reliable)
# ---------------------------------------------------------------------------


class HFInferenceChat(BaseChatModel):
    """LangChain chat model backed by huggingface_hub.InferenceClient.

    Uses the exact same API call pattern as ai_analysis.py which works.
    """

    model: str = "Qwen/Qwen2.5-Coder-32B-Instruct"
    api_key: str = ""
    base_url: str = ""
    temperature: float = 0.2
    max_tokens: int = 768
    timeout: float = 90.0

    @property
    def _llm_type(self) -> str:
        return "hf-inference-chat"

    def _get_client(self) -> InferenceClient:
        kwargs: dict[str, Any] = {
            "api_key": self.api_key,
            "timeout": self.timeout,
        }
        if self.base_url:
            kwargs["base_url"] = self.base_url
        else:
            kwargs["provider"] = "auto"
        return InferenceClient(**kwargs)

    def _to_hf_messages(self, messages: List[BaseMessage]) -> list[dict[str, str]]:
        """Convert LangChain messages to HuggingFace chat format."""
        hf_msgs = []
        for msg in messages:
            content = getattr(msg, "content", None) or ""
            content = content if isinstance(content, str) else str(content)
            if isinstance(msg, SystemMessage):
                hf_msgs.append({"role": "system", "content": content})
            elif isinstance(msg, HumanMessage):
                hf_msgs.append({"role": "user", "content": content})
            elif isinstance(msg, AIMessage):
                hf_msgs.append({"role": "assistant", "content": content})
            else:
                hf_msgs.append({"role": "user", "content": content})
        return hf_msgs

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        client = self._get_client()
        hf_messages = self._to_hf_messages(messages)

        logger.debug("HFInferenceChat calling model=%s with %d messages", self.model, len(hf_messages))

        try:
            completion = client.chat.completions.create(
                model=self.model,
                messages=hf_messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stop=stop or [],
            )
        except Exception:
            logger.exception("HFInferenceChat request failed (model=%s)", self.model)
            raise

        # Extract content from response (handle None, empty, missing choices).
        content = ""
        choices = getattr(completion, "choices", None)
        if choices and len(choices) > 0:
            message = getattr(choices[0], "message", None)
            if message is not None:
                content = getattr(message, "content", None)
                content = (content or "").strip() if isinstance(content, str) else ""

        if not content:
            logger.warning("HFInferenceChat got empty content from model=%s", self.model)
            content = "I couldn't generate a response. Please try again or rephrase."

        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=content))]
        )

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"model": self.model, "base_url": self.base_url}


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_llm() -> HFInferenceChat:
    """Return a cached chat LLM for LangChain agents/chains."""
    if not settings.huggingface_api_key:
        raise RuntimeError("HUGGINGFACE_API_KEY is required. Set it in .env.")

    model = settings.huggingface_model or "Qwen/Qwen2.5-Coder-32B-Instruct"
    base_url = settings.huggingface_base_url or ""

    # Normalize base_url.
    if base_url:
        base_url = base_url.rstrip("/")
        if base_url.endswith("/v1"):
            base_url = base_url[:-3]

    max_tokens = getattr(settings, "llm_max_tokens", 768)
    timeout = getattr(settings, "llm_timeout_sec", 90.0)
    logger.info("LLM: model=%s base_url=%s max_tokens=%s timeout=%s", model, base_url or "(auto)", max_tokens, timeout)
    return HFInferenceChat(
        model=model,
        api_key=settings.huggingface_api_key,
        base_url=base_url,
        temperature=0.2,
        max_tokens=max_tokens,
        timeout=timeout,
    )
