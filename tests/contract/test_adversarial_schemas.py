"""
Adversarial stress-test suite for BLL schemas and models.
tests/contract/test_adversarial_schemas.py

Empirically tests:
1. Pydantic models against corrupted, invalid, out-of-range, and injected payloads.
2. Extra field rejection (extra="forbid").
3. Semantic invariants (abstention consistency, set inclusion S subset C).
4. JSON Schema Draft 2020-12 enforcement against corrupted and edge-case payloads.
5. Known contract gaps and vulnerabilities.
"""

from __future__ import annotations

import json
import math
import pathlib
from typing import Any

import jsonschema
import pytest
from pydantic import ValidationError

from bll.storage.schemas import (
    AbstainReason,
    BackendType,
    CorrelationMetric,
    EnvironmentInfo,
    ExperimentParameters,
    GroundTruth,
    InferenceVerdict,
    InterfaceConfig,
    LinkConfig,
    LoadAssociation,
    LoadProfile,
    MeasurementProtocol,
    NextMeasurement,
    PathInvariants,
    PhaseParameters,
    ProbeProfile,
    QdiscConfig,
    QdiscKind,
    QualityAudit,
    QualityFlags,
    QualityMetrics,
    QueueEvidenceLevel,
    RegionName,
    RouteConfig,
    RunManifest,
    ScenarioName,
    TopologyNode,
    TopologySnapshot,
    TrafficDirection,
    TrafficProtocol,
    VantageProfile,
)

PROJ_ROOT = pathlib.Path(__file__).parent.parent.parent
SCHEMAS_DIR = PROJ_ROOT / "docs" / "schemas"


# ============================================================================
# 1. Pydantic Models: Extra Fields Rejection (extra="forbid")
# ============================================================================

@pytest.mark.parametrize(
    "model_cls,valid_kwargs",
    [
        (PhaseParameters, {"baseline_idle_s": 20.0, "saturation_load_s": 60.0, "recovery_s": 30.0}),
        (LoadProfile, {"protocol": TrafficProtocol.TCP, "direction": TrafficDirection.UPLOAD}),
        (ProbeProfile, {"ping_interval_s": 0.1, "irtt_interval_s": 0.02, "irtt_packet_len": 172}),
        (
            ExperimentParameters,
            {
                "phases": PhaseParameters(),
                "load_profile": LoadProfile(),
                "probe_profile": ProbeProfile(),
            },
        ),
        (
            EnvironmentInfo,
            {
                "hostname": "h",
                "os_name": "Linux",
                "kernel_release": "6.1",
                "architecture": "x86_64",
                "backend": BackendType.MOCK_SIMULATION,
                "git_commit": "abcdef",
                "git_dirty": False,
                "python_version": "3.14.0",
            },
        ),
        (QualityFlags, {}),
        (QualityMetrics, {"total_dropped_probes": 0}),
        (
            LoadAssociation,
            {
                "metric": CorrelationMetric.PEARSON_R,
                "correlation_coefficient": 0.5,
                "p_value": 0.01,
                "delta_rtt_ms": 5.0,
                "significant": True,
            },
        ),
        (
            NextMeasurement,
            {
                "recommended_action": "test",
                "target_vantage": "router",
                "target_protocol": MeasurementProtocol.ICMP,
                "estimated_cost": 2,
                "discriminating_power": "high",
            },
        ),
        (InterfaceConfig, {"name": "bll-eth0", "ipv4_address": "10.0.0.1/24"}),
        (RouteConfig, {"destination_cidr": "10.0.0.0/24", "interface": "bll-eth0"}),
        (
            PathInvariants,
            {"client_to_observer": True, "observer_to_remote": True, "client_to_remote": True},
        ),
        (
            LinkConfig,
            {
                "link_id": "l1",
                "subnet": "10.0.0.0/30",
                "node_a": "a",
                "interface_a": "ia",
                "ip_a": "10.0.0.1",
                "node_b": "b",
                "interface_b": "ib",
                "ip_b": "10.0.0.2",
            },
        ),
        (
            QdiscConfig,
            {
                "node": "n",
                "interface": "i",
                "direction": "egress",
                "qdisc_kind": QdiscKind.TBF,
                "handle": "1:",
                "parent": "root",
            },
        ),
        (
            TopologyNode,
            {
                "name": "node1",
                "role": "client",
                "forwarding_enabled": False,
                "interfaces": [],
                "routes": [],
            },
        ),
    ],
)
def test_all_models_strictly_forbid_extra_fields(model_cls: type, valid_kwargs: dict[str, Any]):
    """Ensure extra='forbid' is enforced across all models."""
    bad_kwargs = dict(valid_kwargs)
    bad_kwargs["malicious_extra_field"] = "payload_injection"
    with pytest.raises(ValidationError) as exc_info:
        model_cls(**bad_kwargs)
    assert "extra_forbidden" in str(exc_info.value) or "Extra inputs are not permitted" in str(exc_info.value)


