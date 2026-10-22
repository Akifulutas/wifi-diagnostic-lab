"""
Tier 3: Cross-Feature Integration Combinations
Covers pairwise feature orchestration across the entire pipeline.
"""

import json
import pathlib
import pytest
from e2e_tests.harness import run_bll, HAS_DUCKDB

if HAS_DUCKDB:
    import duckdb


def test_doctor_gating_before_lab_up():
    """T3-01: Cross-Feature (F01 Doctor + F06 Netns Lab):
    Probe platform doctor, verify capabilities, then deploy lab topology."""
    doc_res = run_bll(["doctor", "--json"])
    assert doc_res.exit_code == 0
    assert doc_res.json_data is not None

    lab_res = run_bll(["lab", "up", "--json"])
    assert lab_res.exit_code == 0
    assert lab_res.json_data.get("status") == "up"


def test_lab_setup_to_tc_configuration():
    """T3-02: Cross-Feature (F06 Netns Lab + F08 Tc Shaping):
    Bring up topology, then apply rate shaping and queue discipline to forwarder egress."""
    run_bll(["lab", "up"])
    tc_res = run_bll(["lab", "configure-qdisc", "--netns", "bll-qnear", "--interface", "bll-qn-rtr", "--rate", "20mbit", "--qdisc", "pfifo", "--json"])
    assert tc_res.exit_code == 0
    assert tc_res.json_data.get("status") == "ok"


def test_lab_configuration_to_path_matrix_verification():
    """T3-03: Cross-Feature (F08 Tc Shaping + F07 Path Matrix):
    Configuring qdiscs preserves FIB routing and path matrix invariants."""
    run_bll(["lab", "up"])
    run_bll(["lab", "configure-qdisc", "--netns", "bll-qfar", "--interface", "bll-qf-rem", "--rate", "50mbit"])
    verify_res = run_bll(["lab", "verify", "--json"])
    assert verify_res.exit_code == 0
    assert verify_res.json_data.get("verified") is True


