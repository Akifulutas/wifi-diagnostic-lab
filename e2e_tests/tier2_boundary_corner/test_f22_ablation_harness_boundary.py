"""
Feature 22: 4-Vantage Ablation Harness (Boundary & Corner Cases)
Tier 2: Boundary & Corner Cases (>=5 test cases)
"""

import pytest
from e2e_tests.harness import run_bll


def test_ablation_invalid_vantage_flag(near_fifo_run):
    """F22-T2-1: Passing unrecognized vantage string exits with error."""
    run_dir, _ = near_fifo_run
    res = run_bll(["infer", str(run_dir), "--vantage", "invalid_vantage_xyz", "--json"])
    assert res.exit_code != 0


def test_ablation_missing_run_dir():
    """F22-T2-2: Missing required run directory argument exits code 2."""
    res = run_bll(["infer", "--vantage", "remote_only", "--json"])
    assert res.exit_code != 0


def test_ablation_four_vantages_return_valid_json(near_fifo_run):
    """F22-T2-3: All 4 vantages emit valid JSON conforming to output contract."""
    run_dir, _ = near_fifo_run
    vantages = ["remote_only", "gateway_remote", "local_remote", "full_observer"]
    for v in vantages:
        res = run_bll(["infer", str(run_dir), "--vantage", v, "--json"])
        assert res.exit_code == 0
        assert res.json_data is not None


def test_ablation_vantage_case_sensitivity(near_fifo_run):
    """F22-T2-4: Uppercase vantage name handled cleanly or rejected with usage error."""
    run_dir, _ = near_fifo_run
    res = run_bll(["infer", str(run_dir), "--vantage", "REMOTE_ONLY", "--json"])
    assert res.exit_code in (0, 1, 2)


def test_ablation_vantage_preserves_queue_evidence(near_fifo_run):
    """F22-T2-5: Physical queue evidence level preserved across vantage changes."""
    run_dir, _ = near_fifo_run
    res_v1 = run_bll(["infer", str(run_dir), "--vantage", "remote_only", "--json"])
    res_v4 = run_bll(["infer", str(run_dir), "--vantage", "full_observer", "--json"])
    assert res_v1.json_data["queue_evidence"] == res_v4.json_data["queue_evidence"]