# ============================================================================
# 2. Boundary Values and Invalid Types Stress Tests
# ============================================================================

def test_phase_parameters_negative_and_zero_values():
    """Phase parameters must be strictly positive (>0)."""
    with pytest.raises(ValidationError):
        PhaseParameters(baseline_idle_s=0.0)
    with pytest.raises(ValidationError):
        PhaseParameters(baseline_idle_s=-5.0)
    with pytest.raises(ValidationError):
        PhaseParameters(saturation_load_s=0.0)
    with pytest.raises(ValidationError):
        PhaseParameters(saturation_load_s=-1.0)
    with pytest.raises(ValidationError):
        PhaseParameters(recovery_s=0.0)
    with pytest.raises(ValidationError):
        PhaseParameters(recovery_s=-10.0)


def test_load_profile_boundary_values():
    """Load profile constraints on bitrate, parallel streams, socket buffer."""
    with pytest.raises(ValidationError):
        LoadProfile(target_bitrate_bps=0.0)
    with pytest.raises(ValidationError):
        LoadProfile(target_bitrate_bps=-1000.0)
    with pytest.raises(ValidationError):
        LoadProfile(parallel_streams=0)
    with pytest.raises(ValidationError):
        LoadProfile(parallel_streams=-1)
    with pytest.raises(ValidationError):
        LoadProfile(socket_buffer_bytes=1023)  # min 1024


def test_probe_profile_boundary_values():
    """Probe profile intervals and packet lengths."""
    with pytest.raises(ValidationError):
        ProbeProfile(ping_interval_s=0.001)  # gt 0.001
    with pytest.raises(ValidationError):
        ProbeProfile(ping_interval_s=0.0)
    with pytest.raises(ValidationError):
        ProbeProfile(irtt_interval_s=0.001)  # gt 0.001
    with pytest.raises(ValidationError):
        ProbeProfile(irtt_packet_len=63)  # ge 64
    with pytest.raises(ValidationError):
        ProbeProfile(irtt_packet_len=65508)  # le 65507


def test_run_manifest_invalid_run_ids():
    """RunManifest run_id must match UUID or run_<hex> format."""
    valid_params = ExperimentParameters(load_profile=LoadProfile())
    valid_env = EnvironmentInfo(
        hostname="h",
        os_name="Linux",
        kernel_release="6.1",
        architecture="x86_64",
        backend=BackendType.MOCK_SIMULATION,
        git_commit="abc",
        git_dirty=False,
        python_version="3.14",
    )

    # Valid run IDs
    RunManifest(run_id="run_12345678abcd", duration_seconds=10.0, parameters=valid_params, environment=valid_env)
    RunManifest(run_id="12345678-1234-1234-1234-123456789abc", duration_seconds=10.0, parameters=valid_params, environment=valid_env)

    # Invalid run IDs: path traversal, command injection, malformed strings
    for bad_id in [
        "../../etc/shadow",
        "run_",
        "run_INVALID!",
        "run_123; rm -rf /",
        "run 123456",
        "",
        "not_a_run_id",
    ]:
        with pytest.raises(ValidationError):
            RunManifest(run_id=bad_id, duration_seconds=10.0, parameters=valid_params, environment=valid_env)


