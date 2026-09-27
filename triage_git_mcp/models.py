"""The data shapes this server hands back.

These are typed models rather than bare dicts because the MCP SDK derives a
tool's *output schema* from its return annotation. A host (and the model
driving it) is then told what the fields mean, instead of receiving
anonymous JSON it has to guess at — so the annotations here are
functionality, not decoration.
"""

from pydantic import BaseModel, Field


# Note: a model's docstring becomes the `description` in the JSON schema the
# host sees, so these docstrings are written for that audience. Internal
# notes belong in comments like this one — deliberately minimal for
# iteration 2; description, labels, comments and linked PRs arrive in
# iteration 3 (docs/plan/03-enrich-issue-context.md).
class AssignedIssue(BaseModel):
    """A GitHub issue assigned to the authenticated user."""

    title: str = Field(description="The issue title.")
    repo: str = Field(description="Repository the issue lives in, as 'owner/name'.")
    url: str = Field(description="Link to the issue on github.com.")
    state: str = Field(description="Either 'open' or 'closed'.")
