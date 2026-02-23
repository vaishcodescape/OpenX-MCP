from __future__ import annotations

import base64
import difflib
import io
import json
import re
import threading
import zipfile
from typing import Any
from urllib.parse import quote

import httpx

from .config import settings
from . import cache as _cache
from . import gh_cli

# CI check conclusions that indicate failure (single source of truth)
_CHECK_CONCLUSION_FAILED = frozenset({
    "failure", "timed_out", "cancelled", "action_required", "startup_failure", "stale",
})


def _load_github() -> Any:
    try:
        from github import Github  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "PyGithub is not installed. Run `pip install -r requirements.txt`."
        ) from exc
    return Github


_github_client: Any = None
_github_client_lock = threading.Lock()


def _client() -> Any:
    """Return a single shared PyGithub client (thread-safe, lazy init)."""
    global _github_client
    if _github_client is not None:
        return _github_client
    with _github_client_lock:
        if _github_client is not None:
            return _github_client
        Github = _load_github()
        if not settings.github_token:
            raise RuntimeError("GITHUB_TOKEN is required for GitHub operations")
        if settings.github_base_url:
            _github_client = Github(base_url=settings.github_base_url, login_or_token=settings.github_token)
        else:
            _github_client = Github(login_or_token=settings.github_token)
    return _github_client


_http_client: httpx.Client | None = None
_http_client_lock = threading.Lock()


def _get_http_client() -> httpx.Client:
    """Shared HTTP client for API requests (connection reuse, thread-safe)."""
    global _http_client
    if _http_client is not None:
        return _http_client
    with _http_client_lock:
        if _http_client is not None:
            return _http_client
        _http_client = httpx.Client(timeout=60, follow_redirects=True)
    return _http_client


def get_repo(full_name: str) -> Any:
    return _client().get_repo(full_name)


def _ci_status_from_check_runs(runs: list[dict[str, Any]]) -> str:
    """Derive overall CI status from check_runs list. Returns 'failure' | 'success' | 'pending'."""
    conclusions = [c.get("conclusion") for c in runs if c.get("conclusion")]
    if any(c in _CHECK_CONCLUSION_FAILED for c in conclusions):
        return "failure"
    if all(c == "success" for c in conclusions):
        return "success"
    return "pending"


def _api_base_url() -> str:
    if settings.github_base_url:
        return settings.github_base_url.rstrip("/")
    return "https://api.github.com"


def _web_base_url() -> str:
    """Base URL for GitHub web UI (issues/PRs). Matches the host we use for the API to avoid 404s."""
    base = (settings.github_base_url or "").strip().rstrip("/")
    if not base:
        return "https://github.com"
    # e.g. https://github.enterprise.com/api/v3 -> https://github.enterprise.com
    if "/api/v3" in base or "/api/" in base:
        base = base.split("/api/")[0]
    return base.rstrip("/")


