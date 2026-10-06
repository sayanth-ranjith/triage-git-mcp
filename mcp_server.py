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
from datetime import datetime

from mcp.server.mcpserver import MCPServer

from triage_git_mcp.config import load_settings
from triage_git_mcp.github_client import DEFAULT_COMMENT_LIMIT, GitHubIssueClient, IssueState
from triage_git_mcp.models import AssignedIssue, IssueDetail
from triage_git_mcp.priority import Priority

# Resolved once at startup, so a misconfigured token fails immediately with
# an actionable message rather than on a host's first tool call.
_settings = load_settings()
_github = GitHubIssueClient(_settings.github_token)

app = MCPServer("triage-git-mcp")


# Issue detail is a tool rather than an MCP resource: resources are picked by
# the host or user, while tools can be called by the model on its own — and
# "dig into the issue that looks most urgent" is the model's decision to make.
# One tool with optional filters, rather than one tool per filter: near-
# identical tools make it harder for the host's model to pick the right one.
# The Literal annotations become enums in the input schema, so the host sees
# exactly which values are allowed.
@app.tool()
def list_my_assigned_issues(
    repo: str | None = None,
    org: str | None = None,
    labels: list[str] | None = None,
    state: IssueState = "open",
    updated_since: datetime | None = None,
    priority: list[Priority] | None = None,
) -> list[AssignedIssue]:
    """List the GitHub issues assigned to you, optionally filtered.

    With no arguments, returns your open issues across every repository you
    have access to. Each issue comes with enough to rank it (labels,
    priority, last update, comment count and the start of its description)
    but not the full discussion. Call get_issue_details on the ones worth a
    closer look.

    Args:
        repo: Only issues in this repository, as 'owner/name'. Can't be
            combined with org.
        org: Only issues in this organization's repositories. Can't be
            combined with repo.
        labels: Only issues that have ALL of these labels. Names must match
            the repository's labels exactly, e.g. 'bug'.
        state: 'open' (default), 'closed' or 'all'.
        updated_since: Only issues updated at or after this time (ISO 8601).
        priority: Only issues with one of these priorities. Priority comes
            from a sev1-sev4 label or ticked checkbox; issues without one
            count as 'medium'. For "high priority" use ['critical', 'high'].
    """
    return _github.list_assigned_issues(
        repo=repo,
        org=org,
        labels=labels,
        state=state,
        updated_since=updated_since,
        priority=priority,
    )


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
