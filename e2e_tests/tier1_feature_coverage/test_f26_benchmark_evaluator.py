"""
Feature 26: Double-Blind Benchmark Evaluator
Tier 1: Feature Coverage (>=5 test cases)
"""

import pytest
from e2e_tests.harness import run_bll


def test_evaluate_cli_command(lab_env):
    """F26-T1-1: bll evaluate executes benchmark scoring across runs and ground truth."""
    res = run_bll(["evaluate", "--runs-dir", str(lab_env / "runs"), "--ground-truth-dir", str(lab_env / "ground_truth"), "--json"])
    assert res.exit_code == 0
    assert res.json_data is not None


def test_evaluate_cle_threshold(lab_env):
    """F26-T1-2: Conditional Localization Error (CLE) satisfies release criterion (CLE <= 0.10)."""
    res = run_bll(["evaluate", "--runs-dir", str(lab_env / "runs"), "--ground-truth-dir", str(lab_env / "ground_truth"), "--json"])
    assert res.exit_code == 0
    cle = res.json_data["conditional_localization_error"]
    assert cle <= 0.10, f"CLE {cle} exceeds release benchmark threshold 0.10"


def test_evaluate_rsc_threshold(lab_env):
    """F26-T1-3: Region-Set Coverage (RSC) satisfies release criterion (RSC >= 0.95)."""
    res = run_bll(["evaluate", "--runs-dir", str(lab_env / "runs"), "--ground-truth-dir", str(lab_env / "ground_truth"), "--json"])
    assert res.exit_code == 0
    rsc = res.json_data["region_set_coverage"]
    assert rsc >= 0.95, f"RSC {rsc} below release benchmark threshold 0.95"


def test_evaluate_negative_control_fpr(lab_env):
    """F26-T1-4: Negative Control False Positive Rate satisfies release criterion (FPR <= 0.05)."""
    res = run_bll(["evaluate", "--runs-dir", str(lab_env / "runs"), "--ground-truth-dir", str(lab_env / "ground_truth"), "--json"])
    assert res.exit_code == 0
    fpr = res.json_data["negative_control_fpr"]
    assert fpr <= 0.05, f"Negative control FPR {fpr} exceeds 0.05 threshold"


def test_evaluate_gate_passed_boolean(lab_env):
    """F26-T1-5: Evaluator summary marks gate_passed=True when all benchmark thresholds are met."""
    res = run_bll(["evaluate", "--runs-dir", str(lab_env / "runs"), "--ground-truth-dir", str(lab_env / "ground_truth"), "--json"])
    assert res.exit_code == 0
    assert res.json_data["gate_passed"] is True
