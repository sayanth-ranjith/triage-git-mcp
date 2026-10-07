"""Tests for the MCP layer: what a host sees when it lists or calls the tools.

The cases here fail input validation before any GitHub request, so a dummy
token is enough and no network is touched.
"""

import asyncio
import importlib

import pytest
from mcp.server.mcpserver.exceptions import ToolError, UnexpectedToolError


@pytest.fixture(scope="module")
def server():
    # mcp_server reads GITHUB_TOKEN at import time, by design (fail fast).
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("GITHUB_TOKEN", "test-token")
        yield importlib.import_module("mcp_server")


@pytest.mark.parametrize(
    ("tool", "arguments", "message"),
    [
        pytest.param(
            "list_my_assigned_issues",
            {"repo": "acme/widgets", "org": "acme"},
            "pass repo or org, not both",
            id="repo and org together",
        ),
        pytest.param(
            "get_issue_details",
            {"repo": "widgets", "number": 7},
            "owner/name",
            id="malformed repo",
        ),
    ],
)
def test_bad_input_reaches_the_host_as_a_readable_error(server, tool, arguments, message):
    with pytest.raises(ToolError, match=message) as raised:
        asyncio.run(server.app.call_tool(tool, arguments))

    # A crash would surface as UnexpectedToolError with the text withheld.
    assert not isinstance(raised.value, UnexpectedToolError)


def test_tools_are_marked_read_only(server):
    tools = asyncio.run(server.app.list_tools())

    assert {tool.name for tool in tools} == {"list_my_assigned_issues", "get_issue_details"}
    for tool in tools:
        assert tool.annotations.read_only_hint is True
        assert tool.annotations.open_world_hint is True
