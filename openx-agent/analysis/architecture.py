"""Repository architecture summary: frameworks, risks, language breakdown."""

from __future__ import annotations

import json
import os
from collections import Counter

from .static_analysis import SKIP_DIRS, _iter_code_files

# Flags a file as "large" when it exceeds this size.
_LARGE_FILE_BYTES = 500_000

_TEST_DIRS: frozenset[str] = frozenset({"test", "tests", "__tests__", "spec", "specs"})
_TEST_NAME_FRAGMENTS: tuple[str, ...] = ("test_", "test-", "_test", "spec_", ".test.", ".spec.")

# Directories that should never be walked when scanning for tests / large files.
_WALK_SKIP: frozenset[str] = frozenset({".git", "node_modules", "__pycache__", ".venv", "venv"})


def detect_frameworks(root: str) -> list[str]:
    """Detect stacks from lock-files and config files in *root*."""
    frameworks: list[str] = []

    for entry in os.listdir(root):
        if entry.startswith("."):
            continue
        path = os.path.join(root, entry)
        if not os.path.isfile(path):
            continue
        lower = entry.lower()

        if lower == "package.json":
            try:
                with open(path, encoding="utf-8", errors="ignore") as fh:
                    pkg = json.load(fh)
                deps = {**(pkg.get("dependencies") or {}), **(pkg.get("devDependencies") or {})}
                dep_str = str(deps)
                if "react" in deps or "next" in dep_str:
                    frameworks.append("React/Next.js")
                elif "vue" in deps or "nuxt" in dep_str:
                    frameworks.append("Vue/Nuxt")
                elif "express" in deps:
                    frameworks.append("Express")
                else:
                    frameworks.append("Node.js")
            except Exception:
                frameworks.append("Node.js")
        elif lower == "pyproject.toml":
            frameworks.append("Python (pyproject)")
        elif lower in ("requirements.txt", "setup.py"):
            frameworks.append("Python")
        elif lower == "go.mod":
            frameworks.append("Go")
        elif lower == "cargo.toml":
            frameworks.append("Rust")
        elif lower in ("pom.xml", "build.gradle", "build.gradle.kts"):
            frameworks.append("Java/JVM")
        elif lower.startswith("dockerfile"):
            frameworks.append("Docker")

    if not frameworks:
        # Fall back to first recognised extension found while walking.
        for path in _iter_code_files(root):
            ext = os.path.splitext(path)[1].lower()
            if ext == ".py":
                frameworks.append("Python")
                break
            if ext in (".ts", ".tsx", ".js", ".jsx"):
                frameworks.append("TypeScript/JavaScript")
                break

    # Preserve discovery order, remove duplicates.
    return list(dict.fromkeys(frameworks))


def detect_risks(root: str) -> list[str]:
    """Return a list of risk descriptions (large files, missing tests, etc.)."""
    risks: list[str] = []
    large_files: list[tuple[str, int]] = []
    has_tests = False

    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in _WALK_SKIP]
        rel_base = os.path.relpath(base, root)
        if any(part in _TEST_DIRS for part in rel_base.split(os.sep)):
            has_tests = True

        for name in files:
            path = os.path.join(base, name)
            lower = name.lower()
            if any(lower.startswith(frag) or frag in lower for frag in _TEST_NAME_FRAGMENTS):
                has_tests = True
            try:
                size = os.path.getsize(path)
                if size > _LARGE_FILE_BYTES:
                    large_files.append((os.path.relpath(path, root), size))
            except OSError:
                pass

    if not has_tests:
        risks.append("No obvious test directory or test files detected")

    for rel, size in sorted(large_files, key=lambda x: -x[1])[:5]:
        risks.append(f"Large file: {rel} ({size // 1024} KB)")

    return risks


def _architecture_insights(language_breakdown: dict[str, int], module_depths: Counter[int]) -> list[str]:
    if not language_breakdown:
        return ["No code files found for architecture insights"]

    notes: list[str] = []
    if sum(module_depths.values()) > 0:
        deep_count = sum(n for depth, n in module_depths.items() if depth >= 4)
        if deep_count:
            notes.append("Deep module nesting detected; consider simplifying package structure")

    if len(language_breakdown) > 5:
        notes.append("Many languages detected; ensure ownership boundaries are clear")

    if ".py" in language_breakdown and ".ts" in language_breakdown:
        notes.append("Mixed backend/frontend stack detected; consider enforcing API boundaries")

    return notes


def summarize_architecture(root: str) -> dict:
    """Return a summary dict covering dirs, LOC, languages, frameworks, and risks."""
    top_level_dirs = sorted(
        e for e in os.listdir(root)
        if not e.startswith(".") and os.path.isdir(os.path.join(root, e))
    )

    # Single code-file walk: count lines, extensions, and nesting depth.
    file_count = 0
    total_lines = 0
    language_breakdown: Counter[str] = Counter()
    module_depths: Counter[int] = Counter()

    for path in _iter_code_files(root):
        file_count += 1
        rel = os.path.relpath(path, root)
        module_depths[rel.count(os.sep)] += 1
        language_breakdown[os.path.splitext(path)[1].lower()] += 1
        try:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                total_lines += sum(1 for _ in fh)
        except OSError:
            pass

    frameworks = detect_frameworks(root)
    risks = detect_risks(root)
    notes = _architecture_insights(dict(language_breakdown), module_depths)
    notes.extend(risks)

    return {
        "top_level_dirs": top_level_dirs,
        "code_file_count": file_count,
        "total_loc": total_lines,
        "language_breakdown": dict(language_breakdown),
        "frameworks": frameworks,
        "risks": risks,
        "module_depth_distribution": dict(module_depths),
        "architecture_notes": notes,
    }