def test_quality_metrics_cpu_percentages():
    """CPU percentages must be in [0.0, 100.0] and dropped probes non-negative."""
    with pytest.raises(ValidationError):
        QualityMetrics(client_max_cpu_percent=-0.1)
    with pytest.raises(ValidationError):
        QualityMetrics(client_max_cpu_percent=100.1)
    with pytest.raises(ValidationError):
        QualityMetrics(server_max_cpu_percent=-0.1)
    with pytest.raises(ValidationError):
        QualityMetrics(server_max_cpu_percent=100.1)
    with pytest.raises(ValidationError):
        QualityMetrics(total_dropped_probes=-1)
    with pytest.raises(ValidationError):
        QualityMetrics(load_reached_bps=-1.0)
    with pytest.raises(ValidationError):
        QualityMetrics(load_target_bps=-1.0)


def test_interface_config_name_regex_and_length():
    """Interface name must have 'bll-' prefix and <= 15 chars."""
    # Valid
    InterfaceConfig(name="bll-cli-qn", ipv4_address="10.10.1.1/30")
    InterfaceConfig(name="bll-1234567890", ipv4_address="10.10.1.1/30")

    # Invalid: > 15 chars
    with pytest.raises(ValidationError):
        InterfaceConfig(name="bll-toolongifname123", ipv4_address="10.10.1.1/30")

    # Invalid: missing bll- prefix
    with pytest.raises(ValidationError):
        InterfaceConfig(name="eth0", ipv4_address="10.10.1.1/30")


# ============================================================================
# 3. Semantic Invariants & Business Logic
# ============================================================================

def test_inference_verdict_abstention_consistency():
    """InferenceVerdict: abstained=True requires abstain_reason; abstained=False forbids it."""
    # Invalid: abstained=True but abstain_reason is None
    with pytest.raises(ValidationError) as exc:
        InferenceVerdict(
            run_id="run_1234abcd",
            vantage_profile="full_observer",
            latency_increase_observed=False,
            load_association=0.0,
            supported_regions=[],
            not_excluded_regions=[],
            queue_evidence=QueueEvidenceLevel.NONE,
            abstained=True,
            abstain_reason=None,
            supporting_run_ids=["run_1234abcd"],
        )
    assert "abstain_reason cannot be None when abstained=True" in str(exc.value)

    # Invalid: abstained=False but abstain_reason is populated
    with pytest.raises(ValidationError) as exc:
        InferenceVerdict(
            run_id="run_1234abcd",
            vantage_profile="full_observer",
            latency_increase_observed=False,
            load_association=0.0,
            supported_regions=[],
            not_excluded_regions=[],
            queue_evidence=QueueEvidenceLevel.NONE,
            abstained=False,
            abstain_reason="UNEXPECTED_REASON",
            supporting_run_ids=["run_1234abcd"],
        )
    assert "abstain_reason must be None when abstained=False" in str(exc.value)


def test_inference_verdict_subset_consistency():
    """InferenceVerdict: supported_regions MUST be a subset of not_excluded_regions (S subset C)."""
    with pytest.raises(ValidationError) as exc:
        InferenceVerdict(
            run_id="run_1234abcd",
            vantage_profile="full_observer",
            latency_increase_observed=True,
            load_association=0.8,
            supported_regions=["near_link"],
            not_excluded_regions=["far_link"],  # near_link is NOT in not_excluded_regions!
            queue_evidence=QueueEvidenceLevel.STRONG,
            abstained=False,
            abstain_reason=None,
            supporting_run_ids=["run_1234abcd"],
        )
    assert "must be a subset of not_excluded_regions" in str(exc.value)


