"""
Feature 7: Path Matrix Invariant Verification
Tier 1: Feature Coverage (>=5 test cases)
"""

import pytest
from e2e_tests.harness import run_bll


@pytest.fixture(autouse=True)
def ensure_lab_up():
    run_bll(["lab", "up"])


def test_lab_verify_cli_command_exit_zero():
    """F07-T1-1: bll lab verify --json exits 0 with verified=True."""
    res = run_bll(["lab", "verify", "--json"])
    assert res.exit_code == 0
    assert res.json_data.get("verified") is True


def test_invariant_client_to_observer_traverses_qnear():
    """F07-T1-2: Invariant 1 verified: Client -> Observer traverses Q_near, not Q_far."""
    res = run_bll(["lab", "verify", "--json"])
    inv = res.json_data.get("invariants", {})
    assert inv.get("client_to_observer") is True


def test_invariant_observer_to_remote_traverses_qfar():
    """F07-T1-3: Invariant 2 verified: Observer -> Remote traverses Q_far, not Q_near."""
    res = run_bll(["lab", "verify", "--json"])
    inv = res.json_data.get("invariants", {})
    assert inv.get("observer_to_remote") is True


def test_invariant_client_to_remote_traverses_both_queues():
    """F07-T1-4: Invariant 3 verified: Client -> Remote traverses both Q_near and Q_far."""
    res = run_bll(["lab", "verify", "--json"])
    inv = res.json_data.get("invariants", {})
    assert inv.get("client_to_remote") is True


def test_lab_verify_reports_matrix_details():
    """F07-T1-5: Verification reports detailed trace verification logs."""
    res = run_bll(["lab", "verify", "--json"])
    details = res.json_data.get("details", [])
    assert isinstance(details, list)
    assert len(details) >= 1
    assert any("verified" in entry.lower() or "pass" in entry.lower() for entry in details)
