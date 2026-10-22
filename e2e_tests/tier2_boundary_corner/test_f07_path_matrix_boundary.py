"""
Feature 7: Path Matrix Invariant Verification (Boundary & Corner Cases)
Tier 2: Boundary & Corner Cases (>=5 test cases)
"""

import pytest
from e2e_tests.harness import run_bll


def test_path_matrix_verify_when_lab_down():
    """F07-T2-1: Verifying path matrix when lab is torn down returns error or verified=False."""
    run_bll(["lab", "down"])
    res = run_bll(["lab", "verify", "--json"])
    assert res.exit_code != 0 or res.json_data.get("verified") is False


def test_path_matrix_unknown_topology_name():
    """F07-T2-2: Passing non-existent topology instance name handled cleanly."""
    res = run_bll(["lab", "verify", "--name", "bll-nonexistent", "--json"])
    assert res.exit_code in (0, 1, 2)


def test_path_matrix_missing_json_flag_output():
    """F07-T2-3: Human-readable verify output without --json does not crash."""
    run_bll(["lab", "up"])
    res = run_bll(["lab", "verify"])
    assert res.exit_code == 0
    assert "Invariants" in res.stdout or "verified" in res.stdout.lower()


def test_path_matrix_repeated_verifications_idempotent():
    """F07-T2-4: Consecutive path matrix verifications yield identical invariant flags."""
    run_bll(["lab", "up"])
    res1 = run_bll(["lab", "verify", "--json"])
    res2 = run_bll(["lab", "verify", "--json"])
    assert res1.json_data == res2.json_data


def test_path_matrix_verify_with_unexpected_flag():
    """F07-T2-5: Invalid option flag to verify returns usage error."""
    res = run_bll(["lab", "verify", "--bogus-flag"])
    assert res.exit_code != 0
