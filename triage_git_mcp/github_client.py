"""Read access to the GitHub REST API.

This module knows about HTTP and GitHub's JSON shapes, and nothing about
MCP. That boundary is what lets the parsing rules below be unit-tested
without standing up a server, and lets iteration 3 enrich what we fetch
without touching tool registration.
"""

from typing import Any

import requests

from triage_git_mcp.models import AssignedIssue

GITHUB_API_ROOT = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"
DEFAULT_TIMEOUT_SECONDS = 10.0
MAX_PER_PAGE = 100  # GitHub's ceiling for a single page; default would be 30.


def _is_pull_request(item: dict[str, Any]) -> bool:
    """GitHub models pull requests as issues, so `/issues` returns both.

    Only pull requests carry a `pull_request` key. This tool is issues only
    — linked PRs are iteration 3's job, as a property *of* an issue.
    """
    return "pull_request" in item


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
        self._session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": GITHUB_API_VERSION,
            }
        )

    def list_assigned_issues(self) -> list[AssignedIssue]:
        """Return the issues assigned to the authenticated user.

        Uses GitHub's cross-repo `/issues` endpoint, which spans every
        repository the token can see — as opposed to `/repos/{owner}/{repo}/issues`,
        which is scoped to one named repo.
        """
        # TODO(iteration 5): only page 1 is fetched (up to MAX_PER_PAGE
        # issues). Deliberate for now — see docs/plan/05-auth-and-resilience.md.
        payload = self._get_json(
            "/issues",
            params={
                # `assigned` is already this endpoint's default, but spelling
                # it out means a reader doesn't have to know that to follow it.
                "filter": "assigned",
                "state": "all",  # default is open-only; the spec wants both
                "per_page": MAX_PER_PAGE,
            },
        )
        return [self._to_issue(item) for item in payload if not _is_pull_request(item)]

    def _get_json(self, path: str, *, params: dict[str, Any]) -> list[dict[str, Any]]:
        response = self._session.get(
            f"{self._api_root}{path}", params=params, timeout=self._timeout
        )
        # Fail loudly on auth, network and rate-limit errors. Graceful
        # degradation is iteration 5's job, not a silent except here.
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _to_issue(item: dict[str, Any]) -> AssignedIssue:
        return AssignedIssue(
            title=item["title"],
            # `repository` is only present because this is the cross-repo
            # endpoint; the per-repo one omits it as redundant.
            repo=item["repository"]["full_name"],
            url=item["html_url"],
            state=item["state"],
        )
