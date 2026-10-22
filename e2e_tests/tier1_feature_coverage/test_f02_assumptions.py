"""
Feature 2: Core Assumptions Doc (docs/assumptions.md)
Tier 1: Feature Coverage (>=5 test cases)
"""

import pathlib
import pytest

PROJ_ROOT = pathlib.Path(__file__).parent.parent.parent
ASSUMPTIONS_PATH = PROJ_ROOT / "docs" / "assumptions.md"


def _read_assumptions_content():
    if not ASSUMPTIONS_PATH.exists():
        # Fallback to checking PROJECT.md assumptions section or skip if pre-M1
        pytest.skip(f"docs/assumptions.md not yet created by Implementation Track at {ASSUMPTIONS_PATH}")
    return ASSUMPTIONS_PATH.read_text()


def test_assumptions_doc_exists():
    """F02-T1-1: docs/assumptions.md exists and is non-empty."""
    content = _read_assumptions_content()
    assert len(content.strip()) > 50, "docs/assumptions.md must be a non-trivial document"


def test_assumptions_doc_has_four_core_sections():
    """F02-T1-2: Document rigorously separates Facts, Decisions, Hypotheses, and Unknowns."""
    content = _read_assumptions_content()
    headers_lower = content.lower()
    assert "fact" in headers_lower, "Assumptions doc must contain Facts section"
    assert "decision" in headers_lower, "Assumptions doc must contain Decisions section"
    assert "hypothes" in headers_lower, "Assumptions doc must contain Hypotheses section"
    assert "unknown" in headers_lower, "Assumptions doc must contain Unknowns section"


def test_assumptions_doc_contains_hypotheses_h1_h2_h3():
    """F02-T1-3: Hypotheses section explicitly defines H1, H2, and H3."""
    content = _read_assumptions_content()
    assert "h1" in content or "H1" in content, "Hypothesis H1 (Observer marginal value) must be documented"
    assert "h2" in content or "H2" in content, "Hypothesis H2 (Abstention on indistinguishable pairs) must be documented"
    assert "h3" in content or "H3" in content, "Hypothesis H3 (Protocol discrepancy) must be documented"


def test_assumptions_doc_netns_facts():
    """F02-T1-4: Document outlines Linux netns, veth isolation, and tc traffic control facts."""
    content = _read_assumptions_content()
    content_lower = content.lower()
    assert "netns" in content_lower or "namespace" in content_lower
    assert "tc" in content_lower or "traffic control" in content_lower


def test_assumptions_doc_unprivileged_controller_decision():
    """F02-T1-5: Document records architectural decision for unprivileged controller execution."""
    content = _read_assumptions_content()
    content_lower = content.lower()
    assert "unprivileged" in content_lower or "privilege" in content_lower
    assert "helper" in content_lower or "bll-lab-helper" in content_lower
