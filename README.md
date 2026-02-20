# OpenX MCP Server

FastAPI-based MCP server for GitHub operations (PRs, repos, CI/CD) plus code analysis and architecture insights.

## Features
- Modular MCP tools with `tools/list` + `tools/call`.
- GitHub integration: list repos, PRs, comment/merge PRs, list/trigger workflows, workflow runs.
- Code analysis: bugs, performance hints, duplicate code, AI-generated markers, bad practices.
- Architecture insights: language breakdown, module depth, LOC summaries.
- Optional AI analysis via OpenAI-compatible API.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set env vars:
- `GITHUB_TOKEN` (required for GitHub tools)
- `GITHUB_BASE_URL` (optional for GitHub Enterprise)
- `LLM_API_KEY` (optional for AI analysis)
- `LLM_BASE_URL` (optional, defaults to `https://api.llm-model.com/v1`)
- `LLM_MODEL` (optional, defaults to `Open-Source Model`)

Run:

```bash
uvicorn app.main:app --reload --port 8000
```

## MCP Usage

List tools:

```bash
curl -s http://localhost:8000/mcp \
  -H 'content-type: application/json' \
  -d '{"id":1,"method":"tools/list"}'
```

Call a tool:

```bash
curl -s http://localhost:8000/mcp \
  -H 'content-type: application/json' \
  -d '{"id":2,"method":"tools/call","params":{"name":"github.list_open_prs","arguments":{"repo_full_name":"org/repo"}}}'
```

Analyze a local repo:

```bash
curl -s http://localhost:8000/mcp \
  -H 'content-type: application/json' \
  -d '{"id":3,"method":"tools/call","params":{"name":"analysis.repo","arguments":{"path":"/path/to/repo"}}}'
```

## Extending Tools
Add a new tool in `app/mcp.py` using the `_tool(...)` decorator and it will be auto-registered on startup.