def test_inference_verdict_empty_supporting_run_ids():
    """InferenceVerdict: supporting_run_ids must not be empty."""
    with pytest.raises(ValidationError):
        InferenceVerdict(
            run_id="run_1234abcd",
            vantage_profile="full_observer",
            latency_increase_observed=False,
            load_association=0.0,
            supported_regions=[],
            not_excluded_regions=[],
            queue_evidence=QueueEvidenceLevel.NONE,
            abstained=False,
            abstain_reason=None,
            supporting_run_ids=[],  # min_length=1
        )


# ============================================================================
# 4. JSON Schema Draft 2020-12 Verification Against Adversarial Payloads
# ============================================================================

def test_manifest_schema_rejection_of_corrupt_payloads():
    """manifest.schema.json rejects corrupted types, missing fields, and extra fields."""
    schema = json.loads((SCHEMAS_DIR / "manifest.schema.json").read_text())

    base_valid = {
        "schema_version": "1.0.0",
        "run_id": "run_12345678abcd",
        "timestamp_utc": "2026-10-21T18:00:00Z",
        "duration_seconds": 110.0,
        "parameters": {
            "phases": {"baseline_idle_s": 20.0, "saturation_load_s": 60.0, "recovery_s": 30.0},
            "load_profile": {"protocol": "tcp", "direction": "upload"},
            "probe_profile": {"ping_interval_s": 0.1, "irtt_interval_s": 0.02, "irtt_packet_len": 172},
        },
        "environment": {
            "hostname": "host",
            "os_name": "Linux",
            "kernel_release": "6.1.0",
            "architecture": "x86_64",
            "backend": "mock_simulation",
            "git_commit": "abc",
            "git_dirty": False,
            "python_version": "3.14.0",
        },
    }
    jsonschema.validate(instance=base_valid, schema=schema)

    # 1. Missing phases
    corrupted_phases = json.loads(json.dumps(base_valid))
    del corrupted_phases["parameters"]["phases"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=corrupted_phases, schema=schema)

    # 2. Corrupt duration_seconds (string instead of number)
    corrupted_duration = json.loads(json.dumps(base_valid))
    corrupted_duration["duration_seconds"] = "one_hundred"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=corrupted_duration, schema=schema)

    # 3. Negative duration_seconds
    corrupted_neg_dur = json.loads(json.dumps(base_valid))
    corrupted_neg_dur["duration_seconds"] = -10.0
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=corrupted_neg_dur, schema=schema)

    # 4. Unknown backend
    corrupted_backend = json.loads(json.dumps(base_valid))
    corrupted_backend["environment"]["backend"] = "quantum_linux"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=corrupted_backend, schema=schema)

    # 5. Invalid artifact hash (must be 64-char hex)
    corrupted_artifact = json.loads(json.dumps(base_valid))
    corrupted_artifact["artifacts"] = {"events.jsonl": "invalid_not_sha256"}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=corrupted_artifact, schema=schema)

    # 6. Extra property at root
    corrupted_extra = json.loads(json.dumps(base_valid))
    corrupted_extra["injected_property"] = True
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=corrupted_extra, schema=schema)


def test_quality_schema_rejection_of_corrupt_payloads():
    """quality.schema.json rejects missing gate status, invalid flags, out-of-range metrics."""
    schema = json.loads((SCHEMAS_DIR / "quality.schema.json").read_text())

    base_valid = {
        "schema_version": "1.0.0",
        "run_id": "run_12345678abcd",
        "timestamp_utc": "2026-10-21T18:00:00Z",
        "valid_for_inference": True,
        "flags": {
            "missing_phases": False,
            "unreached_load": False,
            "route_changes": False,
            "unverified_qdiscs": False,
            "observer_unavailability": False,
            "client_cpu_saturation": False,
            "clock_unsynchronized": False,
            "monotonicity_violation": False,
        },
        "metrics": {"total_dropped_probes": 0, "client_max_cpu_percent": 25.0},
        "warnings": [],
    }
    jsonschema.validate(instance=base_valid, schema=schema)

    # 1. Missing valid_for_inference gate
    corrupt_gate = json.loads(json.dumps(base_valid))
    del corrupt_gate["valid_for_inference"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=corrupt_gate, schema=schema)

    # 2. Missing quality flag
    corrupt_flags = json.loads(json.dumps(base_valid))
    del corrupt_flags["flags"]["monotonicity_violation"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=corrupt_flags, schema=schema)

    # 3. CPU percent > 100.0
    corrupt_cpu = json.loads(json.dumps(base_valid))
    corrupt_cpu["metrics"]["client_max_cpu_percent"] = 105.0
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=corrupt_cpu, schema=schema)


