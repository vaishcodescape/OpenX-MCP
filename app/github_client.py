from __future__ import annotations

from typing import Any

from github import Github
from github.Repository import Repository
from github.PullRequest import PullRequest
from github.Workflow import Workflow
from github.WorkflowRun import WorkflowRun

from .config import settings


def _client() -> Github:
    if not settings.github_token:
        raise RuntimeError("GITHUB_TOKEN is required for GitHub operations")
    if settings.github_base_url:
        return Github(base_url=settings.github_base_url, login_or_token=settings.github_token)
    return Github(login_or_token=settings.github_token)


def get_repo(full_name: str) -> Repository:
    return _client().get_repo(full_name)


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
    pr: PullRequest = repo.get_pull(number)
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
    pr: PullRequest = repo.get_pull(number)
    comment = pr.create_issue_comment(body)
    return {"id": comment.id, "html_url": comment.html_url}


def merge_pr(repo_full_name: str, number: int, method: str = "merge") -> dict[str, Any]:
    repo = get_repo(repo_full_name)
    pr: PullRequest = repo.get_pull(number)
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
    workflow: Workflow = repo.get_workflow(workflow_id)
    workflow.create_dispatch(ref=ref, inputs=inputs or {})
    return {"status": "dispatched"}


def list_workflow_runs(repo_full_name: str, workflow_id: int) -> list[dict[str, Any]]:
    repo = get_repo(repo_full_name)
    workflow: Workflow = repo.get_workflow(workflow_id)
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
    run: WorkflowRun = repo.get_workflow_run(run_id)
    return {
        "id": run.id,
        "name": run.name,
        "status": run.status,
        "conclusion": run.conclusion,
        "html_url": run.html_url,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "updated_at": run.updated_at.isoformat() if run.updated_at else None,
    }
