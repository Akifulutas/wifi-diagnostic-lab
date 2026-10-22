"""
Unit Tests for Milestone 3: Measurement Adapters, Phase Engine, Clock & Pipeline.
tests/unit/test_phase_engine.py
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from bll.measurements.adapters import (
    Iperf3Adapter,
    IrttAdapter,
    PingAdapter,
    QdiscPoller,
)
from bll.measurements.clock import ClockSyncValidator, MonotonicClock
from bll.measurements.engine import MeasurementEngine, PhaseDurations
from bll.runner.phase_engine import execute_run
from bll.storage.analytics import DuckDBAnalytics
from bll.storage.pipeline import RunPipeline
from bll.storage.schemas import RunManifest


# ============================================================================
# 1. Measurement Adapters Tests
# ============================================================================

def test_ping_adapter_valid_and_timeout():
    adapter = PingAdapter(dst_ip="10.10.5.2", run_id="test_run")

    # Valid line
    line = "64 bytes from 10.10.5.2: icmp_seq=1 ttl=64 time=24.5 ms"
    sample = adapter.parse_line(line, "baseline_idle", 1_000_000_000)
    assert sample is not None
    assert sample.seq == 1
    assert sample.rtt_ms == 24.5
    assert sample.ttl == 64
    assert sample.lost is False
    assert sample.timeout is False

    # Timeout line
    timeout_line = "Request timeout for icmp_seq 5"
    lost_sample = adapter.parse_line(timeout_line, "saturation_load", 2_000_000_000)
    assert lost_sample is not None
    assert lost_sample.seq == 5
    assert lost_sample.rtt_ms is None
    assert lost_sample.lost is True
    assert lost_sample.timeout is True


def test_irtt_adapter_clock_sync_gating():
    adapter = IrttAdapter(dst_ip="10.10.5.2", run_id="test_run")
    report = {
        "round_trip": {"mean": 24_000_000, "median": 23_800_000},
        "ipdv": {"mean": 600_000},
        "forward": {"mean": 11_500_000},
        "reverse": {"mean": 12_300_000},
        "stats": {"lost": 0},
        "server": {"processing_time": 250_000},
    }

    # When clock sync is unverified: OWD must be None!
    samples_unsync = adapter.parse_json_report(report, "baseline_idle", clock_sync_verified=False)
    assert len(samples_unsync) == 1
    assert samples_unsync[0].owd_fwd_ms is None
    assert samples_unsync[0].owd_rev_ms is None
    assert samples_unsync[0].rtt_ms == 23.8

    # When clock sync is verified: OWD is populated
    samples_sync = adapter.parse_json_report(report, "baseline_idle", clock_sync_verified=True)
    assert samples_sync[0].owd_fwd_ms == 11.5
    assert samples_sync[0].owd_rev_ms == 12.3


def test_iperf3_adapter_intervals():
    adapter = Iperf3Adapter(server_ip="10.10.5.2", run_id="test_run")
    payload = {
        "intervals": [
            {
                "streams": [
                    {
                        "start": 0.0,
                        "end": 1.0,
                        "bytes": 2_500_000,
                        "bits_per_second": 20_000_000.0,
                        "retransmits": 2,
                        "rtt": 28000,
                        "rttvar": 800,
                        "snd_cwnd": 65536,
                    }
                ],
                "sum": {
                    "start": 0.0,
                    "end": 1.0,
                    "bytes": 2_500_000,
                    "bits_per_second": 20_000_000.0,
                    "retransmits": 2,
                },
            }
        ],
        "end": {"cpu_utilization_percent": {"host_total": 6.2}},
    }
    samples = adapter.parse_json_intervals(payload, phase="saturation_load")
    assert len(samples) == 1
    assert samples[0].throughput_bps == 20_000_000.0
    assert samples[0].retransmits == 2
    assert samples[0].rtt_ms == 28.0
    assert samples[0].rttvar_ms == 0.8
    assert samples[0].cwnd_bytes == 65536
    assert samples[0].cpu_host_pct == 6.2


def test_qdisc_poller():
    poller = QdiscPoller()
    sample_out = (
        "qdisc tbf 1: root refcnt 2 rate 20Mbit burst 15Kb lat 50.0ms\n"
        " Sent 2500000 bytes 1700 pkt (dropped 5, overlimits 120 requeues 0)\n"
        " backlog 50000b 35p requeues 0"
    )
    s = poller.parse_tc_output(
        sample_out, "bll-qnear", "bll-qn-rtr", "saturation_load", "test_run", 1_000_000_000
    )
    assert s is not None
    assert s.qdisc_kind == "tbf"
    assert s.backlog_bytes == 50000
    assert s.backlog_packets == 35
    assert s.drops == 5
    assert s.overlimits == 120


# ============================================================================
# 2. Monotonic Clock & Clock Sync Validator Tests
# ============================================================================

def test_monotonic_clock():
    clk = MonotonicClock()
    r1 = clk.read()
    r2 = clk.read()
    assert r2.monotonic_ns >= r1.monotonic_ns
    assert clk.elapsed_s() >= 0.0


def test_clock_sync_validator():
    validator = ClockSyncValidator(max_allowable_offset_ms=1.0)

    # Clean synchronized timestamps (offset = 0.5ms <= 1.0ms)
    # t1=0, t2=10_500_000, t3=11_000_000, t4=21_000_000
    ok, offset_ms, err = validator.validate_offset(
        client_tx_ns=0,
        server_rx_ns=10_500_000,
        server_tx_ns=11_000_000,
        client_rx_ns=21_000_000,
    )
    assert ok is True
    assert offset_ms <= 1.0
    assert err is None

    # Desynchronized timestamps (offset = 5.0ms > 1.0ms)
    ok, offset_ms, err = validator.validate_offset(
        client_tx_ns=0,
        server_rx_ns=15_000_000,
        server_tx_ns=16_000_000,
        client_rx_ns=21_000_000,
    )
    assert ok is False
    assert offset_ms > 1.0
    assert "exceeds threshold" in err


# ============================================================================
# 3. Pipeline, Parquet Storage & Isolated Ground Truth Tests
# ============================================================================

def test_run_pipeline_lifecycle(tmp_path: Path):
    runs_dir = tmp_path / "runs"
    gt_dir = tmp_path / "ground_truth"

    pipeline = RunPipeline(runs_base_dir=runs_dir, ground_truth_base_dir=gt_dir)
    pipeline.initialize_directories()

    assert pipeline.run_dir.exists()
    assert pipeline.raw_dir.exists()
    assert pipeline.samples_dir.exists()

    # Record events
    pipeline.record_event("TEST_EVENT", {"detail": "unit_test"})
    events_content = (pipeline.run_dir / "events.jsonl").read_text()
    assert "TEST_EVENT" in events_content

    # Save raw log
    pipeline.save_raw_log("ping.log", "dummy ping content")
    assert (pipeline.raw_dir / "ping.log").exists()

    # Write Parquet table
    adapter = PingAdapter(dst_ip="10.10.5.2", run_id=pipeline.run_id)
    sample = adapter.parse_line(
        "64 bytes from 10.10.5.2: icmp_seq=1 ttl=64 time=24.5 ms",
        "baseline_idle",
        1_000_000_000,
    )
    assert sample is not None
    parquet_path = pipeline.write_parquet_samples("ping", [sample])
    assert parquet_path.exists()

    # Finalize manifest
    manifest = pipeline.finalize_manifest(duration_s=10.0)
    assert manifest.run_id == pipeline.run_id
    assert (pipeline.run_dir / "manifest.json").exists()
    assert "samples/ping.parquet" in manifest.artifacts

    # Save isolated ground truth
    gt_path = pipeline.save_ground_truth(
        scenario_name="residential_dsl_near_fifo",
        bottleneck_regions=["near_link"],
        expected_latency_increase=True,
        expected_queue_evidence="strong",
        expected_supported_regions=["near_link"],
        expected_not_excluded_regions=["near_link"],
    )
    assert gt_path.exists()
    assert gt_path.parent == gt_dir
    gt_data = json.loads(gt_path.read_text())
    assert gt_data["scenario_name"] in ("near_fifo", "residential_dsl_near_fifo")


# ============================================================================
# 4. DuckDB Analytics Tests
# ============================================================================

def test_duckdb_analytics(tmp_path: Path):
    runs_dir = tmp_path / "runs"
    gt_dir = tmp_path / "ground_truth"

    engine = MeasurementEngine(
        durations=PhaseDurations(idle_s=0.1, load_s=0.1, recovery_s=0.1),
        runs_dir=runs_dir,
        ground_truth_dir=gt_dir,
    )
    run_id, pipeline = engine.run_experiment("residential_dsl_near_fifo")

    analytics = DuckDBAnalytics(pipeline.run_dir)
    rtt_summary = analytics.get_rtt_summary_by_phase()
    assert "baseline_idle" in rtt_summary
    assert "saturation_load" in rtt_summary

    tput_summary = analytics.get_throughput_summary()
    assert "mean_mbps" in tput_summary

    delta = analytics.get_bufferbloat_delta()
    assert isinstance(delta, float)


# ============================================================================
# 5. CLI Execution & Runner Bridge Tests
# ============================================================================

def test_execute_run_bridge(tmp_path: Path):
    runs_dir = tmp_path / "runs"
    gt_dir = tmp_path / "ground_truth"

    run_id = execute_run(
        scenario="healthy_baseline",
        idle_s=0.05,
        load_s=0.05,
        recovery_s=0.05,
        runs_dir=runs_dir,
        ground_truth_dir=gt_dir,
    )
    assert run_id.startswith("run_")
    run_path = runs_dir / run_id
    assert (run_path / "manifest.json").exists()
    assert (run_path / "samples" / "ping.parquet").exists()
    assert (run_path / "samples" / "iperf3.parquet").exists()
    assert (gt_dir / f"{run_id}.json").exists()
