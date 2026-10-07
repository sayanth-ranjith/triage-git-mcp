"""Translate GitHub's JSON into this server's models.

Pure functions only: dicts in, pydantic models out, no HTTP. Fetching is
`github_client.py`'s job; keeping the two apart means a change to what we
return never touches how we fetch, and every rule here is testable from a
plain dict.
"""

from typing import Any

from triage_git_mcp.models import (
    AssignedIssue,
    IssueComment,
    IssueDetail,
    LinkedPullRequest,
    PullRequestStatus,
)
from triage_git_mcp.priority import find_severity, priority_for

# Caps on how much text goes back to the host. Long bodies and threads would
# otherwise crowd everything else out of the host model's context window.
BODY_PREVIEW_CHARS = 300
MAX_BODY_CHARS = 4000
MAX_COMMENT_CHARS = 1000
TRUNCATION_MARKER = " …[truncated]"


def is_pull_request(item: dict[str, Any]) -> bool:
    """GitHub models pull requests as issues, so `/issues` returns both.

    Only pull requests carry a `pull_request` key. The issue list skips
    them; `get_issue_details` surfaces them as a property *of* an issue.
    """
    return "pull_request" in item


def to_issue(item: dict[str, Any]) -> AssignedIssue:
    return AssignedIssue(
        **_shared_issue_fields(item),
        # The per-repo endpoint omits `repository` as redundant, so fall
        # back to the issue's URL, which always names the repo.
        repo=(item.get("repository") or {}).get("full_name")
        or _repo_from_html_url(item["html_url"]),
        body_preview=_truncate(item.get("body"), BODY_PREVIEW_CHARS),
    )


def to_issue_detail(
    item: dict[str, Any],
    *,
    repo: str,
    comments: list[dict[str, Any]],
    timeline: list[dict[str, Any]],
) -> IssueDetail:
    return IssueDetail(
        **_shared_issue_fields(item),
        repo=repo,
        state_reason=item.get("state_reason"),
        author=item["user"]["login"],
        assignees=[a["login"] for a in item.get("assignees") or []],
        milestone=(item.get("milestone") or {}).get("title"),
        created_at=item["created_at"],
        closed_at=item.get("closed_at"),
        body=_truncate(item.get("body"), MAX_BODY_CHARS),
        recent_comments=[_to_comment(c) for c in comments],
        linked_pull_requests=_linked_pull_requests(timeline),
    )


def _shared_issue_fields(item: dict[str, Any]) -> dict[str, Any]:
    """The fields both issue shapes read the same way (all but `repo`)."""
    labels = _labels(item)
    # Severity is read from the full body, before it is cut down to a
    # preview: the sev checkboxes usually sit at the end of the form.
    severity = find_severity(labels, item.get("body"))
    return {
        "title": item["title"],
        "number": item["number"],
        "url": item["html_url"],
        "state": item["state"],
        "labels": labels,
        "severity": severity,
        "priority": priority_for(severity),
        "updated_at": item["updated_at"],
        "comment_count": item["comments"],
    }


def _to_comment(item: dict[str, Any]) -> IssueComment:
    return IssueComment(
        # `user` is null when the commenter's account has been deleted.
        author=(item.get("user") or {}).get("login", "ghost"),
        created_at=item["created_at"],
        body=_truncate(item.get("body"), MAX_COMMENT_CHARS),
        url=item["html_url"],
    )


def _linked_pull_requests(timeline: list[dict[str, Any]]) -> list[LinkedPullRequest]:
    """PRs that mention this issue, from its `cross-referenced` timeline events.

    Each event embeds the referencing issue-or-PR itself, including its
    state, draft flag and merge time, so PR status costs no extra requests.
    """
    linked: dict[str, LinkedPullRequest] = {}
    for event in timeline:
        source = (event.get("source") or {}).get("issue")
        if event.get("event") != "cross-referenced" or not source:
            continue
        if not is_pull_request(source):
            continue  # mentioned by another issue, not a PR
        # A PR that mentions the issue more than once is listed once.
        linked[source["html_url"]] = LinkedPullRequest(
            repo=_repo_from_html_url(source["html_url"]),
            number=source["number"],
            title=source["title"],
            url=source["html_url"],
            status=_pull_request_status(source),
        )
    return list(linked.values())


def _pull_request_status(item: dict[str, Any]) -> PullRequestStatus:
    """Collapse GitHub's state/draft/merged_at into one status a host can act on."""
    if (item.get("pull_request") or {}).get("merged_at"):
        return "merged"
    if item["state"] == "closed":
        return "closed"
    if item.get("draft"):
        return "draft"
    return "open"


def _labels(item: dict[str, Any]) -> list[str]:
    return [label["name"] for label in item.get("labels") or []]


def _repo_from_html_url(html_url: str) -> str:
    # https://github.com/<owner>/<name>/pull/<n> -> "<owner>/<name>"
    return "/".join(html_url.split("/")[3:5])


def _truncate(text: str | None, limit: int) -> str:
    """Cap `text` at `limit` characters, saying so when it was cut."""
    text = text or ""  # GitHub sends null, not "", for an empty body
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + TRUNCATION_MARKER
