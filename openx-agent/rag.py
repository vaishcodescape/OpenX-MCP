"""RAG pipeline — fetch GitHub data, embed, store in FAISS, retrieve."""

from __future__ import annotations
 
import logging
import os
from typing import Any

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.tools import tool

from .config import settings
from .github_client import (
    get_repo,
    list_open_prs,
    list_repos,
    list_workflows,
)
from .llm import get_embeddings

logger = logging.getLogger(__name__)

# In-memory cache of per-repo FAISS stores.
_STORES: dict[str, FAISS] = {}

# Disk cache directory.
_CACHE_DIR = os.path.join(os.path.expanduser("~"), ".openx_cache", "faiss")


# ---------------------------------------------------------------------------
# Document loaders — turn GitHub API data into LangChain Documents
# ---------------------------------------------------------------------------


def _load_repo_metadata(repo_full_name: str) -> list[Document]:
    """Fetch high-level repo info."""
    docs: list[Document] = []
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
        docs.append(
            Document(
                page_content=text,
                metadata={
                    "source": "github",
                    "repo": repo_full_name,
                    "type": "repo_metadata",
                    "url": repo.html_url,
                },
            )
        )
    except Exception:
        logger.exception("Failed to load repo metadata for %s", repo_full_name)
    return docs


def _load_pull_requests(repo_full_name: str) -> list[Document]:
    """Fetch open PRs as documents."""
    docs: list[Document] = []
    try:
        prs = list_open_prs(repo_full_name)
        for pr in prs[:20]:  # cap to avoid huge payloads
            text = (
                f"Pull Request #{pr['number']}: {pr['title']}\n"
                f"Author: {pr['user']}\n"
                f"State: {pr['state']}\n"
                f"URL: {pr['html_url']}"
            )
            docs.append(
                Document(
                    page_content=text,
                    metadata={
                        "source": "github",
                        "repo": repo_full_name,
                        "type": "pull_request",
                        "pr_number": pr["number"],
                        "url": pr["html_url"],
                    },
                )
            )
    except Exception:
        logger.exception("Failed to load PRs for %s", repo_full_name)
    return docs


def _load_readme(repo_full_name: str) -> list[Document]:
    """Fetch the README as a document."""
    docs: list[Document] = []
    try:
        repo = get_repo(repo_full_name)
        readme = repo.get_readme()
        import base64

        content = base64.b64decode(readme.content).decode("utf-8", errors="replace")
        # Truncate very long READMEs.
        if len(content) > 8_000:
            content = content[:8_000] + "\n\n... [truncated]"
        docs.append(
            Document(
                page_content=content,
                metadata={
                    "source": "github",
                    "repo": repo_full_name,
                    "type": "readme",
                    "url": readme.html_url,
                },
            )
        )
    except Exception:
        logger.exception("Failed to load README for %s", repo_full_name)
    return docs


def _load_workflows(repo_full_name: str) -> list[Document]:
    """Fetch CI/CD workflows as documents."""
    docs: list[Document] = []
    try:
        wfs = list_workflows(repo_full_name)
        for wf in wfs:
            text = (
                f"Workflow: {wf['name']}\n"
                f"Path: {wf['path']}\n"
                f"State: {wf['state']}\n"
                f"URL: {wf['html_url']}"
            )
            docs.append(
                Document(
                    page_content=text,
                    metadata={
                        "source": "github",
                        "repo": repo_full_name,
                        "type": "workflow",
                        "url": wf["html_url"],
                    },
                )
            )
    except Exception:
        logger.exception("Failed to load workflows for %s", repo_full_name)
    return docs


def _load_repo_listing() -> list[Document]:
    """Fetch all repos for the authenticated user."""
    docs: list[Document] = []
    try:
        repos = list_repos()
        for r in repos:
            text = (
                f"Repository: {r['full_name']}\n"
                f"Private: {r['private']}\n"
                f"Default branch: {r['default_branch']}\n"
                f"URL: {r['html_url']}"
            )
            docs.append(
                Document(
                    page_content=text,
                    metadata={
                        "source": "github",
                        "repo": r["full_name"],
                        "type": "repo_listing",
                        "url": r["html_url"],
                    },
                )
            )
    except Exception:
        logger.exception("Failed to list repos")
    return docs


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------


