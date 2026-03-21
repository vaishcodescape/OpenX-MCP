"""RAG pipeline — fetch GitHub data, store in-memory, retrieve via keyword search.

Replaces the previous FAISS/HuggingFace vector approach with a lightweight
TF-IDF keyword search that requires zero ML dependencies.  Documents are
stored as plain text with metadata; retrieval uses term-frequency scoring.
"""

from __future__ import annotations

import base64
import logging
import math
import os
import re
from collections import Counter, OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any

from .config import settings
from .github_client import (
    get_repo,
    list_open_prs,
    list_repos,
    list_workflows,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Document model (stdlib only — no LangChain dependency)
# ---------------------------------------------------------------------------

_STOP_WORDS = frozenset(
    "a an the is was were be been being have has had do does did will would "
    "shall should may might can could and but or nor not so yet for of in on "
    "at to from by with as into through during before after above below between "
    "out off over under again further then once here there when where why how "
    "all each every both few more most other some such no only own same than "
    "too very just don't isn't aren't wasn't weren't hasn't haven't hadn't "
    "doesn't didn't won't wouldn't shan't shouldn't can't cannot couldn't "
    "mustn't let's that's who's what's here's there's it's".split()
)

_TOKEN_RE = re.compile(r"[a-z0-9_]{2,}")


def _tokenize(text: str) -> list[str]:
    """Lowercase, split on non-alnum, drop stop words."""
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOP_WORDS]


@dataclass
class _Document:
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    tokens: list[str] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        if not self.tokens:
            self.tokens = _tokenize(self.content)


# ---------------------------------------------------------------------------
# In-memory document store with TF-IDF scoring
# ---------------------------------------------------------------------------

_MAX_STORES = 20


class _DocStore:
    """Lightweight keyword store for a single repo's documents."""

    __slots__ = ("docs", "idf")

    def __init__(self, docs: list[_Document]) -> None:
        self.docs = docs
        self.idf: dict[str, float] = {}
        self._build_idf()

    def _build_idf(self) -> None:
        n = len(self.docs)
        if n == 0:
            return
        df: Counter[str] = Counter()
        for doc in self.docs:
            df.update(set(doc.tokens))
        self.idf = {term: math.log((n + 1) / (freq + 1)) + 1.0 for term, freq in df.items()}

    def search(self, query: str, k: int = 4) -> list[dict[str, Any]]:
        q_tokens = _tokenize(query)
        if not q_tokens:
            return []

        q_tf = Counter(q_tokens)
        scores: list[tuple[float, int]] = []
        for idx, doc in enumerate(self.docs):
            doc_tf = Counter(doc.tokens)
            score = 0.0
            for term, q_count in q_tf.items():
                if term in doc_tf:
                    tf = 1 + math.log(doc_tf[term])
                    idf = self.idf.get(term, 1.0)
                    score += tf * idf * q_count
            if score > 0:
                scores.append((score, idx))

        scores.sort(key=lambda x: x[0], reverse=True)
        return [
            {"content": self.docs[idx].content, "metadata": self.docs[idx].metadata, "score": round(sc, 4)}
            for sc, idx in scores[:k]
        ]


_STORES: OrderedDict[str, _DocStore] = OrderedDict()


# ---------------------------------------------------------------------------
# Document loaders — turn GitHub API data into _Document objects
# ---------------------------------------------------------------------------


def _load_repo_metadata(repo_full_name: str) -> list[_Document]:
    docs: list[_Document] = []
    try:
        repo = get_repo(repo_full_name)
        text = (
            f"Repository: {repo.full_name}\n"
            f"Description: {repo.description or 'N/A'}\n"
            f"Language: {repo.language or 'N/A'}\n"
            f"Stars: {repo.stargazers_count}  Forks: {repo.forks_count}\n"
            f"Default branch: {repo.default_branch}\n"
            f"Topics: {', '.join(repo.get_topics())}\n"
            f"URL: {repo.html_url}"
        )
        docs.append(_Document(
            content=text,
            metadata={"source": "github", "repo": repo_full_name, "type": "repo_metadata", "url": repo.html_url},
        ))
    except Exception:
        logger.exception("Failed to load repo metadata for %s", repo_full_name)
    return docs


def _load_pull_requests(repo_full_name: str) -> list[_Document]:
    docs: list[_Document] = []
    try:
        prs = list_open_prs(repo_full_name)
        for pr in prs[:20]:
            text = (
                f"Pull Request #{pr['number']}: {pr['title']}\n"
                f"Author: {pr['user']}\n"
                f"State: {pr['state']}\n"
                f"URL: {pr['html_url']}"
            )
            docs.append(_Document(
                content=text,
                metadata={"source": "github", "repo": repo_full_name, "type": "pull_request", "pr_number": pr["number"], "url": pr["html_url"]},
            ))
    except Exception:
        logger.exception("Failed to load PRs for %s", repo_full_name)
    return docs


