"""
Unit tests for BLL Pydantic v2 schemas and models.
tests/unit/test_schemas.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from bll.storage.schemas import (
    AbstainReason,
    BackendType,
    EnvironmentInfo,
    ExperimentParameters,
    GroundTruth,
    InferenceVerdict,
    InterfaceConfig,
    LinkConfig,
    LoadProfile,
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
    ScenarioEvaluationResult,
    BenchmarkSummary,
    TopologyNode,
    TopologySnapshot,
    TrafficDirection,
    TrafficProtocol,
    VantageProfile,
    export_all_json_schemas,
)


@pytest.mark.unit
def test_run_manifest_valid_instantiation():
    """Verify RunManifest instantiates with valid parameters."""
    manifest = RunManifest(
        run_id="run_12345678abcd",
        timestamp_utc=datetime.now(timezone.utc),
        duration_seconds=110.0,
        parameters=ExperimentParameters(
            phases=PhaseParameters(baseline_idle_s=20.0, saturation_load_s=60.0, recovery_s=30.0),
            load_profile=LoadProfile(protocol=TrafficProtocol.TCP, direction=TrafficDirection.UPLOAD),
            probe_profile=ProbeProfile(ping_interval_s=0.1, irtt_interval_s=0.02, irtt_packet_len=172),
        ),
        environment=EnvironmentInfo(
            hostname="test-host",
            os_name="Linux",
            kernel_release="6.1.0",
            architecture="x86_64",
            backend=BackendType.MOCK_SIMULATION,
            git_commit="abcdef0",
            git_dirty=False,
            python_version="3.14.0",
        ),
        artifacts={"samples/ping.parquet": "a" * 64},
    )
    assert manifest.schema_version == "1.0.0"
    assert manifest.run_id == "run_12345678abcd"
    assert manifest.parameters.phases.saturation_load_s == 60.0


@pytest.mark.unit
def test_run_manifest_invalid_run_id_pattern():
    """Assert invalid run_id raises ValidationError."""
    with pytest.raises(ValidationError):
        RunManifest(
            run_id="invalid-id!!",
            duration_seconds=110.0,
            parameters=ExperimentParameters(load_profile=LoadProfile()),
            environment=EnvironmentInfo(
                hostname="h",
                os_name="Linux",
                kernel_release="1",
                architecture="x86_64",
                backend=BackendType.MOCK_SIMULATION,
                git_commit="c",
                git_dirty=False,
                python_version="3.14",
            ),
        )


@pytest.mark.unit
def test_quality_audit_model_validation():
    """Test QualityAudit model and flags validation."""
    audit = QualityAudit(
        run_id="run_12345678abcd",
        valid_for_inference=True,
        flags=QualityFlags(missing_phases=False, unreached_load=False),
        metrics=QualityMetrics(total_dropped_probes=0, client_max_cpu_percent=12.5),
        warnings=[],
    )
    assert audit.valid_for_inference is True
    assert audit.flags.missing_phases is False
    assert audit.metrics.client_max_cpu_percent == 12.5


@pytest.mark.unit
def test_ground_truth_model_validation():
    """Test GroundTruth model with positive and negative controls."""
    gt = GroundTruth(
        run_id="run_12345678abcd",
        scenario_name=ScenarioName.NEAR_FIFO,
        bottleneck_regions=[RegionName.NEAR_LINK],
        expected_latency_increase=True,
        expected_queue_evidence=QueueEvidenceLevel.STRONG,
        expected_supported_regions=[RegionName.NEAR_LINK],
        expected_not_excluded_regions=[RegionName.NEAR_LINK],
        expected_abstained=False,
        expected_abstain_reason=None,
    )
    assert gt.scenario_name == ScenarioName.NEAR_FIFO
    assert gt.bottleneck_regions == [RegionName.NEAR_LINK]


@pytest.mark.unit
def test_inference_verdict_contract_rules():
    """Verify InferenceVerdict consistency rules: abstention and S subset of C."""
    # Valid verdict
    verdict = InferenceVerdict(
        run_id="run_12345678abcd",
        vantage_profile=VantageProfile.FULL_OBSERVER.value,
        latency_increase_observed=True,
        load_association=0.95,
        supported_regions=["near_link"],
        not_excluded_regions=["near_link"],
        queue_evidence=QueueEvidenceLevel.STRONG,
        abstained=False,
        abstain_reason=None,
        next_measurement=None,
        supporting_run_ids=["run_12345678abcd"],
    )
    assert verdict.latency_increase_observed is True

    # Inconsistent abstention (abstained=True but abstain_reason is None)
    with pytest.raises(ValidationError, match="abstain_reason cannot be None"):
        InferenceVerdict(
            run_id="run_12345678abcd",
            vantage_profile="remote_only",
            latency_increase_observed=True,
            load_association=0.8,
            supported_regions=[],
            not_excluded_regions=["near_link", "far_link"],
            queue_evidence=QueueEvidenceLevel.MODERATE,
            abstained=True,
            abstain_reason=None,
            supporting_run_ids=["run_12345678abcd"],
        )

    # Inconsistent regions (S not a subset of C)
    with pytest.raises(ValidationError, match="must be a subset of not_excluded_regions"):
        InferenceVerdict(
            run_id="run_12345678abcd",
            vantage_profile="full_observer",
            latency_increase_observed=True,
            load_association=0.9,
            supported_regions=["near_link", "far_link"],
            not_excluded_regions=["near_link"],  # far_link missing from C
            queue_evidence=QueueEvidenceLevel.STRONG,
            abstained=False,
            abstain_reason=None,
            supporting_run_ids=["run_12345678abcd"],
        )


@pytest.mark.unit
def test_topology_models_and_ifnamesiz_constraint():
    """Verify interface naming constraint <= 15 chars (IFNAMSIZ)."""
    valid_iface = InterfaceConfig(
        name="bll-cli-qn",
        ipv4_address="10.10.1.1/30",
    )
    assert valid_iface.name == "bll-cli-qn"

    # Too long (> 15 chars)
    with pytest.raises(ValidationError):
        InterfaceConfig(
            name="bll-interface-too-long-for-linux",
            ipv4_address="10.10.1.1/30",
        )


@pytest.mark.unit
def test_extra_fields_forbidden():
    """Verify that models forbid undeclared extra fields."""
    with pytest.raises(ValidationError):
        QualityFlags(
            missing_phases=False,
            unreached_load=False,
            unexpected_field_should_fail=True,
        )


@pytest.mark.unit
def test_export_all_json_schemas(tmp_path):
    """Verify export_all_json_schemas writes all 5 valid Draft 2020-12 schemas."""
    exported = export_all_json_schemas(tmp_path)
    assert len(exported) == 5
    for name, path in exported.items():
        assert path.exists()
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
        assert "$id" in data
        assert "properties" in data


@pytest.mark.unit
def test_scenario_evaluation_result_and_benchmark_summary():
    """Verify Interface Contract 5 benchmark evaluator models and confidence interval invariants."""
    res = ScenarioEvaluationResult(
        run_id="run_test123",
        scenario_id="healthy_baseline",
        ground_truth_region=RegionName.LOCAL_HOST,
        predicted_supported_regions=[RegionName.LOCAL_HOST],
        predicted_not_excluded_regions=[RegionName.LOCAL_HOST, RegionName.NEAR_LINK],
        abstained=False,
        abstain_reason=None,
        is_correct=True,
        is_false_positive=False,
        candidate_set_size=1,
    )
    assert res.is_correct is True

    # Duplicate regions in ScenarioEvaluationResult
    with pytest.raises(ValidationError):
        ScenarioEvaluationResult(
            run_id="run_test123",
            scenario_id="healthy_baseline",
            predicted_supported_regions=[RegionName.LOCAL_HOST, RegionName.LOCAL_HOST],
            is_correct=True,
            is_false_positive=False,
            candidate_set_size=1,
        )

    # Valid BenchmarkSummary
    summary = BenchmarkSummary(
        total_runs=100,
        conditional_localization_error=0.05,
        region_set_coverage=0.98,
        negative_control_fpr=0.02,
        decision_coverage=0.85,
        median_candidate_reduction=0.60,
        hypotheses_results={
            "H1": {"p_value": 0.01, "ci_lower": 0.02, "ci_upper": 0.08},
        },
        gate_passed=True,
    )
    assert summary.gate_passed is True

    # Invalid confidence interval ordering (ci_lower > ci_upper)
    with pytest.raises(ValidationError):
        BenchmarkSummary(
            total_runs=10,
            conditional_localization_error=0.05,
            region_set_coverage=0.98,
            negative_control_fpr=0.02,
            decision_coverage=0.85,
            median_candidate_reduction=0.60,
            hypotheses_results={
                "H1": {"p_value": 0.01, "ci_lower": 0.50, "ci_upper": 0.20},
            },
            gate_passed=False,
        )


@pytest.mark.unit
def test_ground_truth_abstain_and_subset_invariants():
    """Verify GroundTruth enforces abstention and differential subset invariants."""
    # Abstained=True without reason
    with pytest.raises(ValidationError, match="expected_abstain_reason cannot be None"):
        GroundTruth(
            run_id="run_gt_invalid",
            scenario_name=ScenarioName.HEALTHY_BASELINE,
            expected_latency_increase=False,
            expected_queue_evidence=QueueEvidenceLevel.NONE,
            expected_abstained=True,
            expected_abstain_reason=None,
        )

    # Abstained=False with reason
    with pytest.raises(ValidationError, match="expected_abstain_reason must be None"):
        GroundTruth(
            run_id="run_gt_invalid",
            scenario_name=ScenarioName.HEALTHY_BASELINE,
            expected_latency_increase=False,
            expected_queue_evidence=QueueEvidenceLevel.NONE,
            expected_abstained=False,
            expected_abstain_reason=AbstainReason.NO_LATENCY_INFLATION,
        )

    # S not subset of C
    with pytest.raises(ValidationError, match="must be a subset of expected_not_excluded_regions"):
        GroundTruth(
            run_id="run_gt_invalid",
            scenario_name=ScenarioName.NEAR_FIFO,
            expected_latency_increase=True,
            expected_queue_evidence=QueueEvidenceLevel.STRONG,
            expected_supported_regions=[RegionName.NEAR_LINK],
            expected_not_excluded_regions=[RegionName.FAR_LINK],
        )

    # Duplicate regions
    with pytest.raises(ValidationError, match="duplicate"):
        GroundTruth(
            run_id="run_gt_invalid",
            scenario_name=ScenarioName.NEAR_FIFO,
            expected_latency_increase=True,
            expected_queue_evidence=QueueEvidenceLevel.STRONG,
            bottleneck_regions=[RegionName.NEAR_LINK, RegionName.NEAR_LINK],
            expected_supported_regions=[RegionName.NEAR_LINK],
            expected_not_excluded_regions=[RegionName.NEAR_LINK],
        )


@pytest.mark.unit
def test_inference_verdict_float_nan_inf_rejected():
    """Verify InferenceVerdict rejects NaN, Inf, and floats outside [-1.0, 1.0]."""
    for bad_val in [float("nan"), float("inf"), float("-inf"), 1.01, -1.01, 999.0, -500.0]:
        with pytest.raises(ValidationError):
            InferenceVerdict(
                run_id="run_bad_float",
                vantage_profile=VantageProfile.FULL_OBSERVER,
                latency_increase_observed=True,
                load_association=bad_val,
                supported_regions=[RegionName.NEAR_LINK],
                not_excluded_regions=[RegionName.NEAR_LINK],
                queue_evidence=QueueEvidenceLevel.STRONG,
                abstained=False,
                abstain_reason=None,
                supporting_run_ids=["run_bad_float"],
            )
