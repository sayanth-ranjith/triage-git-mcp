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
