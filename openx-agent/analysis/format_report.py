"""Format repository analysis as readable text with markdown-style code blocks for display/coloring."""

from __future__ import annotations

import os


_EXT_TO_LANG: dict[str, str] = {
    ".py": "python",
    ".rs": "rust",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "jsx",
    ".go": "go",
    ".java": "java",
    ".rb": "ruby",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
}


def _read_line(path: str, line_num: int) -> str | None:
    """Return the content of the given 1-based line number, or None."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f, start=1):
                if i == line_num:
                    return line.rstrip()
                if i > line_num:
                    break
    except OSError:
        pass
    return None


def _lang(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return _EXT_TO_LANG.get(ext, "text")


def _format_finding(root: str, item: dict, include_snippet: bool = True) -> str:
    filepath = item.get("file", "")
    line = item.get("line", 0)
    message = item.get("message", "")
    parts = [f"- **{os.path.basename(filepath)}:{line}** — {message}"]
    if include_snippet and filepath and line:
        content = _read_line(filepath, int(line))
        if content:
            lang = _lang(filepath)
            parts.append(f"  ```{lang}\n  {content}\n  ```")
    return "\n".join(parts)


def format_analysis_report(
    root: str,
    static_findings: dict[str, list[dict]],
    architecture: dict,
    ai_result: dict,
) -> str:
    """Produce a single text report with sections and markdown code blocks (for LLM/colored display)."""
    lines: list[str] = []

    # ---- Architecture ----
    lines.append("## Architecture")
    lines.append("")
    arch = architecture
    lines.append(f"- **Top-level dirs:** {', '.join(arch.get('top_level_dirs', []) or ['(none)'])}")
    lines.append(f"- **Code files:** {arch.get('code_file_count', 0)}")
    lines.append(f"- **Total lines:** {arch.get('total_loc', 0)}")
    lang_break = arch.get("language_breakdown") or {}
    if lang_break:
        lines.append(f"- **Languages:** {', '.join(f'{k} ({v})' for k, v in sorted(lang_break.items()))}")
    frameworks = arch.get("frameworks") or []
    if frameworks:
        lines.append(f"- **Frameworks detected:** {', '.join(frameworks)}")
    risks = arch.get("risks") or []
    if risks:
        lines.append("- **Risks:**")
        for r in risks:
            lines.append(f"  - {r}")
    notes = arch.get("architecture_notes") or []
    for note in notes:
        lines.append(f"- {note}")
    lines.append("")

    # ---- Static findings ----
    lines.append("## Static findings")
    lines.append("")
    if not static_findings:
        lines.append("No issues found.")
    else:
        for category, items in static_findings.items():
            if category.endswith("_total"):
                continue
            title = category.replace("_", " ").title()
            lines.append(f"### {title}")
            lines.append("")
            item_list = items or []
            for i, item in enumerate(item_list[:15]):  # cap for readability
                lines.append(_format_finding(root, item))
                lines.append("")
            if len(item_list) > 15:
                lines.append(f"  _… and {len(item_list) - 15} more._")
                lines.append("")
    lines.append("")

    # ---- AI analysis ----
    lines.append("## AI analysis")
    lines.append("")
    ai_message = ai_result.get("message", "") if isinstance(ai_result, dict) else ""
    if not ai_message:
        if ai_result.get("enabled") is False:
            ai_message = ai_result.get("message", "AI analysis not run (e.g. no API key).")
        else:
            ai_message = "No AI summary returned."
    # Ensure the AI message is plain text; if it contains code, it's already in natural language.
    lines.append(ai_message.strip())
    lines.append("")

    return "\n".join(lines).strip()
