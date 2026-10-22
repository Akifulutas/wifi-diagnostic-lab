"""
Feature 23: Statistical Hypothesis Verification (Boundary & Corner Cases)
Tier 2: Boundary & Corner Cases (>=5 test cases)
"""

import pytest
from e2e_tests.harness import run_bll


def test_hypothesis_p_values_in_zero_one(lab_env):
    """F23-T2-1: All reported statistical p-values are bounded in [0.0, 1.0]."""
    res = run_bll(["evaluate", "--runs-dir", str(lab_env / "runs"), "--ground-truth-dir", str(lab_env / "ground_truth"), "--json"])
    assert res.exit_code == 0
    hyps = res.json_data.get("hypotheses_results", {})
    for hname, hdata in hyps.items():
        if "p_value" in hdata:
            assert 0.0 <= hdata["p_value"] <= 1.0
        if "wilcoxon_p_value" in hdata:
            assert 0.0 <= hdata["wilcoxon_p_value"] <= 1.0


def test_hypothesis_empty_runs_dir(tmp_path):
    """F23-T2-2: Evaluation over empty runs directory handled safely."""
    empty_runs = tmp_path / "runs"
    empty_gt = tmp_path / "ground_truth"
    empty_runs.mkdir()
    empty_gt.mkdir()
    res = run_bll(["evaluate", "--runs-dir", str(empty_runs), "--ground-truth-dir", str(empty_gt), "--json"])
    assert res.exit_code in (0, 1, 2)


def test_hypothesis_supported_is_boolean(lab_env):
    """F23-T2-3: Hypothesis 'supported' verdicts are strictly boolean."""
    res = run_bll(["evaluate", "--runs-dir", str(lab_env / "runs"), "--ground-truth-dir", str(lab_env / "ground_truth"), "--json"])
    assert res.exit_code == 0
    hyps = res.json_data.get("hypotheses_results", {})
    for hname, hdata in hyps.items():
        assert isinstance(hdata.get("supported"), bool)


def test_hypothesis_gate_status_boolean(lab_env):
    """F23-T2-4: Benchmark summary gate_passed field is boolean."""
    res = run_bll(["evaluate", "--runs-dir", str(lab_env / "runs"), "--ground-truth-dir", str(lab_env / "ground_truth"), "--json"])
    assert res.exit_code == 0
    assert isinstance(res.json_data.get("gate_passed"), bool)


def test_hypothesis_deterministic_reproducibility(lab_env):
    """F23-T2-5: Hypothesis results are identical across repeated evaluations."""
    res1 = run_bll(["evaluate", "--runs-dir", str(lab_env / "runs"), "--ground-truth-dir", str(lab_env / "ground_truth"), "--json"])
    res2 = run_bll(["evaluate", "--runs-dir", str(lab_env / "runs"), "--ground-truth-dir", str(lab_env / "ground_truth"), "--json"])
    assert res1.json_data == res2.json_data
