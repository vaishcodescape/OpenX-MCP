"""RAG MCP tools — index GitHub repos and search the knowledge base."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from ..rag import index_repo as _index_repo, search_knowledge

server = FastMCP("OpenX RAG Tools")


@server.tool
def index_repo(repo_full_name: str) -> Any:
    """Index a GitHub repository into the knowledge base.

    Fetches repo metadata, open PRs, README, and workflows,
    then builds a keyword index for fast retrieval.
    """
    return _index_repo(repo_full_name)


@server.tool
def search(query: str) -> str:
    """Search the indexed knowledge base by keywords.

    Returns relevant information about repositories, PRs,
    README content, and CI/CD workflows.  Index a repo first
    with index_repo if no results are found.
    """
    return search_knowledge(query)
