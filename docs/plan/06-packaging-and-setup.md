# Iteration 6: Packaging and setup

## Goal

Make this usable by someone other than the person who built it: get it
wired into Copilot's MCP configuration, and write real setup docs replacing
the README's "coming soon."

## Why this last

Everything before this made the server *work*. This iteration makes it
*usable* — installable, configurable, documented — which only makes sense
once the tools it exposes are stable. Polishing setup instructions for a
tool whose shape is still changing would mean rewriting them every
iteration.

## What we'll build

- Whatever config Copilot needs to discover and launch this server (an MCP
  server manifest/config entry, pointed at the right transport from
  [iteration 1](01-hello-mcp-server.md)).
- Clear setup docs in the README: install, configure your GitHub token,
  point Copilot at the server, verify it works.
- A decision on what happens to the original FastAPI `/health` endpoint —
  keep it as a standalone health check, fold it into the MCP server's own
  lifecycle, or drop it if it's no longer serving a purpose.

## Out of scope (for now)

- Publishing this anywhere beyond "clone and run locally" (e.g. packaging
  for a registry) — only worth doing if this turns out to be useful beyond
  personal use.

## What "done" looks like

Someone who isn't us can clone this repo, follow the README, and get
"what's on my plate?" working against their own GitHub account, without
needing to ask us anything.

## New concepts we'll hit here

- How MCP hosts discover/launch servers in practice (config file format,
  where it lives, how the host passes secrets like the GitHub token).

## Open questions to resolve in this iteration

- Does the GitHub token get passed via env var in the host config, or does
  the server prompt for it some other way?
- Is there anything left in `main.py`'s FastAPI scaffold worth keeping once
  the MCP server is the real entry point?
