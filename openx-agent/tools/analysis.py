"""Analysis MCP tools — static analysis, architecture, and AI code review."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from ..analysis.ai_analysis import analyze_with_ai
from ..analysis.architecture import summarize_architecture
from ..analysis.format_report import format_analysis_report
from ..analysis.static_analysis import analyze_static
from ..config import config_settings

def analyze_repo(path: str = "") -> Any:
    """Run full code analysis: static findings, architecture summary, and AI review.

    Detects bugs, performance issues, duplicate code, AI-generated patterns,
    and provides actionable recommendations. Omit path to analyze the workspace root.
    """
    root = path or config_settings.workspace_root
    static_findings = analyze_static(root)
    arch = summarize_architecture(root)
    ai = analyze_with_ai({"static_findings": static_findings, "architecture": arch})
    return format_analysis_report(root, static_findings, arch, ai)

def register(mcp: FastMCP) -> None:
    mcp.add_tool(analyze_repo, name="analysis_analyze_repo")
