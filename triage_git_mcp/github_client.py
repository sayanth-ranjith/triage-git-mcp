"""Read access to the GitHub REST API.

This module knows about HTTP and GitHub's JSON shapes, and nothing about
MCP. That boundary is what lets the parsing rules below be unit-tested
without standing up a server.

Request cost, which iteration 5 will care about:

- `list_assigned_issues`: 1 request, however many issues come back — plus
  1 `GET /user` on the first repo-scoped call, to learn the login.
- `get_issue_details`: 3 requests (issue, comments, timeline), plus 1 more
  only when the most recent comments straddle a page boundary.
"""

import math
from datetime import datetime, timezone
from typing import Any, Literal

import requests

from triage_git_mcp.models import AssignedIssue, IssueComment, IssueDetail, LinkedPullRequest
from triage_git_mcp.priority import Priority, find_severity, priority_for

GITHUB_API_ROOT = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"
DEFAULT_TIMEOUT_SECONDS = 10.0
MAX_PER_PAGE = 100  # GitHub's ceiling for a single page; default would be 30.

# Caps on how much text goes back to the host. Long bodies and threads would
# otherwise crowd everything else out of the host model's context window.
BODY_PREVIEW_CHARS = 300
MAX_BODY_CHARS = 4000
MAX_COMMENT_CHARS = 1000
DEFAULT_COMMENT_LIMIT = 10
MAX_COMMENT_LIMIT = MAX_PER_PAGE  # keeps "recent comments" to at most two pages
TRUNCATION_MARKER = " …[truncated]"

IssueState = Literal["open", "closed", "all"]


def _is_pull_request(item: dict[str, Any]) -> bool:
    """GitHub models pull requests as issues, so `/issues` returns both.

    Only pull requests carry a `pull_request` key. The issue list skips
    them; `get_issue_details` surfaces them as a property *of* an issue.
    """
    return "pull_request" in item


def _truncate(text: str | None, limit: int) -> str:
    """Cap `text` at `limit` characters, saying so when it was cut."""
    text = text or ""  # GitHub sends null, not "", for an empty body
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + TRUNCATION_MARKER


def _split_repo(repo: str) -> tuple[str, str]:
    owner, sep, name = repo.strip().partition("/")
    if not sep or not owner or not name or "/" in name:
        raise ValueError(f"repo must look like 'owner/name', got {repo!r}")
    return owner, name


def _check_org(org: str) -> str:
    org = org.strip()
    if not org or "/" in org:
        raise ValueError(f"org must be a bare organization name, got {org!r}")
    return org


def _repo_from_html_url(html_url: str) -> str:
    # https://github.com/<owner>/<name>/pull/<n> -> "<owner>/<name>"
    return "/".join(html_url.split("/")[3:5])


def _github_timestamp(moment: datetime) -> str:
    """Format as GitHub's ISO 8601 `YYYY-MM-DDTHH:MM:SSZ`; naive means UTC."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _labels(item: dict[str, Any]) -> list[str]:
    return [label["name"] for label in item.get("labels") or []]


def _pull_request_status(item: dict[str, Any]) -> str:
    """Collapse GitHub's state/draft/merged_at into one status a host can act on."""
    if (item.get("pull_request") or {}).get("merged_at"):
        return "merged"
    if item["state"] == "closed":
        return "closed"
    if item.get("draft"):
        return "draft"
    return "open"


