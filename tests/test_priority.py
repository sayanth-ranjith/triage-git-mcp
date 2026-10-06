"""Tests for deriving a triage priority from sev1–sev4 markings."""

import pytest

from triage_git_mcp.priority import find_severity, priority_for

# The tail of a body produced by cheese-retry's issue form.
FORM_BODY = """### Version

0.0.11

### Issue criticality

- [ ] sev1
- [ ] sev2
- [x] sev3
- [ ] sev4"""


def test_severity_from_a_label():
    assert find_severity(["bug", "sev2"], None) == "sev2"


def test_label_match_ignores_case():
    assert find_severity(["SEV1"], None) == "sev1"


def test_severity_from_a_ticked_checkbox():
    assert find_severity([], FORM_BODY) == "sev3"


def test_unticked_checkboxes_are_ignored():
    body = FORM_BODY.replace("[x]", "[ ]")

    assert find_severity([], body) is None


def test_capital_x_counts_as_ticked():
    assert find_severity([], "- [X] sev4") == "sev4"


def test_label_wins_over_the_body():
    assert find_severity(["sev1"], FORM_BODY) == "sev1"


def test_sev_mentioned_in_prose_does_not_count():
    assert find_severity([], "This feels like a sev1 to me.") is None


@pytest.mark.parametrize("body", [None, ""])
def test_nothing_found_means_no_severity(body):
    assert find_severity([], body) is None


@pytest.mark.parametrize(
    ("severity", "priority"),
    [("sev1", "critical"), ("sev2", "high"), ("sev3", "medium"), ("sev4", "low"), (None, "medium")],
)
def test_priority_mapping(severity, priority):
    assert priority_for(severity) == priority
