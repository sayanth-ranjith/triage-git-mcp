# Build plan: overview

This folder tracks how we're building `triage-git-mcp`, one iteration at a
time. Each file is one iteration: what we're building in it, why we're
building it *then* and not earlier/later, and what "done" looks like.

## Why iterations, and why this order

The end goal (per the [README](../../README.md)) is an MCP server that lets
GitHub Copilot answer "what's on my plate?" with real context — not just
issue titles, but labels, status, comments, linked PRs.

That's a few genuinely separate problems stacked on top of each other:

1. Speaking MCP correctly, so a host (Copilot) can even talk to this server
2. Talking to GitHub's API and getting *something* back
3. Turning "something" into the rich context that's actually the point of
   this project
4. Making results scoped/filterable instead of a firehose
5. Making it robust enough to trust (auth, errors, rate limits)
6. Making it usable by someone who isn't the person who wrote it

Bundling those together is how a first MCP project stalls — you end up
debugging protocol issues and GitHub API issues and data-shaping issues all
at once. So each iteration below isolates one of these, in an order where
each step is checkable on its own before the next one adds complexity.

## Iterations

| # | File | What it's about | Status |
|---|------|------------------|--------|
| 1 | [`01-hello-mcp-server.md`](01-hello-mcp-server.md) | Stand up the smallest possible MCP server and connect a host to it | Done |
| 2 | [`02-fetch-assigned-issues.md`](02-fetch-assigned-issues.md) | First real tool: list issues assigned to you, bare-bones fields | Not started |
| 3 | [`03-enrich-issue-context.md`](03-enrich-issue-context.md) | Add the context that makes this useful — description, labels, comments, linked PRs | Not started |
| 4 | [`04-filtering-and-scoping.md`](04-filtering-and-scoping.md) | Scope to specific repos/orgs, filter by label/status | Not started |
| 5 | [`05-auth-and-resilience.md`](05-auth-and-resilience.md) | Move past a raw personal access token, handle rate limits and errors | Not started |
| 6 | [`06-packaging-and-setup.md`](06-packaging-and-setup.md) | Wire it into Copilot's MCP config, write real setup docs | Not started |

## How to use this folder

- Update a file's content as decisions actually get made in that iteration —
  this isn't a spec written up front and left to rot, it's a running record.
- Flip the status in the table above (`Not started` → `In progress` → `Done`)
  as we go.
- If an iteration turns out to be wrong-sized (too big, or two iterations
  that should've been one), split/merge the files and update this table —
  don't silently drift from what's written here.
