"""Derive a triage priority from an issue's sev1–sev4 marking.

Pure functions only: no HTTP, no MCP. The rule lives here rather than in
`github_client.py` because it's a triage decision, not a GitHub API detail.

Severity is read from a `sev1`–`sev4` label first, then from a ticked
checkbox in the body (the shape cheese-retry's issue form produces). An
issue with neither gets `medium`, with `severity` left as None so a reader
can tell "defaulted" apart from "stated".
"""

import re
from typing import Literal

Severity = Literal["sev1", "sev2", "sev3", "sev4"]
Priority = Literal["critical", "high", "medium", "low"]

DEFAULT_PRIORITY: Priority = "medium"

PRIORITY_BY_SEVERITY: dict[Severity, Priority] = {
    "sev1": "critical",
    "sev2": "high",
    "sev3": "medium",
    "sev4": "low",
}

# Labels and checkbox text arrive as plain strings in any case; this turns
# one back into a typed Severity without a cast.
_SEVERITY_BY_NAME: dict[str, Severity] = {severity: severity for severity in PRIORITY_BY_SEVERITY}

# A ticked markdown task-list item: "- [x] sev1". The form lists all four
# options in every body, so an unticked "- [ ] sev2" must not match.
_TICKED_SEVERITY = re.compile(r"^\s*[-*]\s+\[[xX]\]\s+(sev[1-4])\b", re.MULTILINE | re.IGNORECASE)


def find_severity(labels: list[str], body: str | None) -> Severity | None:
    """Return the issue's severity, preferring a label over the body."""
    for label in labels:
        if severity := _SEVERITY_BY_NAME.get(label.lower()):
            return severity
    match = _TICKED_SEVERITY.search(body or "")
    return _SEVERITY_BY_NAME[match.group(1).lower()] if match else None


def priority_for(severity: Severity | None) -> Priority:
    return PRIORITY_BY_SEVERITY[severity] if severity else DEFAULT_PRIORITY
