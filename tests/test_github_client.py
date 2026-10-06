"""Tests for the GitHub client's request and parsing rules.

No network here: a stub stands in for `requests.Session`, which is the
practical payoff of injecting the session rather than calling
`requests.get` directly. What's covered is the logic we wrote (field
mapping, PR filtering, query params); what isn't is GitHub actually
answering, which is verified by hand per iteration.
"""

import pytest

from triage_git_mcp.github_client import (
    BODY_PREVIEW_CHARS,
    MAX_BODY_CHARS,
    MAX_PER_PAGE,
    TRUNCATION_MARKER,
    GitHubIssueClient,
)


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
    """Records each request it's handed and replays a canned payload.

    `routes` maps a URL suffix to the payload for it — or to a function of
    the query params, for paginated endpoints. Without routes, every URL
    gets `payload`.
    """

    def __init__(
        self,
        payload: list[dict] | None = None,
        error: Exception | None = None,
        routes: dict | None = None,
    ) -> None:
        self.headers: dict[str, str] = {}
        self.calls: list[dict] = []
        self._payload = payload if payload is not None else []
        self._error = error
        self._routes = routes or {}

    def get(self, url: str, params: dict | None = None, timeout: float | None = None):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        payload = self._payload
        for suffix, routed in self._routes.items():
            if url.endswith(suffix):
                payload = routed(params) if callable(routed) else routed
        return _StubResponse(payload, self._error)


