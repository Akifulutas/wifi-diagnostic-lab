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


def test_hypothesis_h3_unmeasured_with_injected_params_not_evaluated(tmp_path):
    """F23-T1-6: Negative control: scenario injection parameters (15/150 ms) without paired empirical ICMP+TCP RTT telemetry must return not_evaluated and supported=False."""
    import json
    import pyarrow as pa
    import pyarrow.parquet as pq
    from bll.evaluation.benchmark import evaluate_benchmark_suite
    from e2e_tests.harness import create_synthetic_run

    # Case 1: ICMP telemetry exists, TCP RTT telemetry is missing (iperf3.parquet lacks rtt_ms), GT has 15/150 ms
    case1_dir = tmp_path / "case1"
    r1 = case1_dir / "runs" / "run_protocol_discrepancy_icmp_only"
    gt1 = case1_dir / "ground_truth" / "run_protocol_discrepancy_icmp_only.json"
    (case1_dir / "ground_truth").mkdir(parents=True, exist_ok=True)
    create_synthetic_run(r1, gt1, scenario="protocol_discrepancy", duration_idle=5.0, duration_load=10.0, duration_recovery=5.0)
    # Overwrite iperf3.parquet without rtt_ms column so TCP delay is unmeasured
    iperf_no_rtt = pa.Table.from_arrays(
        [
            pa.array([1_000_000_000, 2_000_000_000], pa.int64()),
            pa.array(["idle", "load"], pa.string()),
            pa.array([0.0, 95.5], pa.float64()),
            pa.array([0, 0], pa.int32()),
        ],
        names=["timestamp_ns", "phase", "throughput_mbps", "retransmits"],
    )
    pq.write_table(iperf_no_rtt, r1 / "samples" / "iperf3.parquet")

    summary1 = evaluate_benchmark_suite(case1_dir / "runs", case1_dir / "ground_truth")
    h3_1 = summary1.hypotheses_results["H3_protocol_discrepancy_icmp_vs_tcp"]
    assert h3_1["supported"] is False
    assert h3_1["status"] == "not_evaluated"
    assert h3_1["discrepancy_runs_evaluated"] == 0
    assert h3_1["icmp_delay_underestimation_pct"] is None
    assert h3_1["expected_synthetic_underestimation_pct"] == 90.0
    assert "observed empirically" not in h3_1["note"].lower()

    # Case 2: Neither ICMP nor TCP telemetry exists; only GT has 15/150 ms injection parameters
    case2_dir = tmp_path / "case2"
    r2 = case2_dir / "runs" / "run_protocol_discrepancy_no_samples"
    gt2 = case2_dir / "ground_truth" / "run_protocol_discrepancy_no_samples.json"
    (case2_dir / "ground_truth").mkdir(parents=True, exist_ok=True)
    create_synthetic_run(r2, gt2, scenario="protocol_discrepancy", duration_idle=5.0, duration_load=10.0, duration_recovery=5.0)
    (r2 / "samples" / "ping.parquet").unlink(missing_ok=True)
    (r2 / "samples" / "iperf3.parquet").unlink(missing_ok=True)

    summary2 = evaluate_benchmark_suite(case2_dir / "runs", case2_dir / "ground_truth")
    h3_2 = summary2.hypotheses_results["H3_protocol_discrepancy_icmp_vs_tcp"]
    assert h3_2["supported"] is False
    assert h3_2["status"] == "not_evaluated"
    assert h3_2["discrepancy_runs_evaluated"] == 0
    assert h3_2["icmp_delay_underestimation_pct"] is None
    assert h3_2["expected_synthetic_underestimation_pct"] == 90.0
    assert "observed empirically" not in h3_2["note"].lower()
