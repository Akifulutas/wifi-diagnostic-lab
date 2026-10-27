"""
Feature 23: Statistical Hypothesis Verification
Tier 1: Feature Coverage (>=5 test cases)
"""

import pytest
from e2e_tests.harness import run_bll


def test_hypothesis_h1_observer_marginal_value(lab_env):
    """F23-T1-1: Hypothesis H1 verified: Observer provides empirical candidate set reduction."""
    res = run_bll(["evaluate", "--runs-dir", str(lab_env / "runs"), "--ground-truth-dir", str(lab_env / "ground_truth"), "--json"])
    assert res.exit_code == 0
    h1 = res.json_data.get("hypotheses_results", {}).get("H1_observer_marginal_value", {})
    assert h1.get("supported") is True
    assert h1.get("positive_reduction_runs") > 0
    assert h1.get("candidate_reduction_median") > 0.0
    assert h1.get("statistical_validation") == "deferred_to_large_sample_trials"


def test_hypothesis_h2_indistinguishable_pairs_abstention(lab_env):
    """F23-T1-2: Hypothesis H2 verified: Indistinguishable scenario pairs yield 100% abstention rate."""
    res = run_bll(["evaluate", "--runs-dir", str(lab_env / "runs"), "--ground-truth-dir", str(lab_env / "ground_truth"), "--json"])
    assert res.exit_code == 0
    h2 = res.json_data.get("hypotheses_results", {}).get("H2_abstention_on_indistinguishable_pairs", {})
    assert h2.get("supported") is True
    assert h2.get("abstention_rate") == 1.0


def test_hypothesis_h3_protocol_discrepancy(lab_env):
    """F23-T1-3: Hypothesis H3 verified: ICMP ping underestimates loaded TCP delay under FQ-CoDel."""
    res = run_bll(["evaluate", "--runs-dir", str(lab_env / "runs"), "--ground-truth-dir", str(lab_env / "ground_truth"), "--json"])
    assert res.exit_code == 0
    h3 = res.json_data.get("hypotheses_results", {}).get("H3_protocol_discrepancy_icmp_vs_tcp", {})
    assert h3.get("supported") is True
    assert h3.get("icmp_delay_underestimation_pct") > 50.0


def test_hypothesis_statistical_validation_contract(lab_env):
    """F23-T1-4: Statistical validation contract explicitly defers inferential p-values to high-sample trials."""
    res = run_bll(["evaluate", "--runs-dir", str(lab_env / "runs"), "--ground-truth-dir", str(lab_env / "ground_truth"), "--json"])
    assert res.exit_code == 0
    for h_key in ["H1_observer_marginal_value", "H2_abstention_on_indistinguishable_pairs", "H3_protocol_discrepancy_icmp_vs_tcp"]:
        hyp = res.json_data["hypotheses_results"][h_key]
        assert hyp.get("statistical_validation") == "deferred_to_large_sample_trials"
        assert "note" in hyp


def test_hypothesis_all_three_hypotheses_evaluated(lab_env):
    """F23-T1-5: Evaluator summary contains all three core hypotheses."""
    res = run_bll(["evaluate", "--runs-dir", str(lab_env / "runs"), "--ground-truth-dir", str(lab_env / "ground_truth"), "--json"])
    assert res.exit_code == 0
    hyps = res.json_data.get("hypotheses_results", {})
    assert "H1_observer_marginal_value" in hyps
    assert "H2_abstention_on_indistinguishable_pairs" in hyps
    assert "H3_protocol_discrepancy_icmp_vs_tcp" in hyps
