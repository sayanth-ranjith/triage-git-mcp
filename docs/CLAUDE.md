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

Early-stage / learning project. Iterations 1 (MCP plumbing), 2 (first
real GitHub-backed tool) and 3 (richer issue context) are built:

- `main.py` — a FastAPI app with a single `/health` endpoint. Untouched by
  MCP work — runs as a separate process, at least for now.
- `mcp_server.py` — the MCP entry point and composition root. Registers two
  tools over stdio transport: `list_my_assigned_issues` (cheap summary of
  every assigned issue) and `get_issue_details` (full body, recent comments
  and linked PRs for one issue). It reads config and wires up a client; it
  contains no HTTP or parsing logic itself.
- `triage_git_mcp/` — the MCP-agnostic core. `config.py` (env/`.env`
  loading + validation), `models.py` (`AssignedIssue`, `IssueDetail`,
  `IssueComment`, `LinkedPullRequest` pydantic models),
  `github_client.py` (`GitHubIssueClient` over the GitHub REST API).
  Nothing in this package imports the MCP SDK.
- `tests/` — pytest unit tests for the client's parsing/request rules and
  for config validation, using a stub session instead of the network.
- `requirements.txt` — `fastapi`, `uvicorn[standard]`, `mcp[cli]`,
  `requests`, `python-dotenv`. `requirements-dev.txt` adds `pytest`.

Iterations 4–6 (filtering, real auth/resilience, packaging) are **not
built**. Treat them as not started, not as "existing but broken."

## Planned functionality (not yet implemented)

- (Future) scope to specific repos/orgs, filter by label/status, etc.

## Tech stack

- Python
- FastAPI (service layer)
- Uvicorn (ASGI server)
- `requests` (GitHub REST calls), `python-dotenv` (local `.env` loading),
  `pydantic` (data models; already an MCP SDK dependency)
- Official MCP Python SDK (`mcp[cli]`, v2), stdio transport.

### MCP SDK v2 gotchas (verified against the installed `mcp==2.2.0`)

Most MCP material online predates v2. Don't copy it blindly:

- **`FastMCP` is gone — it's `MCPServer` now**
  (`from mcp.server.mcpserver import MCPServer`). Same class, renamed.
  `mcp/server/fastmcp.py` still exists but is a *tombstone* whose whole body
  is `raise ModuleNotFoundError(...)` pointing at the migration guide. The
  only ways to get the old name are pinning `mcp<2` or installing the
  unrelated third-party `fastmcp` package — neither is worth it, so don't.
- **Protocol model fields are snake_case**, not the wire format's camelCase:
  `tool.input_schema` / `tool.output_schema`, not `inputSchema`/`outputSchema`.
- **Return annotations become the tool's output schema.** Annotating a tool
  `-> list[AssignedIssue]` gives the host a fully described schema, including
  each field's `description=`. A bare `-> list[dict]` gives it nothing.
- **Docstrings are public API.** A tool function's docstring is the
  description the host's model reads when deciding whether to call it, and a
  pydantic model's docstring becomes its schema `description`. Write both for
  that audience; keep internal notes (iteration numbers, TODOs) in `#`
  comments so they don't leak into the schema.

## Running it locally

```bash
python -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
```

The MCP server needs a GitHub token before it will start:

```bash
cp .env.example .env       # then paste a classic PAT with 'repo' scope
```

`.env` is gitignored and must stay that way — never commit a real token.
A missing or empty `GITHUB_TOKEN` fails at startup with a `ConfigError`
telling you this, which is intended behaviour, not a bug.

```bash
python -m pytest tests/    # unit tests, no network needed
python mcp_server.py       # MCP server (stdio; normally launched by a host)
uvicorn main:app --reload  # the separate FastAPI health app
curl http://127.0.0.1:8000/health
```

## Design principles

This is a learning project, but the iterations build on each other, so
today's shortcut becomes tomorrow's refactor. Apply these by default, and
call out deliberate exceptions rather than making them silently:

- **One reason to change per module (SRP).** HTTP/GitHub concerns live in
  `github_client.py`, configuration in `config.py`, data shapes in
  `models.py`, MCP registration in `mcp_server.py`. A tool function should
  read as a one-line delegation; if it grows logic, that logic belongs in
  the core package.
- **Keep the core MCP-agnostic.** Only `mcp_server.py` imports the MCP SDK.
  That's what keeps the GitHub logic testable without a server, and what
  would let the same core back a CLI or the FastAPI app later.
- **Inject collaborators, default them sensibly (DIP).** `GitHubIssueClient`
  takes its `session`, `api_root` and `timeout` as keyword arguments with
  working defaults, so tests substitute a stub and iteration 5 can pass a
  retrying session without editing the class.
- **Pure core, impure shell.** Parsing and validation are pure and easy to
  test (`Settings.from_mapping`, `_to_issue`); the things that touch the
  network, filesystem or `os.environ` sit at the edges (`load_settings`,
  `_get_json`).
- **Fail fast with an actionable message.** Misconfiguration raises at
  startup, saying what to do about it — not a bare `KeyError`, and never a
  silent empty value that turns into a confusing 401 later.
- **Let types do real work.** Annotations and pydantic models are what the
  SDK turns into the schemas a host sees, so precision here is functionality.
- **Test the logic that isn't I/O.** Field mapping, filtering, query params
  and config validation get unit tests. Real network round trips and host
  integration are verified by hand, per iteration.
- **Simplest thing that satisfies the above.** Don't add an interface,
  factory, or abstraction layer until a second implementation or a test
  actually needs it — YAGNI beats speculative generality. Comments should
  explain *why*, not restate the code.

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

- Whether a classic PAT stays the auth mechanism (vs GitHub App or OAuth) —
  iteration 2 uses a PAT from `.env` as the deliberately simplest thing;
  revisiting is iteration 5's job.
- Whether the existing FastAPI app and the MCP server ever merge into one
  process, or stay separate for good — not decided (deferred to the
  packaging iteration, iteration 6). Right now they're just two separate
  processes.
- Repo/org scoping and filtering — deferred per the README's roadmap
  (iteration 4).

## Repo conventions

- `.gitignore` excludes `venv/`, `__pycache__/`, `.idea/` and `.env` — keep
  it that way; don't commit virtualenvs, IDE state, or secrets. `.env.example`
  is committed and must never contain a real token.
- Work happens on feature branches off `main` (see `add-triage-git-mcp-service`
  for the first one), not directly on `main`.
