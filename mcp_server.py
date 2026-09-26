from mcp.server.mcpserver import MCPServer

app = MCPServer("triage-git-mcp")


@app.tool()
def echo(text: str) -> str:
    return text


if __name__ == "__main__":
    app.run()