def test_ground_truth_schema_rejection_of_corrupt_payloads():
    """ground_truth.schema.json rejects missing scenario, invalid regions, duplicate items."""
    schema = json.loads((SCHEMAS_DIR / "ground_truth.schema.json").read_text())

    base_valid = {
        "schema_version": "1.0.0",
        "run_id": "run_12345678abcd",
        "scenario_name": "near_fifo",
        "bottleneck_regions": ["near_link"],
        "expected_latency_increase": True,
        "expected_queue_evidence": "strong",
        "expected_supported_regions": ["near_link"],
        "expected_not_excluded_regions": ["near_link"],
        "expected_abstained": False,
        "expected_abstain_reason": None,
    }
    jsonschema.validate(instance=base_valid, schema=schema)

    # 1. Missing scenario_name
    corrupt_scenario = json.loads(json.dumps(base_valid))
    del corrupt_scenario["scenario_name"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=corrupt_scenario, schema=schema)

    # 2. Invalid scenario_name enum
    corrupt_scenario_name = json.loads(json.dumps(base_valid))
    corrupt_scenario_name["scenario_name"] = "unregistered_scenario"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=corrupt_scenario_name, schema=schema)

    # 3. Invalid region enum
    corrupt_region = json.loads(json.dumps(base_valid))
    corrupt_region["bottleneck_regions"] = ["outer_space"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=corrupt_region, schema=schema)

    # 4. Duplicate region items (uniqueItems: true)
    corrupt_duplicate = json.loads(json.dumps(base_valid))
    corrupt_duplicate["bottleneck_regions"] = ["near_link", "near_link"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=corrupt_duplicate, schema=schema)


def test_inference_schema_rejection_of_corrupt_payloads():
    """inference.schema.json rejects out-of-range correlations, invalid regions, empty runs."""
    schema = json.loads((SCHEMAS_DIR / "inference.schema.json").read_text())

    base_valid = {
        "schema_version": "1.0.0",
        "run_id": "run_12345678abcd",
        "timestamp_utc": "2026-10-21T18:00:00Z",
        "vantage_profile": "full_observer",
        "latency_increase_observed": True,
        "load_association": 0.85,
        "supported_regions": ["near_link"],
        "not_excluded_regions": ["near_link"],
        "queue_evidence": "strong",
        "quality_flags": [],
        "abstained": False,
        "abstain_reason": None,
        "next_measurement": None,
        "supporting_run_ids": ["run_12345678abcd"],
    }
    jsonschema.validate(instance=base_valid, schema=schema)

    # 1. load_association > 1.0
    corrupt_corr = json.loads(json.dumps(base_valid))
    corrupt_corr["load_association"] = 1.5
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=corrupt_corr, schema=schema)

    # 2. load_association < -1.0
    corrupt_neg_corr = json.loads(json.dumps(base_valid))
    corrupt_neg_corr["load_association"] = -1.5
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=corrupt_neg_corr, schema=schema)

    # 3. Invalid region in supported_regions
    corrupt_reg = json.loads(json.dumps(base_valid))
    corrupt_reg["supported_regions"] = ["cloud_region"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=corrupt_reg, schema=schema)

    # 4. Duplicate regions in supported_regions
    corrupt_dup_reg = json.loads(json.dumps(base_valid))
    corrupt_dup_reg["supported_regions"] = ["near_link", "near_link"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=corrupt_dup_reg, schema=schema)

    # 5. Empty supporting_run_ids
    corrupt_runs = json.loads(json.dumps(base_valid))
    corrupt_runs["supporting_run_ids"] = []
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=corrupt_runs, schema=schema)


