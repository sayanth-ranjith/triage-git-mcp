# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this project is

`triage-git-mcp` is an **MCP (Model Context Protocol) server** that connects
GitHub Copilot to a user's GitHub issues, so they can ask something like
"what's on my plate?" from inside their editor instead of switching to a
browser and hunting through filters.

The point isn't just a list of issue titles — it's enough context (description,
labels, status, comments, linked PRs) that Copilot and the user can actually
reason about priority and next steps without a tab switch.

## Where we are right now

Early-stage / learning project. There is no MCP server yet — what exists is a
bare FastAPI scaffold:

- `main.py` — a FastAPI app with a single `/health` endpoint
- `requirements.txt` — `fastapi`, `uvicorn[standard]`

Nothing here talks to GitHub or implements MCP tools yet. Treat anything
beyond the health check as **not built**, not as "existing but broken."

## Planned functionality (not yet implemented)

- Fetch issues currently assigned to the user across their repos
- Pull in detail beyond the title — description, labels, comments, linked PRs
- Expose this to Copilot as MCP tools, so it's triggered conversationally
- (Future) scope to specific repos/orgs, filter by label/status, etc.

## Tech stack

- Python
- FastAPI (service layer)
- Uvicorn (ASGI server)
- MCP tooling — not yet chosen/integrated (see "Open questions" below)

## Running it locally

```bash
python -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

```bash
curl http://127.0.0.1:8000/health
```

## How to work with me on this repo

The user is new to building MCP servers — so am I, in the sense that this
project hasn't established any patterns of its own yet. Given that:

- Don't assume prior MCP context. When introducing an MCP concept (tools,
  resources, transports, the Copilot/host relationship, etc.), briefly say
  what it is and why it's needed here, not just how to code it.
- Prefer small, explainable steps over a large scaffold dropped in one go —
  the goal is for the user to understand the server as it's built, not just
  end up with a working one.
- Favor the simplest thing that demonstrates the concept correctly. This is
  a learning project first, a production service second.
- When a design decision has real tradeoffs (e.g. which MCP SDK/transport,
  how to auth to GitHub, how to structure tools), surface the options and
  reasoning rather than silently picking one.

## Build plan

The iteration-by-iteration build plan — what we're building next and why —
lives in [`plan/`](plan/00-overview.md). Check it before starting work, and
update the relevant iteration file as decisions get made; it's meant to stay
current, not be written once and ignored.

## Open questions / decisions not yet made

- Which MCP server SDK/library to build on (e.g. the official Python MCP
  SDK) — not chosen yet.
- How the server authenticates to GitHub (PAT, GitHub App, OAuth) — not
  decided.
- Whether the existing FastAPI app is the MCP server's transport layer, or
  MCP runs alongside/instead of it — not decided.
- Repo/org scoping and filtering — deferred per the README's roadmap.

## Repo conventions

- `.gitignore` excludes `venv/`, `__pycache__/`, and `.idea/` — keep it that
  way; don't commit virtualenvs or IDE state.
- Work happens on feature branches off `main` (see `add-triage-git-mcp-service`
  for the first one), not directly on `main`.
