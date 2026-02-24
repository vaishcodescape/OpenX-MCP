"""Format raw tool results as human-readable text for the TUI and agent.

The public entry point is `format_tool_result`. It never emits raw JSON.
"""

from __future__ import annotations

from typing import Any


def _fmt_scalar(v: Any, nested: bool = False) -> str:
    """Convert a scalar (or small container) to a display string."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, list):
        if not v:
            return ""
        if nested or len(v) > 5:
            return f"{len(v)} items"
        return ", ".join(_fmt_scalar(x, nested=True) for x in v[:5])
    if isinstance(v, dict):
        if nested:
            pairs = ", ".join(f"{k}: {_fmt_scalar(x, True)}" for k, x in list(v.items())[:3])
            return "{" + pairs + "}"
        return _fmt_dict(v)
    return str(v)


def _fmt_list_item(i: int, item: Any) -> str:
    """Format one element of a list result."""
    if not isinstance(item, dict):
        return f"  {i}. {_fmt_scalar(item)}"

    # PR / issue shape: has number + title.
    if "number" in item and "title" in item:
        number = item.get("number")
        title  = item.get("title", "")
        state  = item.get("state", "")
        user   = item.get("user", "")
        url    = item.get("html_url", "")
        parts  = [f"  {i}. #{number} — {title}"]
        if state:
            parts[0] += f" ({state})"
        if user:
            parts[0] += f" by {user}"
        if url:
            parts.append(f"    {url}")
        return "\n".join(parts)

    # Repository shape: has full_name or name.
    if "full_name" in item or ("name" in item and "html_url" in item):
        name   = item.get("full_name") or item.get("name", "")
        url    = item.get("html_url", "")
        branch = item.get("default_branch", "")
        suffix = f" (default: {branch})" if branch else ""
        line   = f"  {i}. {name}{suffix}"
        return f"{line}\n    {url}" if url else line

    # Workflow/generic id+name shape.
    if "id" in item and "name" in item:
        return f"  {i}. {item['name']} (id: {item['id']})\n    {item.get('html_url', '')}"

    # Fallback: key=value pairs (skip empty values, cap at 6 pairs).
    pairs = " | ".join(
        f"{k}: {_fmt_scalar(v)}" for k, v in item.items()
        if v not in (None, "") and not isinstance(v, (list, dict))
    )
    return f"  {i}. {pairs or str(item)}"


def _fmt_dict(result: dict) -> str:
    """Format a dict result, dispatching on well-known shapes."""
    status  = result.get("status")
    message = result.get("message")

    # Error / terminal-state messages.
    _ERROR_STATUSES = {"error", "no_failing_prs", "not_failing", "no_logs", "no_fix"}
    if message and status in _ERROR_STATUSES:
        lines = [f"**{status}** — {message}"]
        for k in ("stage", "pr_number", "workflow_run_id"):
            if result.get(k) is not None:
                lines.append(f"  {k}: {result[k]}")
        return "\n".join(lines)

    if status and message:
        return f"{status}: {message}"

    # README / file content.
    if "content" in result:
        path    = result.get("path", "README")
        content = result.get("content", "")
        header  = f"**{path}**\n"
        if isinstance(content, str) and len(content) > 8_000:
            return header + content[:8_000] + "\n\n... (truncated)"
        return header + content

    # Newly created issue or PR.
    if "number" in result and "title" in result and "html_url" in result and result.get("state") == "open":
        url  = result["html_url"]
        repo = result.get("repo_full_name", "")
        kind = "Issue" if "/issues/" in url else ("Pull request" if "/pull/" in url else "Item")
        where = f" in {repo}" if repo else ""
        return (
            f"{kind} created{where}: #{result['number']} — {result['title']}\n"
            f"Open this link in your browser: {url}"
        )

    # PR / issue detail view.
    if "number" in result and "title" in result:
        lines = [f"#{result['number']} — {result.get('title', '')}"]
        for k in ("state", "user", "head", "base", "head_sha", "html_url"):
            if result.get(k) is not None:
                lines.append(f"  {k}: {result[k]}")
        if body := result.get("body"):
            lines.append(f"  body: {body[:500]}{'...' if len(body) > 500 else ''}")
        if changed := result.get("files_changed") or []:
            lines.append("  files_changed:")
            for f in changed[:15]:
                lines.append(f"    - {f.get('filename', '')} (+{f.get('additions', 0)}/-{f.get('deletions', 0)})")
            if len(changed) > 15:
                lines.append(f"    ... and {len(changed) - 15} more")
        if checks := result.get("ci_checks") or []:
            lines.append("  ci_checks:")
            for c in checks[:10]:
                lines.append(f"    - {c.get('name', '')}: {c.get('conclusion', '')}")
        return "\n".join(lines)

    # Generic dict: key → formatted value, skip empty, expand nested containers.
    lines: list[str] = []
    for k, v in result.items():
        if v is None or v == "":
            continue
        if isinstance(v, (list, dict)) and len(str(v)) > 400:
            lines.append(f"  {k}: (see below)")
            lines.append(_fmt_dict(v) if isinstance(v, dict) else format_tool_result(v))
        else:
            lines.append(f"  {k}: {_fmt_scalar(v)}")
    return "\n".join(lines) if lines else str(result)


def format_tool_result(result: Any) -> str:
    """Return *result* as a human-readable string.  Never emits raw JSON."""
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    if isinstance(result, list):
        if not result:
            return "No items."
        return "\n".join(_fmt_list_item(i, item) for i, item in enumerate(result, 1))
    if isinstance(result, dict):
        return _fmt_dict(result)
    return str(result)
