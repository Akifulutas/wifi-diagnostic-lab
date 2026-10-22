"""
Bufferbloat Localization Lab (BLL) - Core Data Schemas
src/bll/storage/schemas.py

Pydantic v2 data models for manifests, quality audits, ground truth,
inference contracts, and topology snapshots.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Literal, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


# ============================================================================
# Core Enums
# ============================================================================

class RegionName(str, Enum):
    """Canonical mutually exclusive network regions (R5)."""
    LOCAL_HOST = "local_host"
    NEAR_LINK = "near_link"
    GATEWAY_NODE = "gateway_node"
    FAR_LINK = "far_link"
    REMOTE_HOST = "remote_host"


class QueueEvidenceLevel(str, Enum):
    """Strength of empirical queue buildup evidence."""
    NONE = "none"
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"


class AbstainReason(str, Enum):
    """Mathematical reason for set-valued abstention."""
    AMBIGUOUS_VANTAGE_COVERAGE = "AMBIGUOUS_VANTAGE_COVERAGE"
    INDISTINGUISHABLE_TOPOLOGY = "INDISTINGUISHABLE_TOPOLOGY"
    INSUFFICIENT_LOAD_SATURATION = "INSUFFICIENT_LOAD_SATURATION"
    QUALITY_FLAG_INVALIDATION = "QUALITY_FLAG_INVALIDATION"
    NO_LATENCY_INFLATION = "NO_LATENCY_INFLATION"


class VantageProfile(str, Enum):
    """Ablation harness vantage point configurations."""
    REMOTE_ONLY = "remote_only"
    GATEWAY_REMOTE = "gateway_remote"
    LOCAL_REMOTE = "local_remote"
    FULL_OBSERVER = "full_observer"


class ScenarioName(str, Enum):
    """The 12 reference controlled testbed scenarios."""
    HEALTHY_BASELINE = "healthy_baseline"
    NEAR_FIFO = "near_fifo"
    FAR_FIFO = "far_fifo"
    DUAL_FIFO = "dual_fifo"
    FIXED_DELAY_NO_QUEUE = "fixed_delay_no_queue"
    LOAD_CORRELATED_NON_QUEUE = "load_correlated_non_queue"
    CONTROLLED_LOSS = "controlled_loss"
    ENDPOINT_CPU_DELAY = "endpoint_cpu_delay"
    FIFO_VS_FQCODEL_VS_CAKE = "fifo_vs_fqcodel_vs_cake"
    PROTOCOL_DISCREPANCY = "protocol_discrepancy"
    INDISTINGUISHABLE_PAIR_A = "indistinguishable_pair_a"
    INDISTINGUISHABLE_PAIR_B = "indistinguishable_pair_b"


class BackendType(str, Enum):
    """Execution backend platform."""
    NATIVE_LINUX = "native_linux"
    CONTAINER_LINUX = "container_linux"
    VM_LINUX = "vm_linux"
    MOCK_SIMULATION = "mock_simulation"


class TrafficProtocol(str, Enum):
    """Transport protocol for load generation."""
    TCP = "tcp"
    UDP = "udp"


class TrafficDirection(str, Enum):
    """Load generation directionality."""
    UPLOAD = "upload"
    DOWNLOAD = "download"
    BIDIRECTIONAL = "bidirectional"


class MeasurementProtocol(str, Enum):
    """Telemetry probe protocol."""
    ICMP = "icmp"
    UDP_IRTT = "udp_irtt"
    TCP_PROBE = "tcp_probe"


class CorrelationMetric(str, Enum):
    """Statistical metric for throughput-latency association."""
    SPEARMAN_RANK = "spearman_rank"
    PEARSON_R = "pearson_r"
    HODGES_LEHMANN_SHIFT = "hodges_lehmann_shift"


class QdiscKind(str, Enum):
    """Linux tc qdisc algorithms."""
    TBF = "tbf"
    PFIFO = "pfifo"
    BFIFO = "bfifo"
    NETEM = "netem"
    FQ_CODEL = "fq_codel"
    CAKE = "cake"
    HTB = "htb"


# ============================================================================
# 1. Run Manifest Models
# ============================================================================

class PhaseParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    baseline_idle_s: float = Field(default=20.0, gt=0.0, description="Duration of initial idle probe phase.")
    saturation_load_s: float = Field(default=60.0, gt=0.0, description="Duration of load saturation phase.")
    recovery_s: float = Field(default=30.0, gt=0.0, description="Duration of recovery drain observation phase.")


class LoadProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    protocol: TrafficProtocol = TrafficProtocol.TCP
    direction: TrafficDirection = TrafficDirection.UPLOAD
    target_bitrate_bps: float | None = Field(default=None, gt=0.0)
    tcp_congestion_control: str = Field(default="cubic")
    parallel_streams: int = Field(default=1, ge=1)
    socket_buffer_bytes: int | None = Field(default=None, ge=1024)


class ProbeProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ping_interval_s: float = Field(default=0.1, gt=0.001)
    irtt_interval_s: float = Field(default=0.02, gt=0.001)
    irtt_packet_len: int = Field(default=172, ge=64, le=65507)


class ExperimentParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    phases: PhaseParameters = Field(default_factory=PhaseParameters)
    load_profile: LoadProfile
    probe_profile: ProbeProfile = Field(default_factory=ProbeProfile)


class EnvironmentInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hostname: str
    os_name: str
    kernel_release: str
    architecture: str
    backend: BackendType
    git_commit: str
    git_dirty: bool
    python_version: str


class RunManifest(BaseModel):
    """Root model for runs/<run_id>/manifest.json."""
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0.0"] = "1.0.0"
    run_id: str = Field(pattern=r"^(run_[a-f0-9\-]+|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$")
    timestamp_utc: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    duration_seconds: float = Field(gt=0.0)
    parameters: ExperimentParameters
    environment: EnvironmentInfo
    artifacts: dict[str, Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]] = Field(
        default_factory=dict, description="Artifact relative path to sha256."
    )


# ============================================================================
# 2. Quality Audit Models
# ============================================================================

class QualityFlags(BaseModel):
    model_config = ConfigDict(extra="forbid")
    missing_phases: bool = False
    unreached_load: bool = False
    route_changes: bool = False
    unverified_qdiscs: bool = False
    observer_unavailability: bool = False
    client_cpu_saturation: bool = False
    clock_unsynchronized: bool = False
    monotonicity_violation: bool = False


class QualityMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client_max_cpu_percent: float | None = Field(default=None, ge=0.0, le=100.0)
    server_max_cpu_percent: float | None = Field(default=None, ge=0.0, le=100.0)
    total_dropped_probes: int = Field(default=0, ge=0)
    clock_drift_estimate_ms: float | None = None
    load_reached_bps: float | None = Field(default=None, ge=0.0)
    load_target_bps: float | None = Field(default=None, ge=0.0)


class QualityAudit(BaseModel):
    """Root model for runs/<run_id>/quality.json."""
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0.0"] = "1.0.0"
    run_id: str
    timestamp_utc: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    valid_for_inference: bool
    flags: QualityFlags | list[str] = Field(default_factory=list)
    checks: dict[str, bool] = Field(
        default_factory=lambda: {
            "clock_synchronized": True,
            "qdisc_verified": True,
            "observer_available": True,
            "load_reached": True,
        }
    )
    metrics: QualityMetrics = Field(default_factory=QualityMetrics)
    warnings: list[str] = Field(default_factory=list)


# ============================================================================
# 3. Ground Truth Models (Physically Isolated)
# ============================================================================

class GroundTruth(BaseModel):
    """Root model for ground_truth/<opaque_run_id>.json."""
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0.0"] = "1.0.0"
    run_id: str
    scenario_name: ScenarioName
    bottleneck_regions: list[RegionName] = Field(
        default_factory=list, json_schema_extra={"uniqueItems": True}
    )
    expected_latency_increase: bool
    expected_queue_evidence: QueueEvidenceLevel
    expected_supported_regions: list[RegionName] = Field(
        default_factory=list, json_schema_extra={"uniqueItems": True}
    )
    expected_not_excluded_regions: list[RegionName] = Field(
        default_factory=list, json_schema_extra={"uniqueItems": True}
    )
    expected_abstained: bool = False
    expected_abstain_reason: AbstainReason | None = None
    injected_parameters: dict[str, Any] = Field(default_factory=dict)

    @field_validator("bottleneck_regions", "expected_supported_regions", "expected_not_excluded_regions")
    @classmethod
    def validate_unique_regions(cls, v: list[RegionName]) -> list[RegionName]:
        if len(v) != len(set(v)):
            raise ValueError(f"Region list contains duplicate elements: {v}")
        return v

    @model_validator(mode="after")
    def validate_ground_truth_contract(self) -> "GroundTruth":
        # Rule 1: Abstention consistency
        if self.expected_abstained and self.expected_abstain_reason is None:
            raise ValueError("expected_abstain_reason cannot be None when expected_abstained=True")
        if not self.expected_abstained and self.expected_abstain_reason is not None:
            raise ValueError("expected_abstain_reason must be None when expected_abstained=False")

        # Rule 2: Differential path algebra consistency (S subset of C)
        s_set = set(self.expected_supported_regions)
        c_set = set(self.expected_not_excluded_regions)
        if not s_set.issubset(c_set):
            raise ValueError(
                f"expected_supported_regions {self.expected_supported_regions} must be a subset of expected_not_excluded_regions {self.expected_not_excluded_regions}"
            )
        return self


# ============================================================================
# 4. Inference Output Contract Models
# ============================================================================

class LoadAssociation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metric: CorrelationMetric
    correlation_coefficient: float = Field(ge=-1.0, le=1.0)
    p_value: float = Field(ge=0.0, le=1.0)
    delta_rtt_ms: float = Field(ge=0.0)
    significant: bool


class NextMeasurement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recommended_action: str
    target_vantage: str
    target_protocol: MeasurementProtocol
    estimated_cost: int = Field(ge=1, le=5)
    discriminating_power: str


class InferenceVerdict(BaseModel):
    """Root model for inference.json (R5, Interface Contract 4)."""
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0.0"] = "1.0.0"
    run_id: str
    timestamp_utc: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    vantage_profile: VantageProfile
    latency_increase_observed: bool
    load_association: Union[Annotated[float, Field(ge=-1.0, le=1.0)], LoadAssociation]
    supported_regions: list[RegionName] = Field(
        default_factory=list, json_schema_extra={"uniqueItems": True}
    )
    not_excluded_regions: list[RegionName] = Field(
        default_factory=list, json_schema_extra={"uniqueItems": True}
    )
    queue_evidence: QueueEvidenceLevel
    quality_flags: list[str] = Field(default_factory=list, json_schema_extra={"uniqueItems": True})
    abstained: bool
    abstain_reason: str | None = None
    next_measurement: Union[str, NextMeasurement, None] = None
    supporting_run_ids: list[str] = Field(min_length=1)

    @field_validator("load_association")
    @classmethod
    def validate_load_association(cls, v: Union[float, LoadAssociation]) -> Union[float, LoadAssociation]:
        if isinstance(v, (int, float)):
            val = float(v)
            if math.isnan(val) or math.isinf(val):
                raise ValueError("load_association cannot be NaN or Infinite")
            if not (-1.0 <= val <= 1.0):
                raise ValueError(f"load_association must be in [-1.0, 1.0], got {val}")
        return v

    @field_validator("supported_regions", "not_excluded_regions", "quality_flags")
    @classmethod
    def validate_unique_items(cls, v: list[Any]) -> list[Any]:
        if len(v) != len(set(v)):
            raise ValueError(f"List contains duplicate elements: {v}")
        return v

    @model_validator(mode="after")
    def validate_inference_contract(self) -> "InferenceVerdict":
        # Rule 1: Abstention consistency
        if self.abstained and self.abstain_reason is None:
            raise ValueError("abstain_reason cannot be None when abstained=True")
        if not self.abstained and self.abstain_reason is not None:
            raise ValueError("abstain_reason must be None when abstained=False")

        # Rule 2: Differential path algebra consistency (S subset of C)
        s_set = set(self.supported_regions)
        c_set = set(self.not_excluded_regions)
        if not s_set.issubset(c_set):
            raise ValueError(
                f"supported_regions {self.supported_regions} must be a subset of not_excluded_regions {self.not_excluded_regions}"
            )
        return self


# Backward-compatible alias matching PROJECT.md interface contract name
InferenceOutputContract = InferenceVerdict


# ============================================================================
# 5. Topology Snapshot Models
# ============================================================================

class InterfaceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(max_length=15, pattern=r"^bll-[a-z0-9\-]{1,11}$")
    ipv4_address: str
    mac_address: str | None = None
    peer_node: str | None = None
    peer_interface: str | None = None


class RouteConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    destination_cidr: str
    gateway_ip: str | None = None
    interface: str


class TopologyNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    role: Literal["client", "near_bottleneck", "router", "observer", "far_bottleneck", "remote_target"]
    forwarding_enabled: bool
    interfaces: list[InterfaceConfig]
    routes: list[RouteConfig]


class LinkConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    link_id: str
    subnet: str
    node_a: str
    interface_a: str
    ip_a: str
    node_b: str
    interface_b: str
    ip_b: str


class QdiscConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    node: str
    interface: str
    direction: Literal["egress", "ingress"]
    qdisc_kind: QdiscKind
    handle: str
    parent: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class PathInvariants(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client_to_observer: bool
    observer_to_remote: bool
    client_to_remote: bool
    verified_at_utc: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TopologySnapshot(BaseModel):
    """Root model for runs/<run_id>/topology.json."""
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0.0"] = "1.0.0"
    topology_name: str
    timestamp_utc: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    nodes: list[TopologyNode]
    links: list[LinkConfig]
    qdiscs: list[QdiscConfig]
    invariants_verified: PathInvariants


# ============================================================================
# 6. Evaluator Benchmark Contract Models (Interface Contract 5)
# ============================================================================

class ScenarioEvaluationResult(BaseModel):
    """Evaluation result for a single scenario run against ground truth."""
    model_config = ConfigDict(extra="forbid")
    run_id: str
    scenario_id: str
    ground_truth_region: RegionName | str | None = None
    predicted_supported_regions: list[RegionName] = Field(
        default_factory=list, json_schema_extra={"uniqueItems": True}
    )
    predicted_not_excluded_regions: list[RegionName] = Field(
        default_factory=list, json_schema_extra={"uniqueItems": True}
    )
    abstained: bool = False
    abstain_reason: str | None = None
    is_correct: bool
    is_false_positive: bool
    candidate_set_size: int = Field(ge=0)

    @field_validator("predicted_supported_regions", "predicted_not_excluded_regions")
    @classmethod
    def validate_unique_regions(cls, v: list[RegionName]) -> list[RegionName]:
        if len(v) != len(set(v)):
            raise ValueError(f"List contains duplicate elements: {v}")
        return v


class BenchmarkSummary(BaseModel):
    """Aggregate benchmark evaluation summary across all testbed scenarios."""
    model_config = ConfigDict(extra="forbid")
    total_runs: int = Field(ge=0)
    conditional_localization_error: float = Field(ge=0.0, le=1.0)  # CLE <= 0.10
    region_set_coverage: float = Field(ge=0.0, le=1.0)            # RSC >= 0.95
    negative_control_fpr: float = Field(ge=0.0, le=1.0)            # FPR <= 0.05
    decision_coverage: float = Field(ge=0.0, le=1.0)               # DC >= 0.70
    median_candidate_reduction: float = Field(ge=0.0, le=1.0)      # CSR >= 0.50
    hypotheses_results: dict[str, Any] = Field(default_factory=dict)
    gate_passed: bool

    @field_validator("hypotheses_results")
    @classmethod
    def validate_hypotheses_results(cls, v: dict[str, Any]) -> dict[str, Any]:
        for h_name, h_data in v.items():
            if isinstance(h_data, dict):
                ci_lower = h_data.get("ci_lower")
                ci_upper = h_data.get("ci_upper")
                if ci_lower is not None and ci_upper is not None:
                    if float(ci_lower) > float(ci_upper):
                        raise ValueError(
                            f"Hypothesis {h_name} ci_lower ({ci_lower}) cannot exceed ci_upper ({ci_upper})"
                        )
                p_val = h_data.get("p_value")
                if p_val is not None:
                    if not (0.0 <= float(p_val) <= 1.0):
                        raise ValueError(
                            f"Hypothesis {h_name} p_value ({p_val}) must be in [0.0, 1.0]"
                        )
        return v


# ============================================================================
# JSON Schema Export Utility
# ============================================================================

def export_all_json_schemas(output_dir: Path) -> dict[str, Path]:
    """
    Exports all root Pydantic models to JSON Schema Draft 2020-12 files.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    registry: dict[str, type[BaseModel]] = {
        "manifest.schema.json": RunManifest,
        "quality.schema.json": QualityAudit,
        "ground_truth.schema.json": GroundTruth,
        "inference.schema.json": InferenceVerdict,
        "topology.schema.json": TopologySnapshot,
    }

    generated: dict[str, Path] = {}
    for filename, model_cls in registry.items():
        out_path = output_dir / filename
        schema_dict = model_cls.model_json_schema()
        schema_dict["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        schema_dict["$id"] = f"https://bufferbloat-localization-lab.net/schemas/v1/{filename}"

        # Ensure strict JSON schema required fields for nested models where Pydantic defaults would otherwise omit them
        if filename == "manifest.schema.json" and "$defs" in schema_dict:
            if "ExperimentParameters" in schema_dict["$defs"]:
                schema_dict["$defs"]["ExperimentParameters"]["required"] = [
                    "phases",
                    "load_profile",
                    "probe_profile",
                ]
            if "EnvironmentInfo" in schema_dict["$defs"]:
                env_def = dict(schema_dict["$defs"]["EnvironmentInfo"])
                if "properties" in env_def and "backend" in env_def["properties"] and "BackendType" in schema_dict["$defs"]:
                    env_def["properties"]["backend"] = dict(schema_dict["$defs"]["BackendType"])
                schema_dict["properties"]["environment"] = env_def
        elif filename == "quality.schema.json" and "$defs" in schema_dict:
            if "QualityFlags" in schema_dict["$defs"]:
                schema_dict["$defs"]["QualityFlags"]["required"] = [
                    "missing_phases",
                    "unreached_load",
                    "route_changes",
                    "unverified_qdiscs",
                    "observer_unavailability",
                    "client_cpu_saturation",
                    "clock_unsynchronized",
                    "monotonicity_violation",
                ]

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(schema_dict, f, indent=2)
        generated[filename] = out_path

    return generated
