# Iteration 4: Filtering and scoping

## Goal

Let queries narrow down to specific repos/orgs, and filter by label or
status, instead of always returning every assigned issue everywhere.

## Why this next

This is explicitly called out as future work in the README once the core
flow works. It only becomes valuable once iterations 2–3 already return
real, rich issue data — filtering an empty or bare-bones result isn't worth
building yet. For anyone assigned issues across many repos or orgs, an
unscoped "what's on my plate" answer stops being useful fast, so this is
what makes the tool viable day-to-day rather than a demo.

## What we'll build

- Extend `list_my_assigned_issues` with optional parameters: `repo`, `org`,
  `labels`, `state`, `updated_since` and `priority`.
- Default to open issues only.
- Apply filters on GitHub's side wherever GitHub supports them, instead of
  fetching everything and filtering in Python.
- Derive a `priority` for every issue from its sev1–sev4 marking, with
  `medium` when there is none.

## Out of scope (for now)

- Several repos in one call, OR'd labels, created-date ranges. All of these
  would need the Search API (see decisions).
- A `list_repo_labels` discovery tool. Only worth adding if the model turns
  out to guess label names wrong.
- Pagination beyond page 1 (100 issues). That's iteration 5.
- Saved/default scopes or user preferences persisted across sessions — if
  that turns out to be wanted, it's a later iteration.
- A GitHub Action in cheese-retry that turns the sev checkbox into a label.
  That's a change to that repo, not to this server.
- Auth/resilience work — iteration 5.

## What "done" looks like

You can ask "what's on my plate in `org/repo`?" or "show me my high-priority
bugs" and get a correctly filtered answer, verified against what filtering
the same way on github.com would show.

## New concepts we'll hit here

- **MCP tool parameters/schemas**: how a host knows what arguments a tool
  accepts, and how it maps natural language ("high priority bugs") to
  structured filter values (a specific label name). Parameters annotated
  with `Literal[...]` show up as enums in the tool's input schema, so the
  host's model sees exactly which values are allowed.

## Decisions made

| Question | Decision |
|---|---|
| Single tool with lots of optional parameters, or several narrower tools? | **One tool.** `list_my_assigned_issues` gains optional parameters. The host's model is good at filling in optional parameters, and several near-identical tools would make it harder for the model to choose. |
| How to scope to a repo/org? | **Pick the endpoint by scope** (table below). Every GitHub-side filter runs on GitHub in 1 request, with the same response shape and the normal rate limit. We're not using the Search API, which has a separate 30 requests/min limit, can return slightly stale results, and needs a query builder. Cost: one repo *or* one org per call. |
| Default state | **Open only.** `state` is `open` / `closed` / `all`, default `open`. "What's on my plate?" means open work. |
| Date filter | **`updated_since` only**, which maps to GitHub's `since` param. All three endpoints support it. |
| Do label/status names need to be fuzzy-matched? | **No, exact, on GitHub's side.** Several labels are matched with AND (GitHub's comma-list behaviour). Mapping "urgent" to the label a repo really uses is the model's job. |
| Severity / priority | **Every issue gets a `priority`.** If a sev1–sev4 is present it is mapped (below). Otherwise the priority is `medium`. Only cheese-retry's issue form has the sev checkbox today, so for most repos this will be `medium` with `severity: null`. |

### Tool signature

```python
list_my_assigned_issues(
    repo: str | None = None,          # 'owner/name'
    org: str | None = None,
    labels: list[str] | None = None,  # AND, exact names
    state: Literal["open", "closed", "all"] = "open",
    updated_since: datetime | None = None,
    priority: list[Literal["critical", "high", "medium", "low"]] | None = None,
) -> list[AssignedIssue]
```

Passing both `repo` and `org` raises `ValueError` before any request is
made (fail fast).

### Endpoint per scope (`github_client.py`)

| Scope | Endpoint | Assignee param |
|---|---|---|
| none | `GET /issues` | `filter=assigned` |
| `org` | `GET /orgs/{org}/issues` | `filter=assigned` |
| `repo` | `GET /repos/{owner}/{name}/issues` | `assignee=<login>` |

