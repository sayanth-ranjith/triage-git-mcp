# Iteration 2: Fetch assigned issues (bare-bones)

## Goal

One real MCP tool — something like `list_my_assigned_issues` — that hits the
GitHub API and returns the issues assigned to the authenticated user. Bare
fields only: title, repo, URL, state (open/closed).

## Why this next

With iteration 1 proving the MCP plumbing works, this iteration proves the
*other* half in isolation: can we authenticate to GitHub and pull real data
back. Keeping the returned fields minimal means if something's wrong, it's
either "auth is broken" or "the query is wrong" — not buried under logic for
formatting rich issue detail we haven't built yet.

This is also the first point where the project does something a user could
plausibly care about, even in skeleton form.

## What we'll build

- GitHub authentication — starting with a personal access token (PAT) read
  from an environment variable, because it's the fastest way to get
  something working. (We'll revisit whether a PAT is good enough in
  [iteration 5](05-auth-and-resilience.md).)
- A GitHub API client call (via a library like PyGithub, or raw REST/GraphQL
  calls — TBD) that fetches issues assigned to the authenticated user.
- The MCP tool wrapping that call, returning a simple list of
  `{title, repo, url, state}`.

## Out of scope (for now)

- Descriptions, labels, comments, linked PRs — that's the whole point of
  iteration 3, deliberately deferred.
- Filtering by repo/org/label — iteration 4.
- Handling pagination, rate limits, or API errors gracefully — iteration 5.
  For now it's fine if this breaks loudly on edge cases.

## What "done" looks like

Asking Copilot (or whatever host we're testing with) "what issues are
assigned to me?" returns a real, accurate list of your actual GitHub issues
— titles and links you can click and verify against github.com.

## New concepts we'll hit here

- **GitHub API auth model**: what a PAT can/can't see, and the scopes it
  needs for this to work.
- **MCP tool inputs**: whether this tool takes any parameters yet, or is
  parameter-free for now (likely parameter-free at this stage).

## Open questions to resolve in this iteration

- REST API or GraphQL API for the GitHub call? (GraphQL can fetch more in
  one round trip, which may matter more once we get to iteration 3.)
- Where does the PAT live locally — `.env` file, shell env var — and how do
  we make sure it never ends up committed?

## Resolved

- **REST, not GraphQL.** One endpoint, one round trip, and a response shape
  that's easy to eyeball against github.com while debugging auth. GraphQL's
  advantage is fetching nested data in one request, which doesn't pay off
  until iteration 3 — revisit it there, when labels/comments/linked PRs
  would otherwise mean N+1 requests.
- **Raw `requests`, not PyGithub.** For a single authenticated GET, a
  library mostly hides the thing we're trying to learn. (Note: real `httpx`
  isn't installed — the `httpx2` in the venv is an unrelated transitive
  dependency of the MCP SDK, not a drop-in.)
- **PAT lives in a gitignored `.env`**, loaded with `python-dotenv` and read
  once at startup. `.env` was added to `.gitignore` *before* the file was
  created, so there was never a window in which it could be staged.
  `.env.example` is committed as the onboarding template.
- **Tool signature:** parameter-free, as expected. It returns
  `list[AssignedIssue]` (a pydantic model), not `list[dict]` — see below.

## What we built

Iteration 1 put everything in `mcp_server.py`. Rather than grow that file,
this iteration split it along the boundary that matters — MCP on one side,
GitHub on the other:

- `triage_git_mcp/config.py` — `Settings` (frozen dataclass) plus
  `load_settings()`. Validation is a pure classmethod so it's testable
  without touching the real environment; `.env`/`os.environ` reading is the
  impure edge. An **empty** `GITHUB_TOKEN` counts as missing, which matters:
  a freshly copied `.env` has `GITHUB_TOKEN=`, and `os.environ[...]` would
  have happily returned `""` and failed much later as a confusing 401.
