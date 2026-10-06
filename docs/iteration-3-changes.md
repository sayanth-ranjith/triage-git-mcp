# Iteration 3: what changed

Iteration 3 ("enrich issue context") is built. This doc covers what changed
and why. The proposal it follows is [`next-iteration.md`](next-iteration.md),
and the decisions are recorded in
[`plan/03-enrich-issue-context.md`](plan/03-enrich-issue-context.md).

## In one sentence

The server now gives back enough to **rank** your issues in one cheap call,
and enough to **decide what to do** about any one of them in a second call.

## Before and after

```
BEFORE                                   AFTER
──────                                   ─────
echo(text)                               (removed)

list_my_assigned_issues()                list_my_assigned_issues()       ← still 1 GitHub request
  → title, repo, url, state                → title, repo, url, state,
                                             number, labels, updated_at,
                                             comment_count, body_preview

                                         get_issue_details(repo, number, max_comments=10)   ← NEW
                                           → everything about one issue:
                                             full body, author, assignees,
                                             milestone, dates, state_reason,
                                             recent_comments[],
                                             linked_pull_requests[] (with status)
```

A typical conversation now looks like this:

1. *"What's on my plate?"* The host calls `list_my_assigned_issues` and
   ranks the issues by labels, how recently they changed, and the preview.
2. *"Tell me more about #12"*, or the model decides to dig in by itself. The
   host calls `get_issue_details("owner/repo", 12)` and sees the discussion
   and whether a PR already exists.

## File-by-file

### `triage_git_mcp/models.py`

- **`AssignedIssue`** (the summary) gained `number`, `labels`, `updated_at`,
  `comment_count` and `body_preview`. All of these were already in the
  `/issues` response we were fetching. Before, we threw them away.
- **New `IssueDetail`** is the full picture of one issue.
- **New `IssueComment`** holds `author`, `created_at`, `body` and `url`.
- **New `LinkedPullRequest`** holds `repo`, `number`, `title`, `url` and
  `status`, where `status` is one of `open` / `draft` / `merged` / `closed`.

Every field has a `description=`. The MCP SDK turns these models into the
tool's output schema, so the descriptions are what the host's model reads.

### `triage_git_mcp/github_client.py`

- `_to_issue` maps the new summary fields.
- **New `get_issue_details(repo, number, *, comment_limit=10)`** makes
  3 GitHub requests:
  1. `GET /repos/{owner}/{repo}/issues/{n}`: the issue itself
  2. `GET .../issues/{n}/comments`: the most recent comments (skipped if
     there are none)
  3. `GET .../issues/{n}/timeline`: used to find linked PRs
- **How it gets the most recent comments:** GitHub returns comments oldest
  first and can't reverse the order. Since we already know the total count
  from request 1, we compute the last page and fetch that page directly. If
  the last page is too short (for example, 102 comments puts only 2 on
  page 2), we also fetch the page before it. That is at most 2 requests,
  however long the thread is.
- **How it finds linked PRs:** it looks for `cross-referenced` events in the
  timeline whose source is a PR. Each event already embeds that PR's state,
  draft flag and `merged_at`, so getting the status costs **no extra
  requests**. If a PR mentions the issue more than once, it is listed once.
- **Truncation**, so long text doesn't flood the host's context:
  | What | Cap |
  |---|---|
  | `body_preview` (summary) | 300 chars |
  | `body` (detail) | 4,000 chars |
  | each comment | 1,000 chars |
  | comments returned | 10 by default, host may ask for 0–100 |

  Cut text ends with ` …[truncated]` so the model knows it is incomplete.
- **Input validation:** a `repo` that isn't `owner/name` raises `ValueError`
  before any request is made.
- `_get_json` now accepts no params and returns `Any`, because the detail
  endpoint returns an object where the list endpoint returns a list.
- Small edge cases are handled: a `null` body becomes `""`, and a comment
  from a deleted account is attributed to `ghost`, which is what github.com
  shows.

### `mcp_server.py`

- **Removed `echo`.** It was there to prove the plumbing worked in
  iteration 1. The real tools prove that now.
- **Added `get_issue_details`**, a one-line delegation to the client like the
  other tool.
- The docstring for `list_my_assigned_issues` now tells the model to call
  `get_issue_details` for more. Docstrings are what the host's model reads,
  so this is how the two tools get used together.

### `tests/test_github_client.py`

- The stub session can now send different payloads to different URLs, and
  it paginates comments the way GitHub does.
- 17 new tests, **29 passing** in total. They cover summary field mapping,
  preview truncation, null bodies, detail mapping, body truncation, no
  comments request when the count is 0, newest-N comment selection, comments
  across a page boundary, the `ghost` author, all four PR statuses, ignoring
  non-PR references and duplicates, and rejecting malformed `repo` values.

### Docs

- `plan/03-enrich-issue-context.md` has a "Decisions made" section and a
  verification checklist.
- `plan/00-overview.md` marks iteration 3 as *Implemented, pending live
  verification*.
- `CLAUDE.md` "Where we are" now describes the current tools and models.

## MCP concept: why detail is a tool and not a resource

MCP has two ways to expose data:

- **Tools** are functions the *model* can decide to call by itself.
- **Resources** are readable data, usually attached by the *host app or the
  user*, such as picking a file to add to context.

Deciding which issue deserves a closer look is part of the reasoning we want
the model to do. So `get_issue_details` is a tool. If it were a resource,
the user would have to attach it by hand.

## Request cost (for iteration 5)

| Call | GitHub requests |
|---|---|
| `list_my_assigned_issues` | 1 |
| `get_issue_details` | 3 (2 if no comments; 4 if recent comments cross a page boundary) |

If we had fetched everything up front, 50 issues would cost about 101
requests per question. With this design it costs 1 request, plus about 3 for
each issue the model actually opens.

## Known gaps (deliberately left for later)

- The timeline is read only up to its first page (100 events). On a very
  busy issue, a PR that linked it later may be missed. Marked
  `TODO(iteration 5)`.
- The issue list is still page 1 only, includes both open and closed
  issues, and has no filters. These are for iterations 4 and 5.
- **Not yet checked against real GitHub.** Everything above is unit-tested,
  and both tools register with full schemas, but a live run with a real
  token is still needed (see the checklist in the plan file).
