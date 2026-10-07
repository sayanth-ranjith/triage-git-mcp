# Code-standards / SOLID review

## Context

After iteration 4 you asked for a review of the whole repo against coding
standards, SOLID and design patterns, with fixes made after a plan. The
yardstick is the repo's own `docs/CLAUDE.md` "Design principles" (SRP,
MCP-agnostic core, DIP, pure core / impure shell, fail fast with an
actionable message, let types do real work, YAGNI).

**Overall verdict:** the structure is already sound. The composition root
is `mcp_server.py`. Config is split into a pure and an impure half.
Collaborators are injected (`session`, `api_root`, `timeout`). The core
never imports MCP. `GitHubIssueClient` is a clean Gateway, and tests use
stubs rather than the network. The findings below are the places that drift
from those principles. No new layers are needed, and adding them would break
YAGNI.

**Outcome:** the same behaviour, the same tool schemas apart from two
intended enum additions, all 56 tests still passing, and the standards
enforced by a linter instead of by memory.

## Findings and fixes (priority order)

### 1. Errors don't reach the host (breaks "fail fast with an actionable message")
`ValueError`s such as "pass repo or org, not both" or "repo must look like
'owner/name'" reach the host as only `Error executing tool <name>`. The SDK
hides the text of unexpected exceptions and only passes on messages from its
own `ToolError` (`venv/.../mcp/server/mcpserver/exceptions.py:43`).
- **Fix in `mcp_server.py` only.** A small `_tool_errors` context manager or
  decorator turns `ValueError` into `ToolError(str(exc))`. The core stays
  MCP-agnostic and keeps raising `ValueError`.
- Scope: input validation only. HTTP, auth and rate-limit errors are still
  iteration 5's.

### 2. Types not doing their job ("let types do real work")
- `AssignedIssue.state` / `IssueDetail.state` are `str`, but GitHub only
  sends `open` or `closed`. Make them `Literal["open", "closed"]` so the host
  sees an enum.
- `LinkedPullRequest.status: str` and `_pull_request_status -> str` become
  `Literal["open", "draft", "merged", "closed"]`.
- `IssueState` is a data shape but lives in `github_client.py`, so
  `mcp_server.py` imports a type from the HTTP module. Move it to
  `models.py`.
- `priority.py` has two `# type: ignore[return-value]`. Replace them with a
  typed `dict[str, Severity]` lookup so the type checker is satisfied
  without the ignores.

### 3. `github_client.py` mixes two jobs (SRP, "pure core, impure shell")
The file does HTTP and request orchestration, and it also maps GitHub JSON
into pydantic models (`_to_issue`, `_to_comment`, `_linked_pull_requests`,
`_pull_request_status`, `_labels`, `_truncate`, `_repo_from_html_url`, the
truncation constants). The mapping half is pure and grows with every
iteration.
- **New `triage_git_mcp/github_mapping.py`** holds the pure translation,
  including a `to_issue_detail(item, repo, comments, timeline)` that takes
  the `IssueDetail` construction out of `get_issue_details`.
- `github_client.py` keeps the session, auth headers, scope and endpoint
  choice, pagination, `_get_json` and login caching. It drops from about
  300 lines to about 150.
- `severity` and `priority` are worked out in one helper instead of being
  repeated in two places.
- Existing tests keep passing unchanged because behaviour doesn't change.
  Constants the tests import (`BODY_PREVIEW_CHARS`, `TRUNCATION_MARKER`, …)
  move with the mapping, and the test imports are updated to match.

### 4. Repeated fields in the models (DRY)
`AssignedIssue` and `IssueDetail` both declare title, repo, number, url,
state, labels, severity, priority, updated_at and comment_count. A shared
base `_IssueFields(BaseModel)` holds those, and both models extend it. The
output schemas have the same fields and descriptions; only the field order
changes.

### 5. Standards aren't enforced (coding standards)
There is no linter, formatter or `pyproject.toml`, so style holds only
because people remember it.
- Add `pyproject.toml` with a `ruff` config: line length 100, rule sets `E`,
  `F`, `I` (import order), `UP`, `B`, `SIM`. Add `ruff` to
  `requirements-dev.txt`.
- Run `ruff check --fix` and `ruff format` once, and fix whatever's left.
  Expect small diffs, since no line is over 100 today.
- `main.py`: add a return type to `health()`.

### 6. MCP-specific: mark the tools as read-only
Both tools only read data. Passing
`annotations=ToolAnnotations(readOnlyHint=True)` to `@app.tool(...)` tells
hosts they're safe to call without asking for confirmation. It's one line
per tool and is a documented part of MCP.

### 7. README is out of date
It still says "MCP tools and GitHub issue-fetching logic described above are
still to come". Update the status, what it does, and how to run the MCP
server and tests, using the "Running it locally" section of `docs/CLAUDE.md`.

## Considered and deliberately not done (YAGNI)

- **Parameter object for the six filters:** the parameters are passed
  through in one place. Revisit if the filters keep growing.
- **Strategy classes for repo / org / all scopes:** three `if` branches in
  `_assigned_issues_scope` read better than three classes.
- **An abstract `IssueSource` interface for the client:** there's only one
  implementation, and tests already substitute the session.
- **Moving `_StubSession` to `conftest.py`:** only one test module uses it.

## Files

- Modified: `mcp_server.py`, `triage_git_mcp/github_client.py`,
  `triage_git_mcp/models.py`, `triage_git_mcp/priority.py`, `main.py`,
  `tests/test_github_client.py` (imports only), `requirements-dev.txt`,
  `README.md`, `docs/CLAUDE.md` (module list).
- New: `triage_git_mcp/github_mapping.py`, `pyproject.toml`.

## Verification

1. Before changing anything, dump both tools' input and output schemas to
   the scratchpad. Afterwards dump them again and diff. The only expected
   differences are the new enums on `state` and `status` and field order.
2. `python -m pytest tests/`: 56 pass. Add tests for the
   `ValueError`→`ToolError` conversion, through an in-process MCP client
   session.
3. `ruff check .` and `ruff format --check .` are clean.
4. Live: `scripts/try_mcp.py` plus the iteration-4 filter calls give the
   same results as before. Passing `repo` and `org` together now returns
   "pass repo or org, not both" to the host.

## Status: Done

All seven fixes are in. Verified:

- [x] Schema diff, before vs after: the only changes are the read-only
      annotations on both tools, the enums on `state` and PR `status`, and
      `IssueDetail`'s field order. Descriptions are unchanged.
- [x] `pytest`: 59 pass (the 56 from before plus 3 in `tests/test_mcp_server.py`).
- [x] `ruff check .` and `ruff format --check .` are clean. The first run
      also caught `pytest.raises(Exception)` in `test_config.py`, which would
      have passed on any error; it now expects `FrozenInstanceError`.
- [x] Live, against real GitHub: every iteration-4 filter call returns the
      same issues as before. Passing `repo` and `org` together now gives the
      host "pass repo or org, not both" instead of a bare "Error executing
      tool".

Side effects worth knowing:

- pydantic's `ValidationError` subclasses `ValueError`, so if GitHub ever
  returns something a model rejects (say a new `state` value), the host will
  see that validation message rather than a bare error. That's arguably
  better, but iteration 5 should decide the error policy as a whole.
- `github_client.py` went from 302 to about 180 lines; `github_mapping.py`
  is about 150.
