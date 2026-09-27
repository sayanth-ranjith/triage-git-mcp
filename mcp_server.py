"""MCP entry point: exposes the GitHub client to a host as callable tools.

This is the composition root — the one module that reads configuration and
picks the concrete client the tools use. Tool functions stay thin on
purpose: the work they'd otherwise do inline (HTTP, auth, parsing) lives in
`triage_git_mcp`, where it can be tested without a server.
"""

# MCP SDK v2 renamed the high-level server class from FastMCP to MCPServer.
# Most tutorials online still show `from mcp.server.fastmcp import FastMCP`;
# under v2 that module is a tombstone that raises ModuleNotFoundError with a
# pointer to the migration guide. MCPServer *is* FastMCP, renamed.
from mcp.server.mcpserver import MCPServer

from triage_git_mcp.config import load_settings
from triage_git_mcp.github_client import GitHubIssueClient
from triage_git_mcp.models import AssignedIssue

# Resolved once at startup, so a misconfigured token fails immediately with
# an actionable message rather than on a host's first tool call.
_settings = load_settings()
_github = GitHubIssueClient(_settings.github_token)

app = MCPServer("triage-git-mcp")


# Iteration 1's one tool: proves both the call path and argument passing
# work, ahead of any real GitHub-backed tools.
@app.tool()
def echo(text: str) -> str:
    return text


@app.tool()
def list_my_assigned_issues() -> list[AssignedIssue]:
    """List the GitHub issues currently assigned to you.

    Covers every repository you have access to, and includes both open and
    closed issues. Returns the essentials only: title, repository, link and
    state.
    """
    return _github.list_assigned_issues()


if __name__ == "__main__":
    # Defaults to stdio transport, matching how local hosts (Claude
    # Desktop, VS Code) launch MCP servers as a subprocess.
    app.run()
