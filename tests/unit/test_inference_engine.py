"""
Unit Tests for Milestone 4: Deterministic Inference Engine, Ambiguity & Next Measurement.
tests/unit/test_inference_engine.py
"""

import json
from pathlib import Path
import pytest
import pyarrow as pa
import pyarrow.parquet as pq

from bll.inference.engine import DeterministicEngine, run_inference
from bll.storage.pipeline import RunPipeline
from bll.storage.schemas import (
    AbstainReason,
    InferenceVerdict,
    QualityAudit,
    QualityFlags,
    QueueEvidenceLevel,
    RegionName,
    VantageProfile,
)


@pytest.fixture
def mock_run_dir(tmp_path: Path):
    """Creates a mock immutable run directory with multi-path telemetry without touching ground_truth/."""
    run_dir = tmp_path / "runs" / "run_test_m4_001"
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": "1.0.0",
        "run_id": "run_test_m4_001",
        "scenario_id": "residential_dsl_near_fifo",
        "start_time_utc": "2026-10-21T20:00:00Z",
        "duration_seconds": 110.0,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    quality = {
        "run_id": "run_test_m4_001",
        "valid_for_inference": True,
        "flags": [],
        "checks": {"clock_synchronized": True, "qdisc_verified": True},
    }
    (run_dir / "quality.json").write_text(json.dumps(quality, indent=2))

    # Multi-path telemetry with near-link queue inflation (+150ms in load)
    samples_dir = run_dir / "samples"
    samples_dir.mkdir(parents=True, exist_ok=True)
    timestamps = [1000000000 + i * 100000000 for i in range(30)]
    phases = ["idle"] * 10 + ["load"] * 10 + ["recovery"] * 10

    # client_to_remote: 10ms idle, 160ms load (+150ms), 10ms recovery
    rtts_e2e = [10.0] * 10 + [160.0] * 10 + [10.0] * 10
    # client_to_gateway: 2ms idle, 152ms load (+150ms), 2ms recovery
    rtts_near = [2.0] * 10 + [152.0] * 10 + [2.0] * 10
    # observer_to_remote: 8ms idle, 8ms load (+0ms), 8ms recovery
    rtts_far = [8.0] * 10 + [8.0] * 10 + [8.0] * 10

    all_ts = timestamps * 3
    all_phases = phases * 3
    all_rtts = rtts_e2e + rtts_near + rtts_far
    all_paths = ["client_to_remote"] * 30 + ["client_to_gateway"] * 30 + ["observer_to_remote"] * 30
    all_seqs = list(range(1, 31)) * 3

    table = pa.Table.from_arrays(
        [
            pa.array(all_ts, pa.int64()),
            pa.array(all_phases, pa.string()),
            pa.array(all_rtts, pa.float64()),
            pa.array(all_seqs, pa.int32()),
            pa.array(all_paths, pa.string()),
        ],
        names=["timestamp_ns", "phase", "rtt_ms", "seq", "path"],
    )
    pq.write_table(table, samples_dir / "ping.parquet")
    return run_dir


def test_inference_full_vantage_localizes_near_link(mock_run_dir: Path):
    """Under full observer vantage, near-link bufferbloat is unambiguously localized."""
    verdict = run_inference(mock_run_dir, vantage_profile="full_observer")
    assert isinstance(verdict, InferenceVerdict)
    assert verdict.latency_increase_observed is True
    assert RegionName.NEAR_LINK in verdict.supported_regions
    assert RegionName.NEAR_LINK in verdict.not_excluded_regions
    assert verdict.abstained is False
    assert verdict.abstain_reason is None
    assert verdict.next_measurement is None


def test_inference_remote_only_triggers_set_valued_abstention(mock_run_dir: Path):
    """Under remote-only vantage, engine retains candidate set and explicitly abstains."""
    verdict = run_inference(mock_run_dir, vantage_profile="remote_only")
    assert verdict.abstained is True
    assert verdict.abstain_reason is not None
    assert "ambiguous" in verdict.abstain_reason.lower()
    # Candidate regions preserved
    assert RegionName.NEAR_LINK in verdict.not_excluded_regions
    assert RegionName.FAR_LINK in verdict.not_excluded_regions
    # Next measurement recommended
    assert verdict.next_measurement is not None
    assert "gateway" in verdict.next_measurement.lower()