class GitHubIssueClient:
    """Reads issues from GitHub on behalf of one authenticated user.

    The session and API root are constructor-injected with working defaults:
    tests substitute a stub transport, and iteration 5 can pass in a
    retrying, rate-limit-aware session without this class changing.
    """

    def __init__(
        self,
        token: str,
        *,
        api_root: str = GITHUB_API_ROOT,
        session: requests.Session | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._api_root = api_root.rstrip("/")
        self._timeout = timeout
        self._session = session if session is not None else requests.Session()
        self._login: str | None = None  # looked up lazily; see _authenticated_login
        self._session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": GITHUB_API_VERSION,
            }
        )

    def list_assigned_issues(
        self,
        *,
        repo: str | None = None,
        org: str | None = None,
        labels: list[str] | None = None,
        state: IssueState = "open",
        updated_since: datetime | None = None,
        priority: list[Priority] | None = None,
    ) -> list[AssignedIssue]:
        """Return the issues assigned to the authenticated user.

        Every filter except `priority` is applied by GitHub. `priority` is
        derived from the issue body, which GitHub can't filter on, so it is
        applied here to whatever GitHub returned.
        """
        path, params = self._assigned_issues_scope(repo, org)
        params |= {"state": state, "per_page": MAX_PER_PAGE}
        if labels:
            params["labels"] = ",".join(labels)  # GitHub matches all of them (AND)
        if updated_since is not None:
            params["since"] = _github_timestamp(updated_since)

        # TODO(iteration 5): only page 1 is fetched (up to MAX_PER_PAGE
        # issues), so the priority filter only sees that page too.
        # Deliberate for now — see docs/plan/05-auth-and-resilience.md.
        payload = self._get_json(path, params=params)
        issues = [self._to_issue(item) for item in payload if not _is_pull_request(item)]
        if priority:
            issues = [issue for issue in issues if issue.priority in priority]
        return issues

    def _assigned_issues_scope(
        self, repo: str | None, org: str | None
    ) -> tuple[str, dict[str, Any]]:
        """Pick the endpoint for a scope, plus how that endpoint says "assigned to me".

        The cross-repo `/issues` and the org endpoint both take
        `filter=assigned`. The per-repo endpoint doesn't, and rejects
        `assignee=@me` (422), so it needs the login spelled out.
        """
        if repo and org:
            raise ValueError("pass repo or org, not both")
        if repo:
            owner, name = _split_repo(repo)  # validate before any request
            return f"/repos/{owner}/{name}/issues", {"assignee": self._authenticated_login()}
        if org:
            return f"/orgs/{_check_org(org)}/issues", {"filter": "assigned"}
        return "/issues", {"filter": "assigned"}

    def _authenticated_login(self) -> str:
        if self._login is None:
            self._login = self._get_json("/user")["login"]
        return self._login

    def get_issue_details(
        self, repo: str, number: int, *, comment_limit: int = DEFAULT_COMMENT_LIMIT
    ) -> IssueDetail:
        """Return one issue with its description, recent comments and linked PRs."""
        owner, name = _split_repo(repo)
        comment_limit = max(0, min(comment_limit, MAX_COMMENT_LIMIT))
        base = f"/repos/{owner}/{name}/issues/{number}"

        item = self._get_json(base)
        severity = find_severity(_labels(item), item.get("body"))
        comments = self._recent_comments(base, total=item["comments"], limit=comment_limit)
        # TODO(iteration 5): only the first timeline page is read, so an issue
        # with 100+ timeline events may miss PRs that referenced it later on.
        timeline = self._get_json(f"{base}/timeline", params={"per_page": MAX_PER_PAGE})

        return IssueDetail(
            title=item["title"],
            repo=f"{owner}/{name}",
            number=item["number"],
            url=item["html_url"],
            state=item["state"],
            state_reason=item.get("state_reason"),
            author=item["user"]["login"],
            assignees=[a["login"] for a in item.get("assignees") or []],
            labels=_labels(item),
            severity=severity,
            priority=priority_for(severity),
            milestone=(item.get("milestone") or {}).get("title"),
            created_at=item["created_at"],
            updated_at=item["updated_at"],
            closed_at=item.get("closed_at"),
            body=_truncate(item.get("body"), MAX_BODY_CHARS),
            comment_count=item["comments"],
            recent_comments=[self._to_comment(c) for c in comments],
            linked_pull_requests=self._linked_pull_requests(timeline),
        )

    def _recent_comments(self, path: str, *, total: int, limit: int) -> list[dict[str, Any]]:
        """Fetch the newest `limit` comments without walking the whole thread.

        The comments endpoint is oldest-first with no way to reverse it, so
        jump straight to the last page — and borrow from the page before when
        the last one is too short to fill `limit`.
        """
        if total == 0 or limit == 0:
            return []
        last_page = math.ceil(total / MAX_PER_PAGE)
        comments = self._get_comment_page(path, last_page)
        if len(comments) < limit and last_page > 1:
            comments = self._get_comment_page(path, last_page - 1) + comments
        return comments[-limit:]

    def _get_comment_page(self, path: str, page: int) -> list[dict[str, Any]]:
        return self._get_json(f"{path}/comments", params={"per_page": MAX_PER_PAGE, "page": page})

    @staticmethod
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
            if not _is_pull_request(source):
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

    def _get_json(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        response = self._session.get(
            f"{self._api_root}{path}", params=params, timeout=self._timeout
        )
        # Fail loudly on auth, network and rate-limit errors. Graceful
        # degradation is iteration 5's job, not a silent except here.
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _to_issue(item: dict[str, Any]) -> AssignedIssue:
        labels = _labels(item)
        # Severity is read from the full body, before it is cut down to a
        # preview: the sev checkboxes usually sit at the end of the form.
        severity = find_severity(labels, item.get("body"))
        return AssignedIssue(
            title=item["title"],
            # The per-repo endpoint omits `repository` as redundant, so fall
            # back to the issue's URL, which always names the repo.
            repo=(item.get("repository") or {}).get("full_name")
            or _repo_from_html_url(item["html_url"]),
            number=item["number"],
            url=item["html_url"],
            state=item["state"],
            labels=labels,
            severity=severity,
            priority=priority_for(severity),
            updated_at=item["updated_at"],
            comment_count=item["comments"],
            body_preview=_truncate(item.get("body"), BODY_PREVIEW_CHARS),
        )

    @staticmethod
    def _to_comment(item: dict[str, Any]) -> IssueComment:
        return IssueComment(
            # `user` is null when the commenter's account has been deleted.
            author=(item.get("user") or {}).get("login", "ghost"),
            created_at=item["created_at"],
            body=_truncate(item.get("body"), MAX_COMMENT_CHARS),
            url=item["html_url"],
        )
