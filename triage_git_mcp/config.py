"""Configuration, read once from the environment.

Split into a pure part and an impure part on purpose:

- `Settings.from_mapping` is a pure function of its input, so it can be
  tested without touching the real environment or a real `.env` file.
- `load_settings` is the impure edge that actually reads `.env` and
  `os.environ`.

Keeping "where config comes from" in one module means iteration 5 can
swap a PAT for OAuth without the GitHub client or the MCP layer changing.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass

from dotenv import load_dotenv

GITHUB_TOKEN_VAR = "GITHUB_TOKEN"

_MISSING_TOKEN_HELP = (
    f"{GITHUB_TOKEN_VAR} is not set. Copy .env.example to .env and paste in a "
    "GitHub personal access token (classic, with the 'repo' scope)."
)


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or unusable."""


@dataclass(frozen=True)
class Settings:
    """Everything this server needs from its environment.

    Frozen because configuration is read once at startup and should never
    drift underneath a running server.
    """

    github_token: str

    @classmethod
    def from_mapping(cls, env: Mapping[str, str]) -> "Settings":
        """Build settings from an environment-like mapping.

        Raises `ConfigError` rather than `KeyError` so the failure tells the
        user what to do about it. An empty or whitespace-only value counts
        as missing — that's the state a freshly copied `.env` is in.
        """
        token = env.get(GITHUB_TOKEN_VAR, "").strip()
        if not token:
            raise ConfigError(_MISSING_TOKEN_HELP)
        return cls(github_token=token)


def load_settings() -> Settings:
    """Read settings from `.env` (if present) plus the process environment."""
    # Missing .env is fine — the variable may already be exported, e.g. in CI.
    load_dotenv()
    return Settings.from_mapping(os.environ)
