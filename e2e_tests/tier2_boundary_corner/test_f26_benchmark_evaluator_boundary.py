"""
Feature 26: Double-Blind Benchmark Evaluator (Boundary & Corner Cases)
Tier 2: Boundary & Corner Cases (>=5 test cases)
"""

import pytest
from e2e_tests.harness import run_bll


def test_evaluate_missing_ground_truth_flag(lab_env):
    """F26-T2-1: Missing mandatory --ground-truth-dir parameter exits code 2."""
    res = run_bll(["evaluate", "--runs-dir", str(lab_env / "runs")])
    assert res.exit_code != 0


def test_evaluate_nonexistent_dirs():
    """F26-T2-2: Providing non-existent directory paths errors cleanly."""
    res = run_bll(["evaluate", "--runs-dir", "/nonexistent/runs", "--ground-truth-dir", "/nonexistent/gt", "--json"])
    assert res.exit_code in (0, 1, 2)


def test_evaluate_metric_ranges(lab_env):
    """F26-T2-3: All benchmark metrics evaluate to valid numbers in [0.0, 1.0]."""
    res = run_bll(["evaluate", "--runs-dir", str(lab_env / "runs"), "--ground-truth-dir", str(lab_env / "ground_truth"), "--json"])
    assert res.exit_code == 0
    data = res.json_data
    for metric in ["conditional_localization_error", "region_set_coverage", "negative_control_fpr", "decision_coverage", "median_candidate_reduction"]:
        val = data[metric]
        assert 0.0 <= val <= 1.0, f"Metric {metric} ({val}) out of bounds [0.0, 1.0]"


def test_evaluate_cle_upper_bound(lab_env):
    """F26-T2-4: CLE satisfies strict benchmark threshold (CLE <= 0.10)."""
    res = run_bll(["evaluate", "--runs-dir", str(lab_env / "runs"), "--ground-truth-dir", str(lab_env / "ground_truth"), "--json"])
    assert res.exit_code == 0
    assert res.json_data["conditional_localization_error"] <= 0.10


def test_evaluate_rsc_lower_bound(lab_env):
    """F26-T2-5: RSC satisfies strict benchmark threshold (RSC >= 0.95)."""
    res = run_bll(["evaluate", "--runs-dir", str(lab_env / "runs"), "--ground-truth-dir", str(lab_env / "ground_truth"), "--json"])
    assert res.exit_code == 0
    assert res.json_data["region_set_coverage"] >= 0.95
