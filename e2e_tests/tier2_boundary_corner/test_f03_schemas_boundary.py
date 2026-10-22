"""
Feature 3: Schema v1 Definitions (Boundary & Corner Cases)
Tier 2: Boundary & Corner Cases (>=5 test cases)
"""

import json
import pathlib
import pytest

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

PROJ_ROOT = pathlib.Path(__file__).parent.parent.parent
SCHEMAS_DIR = PROJ_ROOT / "docs" / "schemas"


def _load_schema(filename: str):
    schema_path = SCHEMAS_DIR / filename
    if not schema_path.exists():
        pytest.skip(f"Schema {filename} not yet found")
    with open(schema_path, "r") as f:
        return json.load(f)


def test_schema_validation_empty_dict_rejected():
    """F03-T2-1: Empty dictionary rejected by manifest schema due to missing required keys."""
    if not HAS_JSONSCHEMA:
        pytest.skip("jsonschema not available")
    schema = _load_schema("manifest.schema.json")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance={}, schema=schema)


def test_schema_validation_extra_fields_forbidden():
    """F03-T2-2: Extra unauthorized properties rejected when additionalProperties=false."""
    if not HAS_JSONSCHEMA:
        pytest.skip("jsonschema not available")
    schema = _load_schema("manifest.schema.json")
    bad_manifest = {
        "schema_version": "1.0.0",
        "run_id": "run_0123456789ab",
        "timestamp_utc": "2026-10-21T18:00:00Z",
        "duration_seconds": 110.0,
        "parameters": {
            "phases": {"baseline_idle_s": 20.0, "saturation_load_s": 60.0, "recovery_s": 30.0},
            "load_profile": {"protocol": "tcp", "direction": "upload"},
            "probe_profile": {"ping_interval_s": 0.1, "irtt_interval_s": 0.02, "irtt_packet_len": 172},
        },
        "environment": {
            "hostname": "testbox",
            "os_name": "Linux",
            "kernel_release": "6.1.0",
            "architecture": "x86_64",
            "backend": "mock_simulation",
            "git_commit": "abcdef",
            "git_dirty": False,
            "python_version": "3.14.0",
        },
        "unauthorized_extra_field": "injected_payload",
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad_manifest, schema=schema)


def test_schema_validation_null_run_id_rejected():
    """F03-T2-3: Null value for run_id fails type validation."""
    if not HAS_JSONSCHEMA:
        pytest.skip("jsonschema not available")
    schema = _load_schema("manifest.schema.json")
    bad_manifest = {
        "schema_version": "1.0.0",
        "run_id": None,
        "timestamp_utc": "2026-10-21T18:00:00Z",
        "duration_seconds": 110.0,
        "parameters": {},
        "environment": {},
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad_manifest, schema=schema)


def test_schema_validation_invalid_enum_rejected():
    """F03-T2-4: Invalid backend enum string rejected by environment schema."""
    if not HAS_JSONSCHEMA:
        pytest.skip("jsonschema not available")
    schema = _load_schema("manifest.schema.json")
    env_schema = schema["properties"]["environment"]
    bad_env = {
        "hostname": "testbox",
        "os_name": "Linux",
        "kernel_release": "6.1.0",
        "architecture": "x86_64",
        "backend": "quantum_hypervisor",  # Invalid enum value
        "git_commit": "abcdef",
        "git_dirty": False,
        "python_version": "3.14.0",
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad_env, schema=env_schema)


def test_schema_validation_negative_duration_rejected():
    """F03-T2-5: Negative duration_seconds rejected by exclusiveMinimum constraint."""
    if not HAS_JSONSCHEMA:
        pytest.skip("jsonschema not available")
    schema = _load_schema("manifest.schema.json")
    dur_schema = schema["properties"]["duration_seconds"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=-10.0, schema=dur_schema)
