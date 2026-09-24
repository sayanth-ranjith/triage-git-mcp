# Iteration 1: Hello, MCP server

## Goal

Get the smallest possible MCP server running, and get a host (an MCP client
like Claude Desktop, or Copilot once it supports it) to actually connect to
it and call one trivial tool. No GitHub involved yet.

## Why this first

Neither of us has built an MCP server before. If iteration 1 is "fetch
GitHub issues over MCP," and it doesn't work, we won't know whether the bug
is in our understanding of MCP (tool registration, transport, how the host
discovers the server) or in the GitHub API call. Separating those means each
bug we hit only has one possible cause.

This is the "does the plumbing work at all" step.

## What we'll build

- A minimal MCP server (likely using the official MCP SDK for Python) with
  exactly one tool — something like `ping` that returns a fixed string, or
  `echo` that returns whatever you pass it.
- Whatever transport the host we're testing against expects (MCP supports a
  few — stdio is the common one for local dev tools).
- A host configured to launch this server and call the tool, so we can see
  the round trip actually happen.

## Out of scope (for now)

- Anything GitHub-related
- The existing FastAPI `/health` app — we haven't yet decided whether MCP
  runs inside it, alongside it, or replaces it. That decision can wait until
  we understand what MCP actually needs.
- Real error handling, auth, config — this is a throwaway proof of plumbing.

## What "done" looks like

We can ask the connected host to call the tool, and see the response come
back, end to end. That's it — a working call is the whole bar here.

## New concepts we'll hit here

- **MCP host vs. MCP server**: the host (e.g. Copilot, Claude Desktop) is
  what the user talks to; the server (this repo) is what exposes tools the
  host can call on the user's behalf.
- **Tools**: functions the server exposes that the host can decide to call.
- **Transport**: how the host and server actually talk (stdio, HTTP/SSE,
  etc.) — this affects how the server gets launched and configured.

We'll fill in the specifics here as we actually learn them, rather than
guessing ahead of time.

## Open questions to resolve in this iteration

- Which MCP SDK are we using?
- Which transport, and why does that choice make sense for how Copilot will
  eventually launch this server?
- Does this replace `main.py`'s FastAPI app, wrap it, or run separately?
