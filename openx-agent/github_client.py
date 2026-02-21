from __future__ import annotations

import base64
import difflib
import io
import json
import re
import zipfile
from typing import Any
from urllib.parse import quote

import httpx

from .config import settings


def _load_github() -> Any:
    try:
        from github import Github  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "PyGithub is not installed. Run `pip install -r requirements.txt`."
        ) from exc
    return Github


def _client() -> Any:
    Github = _load_github()
    if not settings.github_token:
        raise RuntimeError("GITHUB_TOKEN is required for GitHub operations")
    if settings.github_base_url:
        return Github(base_url=settings.github_base_url, login_or_token=settings.github_token)
    return Github(login_or_token=settings.github_token)


def get_repo(full_name: str) -> Any:
    return _client().get_repo(full_name)


def _api_base_url() -> str:
    if settings.github_base_url:
        return settings.github_base_url.rstrip("/")
    return "https://api.github.com"


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
    with httpx.Client(timeout=60) as client:
        resp = client.request(
            method,
            url,
            headers=_api_headers(),
            json=json_body,
            follow_redirects=True,
        )
    resp.raise_for_status()
    return resp


def list_repos(org: str | None = None) -> list[dict[str, Any]]:
    gh = _client()
    repos = gh.get_user().get_repos() if org is None else gh.get_organization(org).get_repos()
    return [
        {
            "full_name": r.full_name,
            "private": r.private,
            "default_branch": r.default_branch,
            "html_url": r.html_url,
        }
        for r in repos
    ]


def list_open_prs(repo_full_name: str) -> list[dict[str, Any]]:
    repo = get_repo(repo_full_name)
    prs = repo.get_pulls(state="open")
    return [
        {
            "number": pr.number,
            "title": pr.title,
            "user": pr.user.login,
            "state": pr.state,
            "html_url": pr.html_url,
        }
        for pr in prs
    ]


def get_pr(repo_full_name: str, number: int) -> dict[str, Any]:
    repo = get_repo(repo_full_name)
    pr = repo.get_pull(number)
    return {
        "number": pr.number,
        "title": pr.title,
        "body": pr.body,
        "state": pr.state,
        "user": pr.user.login,
        "html_url": pr.html_url,
        "head": pr.head.ref,
        "base": pr.base.ref,
    }


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
            if conclusion in {
                "failure",
                "timed_out",
                "cancelled",
                "action_required",
                "startup_failure",
                "stale",
            }:
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
