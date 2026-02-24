"""Format a repository analysis result as readable, markdown-enriched text.

Each finding is rendered with a code snippet pulled directly from the source
file so the output is immediately actionable without needing to open an editor.
"""

from __future__ import annotations

import os

_EXT_TO_LANG: dict[str, str] = {
    ".py":  "python",
    ".rs":  "rust",
    ".ts":  "typescript",
    ".tsx": "tsx",
    ".js":  "javascript",
    ".jsx": "jsx",
    ".go":  "go",
    ".java":"java",
    ".rb":  "ruby",
    ".cs":  "csharp",
    ".cpp": "cpp",
    ".c":   "c",
    ".h":   "c",
    ".hpp": "cpp",
}


def _read_line(path: str, line_num: int) -> str | None:
    """Return the content of 1-based *line_num* in *path*, or ``None``."""
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for i, line in enumerate(fh, start=1):
                if i == line_num:
                    return line.rstrip()
                if i > line_num:
                    break
    except OSError:
        pass
    return None


def _lang(path: str) -> str:
    return _EXT_TO_LANG.get(os.path.splitext(path)[1].lower(), "text")


def _format_finding(root: str, item: dict, include_snippet: bool = True) -> str:  # noqa: ARG001
    filepath = item.get("file", "")
    line = item.get("line", 0)
    message = item.get("message", "")
    parts = [f"- **{os.path.basename(filepath)}:{line}** — {message}"]
    if include_snippet and filepath and line:
        content = _read_line(filepath, int(line))
        if content:
            parts.append(f"  ```{_lang(filepath)}\n  {content}\n  ```")
    return "\n".join(parts)


def format_analysis_report(
    root: str,
    static_findings: dict[str, list[dict]],
    architecture: dict,
    ai_result: dict,
) -> str:
    """Render a full analysis report as a markdown string.

    Sections: Architecture → Static findings → AI analysis.
    """
    sections: list[str] = []

    # ── Architecture ──────────────────────────────────────────────────────────
    arch_lines = ["## Architecture", ""]
    arch_lines.append(
        f"- **Top-level dirs:** {', '.join(architecture.get('top_level_dirs', []) or ['(none)'])}"
    )
    arch_lines.append(f"- **Code files:** {architecture.get('code_file_count', 0)}")
    arch_lines.append(f"- **Total lines:** {architecture.get('total_loc', 0)}")

    lang_break = architecture.get("language_breakdown") or {}
    if lang_break:
        arch_lines.append(
            f"- **Languages:** {', '.join(f'{k} ({v})' for k, v in sorted(lang_break.items()))}"
        )
    frameworks = architecture.get("frameworks") or []
    if frameworks:
        arch_lines.append(f"- **Frameworks detected:** {', '.join(frameworks)}")

    risks = architecture.get("risks") or []
    if risks:
        arch_lines.append("- **Risks:**")
        arch_lines.extend(f"  - {r}" for r in risks)

    for note in (architecture.get("architecture_notes") or []):
        arch_lines.append(f"- {note}")

    sections.append("\n".join(arch_lines))

    # ── Static findings ───────────────────────────────────────────────────────
    finding_lines = ["## Static findings", ""]
    if not static_findings:
        finding_lines.append("No issues found.")
    else:
        for category, items in static_findings.items():
            if category.endswith("_total"):
                continue
            finding_lines.append(f"### {category.replace('_', ' ').title()}")
            finding_lines.append("")
            capped = (items or [])[:15]
            for item in capped:
                finding_lines.append(_format_finding(root, item))
                finding_lines.append("")
            if len(items or []) > 15:
                finding_lines.append(f"  _… and {len(items) - 15} more._")
                finding_lines.append("")

    sections.append("\n".join(finding_lines))

    # ── AI analysis ───────────────────────────────────────────────────────────
    ai_message = (
        (ai_result.get("message") if isinstance(ai_result, dict) else "")
        or (
            ai_result.get("message", "AI analysis not run (no API key).")
            if isinstance(ai_result, dict) and ai_result.get("enabled") is False
            else "No AI summary returned."
        )
    )
    sections.append("\n".join(["## AI analysis", "", ai_message.strip()]))

    return "\n\n".join(sections).strip()
