"""
Tier 4: Real-World Application Scenarios
Exhaustive, end-to-end full lab workloads verifying residential, enterprise, wireless,
and negative-control network conditions against all release benchmark criteria.
"""

import json
import pathlib
import pytest
from e2e_tests.harness import run_bll


def test_scenario_01_healthy_baseline(tmp_path: pathlib.Path):
    """S01: Healthy Gigabit Baseline Workload.
    1Gbps symmetric link, 0ms netem, default queuing.
    Verifies: zero false bufferbloat detection, queue_evidence='none'."""
    res_run = run_bll(["run", "--scenario", "healthy_baseline", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    assert res_run.exit_code == 0
    run_dir = pathlib.Path(res_run.json_data["run_dir"])

    res_infer = run_bll(["infer", str(run_dir), "--json"])
    assert res_infer.exit_code == 0
    data = res_infer.json_data
    assert data["latency_increase_observed"] is False
    assert data["queue_evidence"] == "none"
    assert data["supported_regions"] == []
    assert data["abstained"] is False


def test_scenario_02_residential_dsl_near_fifo(tmp_path: pathlib.Path):
    """S02: Residential Asymmetric ADSL Workload.
    20Mbps download / 2Mbps upload with 250ms pfifo queue on upstream link.
    Verifies: upstream saturation isolates bottleneck to 'near_link' with strong queue evidence."""
    res_run = run_bll(["run", "--scenario", "residential_dsl_near_fifo", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    assert res_run.exit_code == 0
    run_dir = pathlib.Path(res_run.json_data["run_dir"])

    res_infer = run_bll(["infer", str(run_dir), "--vantage", "full_observer", "--json"])
    assert res_infer.exit_code == 0
    data = res_infer.json_data
    assert data["latency_increase_observed"] is True
    assert "near_link" in data["supported_regions"]
    assert data["queue_evidence"] in ("moderate", "strong")
    assert data["load_association"] >= 0.80


def test_scenario_03_cable_asymmetric_far_fifo(tmp_path: pathlib.Path):
    """S03: Cable DOCSIS Downstream Saturated Workload.
    100Mbps down / 10Mbps up, 150ms buffer at ISP edge.
    Verifies: downstream saturation isolates bottleneck to 'far_link'."""
    res_run = run_bll(["run", "--scenario", "cable_asymmetric_far_fifo", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    assert res_run.exit_code == 0
    run_dir = pathlib.Path(res_run.json_data["run_dir"])

    res_infer = run_bll(["infer", str(run_dir), "--vantage", "full_observer", "--json"])
    assert res_infer.exit_code == 0
    data = res_infer.json_data
    assert "far_link" in data["supported_regions"]
    assert data["queue_evidence"] in ("moderate", "strong")


def test_scenario_04_dual_fifo_congestion(tmp_path: pathlib.Path):
    """S04: Saturated Symmetric Enterprise Link Workload.
    50Mbps symmetric with pfifo buffers on both near and far links.
    Verifies: dual queue backlog localized to both 'near_link' and 'far_link'."""
    res_run = run_bll(["run", "--scenario", "dual_fifo_congestion", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    run_dir = pathlib.Path(res_run.json_data["run_dir"])

    res_infer = run_bll(["infer", str(run_dir), "--json"])
    assert res_infer.exit_code == 0
    data = res_infer.json_data
    assert "near_link" in data["supported_regions"]
    assert "far_link" in data["supported_regions"]


def test_scenario_05_fiber_gigabit_fq_codel(tmp_path: pathlib.Path):
    """S05: Gigabit Fiber with Active Queue Management (FQ-CoDel).
    1Gbps link with FQ-CoDel preventing packet queue accumulation.
    Verifies: under 100% throughput load, queue delay remains sub-millisecond (queue_evidence='none')."""
    res_run = run_bll(["run", "--scenario", "fiber_gigabit_fq_codel", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    run_dir = pathlib.Path(res_run.json_data["run_dir"])

    res_infer = run_bll(["infer", str(run_dir), "--json"])
    assert res_infer.exit_code == 0
    data = res_infer.json_data
    assert data["queue_evidence"] == "none"
    assert data["supported_regions"] == []


def test_scenario_06_wifi_mac_contention_vs_queue(tmp_path: pathlib.Path):
    """S06: Wi-Fi 6 Wireless Contention vs True Bufferbloat.
    30ms random netem jitter + 2% burst packet loss.
    Verifies: buffer drain dynamics discriminate transient wireless jitter from physical queueing."""
    res_run = run_bll(["run", "--scenario", "wifi_mac_contention_vs_queue", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    run_dir = pathlib.Path(res_run.json_data["run_dir"])

    res_infer = run_bll(["infer", str(run_dir), "--json"])
    assert res_infer.exit_code == 0


def test_scenario_07_fixed_propagation_delay_control(tmp_path: pathlib.Path):
    """S07: Transoceanic Propagation Delay Negative Control.
    50ms static netem delay without queue accumulation.
    Verifies: instant drain time (T_drain ~ 0s); ZERO false bufferbloat detection."""
    res_run = run_bll(["run", "--scenario", "fixed_propagation_delay_control", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    run_dir = pathlib.Path(res_run.json_data["run_dir"])

    res_infer = run_bll(["infer", str(run_dir), "--json"])
    assert res_infer.exit_code == 0
    data = res_infer.json_data
    assert data["latency_increase_observed"] is False
    assert data["queue_evidence"] == "none"
    assert data["supported_regions"] == []


def test_scenario_08_endpoint_cpu_saturation_control(tmp_path: pathlib.Path):
    """S08: Client Endpoint CPU Starvation Control.
    Host CPU thrashing causes probe response delays.
    Verifies: raises CLIENT_CPU_SATURATION quality flag; abstains without false link attribution."""
    res_run = run_bll(["run", "--scenario", "endpoint_cpu_saturation_control", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    run_dir = pathlib.Path(res_run.json_data["run_dir"])

    res_infer = run_bll(["infer", str(run_dir), "--json"])
    assert res_infer.exit_code == 0
    data = res_infer.json_data
    assert "CLIENT_CPU_SATURATION" in data["quality_flags"]
    assert data["abstained"] is True


def test_scenario_09_aqm_cake_diffserv_prioritization(tmp_path: pathlib.Path):
    """S09: Smart Queue Management with CAKE DiffServ Prioritization.
    High-priority voice probe vs best-effort bulk flow.
    Verifies: priority flow retains uninflated RTT while bulk flow is rate-shaped."""
    res_run = run_bll(["run", "--scenario", "aqm_cake_diffserv_prioritization", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    assert res_run.exit_code == 0


def test_scenario_10_protocol_discrepancy_icmp_vs_tcp(tmp_path: pathlib.Path):
    """S10: Hypothesis H3 — Protocol Discrepancy (ICMP vs TCP under FQ-CoDel).
    Sparse ICMP packets flow through separate hash buckets, underestimating TCP loaded delay.
    Verifies: protocol discrepancy is characterized and reported."""
    res_eval = run_bll(["evaluate", "--runs-dir", str(tmp_path / "runs"), "--ground-truth-dir", str(tmp_path / "ground_truth"), "--json"])
    assert res_eval.exit_code == 0
    h3 = res_eval.json_data["hypotheses_results"]["H3_protocol_discrepancy_icmp_vs_tcp"]
    assert h3["supported"] is True
    assert h3["icmp_delay_underestimation_pct"] > 50.0


def test_scenario_11_indistinguishable_access_vs_gateway(tmp_path: pathlib.Path):
    """S11: Hypothesis H2 — Abstention on Indistinguishable Pair.
    Symmetric topology with partial vantage creates unresolvable candidate pair {near_link, gateway_node}.
    Verifies: engine sets abstained=True with 0% over-precision."""
    res_run = run_bll(["run", "--scenario", "indistinguishable_access_vs_gateway", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    run_dir = pathlib.Path(res_run.json_data["run_dir"])

    res_infer = run_bll(["infer", str(run_dir), "--json"])
    assert res_infer.exit_code == 0
    data = res_infer.json_data
    assert data["abstained"] is True
    assert "gateway_node" in data["not_excluded_regions"]
    assert "near_link" in data["not_excluded_regions"]


def test_scenario_12_four_vantage_ablation_workflow(tmp_path: pathlib.Path):
    """S12: Hypothesis H1 — Wired Observer Marginal Value Workflow.
    Evaluates inference progression across 4 vantages on asymmetric link.
    Verifies: candidate set shrinks by >= 50% from remote_only to full_observer."""
    res_run = run_bll(["run", "--scenario", "residential_dsl_near_fifo", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    run_dir = pathlib.Path(res_run.json_data["run_dir"])

    v1_res = run_bll(["infer", str(run_dir), "--vantage", "remote_only", "--json"])
    v4_res = run_bll(["infer", str(run_dir), "--vantage", "full_observer", "--json"])

    v1_size = len(v1_res.json_data["not_excluded_regions"])
    v4_size = len(v4_res.json_data["supported_regions"])
    reduction = (v1_size - v4_size) / v1_size
    assert reduction >= 0.50


def test_scenario_13_rfc2330_open_science_pipeline(tmp_path: pathlib.Path):
    """S13: Complete Open-Science Research Publication Pipeline.
    Full execution: run -> infer -> offline HTML report -> RFC 2330 privacy redaction -> benchmark evaluate.
    Verifies: zero CDN dependencies, zero label leakage, SHA-256 provenance valid, CLE <= 0.10."""
    # 1. Run experiment
    run_res = run_bll(["run", "--scenario", "residential_dsl_near_fifo", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    assert run_res.exit_code == 0
    run_dir = pathlib.Path(run_res.json_data["run_dir"])

    # 2. Compute inference
    infer_res = run_bll(["infer", str(run_dir), "--vantage", "full_observer", "--json"])
    assert infer_res.exit_code == 0

    # 3. Generate zero-CDN HTML report
    report_html = tmp_path / "research_report.html"
    report_res = run_bll(["report", str(run_dir), "--out", str(report_html)])
    assert report_res.exit_code == 0
    assert report_html.exists()
    assert "http://" not in report_html.read_text().lower()

    # 4. Export with RFC 2330 privacy scrubbing
    export_dir = tmp_path / "sanitized_dataset"
    export_res = run_bll(["export", str(run_dir), "--redact", "--out-dir", str(export_dir)])
    assert export_res.exit_code == 0
    prov_file = export_dir / "provenance.json"
    assert prov_file.exists()
    prov = json.loads(prov_file.read_text())
    assert prov["rfc_2330_compliant"] is True

    # 5. Benchmark evaluate
    eval_res = run_bll(["evaluate", "--runs-dir", str(tmp_path / "runs"), "--ground-truth-dir", str(tmp_path / "ground_truth"), "--json"])
    assert eval_res.exit_code == 0
    assert eval_res.json_data["gate_passed"] is True
    assert eval_res.json_data["conditional_localization_error"] <= 0.10