def _api_issue(**overrides) -> dict:
    """A minimal `/issues` item, shaped like GitHub's real response."""
    item = {
        "title": "Fix the flaky test",
        "number": 7,
        "html_url": "https://github.com/acme/widgets/issues/7",
        "state": "open",
        "repository": {"full_name": "acme/widgets"},
        "labels": [{"name": "bug"}, {"name": "p1"}],
        "updated_at": "2026-09-30T12:00:00Z",
        "comments": 0,
        "body": "It fails roughly one run in five.",
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
    assert issue.number == 7
    assert issue.labels == ["bug", "p1"]
    assert issue.comment_count == 0
    assert issue.body_preview == "It fails roughly one run in five."


def test_body_preview_is_truncated_and_marked():
    session = _StubSession([_api_issue(body="x" * (BODY_PREVIEW_CHARS + 50))])

    (issue,) = _client(session).list_assigned_issues()

    assert issue.body_preview == "x" * BODY_PREVIEW_CHARS + TRUNCATION_MARKER


def test_null_body_becomes_empty_preview():
    session = _StubSession([_api_issue(body=None, labels=[])])

    (issue,) = _client(session).list_assigned_issues()

    assert issue.body_preview == ""
    assert issue.labels == []


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


# --- get_issue_details --------------------------------------------------------

ISSUE_PATH = "/repos/acme/widgets/issues/7"


def _api_issue_detail(**overrides) -> dict:
    """A minimal `/repos/{owner}/{repo}/issues/{n}` response."""
    item = _api_issue(
        user={"login": "alice"},
        assignees=[{"login": "me"}],
        milestone={"title": "v1.0"},
        created_at="2026-09-01T09:00:00Z",
        closed_at=None,
        state_reason=None,
    )
    del item["repository"]  # the per-repo endpoint omits it
    item.update(overrides)
    return item


def _api_comment(n: int) -> dict:
    return {
        "user": {"login": f"user{n}"},
        "created_at": "2026-09-02T09:00:00Z",
        "body": f"comment {n}",
        "html_url": f"https://github.com/acme/widgets/issues/7#issuecomment-{n}",
    }


def _cross_reference(number: int, *, state="open", draft=False, merged_at=None, is_pr=True):
    source = {
        "number": number,
        "title": f"PR {number}",
        "html_url": f"https://github.com/acme/widgets/pull/{number}",
        "state": state,
        "draft": draft,
    }
    if is_pr:
        source["pull_request"] = {"merged_at": merged_at}
    return {"event": "cross-referenced", "source": {"type": "issue", "issue": source}}


def _detail_session(issue=None, comments=(), timeline=()) -> _StubSession:
    """Serves one issue, its comments (paginated like GitHub) and its timeline."""
    comments = list(comments)

    def comment_page(params):
        start = (params["page"] - 1) * params["per_page"]
        return comments[start : start + params["per_page"]]

    return _StubSession(
        routes={
            ISSUE_PATH: issue or _api_issue_detail(comments=len(comments)),
            f"{ISSUE_PATH}/comments": comment_page,
            f"{ISSUE_PATH}/timeline": list(timeline),
        }
    )


def test_detail_maps_issue_fields():
    session = _detail_session()

    detail = _client(session).get_issue_details("acme/widgets", 7)

    assert detail.repo == "acme/widgets"
    assert detail.number == 7
    assert detail.author == "alice"
    assert detail.assignees == ["me"]
    assert detail.labels == ["bug", "p1"]
    assert detail.milestone == "v1.0"
    assert detail.body == "It fails roughly one run in five."
    assert detail.closed_at is None
    assert detail.recent_comments == []
    assert detail.linked_pull_requests == []


def test_detail_body_is_truncated():
    session = _detail_session(issue=_api_issue_detail(body="y" * (MAX_BODY_CHARS + 1)))

    detail = _client(session).get_issue_details("acme/widgets", 7)

    assert detail.body.endswith(TRUNCATION_MARKER)
    assert len(detail.body) == MAX_BODY_CHARS + len(TRUNCATION_MARKER)


def test_no_comment_request_when_there_are_no_comments():
    session = _detail_session()

    _client(session).get_issue_details("acme/widgets", 7)

    assert not any(call["url"].endswith("/comments") for call in session.calls)


def test_returns_only_the_most_recent_comments():
    session = _detail_session(comments=[_api_comment(n) for n in range(1, 16)])

    detail = _client(session).get_issue_details("acme/widgets", 7, comment_limit=3)

    assert [c.body for c in detail.recent_comments] == ["comment 13", "comment 14", "comment 15"]
    assert detail.comment_count == 15


def test_recent_comments_span_a_page_boundary():
    # 102 comments: last page holds only 2, so the page before must fill in.
    session = _detail_session(comments=[_api_comment(n) for n in range(1, 103)])

    detail = _client(session).get_issue_details("acme/widgets", 7, comment_limit=5)

    assert [c.body for c in detail.recent_comments] == [
        f"comment {n}" for n in range(98, 103)
    ]
    pages = [c["params"]["page"] for c in session.calls if c["url"].endswith("/comments")]
    assert pages == [2, 1]


def test_comment_from_deleted_account_is_attributed_to_ghost():
    comment = _api_comment(1) | {"user": None}
    session = _detail_session(issue=_api_issue_detail(comments=1), comments=[comment])

    detail = _client(session).get_issue_details("acme/widgets", 7)

    assert detail.recent_comments[0].author == "ghost"


@pytest.mark.parametrize(
    ("event", "status"),
    [
        pytest.param(_cross_reference(1), "open", id="open"),
        pytest.param(_cross_reference(1, draft=True), "draft", id="draft"),
        pytest.param(
            _cross_reference(1, state="closed", merged_at="2026-09-03T00:00:00Z"),
            "merged",
            id="merged",
        ),
        pytest.param(_cross_reference(1, state="closed"), "closed", id="closed unmerged"),
    ],
)
def test_linked_pull_request_status(event, status):
    session = _detail_session(timeline=[event])

    (pr,) = _client(session).get_issue_details("acme/widgets", 7).linked_pull_requests

    assert pr.status == status
    assert pr.repo == "acme/widgets"
    assert pr.number == 1


def test_linked_pull_requests_ignore_issues_other_events_and_duplicates():
    session = _detail_session(
        timeline=[
            {"event": "labeled", "label": {"name": "bug"}},
            _cross_reference(2, is_pr=False),  # mentioned by an issue, not a PR
            _cross_reference(3),
            _cross_reference(3),  # same PR referencing twice
        ]
    )

    prs = _client(session).get_issue_details("acme/widgets", 7).linked_pull_requests

    assert [pr.number for pr in prs] == [3]


@pytest.mark.parametrize("repo", ["widgets", "acme/", "/widgets", "acme/widgets/extra"])
def test_rejects_malformed_repo(repo):
    session = _detail_session()

    with pytest.raises(ValueError, match="owner/name"):
        _client(session).get_issue_details(repo, 7)

    assert session.calls == []
