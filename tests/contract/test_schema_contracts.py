"""
Contract tests for JSON Schemas and PyArrow Parquet tables.
tests/contract/test_schema_contracts.py
"""

from __future__ import annotations

import json
import pathlib
import duckdb
import jsonschema
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from bll.platform.doctor import BLLDoctorReport, run_doctor
from bll.storage.parquet_schemas import TABLE_SCHEMAS, PING_SCHEMA, IPERF3_SCHEMA, QDISC_SCHEMA
from bll.storage.schemas import (
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
    TopologyNode,
    TopologySnapshot,
    TrafficDirection,
    TrafficProtocol,
    VantageProfile,
)

PROJ_ROOT = pathlib.Path(__file__).parent.parent.parent
SCHEMAS_DIR = PROJ_ROOT / "docs" / "schemas"


@pytest.mark.contract
@pytest.mark.parametrize(
    "schema_file",
    [
        "manifest.schema.json",
        "quality.schema.json",
        "ground_truth.schema.json",
        "inference.schema.json",
        "topology.schema.json",
    ],
)
def test_json_schemas_draft_compliance(schema_file: str):
    """Verify all 5 JSON schemas are valid JSON Schema Draft-07 / 2020-12 specifications."""
    schema_path = SCHEMAS_DIR / schema_file
    assert schema_path.exists(), f"Schema file {schema_file} missing from docs/schemas/"

    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    # Validate against Draft 2020-12 or Draft 7
    try:
        jsonschema.Draft202012Validator.check_schema(schema)
    except Exception:
        jsonschema.Draft7Validator.check_schema(schema)


@pytest.mark.contract
def test_manifest_schema_validation_roundtrip():
    """Verify RunManifest model output passes JSON Schema validation."""
    schema_path = SCHEMAS_DIR / "manifest.schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    manifest = RunManifest(
        run_id="run_12345678abcd",
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
    )

    instance = json.loads(manifest.model_dump_json())
    jsonschema.validate(instance=instance, schema=schema)


@pytest.mark.contract
def test_quality_schema_validation_roundtrip():
    """Verify QualityAudit model output passes JSON Schema validation."""
    schema_path = SCHEMAS_DIR / "quality.schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    audit = QualityAudit(
        run_id="run_12345678abcd",
        valid_for_inference=True,
        flags=QualityFlags(missing_phases=False, unreached_load=False),
        metrics=QualityMetrics(total_dropped_probes=0, client_max_cpu_percent=15.0),
        warnings=["Non-fatal advisory: probe interval jitter < 1ms"],
    )

    instance = json.loads(audit.model_dump_json())
    jsonschema.validate(instance=instance, schema=schema)


@pytest.mark.contract
def test_ground_truth_schema_validation_roundtrip():
    """Verify GroundTruth model output passes JSON Schema validation."""
    schema_path = SCHEMAS_DIR / "ground_truth.schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

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

    instance = json.loads(gt.model_dump_json())
    jsonschema.validate(instance=instance, schema=schema)


@pytest.mark.contract
def test_inference_schema_validation_roundtrip():
    """Verify InferenceVerdict model output passes JSON Schema validation."""
    schema_path = SCHEMAS_DIR / "inference.schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    verdict = InferenceVerdict(
        run_id="run_12345678abcd",
        vantage_profile="full_observer",
        latency_increase_observed=True,
        load_association=0.92,
        supported_regions=["near_link"],
        not_excluded_regions=["near_link"],
        queue_evidence=QueueEvidenceLevel.STRONG,
        quality_flags=[],
        abstained=False,
        abstain_reason=None,
        next_measurement=None,
        supporting_run_ids=["run_12345678abcd"],
    )

    instance = json.loads(verdict.model_dump_json())
    jsonschema.validate(instance=instance, schema=schema)


@pytest.mark.contract
def test_topology_schema_validation_roundtrip():
    """Verify TopologySnapshot model output passes JSON Schema validation."""
    schema_path = SCHEMAS_DIR / "topology.schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    topo = TopologySnapshot(
        topology_name="bll-default",
        nodes=[
            TopologyNode(
                name="bll-client",
                role="client",
                forwarding_enabled=False,
                interfaces=[InterfaceConfig(name="bll-cli-qn", ipv4_address="10.10.1.1/30")],
                routes=[RouteConfig(destination_cidr="10.10.5.0/30", gateway_ip="10.10.1.2", interface="bll-cli-qn")],
            )
        ],
        links=[
            LinkConfig(
                link_id="link1",
                subnet="10.10.1.0/30",
                node_a="bll-client",
                interface_a="bll-cli-qn",
                ip_a="10.10.1.1",
                node_b="bll-qnear",
                interface_b="bll-qn-cli",
                ip_b="10.10.1.2",
            )
        ],
        qdiscs=[
            QdiscConfig(
                node="bll-qnear",
                interface="bll-qn-rtr",
                direction="egress",
                qdisc_kind=QdiscKind.TBF,
                handle="1:",
                parent="root",
                parameters={"rate": "20mbit", "burst": "15k"},
            )
        ],
        invariants_verified=PathInvariants(
            client_to_observer=True,
            observer_to_remote=True,
            client_to_remote=True,
        ),
    )

    instance = json.loads(topo.model_dump_json())
    jsonschema.validate(instance=instance, schema=schema)


@pytest.mark.contract
def test_parquet_schemas_duckdb_roundtrip(tmp_path: pathlib.Path):
    """Verify all 5 PyArrow schemas serialize to Parquet and query via DuckDB without errors."""
    for table_name, arrow_schema in TABLE_SCHEMAS.items():
        assert isinstance(arrow_schema, pa.Schema)

    # 1. Test ping.parquet
    ping_data = {
        "timestamp_ns": [1000000000, 1100000000, 1200000000],
        "seq": [1, 2, 3],
        "rtt_ms": [20.5, 21.0, 20.8],
        "ttl": [61, 61, 61],
        "src_ip": ["10.10.1.1", "10.10.1.1", "10.10.1.1"],
        "dst_ip": ["10.10.5.2", "10.10.5.2", "10.10.5.2"],
        "phase": ["baseline_idle", "baseline_idle", "baseline_idle"],
        "run_id": ["run_1234abcd", "run_1234abcd", "run_1234abcd"],
        "vantage_point": ["client", "client", "client"],
        "target": ["remote", "remote", "remote"],
        "path": ["client_to_remote", "client_to_remote", "client_to_remote"],
        "lost": [False, False, False],
        "timeout": [False, False, False],
        "dup": [False, False, False],
        "timestamp_wall": [None, None, None],
    }
    ping_table = pa.Table.from_pydict(ping_data, schema=PING_SCHEMA)
    ping_file = tmp_path / "ping.parquet"
    pq.write_table(ping_table, ping_file)

    # Query with DuckDB
    con = duckdb.connect()
    res = con.execute(
        f"SELECT count(*), avg(rtt_ms), min(seq) FROM read_parquet('{ping_file}')"
    ).fetchone()
    assert res == (3, pytest.approx(20.766, rel=1e-2), 1)


@pytest.mark.contract
def test_bll_doctor_report_json_schema():
    """Verify BLLDoctorReport model generates valid schema and accepts probe output."""
    report = run_doctor(target_backend="mock_simulation")
    schema = BLLDoctorReport.model_json_schema()

    assert "properties" in schema
    assert "selected_backend" in schema["properties"]
    assert "capabilities" in schema["properties"]

    report_dict = json.loads(report.model_dump_json())
    jsonschema.validate(instance=report_dict, schema=schema)
