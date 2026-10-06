"""The data shapes this server hands back.

These are typed models rather than bare dicts because the MCP SDK derives a
tool's *output schema* from its return annotation. A host (and the model
driving it) is then told what the fields mean, instead of receiving
anonymous JSON it has to guess at — so the annotations here are
functionality, not decoration.
"""

from datetime import datetime

from pydantic import BaseModel, Field


# Note: a model's docstring becomes the `description` in the JSON schema the
# host sees, so these docstrings are written for that audience. Internal
# notes belong in comments like this one.
#
# Two shapes on purpose: `AssignedIssue` is the cheap summary (one GitHub
# request for the whole list), `IssueDetail` is the expensive drill-down
# (three requests per issue). See docs/plan/03-enrich-issue-context.md.
class AssignedIssue(BaseModel):
    """A GitHub issue assigned to the authenticated user, summarised for triage."""

    title: str = Field(description="The issue title.")
    repo: str = Field(description="Repository the issue lives in, as 'owner/name'.")
    number: int = Field(description="Issue number within its repository.")
    url: str = Field(description="Link to the issue on github.com.")
    state: str = Field(description="Either 'open' or 'closed'.")
    labels: list[str] = Field(description="Label names applied to the issue.")
    updated_at: datetime = Field(description="When the issue last changed.")
    comment_count: int = Field(description="Total number of comments on the issue.")
    body_preview: str = Field(
        description=(
            "The start of the issue description, truncated. Call "
            "get_issue_details for the full text."
        )
    )


class IssueComment(BaseModel):
    """One comment on an issue."""

    author: str = Field(description="GitHub login of the commenter.")
    created_at: datetime = Field(description="When the comment was posted.")
    body: str = Field(description="Comment text, truncated if very long.")
    url: str = Field(description="Link to the comment on github.com.")


class LinkedPullRequest(BaseModel):
    """A pull request that references the issue."""

    repo: str = Field(description="Repository the pull request lives in, as 'owner/name'.")
    number: int = Field(description="Pull request number.")
    title: str = Field(description="The pull request title.")
    url: str = Field(description="Link to the pull request on github.com.")
    status: str = Field(
        description="One of 'open', 'draft', 'merged' or 'closed' (closed without merging)."
    )


class IssueDetail(BaseModel):
    """Full context for one issue: description, discussion and linked pull requests."""

    title: str = Field(description="The issue title.")
    repo: str = Field(description="Repository the issue lives in, as 'owner/name'.")
    number: int = Field(description="Issue number within its repository.")
    url: str = Field(description="Link to the issue on github.com.")
    state: str = Field(description="Either 'open' or 'closed'.")
    state_reason: str | None = Field(
        description="Why it was closed ('completed', 'not_planned') or reopened, if known."
    )
    author: str = Field(description="GitHub login of whoever opened the issue.")
    assignees: list[str] = Field(description="GitHub logins of everyone assigned.")
    labels: list[str] = Field(description="Label names applied to the issue.")
    milestone: str | None = Field(description="Milestone title, if any.")
    created_at: datetime = Field(description="When the issue was opened.")
    updated_at: datetime = Field(description="When the issue last changed.")
    closed_at: datetime | None = Field(description="When the issue was closed, if it is.")
    body: str = Field(description="The issue description, truncated if very long.")
    comment_count: int = Field(
        description="Total comments on the issue; may exceed len(recent_comments)."
    )
    recent_comments: list[IssueComment] = Field(
        description="The most recent comments, oldest first."
    )
    linked_pull_requests: list[LinkedPullRequest] = Field(
        description="Pull requests that reference this issue. Empty means no PR exists yet."
    )