def _load_readme(repo_full_name: str) -> list[_Document]:
    docs: list[_Document] = []
    try:
        repo = get_repo(repo_full_name)
        readme = repo.get_readme()
        content = base64.b64decode(readme.content).decode("utf-8", errors="replace")
        if len(content) > 8_000:
            content = content[:8_000] + "\n\n... [truncated]"
        docs.append(_Document(
            content=content,
            metadata={"source": "github", "repo": repo_full_name, "type": "readme", "url": readme.html_url},
        ))
    except Exception:
        logger.exception("Failed to load README for %s", repo_full_name)
    return docs


def _load_workflows(repo_full_name: str) -> list[_Document]:
    docs: list[_Document] = []
    try:
        wfs = list_workflows(repo_full_name)
        for wf in wfs:
            text = (
                f"Workflow: {wf['name']}\n"
                f"Path: {wf['path']}\n"
                f"State: {wf['state']}\n"
                f"URL: {wf['html_url']}"
            )
            docs.append(_Document(
                content=text,
                metadata={"source": "github", "repo": repo_full_name, "type": "workflow", "url": wf["html_url"]},
            ))
    except Exception:
        logger.exception("Failed to load workflows for %s", repo_full_name)
    return docs


def _load_repo_listing() -> list[_Document]:
    docs: list[_Document] = []
    try:
        repos = list_repos()
        for r in repos:
            text = (
                f"Repository: {r['full_name']}\n"
                f"Private: {r['private']}\n"
                f"Default branch: {r['default_branch']}\n"
                f"URL: {r['html_url']}"
            )
            docs.append(_Document(
                content=text,
                metadata={"source": "github", "repo": r["full_name"], "type": "repo_listing", "url": r["html_url"]},
            ))
    except Exception:
        logger.exception("Failed to list repos")
    return docs


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------


def index_repo(repo_full_name: str) -> dict[str, Any]:
    """Fetch GitHub data for a repo and build a keyword index."""
    logger.info("Indexing repo: %s", repo_full_name)

    loaders: list[tuple[Any, ...]] = [
        (_load_repo_metadata, repo_full_name),
        (_load_pull_requests, repo_full_name),
        (_load_readme, repo_full_name),
        (_load_workflows, repo_full_name),
        (_load_repo_listing,),
    ]
    docs: list[_Document] = []
    with ThreadPoolExecutor(max_workers=5, thread_name_prefix="rag_loader") as pool:
        futures = [pool.submit(fn, *args) for fn, *args in loaders]
        for future in as_completed(futures):
            try:
                docs.extend(future.result())
            except Exception:
                logger.exception("Document loader raised an exception")

    if not docs:
        return {"status": "error", "message": "No documents fetched."}

    logger.info("Building keyword index from %d documents", len(docs))
    store = _DocStore(docs)

    if len(_STORES) >= _MAX_STORES:
        _STORES.popitem(last=False)
    _STORES[repo_full_name] = store
    _STORES.move_to_end(repo_full_name)

    logger.info("Indexed %d documents for %s", len(docs), repo_full_name)
    return {"status": "indexed", "repo": repo_full_name, "document_count": len(docs)}


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


def query_repo(repo_full_name: str, question: str, k: int = 4) -> list[dict[str, Any]]:
    """Query the keyword index for a repo.  Auto-indexes if needed."""
    store = _STORES.get(repo_full_name)
    if store is None:
        index_repo(repo_full_name)
        store = _STORES.get(repo_full_name)

    if store is None:
        return [{"error": f"No index available for {repo_full_name}"}]

    return store.search(question, k=k)


# ---------------------------------------------------------------------------
# Convenience search across all indexed repos
# ---------------------------------------------------------------------------


def search_knowledge(query: str) -> str:
    """Search all indexed repos for relevant information."""
    all_results: list[dict[str, Any]] = []
    for repo_name in list(_STORES.keys()):
        all_results.extend(query_repo(repo_name, query, k=3))

    if not all_results:
        return "No indexed repositories found. Use rag_index_repo to index a repository first."

    all_results.sort(key=lambda r: r.get("score", 0), reverse=True)

    parts: list[str] = []
    for r in all_results[:6]:
        meta = r.get("metadata", {})
        parts.append(
            f"[{meta.get('type', 'unknown')}] ({meta.get('repo', '?')})\n"
            f"{r.get('content', '')}"
        )
    return "\n---\n".join(parts)
