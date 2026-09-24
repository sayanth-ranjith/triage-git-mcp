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

- Extend the MCP tool(s) to accept parameters: repo, org, label, state
  (open/closed/all), maybe a date range.
- Decide sensible defaults (e.g. open issues only, unless asked otherwise).
- Update the GitHub API call(s) to apply these filters server-side where
  possible, rather than fetching everything and filtering in Python.

## Out of scope (for now)

- Saved/default scopes or user preferences persisted across sessions — if
  that turns out to be wanted, it's a later iteration.
- Auth/resilience work — iteration 5.

## What "done" looks like

You can ask "what's on my plate in `org/repo`?" or "show me my high-priority
bugs" and get a correctly filtered answer, verified against what filtering
the same way on github.com would show.

## New concepts we'll hit here

- **MCP tool parameters/schemas**: how a host knows what arguments a tool
  accepts, and how it maps natural language ("high priority bugs") to
  structured filter values (a specific label name).

## Open questions to resolve in this iteration

- Do label/status names need to be fuzzy-matched (user says "urgent," repo
  uses label "P0") or exact?
- Single tool with lots of optional parameters, or several narrower tools?