# ============================================================================
# 5. Empirical Bug Demonstrations (Vulnerability Reproduction)
# ============================================================================

def test_demonstrate_bug_inference_verdict_accepts_out_of_bounds_float():
    """Verify InferenceVerdict rejects out-of-bounds float load_association."""
    with pytest.raises(ValidationError):
        InferenceVerdict(
            run_id="run_1234abcd",
            vantage_profile=VantageProfile.FULL_OBSERVER,
            latency_increase_observed=True,
            load_association=999.0,
            supported_regions=[RegionName.NEAR_LINK],
            not_excluded_regions=[RegionName.NEAR_LINK],
            queue_evidence=QueueEvidenceLevel.STRONG,
            abstained=False,
            abstain_reason=None,
            supporting_run_ids=["run_1234abcd"],
        )


def test_demonstrate_bug_inference_verdict_accepts_arbitrary_string_regions():
    """Verify InferenceVerdict rejects arbitrary invalid region strings."""
    with pytest.raises(ValidationError):
        InferenceVerdict(
            run_id="run_1234abcd",
            vantage_profile=VantageProfile.FULL_OBSERVER,
            latency_increase_observed=True,
            load_association=0.5,
            supported_regions=["invalid_region_name"],
            not_excluded_regions=["invalid_region_name"],
            queue_evidence=QueueEvidenceLevel.STRONG,
            abstained=False,
            abstain_reason=None,
            supporting_run_ids=["run_1234abcd"],
        )


def test_demonstrate_bug_inference_verdict_accepts_unvalidated_vantage_profile():
    """Verify InferenceVerdict rejects unvalidated vantage profile."""
    with pytest.raises(ValidationError):
        InferenceVerdict(
            run_id="run_1234abcd",
            vantage_profile="completely_bogus_profile",
            latency_increase_observed=True,
            load_association=0.5,
            supported_regions=[RegionName.NEAR_LINK],
            not_excluded_regions=[RegionName.NEAR_LINK],
            queue_evidence=QueueEvidenceLevel.STRONG,
            abstained=False,
            abstain_reason=None,
            supporting_run_ids=["run_1234abcd"],
        )


def test_demonstrate_bug_ground_truth_missing_abstain_and_subset_invariants():
    """Verify GroundTruth enforces abstention consistency and S subset C invariants."""
    # 1. Abstained=True without reason
    with pytest.raises(ValidationError):
        GroundTruth(
            run_id="run_1234abcd",
            scenario_name=ScenarioName.HEALTHY_BASELINE,
            expected_latency_increase=False,
            expected_queue_evidence=QueueEvidenceLevel.NONE,
            expected_abstained=True,
            expected_abstain_reason=None,
        )

    # 2. S not subset of C
    with pytest.raises(ValidationError):
        GroundTruth(
            run_id="run_1234abcd",
            scenario_name=ScenarioName.HEALTHY_BASELINE,
            expected_latency_increase=False,
            expected_queue_evidence=QueueEvidenceLevel.NONE,
            expected_supported_regions=[RegionName.NEAR_LINK],
            expected_not_excluded_regions=[RegionName.FAR_LINK],
        )


def test_demonstrate_bug_run_manifest_accepts_unvalidated_artifact_hashes():
    """Verify RunManifest rejects non-SHA-256 artifact hashes."""
    with pytest.raises(ValidationError):
        RunManifest(
            run_id="run_12345678abcd",
            duration_seconds=10.0,
            parameters=ExperimentParameters(load_profile=LoadProfile()),
            environment=EnvironmentInfo(
                hostname="h",
                os_name="Linux",
                kernel_release="6.1",
                architecture="x86_64",
                backend=BackendType.MOCK_SIMULATION,
                git_commit="abc",
                git_dirty=False,
                python_version="3.14",
            ),
            artifacts={"events.jsonl": "not_a_valid_sha256_hash"},
        )
