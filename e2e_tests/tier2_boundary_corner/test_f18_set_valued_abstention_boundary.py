"""
Feature 18: Set-Valued Ambiguity & Abstention (Boundary & Corner Cases)
Tier 2: Boundary & Corner Cases (>=5 test cases)
"""

import pytest
from e2e_tests.harness import run_bll


def test_abstention_reason_required_when_abstained(near_fifo_run):
    """F18-T2-1: Whenever abstained=True, abstain_reason cannot be null or empty."""
    run_dir, _ = near_fifo_run
    res = run_bll(["infer", str(run_dir), "--vantage", "remote_only", "--json"])
    assert res.exit_code == 0
    if res.json_data["abstained"]:
        assert res.json_data["abstain_reason"] is not None
        assert len(res.json_data["abstain_reason"].strip()) > 0


def test_abstention_reason_null_when_not_abstained(near_fifo_run):
    """F18-T2-2: Whenever abstained=False, abstain_reason must be null."""
    run_dir, _ = near_fifo_run
    res = run_bll(["infer", str(run_dir), "--vantage", "full_observer", "--json"])
    assert res.exit_code == 0
    if not res.json_data["abstained"]:
        assert res.json_data["abstain_reason"] is None


def test_abstention_not_excluded_regions_non_empty(near_fifo_run):
    """F18-T2-3: When abstaining with latency increase observed, not_excluded_regions is non-empty."""
    run_dir, _ = near_fifo_run
    res = run_bll(["infer", str(run_dir), "--vantage", "remote_only", "--json"])
    assert res.exit_code == 0
    if res.json_data["abstained"] and res.json_data["latency_increase_observed"]:
        assert len(res.json_data["not_excluded_regions"]) >= 2


def test_abstention_single_candidate_no_abstention(near_fifo_run):
    """F18-T2-4: When only 1 candidate region remains and no quality flags are raised, engine does not abstain."""
    run_dir, _ = near_fifo_run
    res = run_bll(["infer", str(run_dir), "--vantage", "full_observer", "--json"])
    assert res.exit_code == 0
    if len(res.json_data["supported_regions"]) == 1 and not res.json_data["quality_flags"]:
        assert res.json_data["abstained"] is False


def test_abstention_preserves_supported_regions_consistency(near_fifo_run):
    """F18-T2-5: When abstained=True, supported_regions cannot assert a single definitive region."""
    run_dir, _ = near_fifo_run
    res = run_bll(["infer", str(run_dir), "--vantage", "remote_only", "--json"])
    assert res.exit_code == 0
    if res.json_data["abstained"]:
        assert len(res.json_data["supported_regions"]) == 0
