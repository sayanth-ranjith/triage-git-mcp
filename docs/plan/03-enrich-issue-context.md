# Iteration 3: Enrich issue context

## Goal

Turn the bare-bones issue list from iteration 2 into the thing this project
is actually for: enough context to reason about priority and next steps
without leaving the editor. Add description, labels, status detail,
comments, and linked PRs to each issue.

## Why this next

Per the README, "the goal isn't just a list of titles" — this iteration is
where the project starts delivering on that. It only makes sense once
iteration 2 proves we can reliably fetch and return issues at all; enriching
data we can't yet fetch correctly would just compound debugging.

## What we'll build

- Expand the GitHub API call(s) to pull:
  - Full issue description/body
  - Labels
  - Comments (or at least a recent/relevant subset — full comment history
    could get long)
  - Linked/referenced PRs
- Decide how much of this to return by default vs. behind a "give me more
  detail on issue X" follow-up tool — returning everything for every issue
  up front may be more than a host needs for a first answer.
- Shape the tool's output so a host model can actually use it to reason
  about priority (e.g., structured fields it can act on, not a wall of raw
  text).

## Out of scope (for now)

- Filtering/scoping which issues get fetched — iteration 4.
- Performance/rate-limit concerns from fetching this much more data —
  iteration 5, though keep an eye on it here since this is where request
  volume goes up.

## What "done" looks like

Asking "what's on my plate?" returns issues with enough detail that you
could decide what to work on next *from the answer alone*, without opening
GitHub — which is the exact scenario from the README's "Why this exists"
section.

## New concepts we'll hit here

- **MCP resources vs. tools** (if relevant): MCP distinguishes tools
  (actions/queries a host calls) from resources (data a host can read) —
  worth understanding whether issue detail is better modeled as one or the
  other.
- Tradeoffs in how much context to hand an LLM host per call vs. per
  follow-up request.

## Open questions to resolve in this iteration

- Return everything in one call, or a summary tool plus a detail tool?
- How do we cap comment volume on issues with long discussion threads?
- Do linked PRs need their own status (open/merged/draft) included, or just
  a link?

## Decisions made

Implemented following the proposal in [`../next-iteration.md`](../next-iteration.md).
What changed, file by file, is in [`../iteration-3-changes.md`](../iteration-3-changes.md).

| Question | Decision |
|---|---|
| One call, or summary + detail? | **Summary + detail.** `list_my_assigned_issues` stays at one GitHub request and gains labels, number, `updated_at`, comment count and a 300-char body preview. New `get_issue_details(repo, number, max_comments=10)` fetches the rest on demand. |
| Capping comment volume | Newest **10** by default (host can ask for 0–100), each truncated to 1,000 chars, plus `comment_count` so the host knows more exist. Fetched by jumping to the last page rather than walking the thread. |
| Linked PRs: status or link? | **Status** (`open` / `draft` / `merged` / `closed`), read from the issue timeline's `cross-referenced` events — no extra request per PR. |
| Tool or resource? | **Tool.** Resources are chosen by the host/user; tools can be called by the model itself, and choosing which issue to dig into is the model's call. |
| REST or GraphQL? | **REST.** Detail costs 3 requests (4 if recent comments cross a page boundary). |
| `echo` tool | **Removed** — real tools now prove the plumbing. |

## Status: Implemented, pending live verification

- [x] Unit tests (29 passing) cover field mapping, truncation, comment
      paging, PR status, PR de-duplication and repo validation.
- [x] Server registers both tools with typed input/output schemas.
- [ ] With a real token: ask "what's on my plate?" and "tell me more about
      #N", and check both answers against github.com.
