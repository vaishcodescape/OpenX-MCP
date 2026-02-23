# OpenX MCP Server

FastAPI-based MCP server for GitHub operations (PRs, repos, CI/CD) plus code analysis and architecture insights.

## Features
- Modular MCP tools with `tools/list` + `tools/call`.
- GitHub integration: list repos, PRs, comment/merge PRs, list/trigger workflows, workflow runs.
- Code analysis: bugs, performance hints, duplicate code, AI-generated markers, bad practices.
- Architecture insights: language breakdown, module depth, LOC summaries.
- Optional AI analysis via Hugging Face Inference API.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Set env vars:
- `GITHUB_TOKEN` (required for GitHub tools)
- `GITHUB_BASE_URL` (optional for GitHub Enterprise)
- `HUGGINGFACE_API_KEY` (optional for AI analysis)
- `HUGGINGFACE_BASE_URL` (optional, defaults to `https://router.huggingface.co/v1`)
- `HUGGINGFACE_MODEL` (optional, defaults to `Qwen/Qwen2.5-Coder-32B-Instruct` — best HF coding model; use `Qwen/Qwen2.5-7B-Instruct` if unavailable)

**Run openx-agent (MCP server):**

```bash
make openx-agent
# or
./run-openx-agent
```

**Run openx-tui (Rust TUI):**  
Start openx-agent in another terminal first, then:

```bash
make openx-tui
# or
./run-openx-tui
```

Optional: `OPENX_BASE_URL=http://...` to point the TUI at a different server.

**Classic REPL:** `openx-cli`

Rust TUI keybindings (see `openx-tui/README.md` for full list):
- `Ctrl+K` command palette, `Ctrl+P` file search, `Ctrl+J` focus input
- `Ctrl+E` layout, `Ctrl+D` activity drawer, `Tab` cycle panels, `Ctrl+C` quit

Slash command examples:
- `/help` - Show available commands and usage examples.
- `/tools` - List all registered MCP tools available in this workspace.
- `/schema` - Show the expected input schema for a selected tool.
- `/call` - Call a tool directly with raw JSON arguments.
- `/analyzerepo` - Run repository static analysis and architecture summary.
- `/listrepos` - List repositories for the authenticated account or org.
- `/listprs` - List open pull requests for a repository.
- `/getpr` - Get detailed information for a pull request number.
- `/commentpr` - Post a comment on a pull request.
- `/mergepr` - Merge a pull request using the selected strategy.
- `/listworkflows` - List GitHub Actions workflows in a repository.
- `/triggerworkflow` - Dispatch a GitHub Actions workflow run.
- `/listworkflowruns` - List workflow runs for a specific workflow.
- `/getworkflowrun` - Get details for one workflow run by run id.

Inside the classic terminal:
- Press `Tab` to autocomplete commands/tool names.
- Use aliases: `prs`, `pr`, `wfs`, `runs`, `run`, `analyze`, `q`.

One-shot examples:

```bash
openx-cli tools
openx-cli list_prs org/repo
openx-cli analyze_repo /path/to/repo
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
Add a new tool in `openx/mcp.py` using the `_tool(...)` decorator and it will be auto-registered on startup.
