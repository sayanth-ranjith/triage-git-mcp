"""Read access to the GitHub REST API.

This module knows about HTTP: which endpoint to call, with which params,
and how to page through results. Turning the JSON that comes back into
models is `github_mapping.py`'s job, and nothing here knows about MCP.

Request cost, which iteration 5 will care about:

- `list_assigned_issues`: 1 request, however many issues come back — plus
  1 `GET /user` on the first repo-scoped call, to learn the login.
- `get_issue_details`: 3 requests (issue, comments, timeline), plus 1 more
  only when the most recent comments straddle a page boundary.
"""

import math
from datetime import UTC, datetime
from typing import Any

import requests

from triage_git_mcp.github_mapping import is_pull_request, to_issue, to_issue_detail
from triage_git_mcp.models import AssignedIssue, IssueDetail, IssueStateFilter
from triage_git_mcp.priority import Priority

GITHUB_API_ROOT = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"
DEFAULT_TIMEOUT_SECONDS = 10.0
MAX_PER_PAGE = 100  # GitHub's ceiling for a single page; default would be 30.
DEFAULT_COMMENT_LIMIT = 10
MAX_COMMENT_LIMIT = MAX_PER_PAGE  # keeps "recent comments" to at most two pages


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


def _github_timestamp(moment: datetime) -> str:
    """Format as GitHub's ISO 8601 `YYYY-MM-DDTHH:MM:SSZ`; naive means UTC."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


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
        state: IssueStateFilter = "open",
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
        issues = [to_issue(item) for item in payload if not is_pull_request(item)]
        if priority:
            issues = [issue for issue in issues if issue.priority in priority]
        return issues

    def get_issue_details(
        self, repo: str, number: int, *, comment_limit: int = DEFAULT_COMMENT_LIMIT
    ) -> IssueDetail:
        """Return one issue with its description, recent comments and linked PRs."""
        owner, name = _split_repo(repo)
        comment_limit = max(0, min(comment_limit, MAX_COMMENT_LIMIT))
        base = f"/repos/{owner}/{name}/issues/{number}"

        item = self._get_json(base)
        comments = self._recent_comments(base, total=item["comments"], limit=comment_limit)
        # TODO(iteration 5): only the first timeline page is read, so an issue
        # with 100+ timeline events may miss PRs that referenced it later on.
        timeline = self._get_json(f"{base}/timeline", params={"per_page": MAX_PER_PAGE})

        return to_issue_detail(item, repo=f"{owner}/{name}", comments=comments, timeline=timeline)

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

    def _get_json(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        response = self._session.get(
            f"{self._api_root}{path}", params=params, timeout=self._timeout
        )
        # Fail loudly on auth, network and rate-limit errors. Graceful
        # degradation is iteration 5's job, not a silent except here.
        response.raise_for_status()
        return response.json()