- All three send `state`, `labels` (comma-joined), `since` (ISO 8601) and
  `per_page=100`, and all skip PRs with the existing `_is_pull_request`.
- `repo` is validated with the existing `_split_repo`.
- **Verified while building: the repo endpoint rejects `assignee=@me`**
  (422 Validation Failed). So the client looks up the login once with
  `GET /user` and caches it. That costs 1 extra request, on the first
  repo-scoped call only.
- The repo endpoint also leaves the `repository` key out of each issue, so
  the summary takes its `repo` from the issue URL when the key is missing.

### Priority (new pure module, e.g. `triage_git_mcp/priority.py`)

- **Where sev comes from, in order:**
  1. a label named `sev1`–`sev4`
  2. a **ticked** checkbox in the body, e.g. `- [x] sev1` (`x` or `X`)

  The cheese-retry form lists all four options in every body, so unticked
  boxes (`- [ ] sev2`) must not match.
- **Mapping:**

  | Severity | Priority |
  |---|---|
  | sev1 | `critical` |
  | sev2 | `high` |
  | sev3 | `medium` |
  | sev4 | `low` |
  | none found | `medium` |

- **New fields** on both `AssignedIssue` and `IssueDetail`:
  - `severity`: `"sev1"` … `"sev4"`, or `null` when none was found
  - `priority`: always set

  `severity: null` tells the model that `medium` is the default, not
  something the issue actually said.
- **Parse the full body, before truncating it.** The `/issues` response
  already includes the full body. On cheese-retry #12 the ticked sev4 comes
  after the 300-char preview cut, which is why the host wrongly reported
  "no severity set" in iteration 3's live run.
- **The `priority` filter runs in Python** after the fetch, because GitHub
  can't filter on body text. This is a deliberate exception to "filter on
  GitHub's side". Caveat: until iteration 5 adds pagination, it only sees
  page 1 (up to 100 issues).

### Tests to add

In `tests/test_github_client.py`:

- the right endpoint and params for each scope (none / org / repo)
- `state` defaults to `open`
- `labels` are comma-joined
- `updated_since` is sent as ISO 8601 `since`
- `repo` and `org` together are rejected before any request
- the `priority` filter keeps only matching issues

In a new `tests/test_priority.py`:

- sev from a label
- sev from a ticked checkbox, with unticked boxes ignored
- a label wins over the body
- nothing found gives `medium` with `severity=None`
- a sev found after the 300-char preview cut is still picked up

## Status: Implemented, pending host verification

- [x] Verify whether `assignee=@me` works on the repo endpoint (it doesn't;
      see above)
- [x] Implement the scoped endpoints and filter params
- [x] Implement priority parsing and the `priority` filter
      (`triage_git_mcp/priority.py`)
- [x] Unit tests for all of the above (56 passing, up from 29)
- [x] With a real token, through the MCP server over stdio: the default call
      returns open issues only (#2 is gone), `repo=sayanth-ranjith/cheese-retry`
      returns only #13 and #12, `labels=["bug"]` plus
      `priority=["critical","high"]` returns only #13, and #12 shows
      sev4 / `low`
- [ ] In a host chat: ask "what's on my plate in
      `sayanth-ranjith/cheese-retry`?" and "show me my high-priority bugs",
      and check that the host picks the right parameters
- [ ] `org` scope against a real org (no org to test with yet; unit-tested
      only)

### Noticed while building (for iteration 5)

- When a tool raises an error such as `ValueError` ("pass repo or org, not
  both"), the host only sees `Error executing tool <name>`. The MCP SDK hides
  the text of unexpected exceptions and only passes on messages from its own
  `ToolError`. This already affected `get_issue_details` in iteration 3.
- Parameter descriptions live in the tool docstring's `Args:` section, which
  the host reads as part of the tool description. The SDK doesn't copy them
  into each parameter's input-schema entry, but the enums and types are
  there.
