"""Tests for the GitHub client's request and parsing rules.

No network here: a stub stands in for `requests.Session`, which is the
practical payoff of injecting the session rather than calling
`requests.get` directly. What's covered is the logic we wrote (field
mapping, PR filtering, query params); what isn't is GitHub actually
answering, which is verified by hand per iteration.
"""

import pytest

from triage_git_mcp.github_client import MAX_PER_PAGE, GitHubIssueClient


class _StubResponse:
    def __init__(self, payload: list[dict], error: Exception | None = None) -> None:
        self._payload = payload
        self._error = error

    def raise_for_status(self) -> None:
        if self._error is not None:
            raise self._error

    def json(self) -> list[dict]:
        return self._payload


class _StubSession:
    """Records the request it was handed and replays a canned payload."""

    def __init__(self, payload: list[dict], error: Exception | None = None) -> None:
        self.headers: dict[str, str] = {}
        self.calls: list[dict] = []
        self._response = _StubResponse(payload, error)

    def get(self, url: str, params: dict | None = None, timeout: float | None = None):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        return self._response


def _api_issue(**overrides) -> dict:
    """A minimal `/issues` item, shaped like GitHub's real response."""
    item = {
        "title": "Fix the flaky test",
        "html_url": "https://github.com/acme/widgets/issues/7",
        "state": "open",
        "repository": {"full_name": "acme/widgets"},
    }
    item.update(overrides)
    return item


def _client(session: _StubSession, token: str = "test-token") -> GitHubIssueClient:
    return GitHubIssueClient(token, session=session)


def test_maps_api_fields_onto_the_issue_model():
    session = _StubSession([_api_issue()])

    (issue,) = _client(session).list_assigned_issues()

    assert issue.title == "Fix the flaky test"
    assert issue.repo == "acme/widgets"
    assert issue.url == "https://github.com/acme/widgets/issues/7"
    assert issue.state == "open"


def test_skips_pull_requests():
    # /issues returns PRs too; only they carry a "pull_request" key.
    session = _StubSession(
        [
            _api_issue(title="A real issue"),
            _api_issue(title="Actually a PR", pull_request={"url": "..."}),
        ]
    )

    issues = _client(session).list_assigned_issues()

    assert [issue.title for issue in issues] == ["A real issue"]


def test_asks_for_assigned_issues_in_both_states():
    session = _StubSession([])

    _client(session).list_assigned_issues()

    params = session.calls[0]["params"]
    assert params["filter"] == "assigned"
    assert params["state"] == "all"
    assert params["per_page"] == MAX_PER_PAGE


def test_calls_the_cross_repo_issues_endpoint():
    session = _StubSession([])

    _client(session).list_assigned_issues()

    assert session.calls[0]["url"] == "https://api.github.com/issues"
    assert session.calls[0]["timeout"] is not None


def test_authenticates_with_a_bearer_token():
    session = _StubSession([])

    _client(session, token="s3cret")

    assert session.headers["Authorization"] == "Bearer s3cret"
    assert session.headers["X-GitHub-Api-Version"] == "2022-11-28"


def test_http_errors_propagate():
    # Iteration 5 owns graceful handling; until then failures must be loud.
    session = _StubSession([], error=RuntimeError("401 Unauthorized"))

    with pytest.raises(RuntimeError, match="401"):
        _client(session).list_assigned_issues()
