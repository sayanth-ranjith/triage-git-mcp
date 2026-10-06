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
from triage_git_mcp.github_client import DEFAULT_COMMENT_LIMIT, GitHubIssueClient
from triage_git_mcp.models import AssignedIssue, IssueDetail

# Resolved once at startup, so a misconfigured token fails immediately with
# an actionable message rather than on a host's first tool call.
_settings = load_settings()
_github = GitHubIssueClient(_settings.github_token)

app = MCPServer("triage-git-mcp")


# Issue detail is a tool rather than an MCP resource: resources are picked by
# the host or user, while tools can be called by the model on its own — and
# "dig into the issue that looks most urgent" is the model's decision to make.
@app.tool()
def list_my_assigned_issues() -> list[AssignedIssue]:
    """List the GitHub issues currently assigned to you.

    Covers every repository you have access to, and includes both open and
    closed issues. Each issue comes with enough to rank it (labels, last
    update, comment count and the start of its description) but not the full
    discussion. Call get_issue_details on the ones worth a closer look.
    """
    return _github.list_assigned_issues()


@app.tool()
def get_issue_details(
    repo: str, number: int, max_comments: int = DEFAULT_COMMENT_LIMIT
) -> IssueDetail:
    """Get full context for one GitHub issue.

    Returns the complete description, the most recent comments, and any pull
    requests that reference the issue with their status (open, draft, merged
    or closed). Use it after list_my_assigned_issues to dig into one issue.

    Args:
        repo: Repository as 'owner/name', e.g. 'octocat/hello-world'.
        number: The issue number within that repository.
        max_comments: How many of the most recent comments to include (0-100).
    """
    return _github.get_issue_details(repo, number, comment_limit=max_comments)


if __name__ == "__main__":
    # Defaults to stdio transport, matching how local hosts (Claude
    # Desktop, VS Code) launch MCP servers as a subprocess.
    app.run()