def index_repo(repo_full_name: str) -> dict[str, Any]:
    """Fetch GitHub data for a repo and build a FAISS index."""
    from .progress import clear_progress, set_progress

    op = "index"
    logger.info("Indexing repo: %s", repo_full_name)
    set_progress(op, "fetch", "Fetching repo metadata and content...", {"repo": repo_full_name})

    docs: list[Document] = []
    docs.extend(_load_repo_metadata(repo_full_name))
    docs.extend(_load_pull_requests(repo_full_name))
    set_progress(op, "fetch", f"Loaded {len(docs)} docs, loading README and workflows...", {"repo": repo_full_name})
    docs.extend(_load_readme(repo_full_name))
    docs.extend(_load_workflows(repo_full_name))
    docs.extend(_load_repo_listing())

    if not docs:
        clear_progress(op)
        return {"status": "error", "message": "No documents fetched."}

    set_progress(op, "embed", "Building embeddings and FAISS index...", {"document_count": len(docs)})
    embeddings = get_embeddings()
    store = FAISS.from_documents(docs, embeddings)
    _STORES[repo_full_name] = store

    set_progress(op, "save", "Saving index to disk...", {})
    os.makedirs(_CACHE_DIR, exist_ok=True)
    store_path = os.path.join(_CACHE_DIR, repo_full_name.replace("/", "_"))
    store.save_local(store_path)

    clear_progress(op)
    logger.info("Indexed %d documents for %s", len(docs), repo_full_name)
    return {
        "status": "indexed",
        "repo": repo_full_name,
        "document_count": len(docs),
    }


def _get_store(repo_full_name: str) -> FAISS | None:
    """Get the FAISS store for a repo, loading from disk if needed."""
    if repo_full_name in _STORES:
        return _STORES[repo_full_name]

    store_path = os.path.join(_CACHE_DIR, repo_full_name.replace("/", "_"))
    if os.path.exists(store_path):
        embeddings = get_embeddings()
        store = FAISS.load_local(
            store_path,
            embeddings,
            allow_dangerous_deserialization=True,
        )
        _STORES[repo_full_name] = store
        return store

    return None


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


def query_repo(repo_full_name: str, question: str, k: int = 4) -> list[dict[str, Any]]:
    """Query the FAISS index for a repo. Auto-indexes if needed."""
    store = _get_store(repo_full_name)
    if store is None:
        # Auto-index on first query.
        index_repo(repo_full_name)
        store = _get_store(repo_full_name)

    if store is None:
        return [{"error": f"No index available for {repo_full_name}"}]

    results = store.similarity_search(question, k=k)
    return [
        {
            "content": doc.page_content,
            "metadata": doc.metadata,
        }
        for doc in results
    ]


# ---------------------------------------------------------------------------
# LangChain tool wrapper (used by the agent)
# ---------------------------------------------------------------------------


@tool
def search_github_knowledge(query: str) -> str:
    """Search the indexed GitHub knowledge base for relevant information.

    Use this tool when you need to look up details about repositories,
    pull requests, README documentation, or CI/CD workflows. The knowledge
    base is populated by indexing GitHub repos.

    Args:
        query: Natural language question about the repository data.
    """
    # Try all indexed repos.
    all_results: list[dict[str, Any]] = []
    for repo_name in list(_STORES.keys()):
        all_results.extend(query_repo(repo_name, query, k=3))

    if not all_results:
        return "No indexed repositories found. Use 'index <repo_full_name>' first."

    parts: list[str] = []
    for r in all_results[:6]:
        meta = r.get("metadata", {})
        parts.append(
            f"[{meta.get('type', 'unknown')}] ({meta.get('repo', '?')})\n"
            f"{r.get('content', '')}"
        )
    return "\n---\n".join(parts)
