"""Tests for configuration loading.

These exercise `Settings.from_mapping`, the pure half of `config`, so they
never read the real environment or the developer's `.env`.
"""

from dataclasses import FrozenInstanceError

import pytest

from triage_git_mcp.config import ConfigError, Settings


def test_reads_the_token_from_the_environment():
    settings = Settings.from_mapping({"GITHUB_TOKEN": "ghp_example"})

    assert settings.github_token == "ghp_example"


def test_surrounding_whitespace_is_stripped():
    settings = Settings.from_mapping({"GITHUB_TOKEN": "  ghp_example\n"})

    assert settings.github_token == "ghp_example"


@pytest.mark.parametrize(
    "env",
    [
        pytest.param({}, id="variable absent"),
        pytest.param({"GITHUB_TOKEN": ""}, id="empty, as in a fresh .env"),
        pytest.param({"GITHUB_TOKEN": "   "}, id="whitespace only"),
    ],
)
def test_missing_token_raises_an_actionable_error(env):
    with pytest.raises(ConfigError, match="Copy .env.example"):
        Settings.from_mapping(env)


def test_settings_are_immutable():
    settings = Settings.from_mapping({"GITHUB_TOKEN": "ghp_example"})

    with pytest.raises(FrozenInstanceError):
        settings.github_token = "something else"  # type: ignore[misc]