def test_inference_healthy_baseline_negative_control(tmp_path: Path):
    """Healthy baseline run produces zero queue evidence and empty supported regions."""
    run_dir = tmp_path / "runs" / "run_healthy_test"
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": "1.0.0",
        "run_id": "run_healthy_test",
        "scenario_id": "healthy_baseline",
        "start_time_utc": "2026-10-21T20:00:00Z",
        "duration_seconds": 110.0,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest))
    verdict = run_inference(run_dir)
    assert verdict.latency_increase_observed is False
    assert verdict.queue_evidence == QueueEvidenceLevel.NONE
    assert verdict.supported_regions == []
    assert verdict.abstained is False


def test_inference_fixed_delay_discriminated_as_non_queue(tmp_path: Path):
    """Fixed propagation delay without buffer queue is not falsely attributed to bufferbloat."""
    run_dir = tmp_path / "runs" / "run_fixed_delay_test"
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": "1.0.0",
        "run_id": "run_fixed_delay_test",
        "scenario_id": "fixed_propagation_delay_control",
        "start_time_utc": "2026-10-21T20:00:00Z",
        "duration_seconds": 110.0,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest))
    
    # Telemetry with high fixed propagation delay (60ms) across all phases
    samples_dir = run_dir / "samples"
    samples_dir.mkdir(parents=True, exist_ok=True)
    n_samples = 30
    phases = ["idle"] * 10 + ["load"] * 10 + ["recovery"] * 10
    rtts = [60.0] * 30  # Flat 60ms delay, Delta RTT = 0ms
    table = pa.Table.from_arrays(
        [
            pa.array(list(range(n_samples)), pa.int64()),
            pa.array(phases, pa.string()),
            pa.array(rtts, pa.float64()),
            pa.array(list(range(1, n_samples + 1)), pa.int32()),
            pa.array(["client_to_remote"] * n_samples, pa.string()),
        ],
        names=["timestamp_ns", "phase", "rtt_ms", "seq", "path"],
    )
    pq.write_table(table, samples_dir / "ping.parquet")

    verdict = run_inference(run_dir)
    assert verdict.latency_increase_observed is False
    assert verdict.queue_evidence == QueueEvidenceLevel.NONE
    assert verdict.supported_regions == []


def test_inference_cpu_saturation_quality_flag_forces_abstention(tmp_path: Path):
    """Critical quality control flag (CLIENT_CPU_SATURATION) forces localization abstention."""
    run_dir = tmp_path / "runs" / "run_cpu_sat_test"
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": "1.0.0",
        "run_id": "run_cpu_sat_test",
        "scenario_id": "endpoint_cpu_saturation_control",
        "start_time_utc": "2026-10-21T20:00:00Z",
        "duration_seconds": 110.0,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest))
    quality = {
        "run_id": "run_cpu_sat_test",
        "valid_for_inference": False,
        "flags": ["CLIENT_CPU_SATURATION"],
        "checks": {"clock_synchronized": True, "qdisc_verified": True},
    }
    (run_dir / "quality.json").write_text(json.dumps(quality))
    verdict = run_inference(run_dir)
    assert verdict.abstained is True
    assert "CLIENT_CPU_SATURATION" in verdict.quality_flags
    assert "repeat_test_with_unloaded_cpu" in verdict.next_measurement


def test_inference_zero_label_leakage_on_scenario_rename(mock_run_dir: Path):
    """Verifies that altering scenario_id in manifest.json does NOT change the verdict."""
    v1 = run_inference(mock_run_dir, vantage_profile="full_observer")

    # Tamper with scenario_id to an unseen arbitrary name
    manifest_file = mock_run_dir / "manifest.json"
    m_data = json.loads(manifest_file.read_text(encoding="utf-8"))
    m_data["scenario_id"] = "arbitrary_user_experiment_name_xyz_999"
    manifest_file.write_text(json.dumps(m_data, indent=2), encoding="utf-8")

    v2 = run_inference(mock_run_dir, vantage_profile="full_observer")
    assert v1.supported_regions == v2.supported_regions
    assert v1.not_excluded_regions == v2.not_excluded_regions
    assert v1.abstained == v2.abstained
    assert v1.latency_increase_observed == v2.latency_increase_observed
    assert v1.queue_evidence == v2.queue_evidence


def test_inference_prohibits_ground_truth_label_leakage(tmp_path: Path):
    """Inference engine strictly refuses to inspect directories inside ground_truth/."""
    gt_dir = tmp_path / "ground_truth" / "run_leakage_attempt"
    gt_dir.mkdir(parents=True, exist_ok=True)
    with pytest.raises(PermissionError, match="Label leakage violation"):
        run_inference(gt_dir)
