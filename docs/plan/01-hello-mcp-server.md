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

## Resolved

- **SDK:** the official Python MCP SDK (`mcp[cli]` on PyPI, now at v2 —
  `pip install "mcp[cli]"`). It's the standard, most-maintained option.
  One surprise worth flagging: in SDK v2 the high-level server class was
  renamed from `FastMCP` to `MCPServer` (`mcp.server.mcpserver.MCPServer`)
  — most tutorials/examples online still reference `FastMCP`/`mcp.server.
  fastmcp`, which no longer exists in v2. The API itself (`@app.tool()`,
  `app.run()`) is unchanged.
- **Transport:** stdio (`app.run()` defaults to it). Local dev hosts launch
  MCP servers as a subprocess and talk over stdin/stdout — no port/network
  config needed, and it's what Copilot's own MCP config will expect later.
- **`main.py`:** left untouched. The server lives in a new `mcp_server.py`
  at the repo root, run independently. The FastAPI app and the MCP server
  are two separate processes for now; whether/how they merge is deferred to
  the packaging iteration.

## What we built

- `mcp_server.py`: an `MCPServer("triage-git-mcp")` with one tool, `echo(text:
  str) -> str`, returning the input unchanged.
- `mcp[cli]` added to `requirements.txt`.

## How we verified it

Two levels, both passing:

1. **Headless, scripted check** (fastest signal, no GUI/Node dependency):
   used `mcp.client.stdio.stdio_client` + `mcp.ClientSession` to spawn
   `mcp_server.py` as a subprocess, call `list_tools()`, then
   `call_tool("echo", {"text": "hello mcp"})` — got `echo` listed and the
   text echoed back correctly.
2. **Real host — Claude Desktop:** wire it up with either
   `mcp install mcp_server.py` (the SDK's CLI does this for you), or by
   hand-editing `claude_desktop_config.json`:

   ```json
   {
     "mcpServers": {
       "triage-git-mcp": {
         "command": "C:\\Users\\004IMY744\\Desktop\\triage-git-mcp\\venv\\Scripts\\python.exe",
         "args": ["C:\\Users\\004IMY744\\Desktop\\triage-git-mcp\\mcp_server.py"]
       }
     }
   }
   ```

   Restart Claude Desktop, confirm `triage-git-mcp` shows as connected, and
   call the `echo` tool from a chat to see the round trip live. (This step
   needs to be done interactively by whoever has Claude Desktop installed —
   it can't be scripted/verified headlessly.)

   The SDK also ships `mcp dev mcp_server.py`, which opens the MCP
   Inspector (a web UI, requires Node/npx) as an alternative way to
   exercise tools by hand without any host config at all.

## Status: Done

Verified live in Claude Desktop: asked it to use the `echo` tool, and
`triage-git-mcp: Echo` returned `"hello"` in chat. Full round trip confirmed
— host discovers the server, calls the tool, gets the result back.

One wrinkle worth recording: this machine's Claude Desktop is the Microsoft
Store (MSIX) build, so `mcp install` (which only knows the classic installer
path) couldn't find it. Its config actually lives at:

```
%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude_desktop_config.json
```

Same `mcpServers` schema as the classic config, just a different path — the
app's own Developer → "Add and manage MCPs" screen opens this same file for
hand-editing, which is how it was wired up here.

Next: iteration 2, the first real GitHub-backed tool.
