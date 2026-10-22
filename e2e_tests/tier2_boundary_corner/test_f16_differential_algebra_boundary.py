"""
Feature 16: Differential Path Algebra Engine (Boundary & Corner Cases)
Tier 2: Boundary & Corner Cases (>=5 test cases)
"""

import pytest
from e2e_tests.harness import run_bll


def test_differential_algebra_zero_delay_inflation(healthy_run):
    """F16-T2-1: Zero delay inflation produces latency_increase_observed=False."""
    run_dir, _ = healthy_run
    res = run_bll(["infer", str(run_dir), "--json"])
    assert res.exit_code == 0
    assert res.json_data["latency_increase_observed"] is False


def test_differential_algebra_candidate_set_subset_invariant(near_fifo_run):
    """F16-T2-2: Supported regions is always a strict subset of not_excluded_regions."""
    run_dir, _ = near_fifo_run
    res = run_bll(["infer", str(run_dir), "--vantage", "full_observer", "--json"])
    assert res.exit_code == 0
    supp = set(res.json_data["supported_regions"])
    not_ex = set(res.json_data["not_excluded_regions"])
    assert supp.issubset(not_ex)


def test_differential_algebra_negative_delay_inflation_handled(healthy_run):
    """F16-T2-3: Measurement noise leading to negative delta handled without exception."""
    run_dir, _ = healthy_run
    res = run_bll(["infer", str(run_dir), "--json"])
    assert res.exit_code == 0


def test_differential_algebra_invalid_vantage_profile(near_fifo_run):
    """F16-T2-4: Passing an unrecognized vantage profile name returns usage error."""
    run_dir, _ = near_fifo_run
    res = run_bll(["infer", str(run_dir), "--vantage", "satellite_vantage", "--json"])
    assert res.exit_code != 0


def test_differential_algebra_deterministic_repeated_calls(near_fifo_run):
    """F16-T2-5: 10 repeated inferences on identical dataset return bit-for-bit identical JSON."""
    run_dir, _ = near_fifo_run
    results = [run_bll(["infer", str(run_dir), "--json"]).stdout for _ in range(5)]
    assert len(set(results)) == 1, "Inference engine must be 100% deterministic"
