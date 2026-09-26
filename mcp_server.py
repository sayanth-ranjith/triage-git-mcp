# MCP SDK v2 renamed the high-level server class from FastMCP to MCPServer;
# most MCP tutorials online still reference the old fastmcp module/name.
from mcp.server.mcpserver import MCPServer

app = MCPServer("triage-git-mcp")


# Iteration 1's one tool: proves both the call path and argument passing
# work, ahead of any real GitHub-backed tools.
@app.tool()
def echo(text: str) -> str:
    return text


if __name__ == "__main__":
    # Defaults to stdio transport, matching how local hosts (Claude
    # Desktop, VS Code) launch MCP servers as a subprocess.
    app.run()