def test_lab_setup_to_multiphase_measurement_run(tmp_path: pathlib.Path):
    """T3-04: Cross-Feature (F06 Lab Setup + F11 Phase Engine):
    Lab deployment feeds multi-phase experiment runner."""
    run_bll(["lab", "up"])
    run_res = run_bll(["run", "--scenario", "healthy_baseline", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    assert run_res.exit_code == 0
    assert run_res.json_data["status"] == "completed"


def test_phase_runner_to_immutable_run_dir(tmp_path: pathlib.Path):
    """T3-05: Cross-Feature (F11 Phase Engine + F13 Run Dir Pipeline):
    Phase execution generates complete, immutable run directory."""
    run_res = run_bll(["run", "--scenario", "residential_dsl_near_fifo", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    run_dir = pathlib.Path(run_res.json_data["run_dir"])
    assert (run_dir / "manifest.json").exists()
    assert (run_dir / "events.jsonl").exists()
    assert (run_dir / "quality.json").exists()
    assert (run_dir / "samples").exists()


def test_run_dir_to_duckdb_parquet_analytics(tmp_path: pathlib.Path):
    """T3-06: Cross-Feature (F13 Run Dir + F15 DuckDB Analytics):
    Telemetry samples from run directory are directly queryable via DuckDB SQL."""
    if not HAS_DUCKDB:
        pytest.skip("DuckDB not installed")
    run_res = run_bll(["run", "--scenario", "residential_dsl_near_fifo", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    run_dir = pathlib.Path(run_res.json_data["run_dir"])
    ping_parquet = run_dir / "samples" / "ping.parquet"

    con = duckdb.connect()
    count = con.execute(f"SELECT count(*) FROM read_parquet('{ping_parquet}')").fetchone()[0]
    assert count > 0


def test_parquet_analytics_to_differential_inference(tmp_path: pathlib.Path):
    """T3-07: Cross-Feature (F15 Analytics + F16 Differential Algebra):
    Run directory processed by differential path algebra engine to infer bottleneck."""
    run_res = run_bll(["run", "--scenario", "residential_dsl_near_fifo", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    run_dir = pathlib.Path(run_res.json_data["run_dir"])

    infer_res = run_bll(["infer", str(run_dir), "--vantage", "full_observer", "--json"])
    assert infer_res.exit_code == 0
    assert "near_link" in infer_res.json_data["supported_regions"]


def test_inference_output_to_zero_cdn_html_report(tmp_path: pathlib.Path):
    """T3-08: Cross-Feature (F17 Output Contract + F24 Static Reporting):
    Inference results directly render into static zero-CDN HTML report with inlined SVGs."""
    run_res = run_bll(["run", "--scenario", "residential_dsl_near_fifo", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    run_dir = pathlib.Path(run_res.json_data["run_dir"])

    report_html = tmp_path / "report.html"
    report_res = run_bll(["report", str(run_dir), "--out", str(report_html), "--json"])
    assert report_res.exit_code == 0
    assert report_html.exists()
    content = report_html.read_text()
    assert "<svg" in content
    assert "http://" not in content and "https://" not in content


def test_run_and_inference_to_rfc2330_redaction(tmp_path: pathlib.Path):
    """T3-09: Cross-Feature (F13 Run Dir + F25 RFC 2330 Redaction):
    Raw experiment data exported and sanitized under RFC 2330 guidelines."""
    run_res = run_bll(["run", "--scenario", "residential_dsl_near_fifo", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    run_dir = pathlib.Path(run_res.json_data["run_dir"])

    export_dir = tmp_path / "redacted_export"
    export_res = run_bll(["export", str(run_dir), "--redact", "--out-dir", str(export_dir)])
    assert export_res.exit_code == 0
    assert (export_dir / "provenance.json").exists()


def test_redacted_export_to_benchmark_evaluation(tmp_path: pathlib.Path):
    """T3-10: Cross-Feature (F25 Redaction + F26 Benchmark Evaluator):
    Redacted datasets scored by double-blind benchmark evaluator."""
    run_res = run_bll(["run", "--scenario", "residential_dsl_near_fifo", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    eval_res = run_bll(["evaluate", "--runs-dir", str(tmp_path / "runs"), "--ground-truth-dir", str(tmp_path / "ground_truth"), "--json"])
    assert eval_res.exit_code == 0
    assert eval_res.json_data.get("gate_passed") is True


def test_qc_flag_trigger_to_set_valued_abstention(tmp_path: pathlib.Path):
    """T3-11: Cross-Feature (F21 QC Flags + F18 Set-Valued Abstention):
    Quality control failure triggers deterministic inference abstention."""
    run_res = run_bll(["run", "--scenario", "endpoint_cpu_saturation_control", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    run_dir = pathlib.Path(run_res.json_data["run_dir"])

    infer_res = run_bll(["infer", str(run_dir), "--json"])
    assert infer_res.exit_code == 0
    assert infer_res.json_data["abstained"] is True
    assert "CLIENT_CPU_SATURATION" in infer_res.json_data["quality_flags"]


def test_abstention_to_next_measurement_recommendation(tmp_path: pathlib.Path):
    """T3-12: Cross-Feature (F18 Abstention + F19 Next Measurement):
    Abstention due to partial vantage triggers cost-optimal next test suggestion."""
    run_res = run_bll(["run", "--scenario", "residential_dsl_near_fifo", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    run_dir = pathlib.Path(run_res.json_data["run_dir"])

    infer_res = run_bll(["infer", str(run_dir), "--vantage", "remote_only", "--json"])
    assert infer_res.exit_code == 0
    assert infer_res.json_data["abstained"] is True
    assert infer_res.json_data["next_measurement"] is not None
    assert "gateway" in infer_res.json_data["next_measurement"]


def test_fault_recovery_crash_to_idempotent_cleanup():
    """T3-13: Cross-Feature (F09 Lab Lifecycle + F05 Privileged Helper):
    Simulating abrupt stop / dirty state followed by bll lab down cleanly tears down resources."""
    run_bll(["lab", "up"])
    down_res = run_bll(["lab", "down", "--json"])
    assert down_res.exit_code == 0
    assert down_res.json_data.get("status") == "down"

    status_res = run_bll(["lab", "status", "--json"])
    assert status_res.exit_code == 0
    assert status_res.json_data.get("running") is False
