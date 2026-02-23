"""Format tool results as human-readable text for the TUI and agent (no raw JSON)."""

from __future__ import annotations

from typing import Any


def _fmt_val(v: Any, nested: bool = False) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, list):
        if not v:
            return ""
        if nested or len(v) > 5:
            return f"{len(v)} items"
        return ", ".join(_fmt_val(x, nested=True) for x in v[:5])
    if isinstance(v, dict):
        if nested:
            return "{" + ", ".join(f"{k}: {_fmt_val(x, True)}" for k, x in list(v.items())[:3]) + "}"
        return _format_result(v)
    return str(v)


def _format_result(result: Any) -> str:
    """Convert a single value to readable text (no JSON)."""
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    if isinstance(result, dict) and result.get("status") == "ok" and "output" in result:
        return str(result["output"])
    if isinstance(result, list):
        if not result:
            return "No items."
        lines = []
        for i, item in enumerate(result, 1):
            if isinstance(item, dict):
                # List of dicts: format by known shapes (PRs, issues, etc.)
                if "number" in item and "title" in item:
                    url = item.get("html_url", "")
                    state = item.get("state", "")
                    user = item.get("user", "")
                    part = f"  {i}. #{item.get('number')} — {item.get('title', '')}"
                    if state or user:
                        part += f" ({state})" if state else ""
                        part += f" by {user}" if user else ""
                    if url:
                        part += f"\n    {url}"
                    lines.append(part)
                elif "full_name" in item or "name" in item:
                    name = item.get("full_name") or item.get("name", "")
                    url = item.get("html_url", "")
                    branch = item.get("default_branch", "")
                    extra = f" (default: {branch})" if branch else ""
                    lines.append(f"  {i}. {name}{extra}\n    {url}" if url else f"  {i}. {name}{extra}")
                elif "id" in item and "name" in item:
                    lines.append(f"  {i}. {item.get('name', '')} (id: {item.get('id')})\n    {item.get('html_url', '')}")
                else:
                    parts = [f"{k}: {_fmt_val(v)}" for k, v in item.items() if v not in (None, "")]
                    lines.append(f"  {i}. " + " | ".join(parts[:6]))
            else:
                lines.append(f"  {i}. {_fmt_val(item)}")
        return "\n".join(lines)
    if isinstance(result, dict):
        # Status/message pattern (errors, success)
        status = result.get("status")
        message = result.get("message")
        if message and status in ("error", "no_failing_prs", "not_failing", "no_logs", "no_fix"):
            out = [f"**{status}** — {message}"]
            for k in ("stage", "pr_number", "workflow_run_id"):
                if result.get(k) is not None:
                    out.append(f"  {k}: {result[k]}")
            return "\n".join(out)
        if status and message and status not in ("error",):
            return f"{status}: {message}"
        # README / content
        if "content" in result:
            content = result.get("content", "")
            path = result.get("path", "README")
            head = f"**{path}**\n"
            if isinstance(content, str) and len(content) > 8000:
                head += content[:8000] + "\n\n... (truncated)"
            else:
                head += content
            return head
        # Created issue/PR (include repo so user knows where to look; link is the exact URL to open)
        if "number" in result and "title" in result and "html_url" in result and result.get("state") == "open":
            url = result["html_url"]
            repo = result.get("repo_full_name", "")
            if "/issues/" in url:
                kind = "Issue"
            elif "/pull/" in url:
                kind = "Pull request"
            else:
                kind = "Item"
            where = f" in {repo}" if repo else ""
            return f"{kind} created{where}: #{result['number']} — {result['title']}\nOpen this link in your browser: {url}"
        # PR / issue detail
        if "number" in result and "title" in result:
            lines = [f"#{result.get('number')} — {result.get('title', '')}"]
            for k in ("state", "user", "head", "base", "head_sha", "body", "html_url"):
                v = result.get(k)
                if v is not None and k != "body":
                    lines.append(f"  {k}: {v}")
            if result.get("body"):
                body = result["body"] or ""
                lines.append("  body: " + (body[:500] + "..." if len(body) > 500 else body))
            files_changed = result.get("files_changed") or []
            if files_changed:
                lines.append("  files_changed:")
                for f in files_changed[:15]:
                    name = f.get("filename", "")
                    add = f.get("additions", 0)
                    dele = f.get("deletions", 0)
                    lines.append(f"    - {name} (+{add}/-{dele})")
                if len(files_changed) > 15:
                    lines.append(f"    ... and {len(files_changed) - 15} more")
            ci_checks = result.get("ci_checks") or []
            if ci_checks:
                lines.append("  ci_checks:")
                for c in ci_checks[:10]:
                    name = c.get("name", "")
                    concl = c.get("conclusion", "")
                    lines.append(f"    - {name}: {concl}")
            if result.get("html_url"):
                lines.append(f"  {result['html_url']}")
            return "\n".join(lines)
        # Generic dict: key-value lines
        lines = []
        for k, v in result.items():
            if v is None or v == "":
                continue
            if isinstance(v, (list, dict)) and len(str(v)) > 400:
                lines.append(f"  {k}: (see below)")
                lines.append(_format_result(v))
            else:
                lines.append(f"  {k}: {_fmt_val(v)}")
        return "\n".join(lines) if lines else str(result)
    return str(result)


def format_tool_result(result: Any) -> str:
    """Return tool result as human-readable text for display in TUI and agent.
    Never returns raw JSON.
    """
    if isinstance(result, str):
        return result
    return _format_result(result)
