from __future__ import annotations

import os
from collections import Counter

from .static_analysis import _iter_code_files, file_stats


def summarize_architecture(root: str) -> dict:
    top_level_dirs = []
    for entry in os.listdir(root):
        if entry.startswith("."):
            continue
        full = os.path.join(root, entry)
        if os.path.isdir(full):
            top_level_dirs.append(entry)

    file_count = 0
    total_lines = 0
    for path in _iter_code_files(root):
        file_count += 1
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                total_lines += sum(1 for _ in f)
        except OSError:
            pass

    language_breakdown = file_stats(root)

    module_depths = Counter()
    for path in _iter_code_files(root):
        rel = os.path.relpath(path, root)
        depth = rel.count(os.sep)
        module_depths[depth] += 1

    return {
        "top_level_dirs": sorted(top_level_dirs),
        "code_file_count": file_count,
        "total_loc": total_lines,
        "language_breakdown": language_breakdown,
        "module_depth_distribution": dict(module_depths),
        "architecture_notes": _insights(language_breakdown, module_depths),
    }


def _insights(language_breakdown: dict, module_depths: Counter) -> list[str]:
    notes: list[str] = []
    if not language_breakdown:
        return ["No code files found for architecture insights"]

    if sum(module_depths.values()) > 0:
        deep = sum(count for depth, count in module_depths.items() if depth >= 4)
        if deep > 0:
            notes.append("Deep module nesting detected; consider simplifying package structure")

    if len(language_breakdown) > 5:
        notes.append("Many languages detected; ensure ownership boundaries are clear")

    if ".py" in language_breakdown and ".ts" in language_breakdown:
        notes.append("Mixed backend/frontend stack detected; consider enforcing API boundaries")

    return notes
