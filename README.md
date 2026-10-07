# triage-git-mcp

An MCP (Model Context Protocol) server that connects agent(Copilot, Claude Code, or if you're weird enough to use vim + a shell script you call "AI.") to your GitHub issues — so you can ask "what's on my plate?" and get a real answer, without leaving your editor.

## Why this exists

Checking assigned issues usually means switching to a browser, hunting through filters, and clicking into each one for context. This project aims to close that gap: trigger it from Copilot, and it fetches the issues assigned to you along with the detail you'd normally have to dig for — description, labels, status, and anything else useful for deciding what to work on next.

The goal isn't just a list of titles. It's enough context that Copilot (and you) can actually reason about priority and next steps without a tab switch.

## What it does

Two MCP tools, both read-only:

- **`list_my_assigned_issues`** — your assigned issues across every repo
  you can see, open only by default. Each comes with labels, a priority,
  last update, comment count and the start of its description — enough to
  rank them. Filter by `repo` or `org`, `labels`, `state`
  (`open`/`closed`/`all`), `updated_since` and `priority`.
- **`get_issue_details`** — everything about one issue: full description,
  the most recent comments, and linked pull requests with their status
  (open, draft, merged, closed).

Priority comes from a `sev1`–`sev4` label or a ticked sev checkbox in the
issue body (sev1 = critical … sev4 = low); issues without one count as
medium.

## Status

Learning project, built in iterations — see [`docs/plan/`](docs/plan/00-overview.md).
Iterations 1–4 (MCP plumbing, assigned issues, rich context, filtering) are
built. Auth/rate-limit hardening and packaging are next.

## Tech stack

- Python 3.11+
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) (v2), stdio transport
- `requests` for the GitHub REST API, `pydantic` for the data models
- [FastAPI](https://fastapi.tiangolo.com/) + [Uvicorn](https://www.uvicorn.org/) for a separate `/health` service

## Getting started

```bash
python -m venv venv
source venv/bin/activate   # On Windows: venv\Scriptsctivate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env       # then paste a classic GitHub PAT with 'repo' scope
```

Try the MCP server from the terminal — this launches it the way a host
would and calls its tools:

```bash
python scripts/try_mcp.py                  # list tools + your open issues
python scripts/try_mcp.py owner/repo 12    # also fetch one issue's details
```

To use it from a host (Claude Code, Copilot, …), register it as a stdio
server whose command is your venv's `python` and whose argument is the path
to `mcp_server.py`.

## Development

```bash
python -m pytest           # unit tests, no network needed
ruff check . && ruff format --check .
```
