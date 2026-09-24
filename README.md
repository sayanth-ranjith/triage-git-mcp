# triage-git-mcp

An MCP (Model Context Protocol) server that connects GitHub Copilot to your GitHub issues — so you can ask "what's on my plate?" and get a real answer, without leaving your editor.

## Why this exists

Checking assigned issues usually means switching to a browser, hunting through filters, and clicking into each one for context. This project aims to close that gap: trigger it from Copilot, and it fetches the issues assigned to you along with the detail you'd normally have to dig for — description, labels, status, and anything else useful for deciding what to work on next.

The goal isn't just a list of titles. It's enough context that Copilot (and you) can actually reason about priority and next steps without a tab switch.

## What it does (planned)

- Fetches issues currently assigned to you across your repos
- Pulls in the detail that matters — description, labels, comments, linked PRs — not just the title
- Exposes this to Copilot as MCP tools, so it can be triggered conversationally
- (Future) Supports scoping to specific repos/orgs, filtering by label or status, etc.

## Status

Early-stage / learning project. Core flow and tool design are still being figured out.

## Tech stack

- Python
- [FastAPI](https://fastapi.tiangolo.com/) for the service layer
- [Uvicorn](https://www.uvicorn.org/) as the ASGI server

## Getting started

```bash
python -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Once running, check the service is up:

```bash
curl http://127.0.0.1:8000/health
```

This currently just scaffolds the FastAPI app with a `/health` endpoint — the MCP tools and GitHub issue-fetching logic described above are still to come.
