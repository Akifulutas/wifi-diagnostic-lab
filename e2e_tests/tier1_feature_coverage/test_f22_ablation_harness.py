"""
Feature 22: 4-Vantage Ablation Harness
Tier 1: Feature Coverage (>=5 test cases)
"""

import pytest
from e2e_tests.harness import run_bll


def test_ablation_cli_four_vantages(near_fifo_run):
    """F22-T1-1: bll infer accepts all 4 standard vantage profiles."""
    run_dir, _ = near_fifo_run
    for vantage in ["remote_only", "gateway_remote", "local_remote", "full_observer"]:
        res = run_bll(["infer", str(run_dir), "--vantage", vantage, "--json"])
        assert res.exit_code == 0, f"Failed for vantage {vantage}: {res.stderr}"
        assert res.json_data["vantage_profile"] == vantage


def test_ablation_remote_only_yields_ambiguity(near_fifo_run):
    """F22-T1-2: Vantage 1 (remote_only) retains multiple candidate regions in not_excluded_regions."""
    run_dir, _ = near_fifo_run
    res = run_bll(["infer", str(run_dir), "--vantage", "remote_only", "--json"])
    assert res.exit_code == 0
    assert len(res.json_data["not_excluded_regions"]) >= 2


def test_ablation_full_observer_reduces_candidate_set(near_fifo_run):
    """F22-T1-3: Vantage 4 (full_observer) reduces candidate set down to exact bottleneck link."""
    run_dir, _ = near_fifo_run
    res = run_bll(["infer", str(run_dir), "--vantage", "full_observer", "--json"])
    assert res.exit_code == 0
    assert len(res.json_data["supported_regions"]) == 1
    assert "near_link" in res.json_data["supported_regions"]


def test_ablation_candidate_reduction_ratio(near_fifo_run):
    """F22-T1-4: Candidate set size reduces by >= 50% between Vantage 1 and Vantage 4."""
    run_dir, _ = near_fifo_run
    res_v1 = run_bll(["infer", str(run_dir), "--vantage", "remote_only", "--json"])
    res_v4 = run_bll(["infer", str(run_dir), "--vantage", "full_observer", "--json"])
    size_v1 = len(res_v1.json_data["not_excluded_regions"])
    size_v4 = len(res_v4.json_data["supported_regions"])
    reduction = (size_v1 - size_v4) / size_v1
    assert reduction >= 0.50, f"Expected >= 50% candidate reduction, got {reduction * 100}%"


def test_ablation_preserves_run_id(near_fifo_run):
    """F22-T1-5: All ablation evaluations preserve the original opaque run_id."""
    run_dir, _ = near_fifo_run
    res = run_bll(["infer", str(run_dir), "--vantage", "local_remote", "--json"])
    assert res.exit_code == 0
    assert res.json_data["run_id"] == run_dir.name