def _api_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    if not settings.github_token:
        raise RuntimeError("GITHUB_TOKEN is required for GitHub operations")
    headers = {
        "Authorization": f"Bearer {settings.github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if extra:
        headers.update(extra)
    return headers


def _api_request(method: str, path: str, *, json_body: dict[str, Any] | None = None) -> httpx.Response:
    url = f"{_api_base_url()}{path}"
    client = _get_http_client()
    resp = client.request(method, url, headers=_api_headers(), json=json_body)
    resp.raise_for_status()
    return resp


def list_repos(org: str | None = None) -> list[dict[str, Any]]:
    def _fetch():
        if gh_cli.available():
            result = gh_cli.run_in_background(gh_cli.list_repos, org)
            if result is not None:
                return result
        gh = _client()
        repos = gh.get_user().get_repos() if org is None else gh.get_organization(org).get_repos()
        return [
            {"full_name": r.full_name, "private": r.private, "default_branch": r.default_branch, "html_url": r.html_url}
            for r in repos
        ]
    cache_key = f"list_repos:{org or 'user'}"
    return _cache.cached_list(cache_key, _cache.CACHE_TTL_LIST, _fetch)


def list_open_prs(
    repo_full_name: str,
    include_ci_status: bool = False,
    ci_status_max: int = 10,
) -> list[dict[str, Any]]:
    """List open PRs. If include_ci_status=True, add ci_status (success/failure/pending) for up to ci_status_max PRs."""

    def _fetch() -> list[dict[str, Any]]:
        if gh_cli.available() and not include_ci_status:
            result = gh_cli.run_in_background(gh_cli.list_open_prs, repo_full_name, False)
            if result is not None:
                return result
        if gh_cli.available() and include_ci_status:
            result = gh_cli.run_in_background(gh_cli.list_open_prs, repo_full_name, True)
            if result is not None:
                return result
        repo = get_repo(repo_full_name)
        prs = repo.get_pulls(state="open")
        out_inner: list[dict[str, Any]] = []
        for i, pr in enumerate(prs):
            entry: dict[str, Any] = {
                "number": pr.number,
                "title": pr.title,
                "user": pr.user.login,
                "state": pr.state,
                "html_url": pr.html_url,
            }
            if include_ci_status and i < ci_status_max:
                try:
                    checks_resp = _api_request(
                        "GET",
                        f"/repos/{repo_full_name}/commits/{pr.head.sha}/check-runs",
                    )
                    runs = checks_resp.json().get("check_runs", [])
                    if runs:
                        entry["ci_status"] = _ci_status_from_check_runs(runs)
                    else:
                        status_resp = _api_request("GET", f"/repos/{repo_full_name}/commits/{pr.head.sha}/status")
                        entry["ci_status"] = status_resp.json().get("state") or "pending"
                except Exception:
                    entry["ci_status"] = "unknown"
            out_inner.append(entry)
        return out_inner

    if not include_ci_status:
        return _cache.cached_list(f"list_prs:{repo_full_name}", _cache.CACHE_TTL_LIST, _fetch)
    return _fetch()


def get_pr(repo_full_name: str, number: int) -> dict[str, Any]:
    """Fetch PR details including files changed, diff, and CI check status."""

    def _fetch() -> dict[str, Any]:
        if gh_cli.available():
            result = gh_cli.run_in_background(gh_cli.get_pr, repo_full_name, number)
            if result is not None:
                return result
        repo = get_repo(repo_full_name)
        pr = repo.get_pull(number)
        head_sha = pr.head.sha
        base_ref = pr.base.ref
        head_ref = pr.head.ref

        files_changed = []
        combined_patch = []
        try:
            for f in pr.get_files():
                patch = (f.patch or "")[:12000]
                if patch:
                    combined_patch.append(f"--- a/{f.filename}\n+++ b/{f.filename}\n{patch}")
                files_changed.append({
                    "filename": f.filename,
                    "status": f.status,
                    "additions": f.additions,
                    "deletions": f.deletions,
                    "patch": patch or None,
                })
        except Exception:
            pass

        diff_text = "\n".join(combined_patch)[:50000] if combined_patch else ""
        if not diff_text:
            try:
                resp = _get_http_client().get(
                    f"{_api_base_url()}/repos/{repo_full_name}/pulls/{number}",
                    headers={**_api_headers(), "Accept": "application/vnd.github.v3.diff"},
                    timeout=30,
                )
                if resp.status_code == 200 and resp.text:
                    diff_text = resp.text[:50000]
            except Exception:
                pass

        ci_checks = []
        try:
            checks_resp = _api_request(
                "GET",
                f"/repos/{repo_full_name}/commits/{head_sha}/check-runs",
            )
            for check in checks_resp.json().get("check_runs", []):
                ci_checks.append({
                    "name": check.get("name"),
                    "status": check.get("status"),
                    "conclusion": check.get("conclusion"),
                    "details_url": check.get("details_url"),
                })
            if not ci_checks:
                status_resp = _api_request("GET", f"/repos/{repo_full_name}/commits/{head_sha}/status")
                state = status_resp.json().get("state")
                if state:
                    ci_checks.append({"name": "combined", "status": "completed", "conclusion": state, "details_url": None})
        except Exception:
            pass

        return {
            "number": pr.number,
            "title": pr.title,
            "body": pr.body,
            "state": pr.state,
            "user": pr.user.login,
            "html_url": pr.html_url,
            "head": head_ref,
            "base": base_ref,
            "head_sha": head_sha,
            "files_changed": files_changed,
            "diff": diff_text,
            "ci_checks": ci_checks,
        }

    return _cache.cached_pr(repo_full_name, number, _fetch)


def comment_pr(repo_full_name: str, number: int, body: str) -> dict[str, Any]:
    repo = get_repo(repo_full_name)
    pr = repo.get_pull(number)
    comment = pr.create_issue_comment(body)
    return {"id": comment.id, "html_url": comment.html_url}


def merge_pr(repo_full_name: str, number: int, method: str = "merge") -> dict[str, Any]:
    repo = get_repo(repo_full_name)
    pr = repo.get_pull(number)
    result = pr.merge(merge_method=method)
    return {"merged": result.merged, "message": result.message}


def create_pull(
    repo_full_name: str,
    title: str,
    head: str,
    base: str = "main",
    body: str = "",
) -> dict[str, Any]:
    """Create a pull request via GitHub API (uses GITHUB_TOKEN so it appears on the repo you expect)."""
    repo_full_name = (repo_full_name or "").strip()
    if not repo_full_name or "/" not in repo_full_name:
        return {"status": "error", "message": "repo_full_name must be owner/repo (e.g. owner/repo)"}
    try:
        repo = get_repo(repo_full_name)
        pr = repo.create_pull(title=title, body=body or None, head=head, base=base)
        web_base = _web_base_url()
        html_url = f"{web_base}/{repo_full_name}/pull/{pr.number}"
        try:
            created = repo.get_pull(pr.number)
            return {
                "repo_full_name": repo_full_name,
                "number": created.number,
                "title": created.title,
                "state": created.state,
                "html_url": html_url,
            }
        except Exception:
            return {
                "repo_full_name": repo_full_name,
                "number": pr.number,
                "title": pr.title,
                "state": pr.state,
                "html_url": html_url,
            }
    except Exception as e:
        return {"status": "error", "message": _github_error_message(e, for_issues=False)}


# ---------------------------------------------------------------------------
# README (get / update)
# ---------------------------------------------------------------------------

def get_readme(repo_full_name: str, ref: str | None = None) -> dict[str, Any]:
    """Get README content. ref = branch/tag/SHA or None for default branch."""
    repo = get_repo(repo_full_name)
    readme = repo.get_readme(ref=ref) if ref else repo.get_readme()
    content = base64.b64decode(readme.content).decode("utf-8", errors="replace")
    return {
        "path": readme.path,
        "content": content,
        "sha": readme.sha,
        "html_url": readme.html_url,
    }


def update_readme(repo_full_name: str, content: str, branch: str | None = None, message: str = "docs: update README") -> dict[str, Any]:
    """Create or update README in the repo. branch = target branch or default."""
    repo = get_repo(repo_full_name)
    ref = branch or repo.default_branch
    try:
        readme = repo.get_readme(ref=ref)
        path = readme.path
        sha = readme.sha
        repo.update_file(path, message, content, sha, branch=ref)
        return {"status": "updated", "path": path, "branch": ref}
    except Exception as e:
        err_str = str(e).lower()
        if "404" in err_str or "not found" in err_str:
            repo.create_file("README.md", message, content, branch=ref)
            return {"status": "created", "path": "README.md", "branch": ref}
        raise


# ---------------------------------------------------------------------------
# GitHub Issues
# ---------------------------------------------------------------------------


def list_issues(
    repo_full_name: str,
    state: str = "open",
) -> list[dict[str, Any]]:
    """List issues in a repository. state: open, closed, or all."""
    if gh_cli.available():
        result = gh_cli.run_in_background(gh_cli.list_issues, repo_full_name, state)
        if result is not None:
            return result
    repo = get_repo(repo_full_name)
    issues = repo.get_issues(state=state)
    return [
        {
            "number": i.number,
            "title": i.title,
            "state": i.state,
            "user": i.user.login if i.user else None,
            "html_url": i.html_url,
            "labels": [lb.name for lb in (i.labels or [])],
        }
        for i in issues
    ]


def get_issue(repo_full_name: str, number: int) -> dict[str, Any]:
    """Get a single issue by number."""
    if gh_cli.available():
        result = gh_cli.run_in_background(gh_cli.get_issue, repo_full_name, number)
        if result is not None:
            return result
    repo = get_repo(repo_full_name)
    issue = repo.get_issue(number)
    return {
        "number": issue.number,
        "title": issue.title,
        "body": issue.body,
        "state": issue.state,
        "user": issue.user.login if issue.user else None,
        "html_url": issue.html_url,
        "labels": [lb.name for lb in (issue.labels or [])],
    }


def _github_error_message(exc: Exception, for_issues: bool = True) -> str:
    """Return error message; append fine-grained token hint for permission-like errors."""
    msg = str(exc)
    lower = msg.lower()
    if "403" in msg or "resource not accessible" in lower or "permission" in lower or "denied" in lower:
        hint = (
            " Fine-grained PAT: grant 'Issues: Read and write' and add this repo under Repository access."
            if for_issues
            else " Fine-grained PAT: grant 'Pull requests: Read and write' and add this repo under Repository access."
        )
        msg = msg.rstrip(".") + "." + hint
    return msg


def create_issue(
    repo_full_name: str,
    title: str,
    body: str = "",
    labels: list[str] | None = None,
) -> dict[str, Any]:
    """Create a new issue via GitHub API (uses GITHUB_TOKEN so it appears on the repo you expect)."""
    repo_full_name = (repo_full_name or "").strip()
    if not repo_full_name or "/" not in repo_full_name:
        return {"status": "error", "message": "repo_full_name must be owner/repo (e.g. owner/repo)"}
    try:
        repo = get_repo(repo_full_name)
        issue = repo.create_issue(title=title, body=body or None, labels=labels or [])
        # Verify it exists on GitHub by refetching; build URL from our API host to avoid 404.
        web_base = _web_base_url()
        html_url = f"{web_base}/{repo_full_name}/issues/{issue.number}"
        try:
            created = repo.get_issue(issue.number)
            return {
                "repo_full_name": repo_full_name,
                "number": created.number,
                "title": created.title,
                "state": created.state,
                "html_url": html_url,
            }
        except Exception:
            return {
                "repo_full_name": repo_full_name,
                "number": issue.number,
                "title": issue.title,
                "state": issue.state,
                "html_url": html_url,
            }
    except Exception as e:
        return {"status": "error", "message": _github_error_message(e, for_issues=True)}


def comment_issue(repo_full_name: str, number: int, body: str) -> dict[str, Any]:
    """Add a comment to an issue (or PR; issues and PRs share the same comment API)."""
    repo = get_repo(repo_full_name)
    issue = repo.get_issue(number)
    comment = issue.create_comment(body)
    return {"id": comment.id, "html_url": comment.html_url}


def close_issue(repo_full_name: str, number: int) -> dict[str, Any]:
    """Close an issue."""
    repo = get_repo(repo_full_name)
    issue = repo.get_issue(number)
    issue.edit(state="closed")
    return {"number": issue.number, "state": "closed"}


def list_workflows(repo_full_name: str) -> list[dict[str, Any]]:
    repo = get_repo(repo_full_name)
    workflows = repo.get_workflows()
    return [
        {
            "id": wf.id,
            "name": wf.name,
            "path": wf.path,
            "state": wf.state,
            "html_url": wf.html_url,
        }
        for wf in workflows
    ]


def trigger_workflow(repo_full_name: str, workflow_id: int, ref: str, inputs: dict[str, Any] | None = None) -> dict[str, Any]:
    repo = get_repo(repo_full_name)
    workflow = repo.get_workflow(workflow_id)
    workflow.create_dispatch(ref=ref, inputs=inputs or {})
    return {"status": "dispatched"}


def list_workflow_runs(repo_full_name: str, workflow_id: int) -> list[dict[str, Any]]:
    repo = get_repo(repo_full_name)
    workflow = repo.get_workflow(workflow_id)
    runs = workflow.get_runs()
    return [
        {
            "id": run.id,
            "name": run.name,
            "status": run.status,
            "conclusion": run.conclusion,
            "html_url": run.html_url,
            "created_at": run.created_at.isoformat() if run.created_at else None,
        }
        for run in runs
    ]


def get_workflow_run(repo_full_name: str, run_id: int) -> dict[str, Any]:
    repo = get_repo(repo_full_name)
    run = repo.get_workflow_run(run_id)
    return {
        "id": run.id,
        "name": run.name,
        "status": run.status,
        "conclusion": run.conclusion,
        "html_url": run.html_url,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "updated_at": run.updated_at.isoformat() if run.updated_at else None,
    }


def _extract_run_id(details_url: str | None) -> int | None:
    if not details_url:
        return None
    match = re.search(r"/runs/(\d+)", details_url)
    return int(match.group(1)) if match else None


def get_failing_prs(repo_full_name: str) -> list[dict[str, Any]]:
    repo = get_repo(repo_full_name)
    results: list[dict[str, Any]] = []
    for pr in repo.get_pulls(state="open"):
        failed_checks: list[dict[str, Any]] = []
        head_sha = pr.head.sha

        checks_resp = _api_request(
            "GET",
            f"/repos/{repo_full_name}/commits/{head_sha}/check-runs",
        )
        checks_payload = checks_resp.json()
        for check in checks_payload.get("check_runs", []):
            conclusion = check.get("conclusion")
            if conclusion in _CHECK_CONCLUSION_FAILED:
                failed_checks.append(
                    {
                        "name": check.get("name"),
                        "status": check.get("status"),
                        "conclusion": conclusion,
                        "details_url": check.get("details_url"),
                        "workflow_run_id": _extract_run_id(check.get("details_url")),
                    }
                )

        status_resp = _api_request("GET", f"/repos/{repo_full_name}/commits/{head_sha}/status")
        status_payload = status_resp.json()
        combined_state = status_payload.get("state")
        if combined_state in {"failure", "error"} and not failed_checks:
            failed_checks.append(
                {
                    "name": "combined-status",
                    "status": "completed",
                    "conclusion": combined_state,
                    "details_url": None,
                    "workflow_run_id": None,
                }
            )

        if failed_checks:
            results.append(
                {
                    "pr_number": pr.number,
                    "title": pr.title,
                    "head_sha": head_sha,
                    "head_ref": pr.head.ref,
                    "html_url": pr.html_url,
                    "failed_checks": failed_checks,
                }
            )
    return results


def get_ci_logs(repo_full_name: str, workflow_run_id: int) -> str:
    resp = _api_request(
        "GET",
        f"/repos/{repo_full_name}/actions/runs/{workflow_run_id}/logs",
    )
    data = resp.content
    if not data:
        return ""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        chunks: list[str] = []
        for name in sorted(archive.namelist()):
            if name.endswith("/"):
                continue
            with archive.open(name) as fh:
                raw = fh.read().decode("utf-8", errors="replace")
            chunks.append(f"===== {name} =====\n{raw.strip()}\n")
    return "\n".join(chunks).strip()


def analyze_ci_failure(logs: str) -> dict[str, str]:
    if not logs.strip():
        return {"error_type": "unknown", "file_hint": "", "reason": "No logs provided"}

    file_hint = ""

    py_trace = re.findall(r'File "([^"]+)", line (\d+)', logs)
    if py_trace:
        path, line = py_trace[-1]
        file_hint = f"{path}:{line}"

    if not file_hint:
        file_match = re.search(
            r"([A-Za-z0-9_./-]+\.(?:py|js|jsx|ts|tsx|java|go|rb|php|cpp|c|cs|rs|yml|yaml|json))(?::(\d+))?",
            logs,
        )
        if file_match:
            file_hint = file_match.group(1)
            if file_match.group(2):
                file_hint = f"{file_hint}:{file_match.group(2)}"

    patterns: list[tuple[str, str]] = [
        (r"ModuleNotFoundError: No module named ['\"]([^'\"]+)['\"]", "missing_dependency"),
        (r"ImportError: cannot import name ['\"]([^'\"]+)['\"]", "import_error"),
        (r"SyntaxError:", "syntax_error"),
        (r"IndentationError:", "indentation_error"),
        (r"NameError: name ['\"]([^'\"]+)['\"] is not defined", "name_error"),
        (r"AttributeError:", "attribute_error"),
        (r"AssertionError:", "test_assertion_failure"),
        (r"FAILED\s+([^\n]+)", "test_failure"),
        (r"error Command failed with exit code", "build_failure"),
        (r"npm ERR!", "npm_failure"),
        (r"ruff .*Found", "lint_failure"),
        (r"would reformat", "format_failure"),
    ]

    for pat, err_type in patterns:
        match = re.search(pat, logs, re.MULTILINE)
        if match:
            reason = match.group(0).strip()
            return {"error_type": err_type, "file_hint": file_hint, "reason": reason}

    tail = "\n".join(logs.strip().splitlines()[-10:])
    return {"error_type": "unknown", "file_hint": file_hint, "reason": tail[:400]}


def _decode_content(encoded: str) -> str:
    return base64.b64decode(encoded).decode("utf-8", errors="replace")


def _strip_file_hint(file_hint: str) -> tuple[str, int | None]:
    if ":" in file_hint:
        path, line = file_hint.rsplit(":", 1)
        if line.isdigit():
            return path, int(line)
    return file_hint, None


def _snippet(lines: list[str], line_no: int | None, radius: int = 5) -> tuple[str, int, int]:
    if not lines:
        return "", 1, 1
    if line_no is None:
        start = 1
        end = min(len(lines), 25)
    else:
        start = max(1, line_no - radius)
        end = min(len(lines), line_no + radius)
    snippet = "\n".join(lines[start - 1:end])
    return snippet, start, end


def locate_code_context(repo_full_name: str, error_context: dict[str, Any]) -> dict[str, Any]:
    repo = get_repo(repo_full_name)
    file_hint = str(error_context.get("file_hint") or "")
    path_hint, line_hint = _strip_file_hint(file_hint)
    contexts: list[dict[str, Any]] = []

    def add_context(path: str) -> None:
        if any(ctx["path"] == path for ctx in contexts):
            return
        try:
            file_obj = repo.get_contents(path, ref=repo.default_branch)
        except Exception:
            return
        if isinstance(file_obj, list):
            return
        decoded = _decode_content(file_obj.content)
        lines = decoded.splitlines()
        snip, start, end = _snippet(lines, line_hint if path == path_hint else None)
        contexts.append(
            {
                "path": path,
                "start_line": start,
                "end_line": end,
                "snippet": snip,
            }
        )

    if path_hint:
        add_context(path_hint)

    if not contexts and path_hint:
        search_q = f"repo:{repo_full_name} {path_hint.split('/')[-1]} in:path"
        resp = _api_request("GET", f"/search/code?q={quote(search_q, safe='')}")
        for item in resp.json().get("items", [])[:3]:
            add_context(item.get("path", ""))

    reason = str(error_context.get("reason") or "").strip()
    if not contexts and reason:
        terms = re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", reason)
        if terms:
            query = f"repo:{repo_full_name} {terms[0]} in:file"
            resp = _api_request("GET", f"/search/code?q={quote(query, safe='')}")
            for item in resp.json().get("items", [])[:2]:
                add_context(item.get("path", ""))

    return {
        "repo": repo_full_name,
        "error_context": error_context,
        "contexts": contexts,
    }


def _parse_unified_diff(patch: str) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    lines = patch.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("--- "):
            old_path = line[4:].strip()
            i += 1
            if i >= len(lines) or not lines[i].startswith("+++ "):
                raise ValueError("Invalid patch: missing +++ line")
            new_path = lines[i][4:].strip()
            i += 1
            hunks: list[dict[str, Any]] = []
            while i < len(lines) and lines[i].startswith("@@"):
                header = lines[i]
                match = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", header)
                if not match:
                    raise ValueError(f"Invalid hunk header: {header}")
                i += 1
                hunk_lines: list[str] = []
                while i < len(lines) and not lines[i].startswith("@@") and not lines[i].startswith("--- "):
                    if lines[i].startswith("\\ No newline at end of file"):
                        i += 1
                        continue
                    hunk_lines.append(lines[i])
                    i += 1
                hunks.append(
                    {
                        "old_start": int(match.group(1)),
                        "new_start": int(match.group(3)),
                        "lines": hunk_lines,
                    }
                )
            files.append({"old_path": old_path, "new_path": new_path, "hunks": hunks})
            continue
        i += 1
    return files


def _normalize_patch_path(path: str) -> str:
    if path.startswith("a/") or path.startswith("b/"):
        return path[2:]
    return path


def _apply_hunks(original: str, hunks: list[dict[str, Any]]) -> str:
    src = original.splitlines(keepends=True)
    out: list[str] = []
    src_idx = 0
    for hunk in hunks:
        target_idx = max(0, hunk["old_start"] - 1)
        out.extend(src[src_idx:target_idx])
        src_idx = target_idx
        for line in hunk["lines"]:
            if not line:
                tag = " "
                text = ""
            else:
                tag = line[0]
                text = line[1:]
            if tag == " ":
                if src_idx >= len(src) or src[src_idx].rstrip("\n") != text:
                    raise ValueError("Patch context mismatch")
                out.append(src[src_idx])
                src_idx += 1
            elif tag == "-":
                if src_idx >= len(src) or src[src_idx].rstrip("\n") != text:
                    raise ValueError("Patch removal mismatch")
                src_idx += 1
            elif tag == "+":
                out.append(text + "\n")
            else:
                raise ValueError(f"Unsupported patch line prefix: {tag}")
    out.extend(src[src_idx:])
    return "".join(out)


def generate_fix_patch(code_context: Any, error: dict[str, Any]) -> str:
    data = code_context
    if isinstance(code_context, str):
        try:
            data = json.loads(code_context)
        except json.JSONDecodeError:
            data = {"contexts": []}
    contexts = data.get("contexts", []) if isinstance(data, dict) else []
    error_type = str(error.get("error_type") or "")
    reason = str(error.get("reason") or "")

    if error_type == "missing_dependency":
        dep_match = re.search(r"No module named ['\"]([^'\"]+)['\"]", reason)
        dep = dep_match.group(1) if dep_match else None
        if dep:
            req_ctx = next((c for c in contexts if c.get("path") == "requirements.txt"), None)
            old = req_ctx.get("snippet", "") if req_ctx else ""
            if dep not in old.splitlines():
                new_lines = old.splitlines()
                new_lines.append(dep)
                new = "\n".join([line for line in new_lines if line.strip()]).strip() + "\n"
                return "\n".join(
                    difflib.unified_diff(
                        old.splitlines(),
                        new.splitlines(),
                        fromfile="a/requirements.txt",
                        tofile="b/requirements.txt",
                        lineterm="",
                    )
                )

    if error_type == "name_error":
        name_match = re.search(r"name ['\"]([^'\"]+)['\"] is not defined", reason)
        symbol = name_match.group(1) if name_match else None
        if symbol and contexts:
            ctx = contexts[0]
            path = ctx.get("path", "")
            snippet = ctx.get("snippet", "")
            if path.endswith(".py") and symbol in {"Optional", "List", "Dict", "Set", "Tuple"}:
                if "from typing import" not in snippet:
                    new_snippet = f"from typing import {symbol}\n" + snippet
                    return "\n".join(
                        difflib.unified_diff(
                            snippet.splitlines(),
                            new_snippet.splitlines(),
                            fromfile=f"a/{path}",
                            tofile=f"b/{path}",
                            lineterm="",
                        )
                    )

    return ""


def apply_fix_to_pr(repo_full_name: str, pr_number: int, patch: str) -> dict[str, Any]:
    if not patch.strip():
        raise ValueError("Patch is empty")

    repo = get_repo(repo_full_name)
    pr = repo.get_pull(pr_number)
    branch = pr.head.ref
    files = _parse_unified_diff(patch)
    if not files:
        raise ValueError("Patch did not contain any file changes")

    commits: list[dict[str, Any]] = []
    for file_diff in files:
        old_path_raw = file_diff["old_path"]
        new_path_raw = file_diff["new_path"]
        is_new = old_path_raw == "/dev/null"
        is_delete = new_path_raw == "/dev/null"
        target_path = _normalize_patch_path(new_path_raw if not is_delete else old_path_raw)

        current_text = ""
        current_sha: str | None = None
        if not is_new:
            current_obj = repo.get_contents(_normalize_patch_path(old_path_raw), ref=branch)
            if isinstance(current_obj, list):
                raise ValueError(f"Expected file but found directory: {old_path_raw}")
            current_text = _decode_content(current_obj.content)
            current_sha = current_obj.sha

        updated_text = _apply_hunks(current_text, file_diff["hunks"]) if not is_delete else ""
        message = f"chore(self-heal): apply AI-generated fix for PR #{pr_number}"

        if is_delete:
            if not current_sha:
                raise ValueError(f"File not found for delete: {target_path}")
            resp = repo.delete_file(target_path, message, current_sha, branch=branch)
            commits.append({"path": target_path, "commit_sha": resp["commit"].sha, "action": "delete"})
        elif is_new:
            resp = repo.create_file(target_path, message, updated_text, branch=branch)
            commits.append({"path": target_path, "commit_sha": resp["commit"].sha, "action": "create"})
        else:
            if not current_sha:
                raise ValueError(f"File not found for update: {target_path}")
            resp = repo.update_file(target_path, message, updated_text, current_sha, branch=branch)
            commits.append({"path": target_path, "commit_sha": resp["commit"].sha, "action": "update"})

    return {"status": "applied", "branch": branch, "commits": commits}


def rerun_ci(repo_full_name: str, workflow_run_id: int) -> dict[str, Any]:
    _api_request(
        "POST",
        f"/repos/{repo_full_name}/actions/runs/{workflow_run_id}/rerun",
    )
    return {"status": "rerun_requested", "workflow_run_id": workflow_run_id}


def heal_failing_pr(repo_full_name: str, pr_number: int | None = None) -> dict[str, Any]:
    """Run full CI healing pipeline: find failing PR → get logs → analyze → locate context → generate patch → apply to PR → rerun CI.
    If pr_number is None, heals the first failing PR in the repo. Returns structured status and errors."""
    from .progress import clear_progress, set_progress

    op = "heal_ci"
    try:
        set_progress(op, "get_failing_prs", "Finding PRs with failing CI...", {"repo": repo_full_name})
        failing = get_failing_prs(repo_full_name)
    except Exception as e:
        clear_progress(op)
        return {"status": "error", "message": f"Failed to get failing PRs: {e}", "stage": "get_failing_prs"}

    if not failing:
        clear_progress(op)
        return {"status": "no_failing_prs", "message": "No open PRs with failed CI in this repo."}

    pr_entry = next((p for p in failing if p["pr_number"] == pr_number), None) if pr_number else failing[0]
    if pr_number and not pr_entry:
        clear_progress(op)
        return {"status": "not_failing", "message": f"PR #{pr_number} does not have failed CI or not found."}

    assert pr_entry is not None
    pr_num = pr_entry["pr_number"]
    set_progress(op, "get_failing_prs", f"Found failing PR #{pr_num}", {"pr_number": pr_num})
    failed_checks = pr_entry.get("failed_checks", [])
    run_id = None
    for check in failed_checks:
        run_id = check.get("workflow_run_id")
        if run_id:
            break
    if not run_id:
        clear_progress(op)
        return {
            "status": "no_logs",
            "pr_number": pr_num,
            "message": "No workflow run ID available for failed checks; cannot fetch logs.",
        }

    try:
        set_progress(op, "get_ci_logs", "Fetching CI logs...", {"workflow_run_id": run_id})
        logs = get_ci_logs(repo_full_name, run_id)
    except Exception as e:
        clear_progress(op)
        return {"status": "error", "pr_number": pr_num, "message": f"Failed to get CI logs: {e}", "stage": "get_ci_logs"}

    set_progress(op, "analyze_ci_failure", "Analyzing failure...", {})
    error = analyze_ci_failure(logs)
    try:
        set_progress(op, "locate_code_context", "Locating code context...", {"file_hint": error.get("file_hint")})
        code_context = locate_code_context(repo_full_name, error)
    except Exception as e:
        clear_progress(op)
        return {"status": "error", "pr_number": pr_num, "message": f"Failed to locate code context: {e}", "stage": "locate_code_context"}

    set_progress(op, "generate_fix_patch", "Generating fix patch...", {})
    patch = generate_fix_patch(code_context, error)
    if not patch or not patch.strip():
        clear_progress(op)
        return {
            "status": "no_fix",
            "pr_number": pr_num,
            "error_type": error.get("error_type"),
            "reason": (error.get("reason") or "")[:300],
            "message": "No automated fix available for this error type. Consider manual fix or extend generate_fix_patch.",
        }

    try:
        set_progress(op, "apply_fix_to_pr", f"Applying patch to PR #{pr_num}...", {})
        result = apply_fix_to_pr(repo_full_name, pr_num, patch)
    except Exception as e:
        clear_progress(op)
        return {"status": "error", "pr_number": pr_num, "message": f"Failed to apply fix to PR: {e}", "stage": "apply_fix_to_pr"}

    try:
        set_progress(op, "rerun_ci", "Re-running CI...", {"workflow_run_id": run_id})
        rerun_ci(repo_full_name, run_id)
    except Exception as e:
        result["rerun_error"] = str(e)
    clear_progress(op)
    result["status"] = "healed"
    result["pr_number"] = pr_num
    result["workflow_run_id"] = run_id
    result["error_type"] = error.get("error_type")
    result["message"] = f"Applied fix for PR #{pr_num} ({error.get('error_type', 'unknown')}) and requested CI re-run."
    return result
