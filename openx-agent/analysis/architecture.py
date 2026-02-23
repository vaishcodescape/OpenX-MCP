from __future__ import annotations

import json
import os
from collections import Counter

from .static_analysis import _iter_code_files

# Max file size (bytes) to flag as "large file" risk
_LARGE_FILE_BYTES = 500_000
# Test dir/file patterns
_TEST_DIRS = ("test", "tests", "__tests__", "spec", "specs")
_TEST_PREFIXES = ("test_", "test-", "_test", "spec_", ".test.", ".spec.")


def detect_frameworks(root: str) -> list[str]:
    """Detect frameworks from lockfiles, config files, and directory layout."""
    frameworks: list[str] = []
    for entry in os.listdir(root):
        if entry.startswith("."):
            continue
        path = os.path.join(root, entry)
        if not os.path.isfile(path):
            continue
        low = entry.lower()
        if low == "package.json":
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    data = json.load(f)
                deps = {**(data.get("dependencies") or {}), **(data.get("devDependencies") or {})}
                if "react" in deps or "next" in str(deps):
                    frameworks.append("React/Next.js")
                elif "vue" in deps or "nuxt" in str(deps):
                    frameworks.append("Vue/Nuxt")
                elif "express" in deps:
                    frameworks.append("Express")
                else:
                    frameworks.append("Node.js")
            except Exception:
                frameworks.append("Node.js")
        elif low == "pyproject.toml":
            frameworks.append("Python (pyproject)")
        elif low == "requirements.txt" or low == "setup.py":
            frameworks.append("Python")
        elif low == "go.mod":
            frameworks.append("Go")
        elif low == "cargo.toml":
            frameworks.append("Rust")
        elif low == "pom.xml" or low == "build.gradle" or low == "build.gradle.kts":
            frameworks.append("Java/JVM")
        elif low == "dockerfile" or entry.lower().startswith("dockerfile"):
            frameworks.append("Docker")
    if not frameworks:
        for path in _iter_code_files(root):
            ext = os.path.splitext(path)[1].lower()
            if ext == ".py":
                frameworks.append("Python")
                break
            if ext in (".ts", ".tsx", ".js", ".jsx"):
                frameworks.append("TypeScript/JavaScript")
                break
    return list(dict.fromkeys(frameworks))  # preserve order, no dupes


def detect_risks(root: str) -> list[str]:
    """Detect risks: large files, no tests, etc."""
    risks: list[str] = []
    large_files: list[tuple[str, int]] = []
    has_test_files = False
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__", ".venv", "venv")]
        rel_base = os.path.relpath(base, root)
        if any(t in rel_base.split(os.sep) for t in _TEST_DIRS):
            has_test_files = True
        for name in files:
            path = os.path.join(base, name)
            try:
                size = os.path.getsize(path)
                if size > _LARGE_FILE_BYTES:
                    large_files.append((os.path.relpath(path, root), size))
            except OSError:
                pass
            if any(name.lower().startswith(p) or p in name.lower() for p in _TEST_PREFIXES):
                has_test_files = True
    if not has_test_files:
        risks.append("No obvious test directory or test files detected")
    large_files.sort(key=lambda x: -x[1])
    for rel, size in large_files[:5]:
        risks.append(f"Large file: {rel} ({size // 1024} KB)")
    return risks


def summarize_architecture(root: str) -> dict:
    top_level_dirs = []
    for entry in os.listdir(root):
        if entry.startswith("."):
            continue

        full = os.path.join(root, entry)
        if os.path.isdir(full):
            top_level_dirs.append(entry)

    # Single pass over code files: count lines, extensions, and depths (avoids 3x os.walk).
    file_count = 0
    total_lines = 0
    language_breakdown = Counter()
    module_depths = Counter()
    for path in _iter_code_files(root):
        file_count += 1
        rel = os.path.relpath(path, root)
        module_depths[rel.count(os.sep)] += 1
        language_breakdown[os.path.splitext(path)[1].lower()] += 1
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                total_lines += sum(1 for _ in f)
        except OSError:
            pass

    language_breakdown = dict(language_breakdown)
    frameworks = detect_frameworks(root)
    risks = detect_risks(root)

    notes = _insights(language_breakdown, module_depths)
    notes.extend(risks)

    return {
        "top_level_dirs": sorted(top_level_dirs),
        "code_file_count": file_count,
        "total_loc": total_lines,
        "language_breakdown": language_breakdown,
        "frameworks": frameworks,
        "risks": risks,
        "module_depth_distribution": dict(module_depths),
        "architecture_notes": notes,
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