- `triage_git_mcp/models.py` — the `AssignedIssue` pydantic model.
- `triage_git_mcp/github_client.py` — `GitHubIssueClient`, holding all HTTP
  and JSON-shape knowledge. Session/api_root/timeout are injected with
  defaults, so tests stub the transport and iteration 5 can swap in a
  rate-limit-aware session without touching the class.
- `mcp_server.py` — now just the composition root: load config, build the
  client, register `echo` (unchanged from iteration 1) and
  `list_my_assigned_issues`, run stdio.
- `tests/` + `requirements-dev.txt` — 12 pytest unit tests over the parsing
  rules and config validation, no network required.

The API call itself: `GET https://api.github.com/issues` with
`filter=assigned`, `state=all`, `per_page=100`, and headers
`Authorization: Bearer <PAT>`, `Accept: application/vnd.github+json`,
`X-GitHub-Api-Version: 2022-11-28`.

Two things that weren't obvious going in:

- **`/issues` returns pull requests too**, because GitHub models a PR as an
  issue. Only PRs carry a `pull_request` key, so we filter on that. Without
  it, "your issues" silently includes every PR assigned to you.
- **`state=all` is required.** The endpoint defaults to open-only, whereas
  the spec here wants both. By contrast `filter=assigned` *is* the default,
  but we pass it explicitly so the intent is readable.

### Why a pydantic model instead of `list[dict]`

The plan originally called for a plain `list[dict]` as the simpler option.
Checking the generated schema changed the answer: the MCP SDK derives a
tool's **output schema** from its return annotation, so `list[AssignedIssue]`
tells the host each field's name, type and description, while `list[dict]`
tells it nothing. That's a functional difference in what the host's model
knows, not just typing hygiene — so the model earns its keep now rather than
in iteration 3.

Related trap found the same way: a pydantic model's *docstring* becomes the
schema's `description`, which is sent to the host. Internal notes ("iteration
3 will add labels…") were leaking into it, and now live in `#` comments.

## PAT setup

Classic PAT with the **`repo`** scope (Settings → Developer settings →
Personal access tokens → Tokens (classic)). `public_repo` alone is not
enough if any assigned issue lives in a private repo.

Fine-grained PATs are a poor fit for *this* tool: they require selecting
specific repositories up front (plus org-owner approval for org-owned ones),
which contradicts "everything assigned to me, everywhere." Worth revisiting
in iteration 5 alongside the broader auth question.

## How we verified it

1. **Unit tests** — `python -m pytest tests/`, 12 passing. Covers field
   mapping, PR filtering, query params, auth header, and the config rules
   (including that HTTP errors propagate rather than being swallowed).
2. **Headless stdio client** — spawned `mcp_server.py` as a subprocess with
   a dummy token and called `list_tools()`: both `echo` and
   `list_my_assigned_issues` register, the latter with an empty input schema
   and a fully described `AssignedIssue` output schema.
3. **Startup failure path** — ran the server with the real (empty) `.env`
   and confirmed it exits immediately with
   `ConfigError: GITHUB_TOKEN is not set. Copy .env.example to .env...`.

Two more MCP SDK v2 naming changes surfaced while writing the stdio check
(recorded in `docs/CLAUDE.md`): the protocol models use snake_case
`tool.input_schema` / `tool.output_schema`, not the wire format's camelCase.

## Status: Implemented, pending live verification

Everything above is verified. What's **not** yet done is the bar this
iteration actually sets — a real token, hitting real GitHub, returning real
issues:

- [ ] Paste a real classic PAT into `.env`
- [ ] Call `list_my_assigned_issues` and check titles/URLs against github.com
- [ ] Ask Claude Desktop "what issues are assigned to me?" and confirm the
      round trip (no config change needed — it already points at
      `mcp_server.py` from iteration 1)

Flip this to `Done`, and the row in `00-overview.md` with it, once those pass.
