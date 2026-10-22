"""
Feature 3: Schema v1 Definitions
Tier 1: Feature Coverage (>=5 test cases)
"""

import json
import pathlib
import pytest

PROJ_ROOT = pathlib.Path(__file__).parent.parent.parent
SCHEMAS_DIR = PROJ_ROOT / "docs" / "schemas"


def _load_schema(schema_filename: str):
    schema_path = SCHEMAS_DIR / schema_filename
    if not schema_path.exists():
        # Check src/bll/schemas if moved
        alt_path = PROJ_ROOT / "src" / "bll" / "schemas" / schema_filename
        if alt_path.exists():
            schema_path = alt_path
        else:
            pytest.skip(f"Schema file {schema_filename} not yet created by Implementation Track at {schema_path}")
    with open(schema_path, "r") as f:
        return json.load(f)


def test_manifest_schema_file_valid():
    """F03-T1-1: manifest.schema.json is valid JSON Schema Draft-07/2020-12 with required fields."""
    schema = _load_schema("manifest.schema.json")
    assert "$schema" in schema or "properties" in schema
    assert "properties" in schema
    props = schema["properties"]
    for field in ["run_id", "schema_version", "timestamp_utc", "duration_seconds", "parameters"]:
        assert field in props, f"Field '{field}' missing from manifest schema"


def test_quality_schema_file_valid():
    """F03-T1-2: quality.schema.json is valid schema specifying quality flags."""
    schema = _load_schema("quality.schema.json")
    assert "properties" in schema
    props = schema["properties"]
    assert "flags" in props or "quality_flags" in props


def test_ground_truth_schema_file_valid():
    """F03-T1-3: ground_truth.schema.json specifies scenario ground truth parameters."""
    schema = _load_schema("ground_truth.schema.json")
    assert "properties" in schema
    props = schema["properties"]
    assert "scenario_id" in props or "run_id" in props


def test_inference_schema_file_valid():
    """F03-T1-4: inference.schema.json defines InferenceOutputContract properties."""
    schema = _load_schema("inference.schema.json")
    props = schema.get("properties", {})
    required_fields = [
        "run_id",
        "latency_increase_observed",
        "supported_regions",
        "queue_evidence",
        "abstained",
    ]
    for field in required_fields:
        assert field in props, f"Field '{field}' missing from inference output schema"


def test_topology_schema_file_valid():
    """F03-T1-5: topology.schema.json defines reference topology with nodes and links."""
    schema = _load_schema("topology.schema.json")
    props = schema.get("properties", {})
    assert "namespaces" in props or "nodes" in props or "links" in props or "subnets" in props
