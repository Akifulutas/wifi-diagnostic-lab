"""
Feature 1: bll doctor --json (Platform & Capability Probe)
Tier 1: Feature Coverage (>=5 test cases)
"""

import pytest
from e2e_tests.harness import run_bll


def test_doctor_json_flag_returns_zero_exit_code():
    """F01-T1-1: bll doctor --json returns exit code 0."""
    res = run_bll(["doctor", "--json"])
    assert res.exit_code == 0, f"Expected 0, got {res.exit_code}, stderr: {res.stderr}"
    assert res.json_data is not None, "Output must be valid JSON"


def test_doctor_json_contains_required_top_level_keys():
    """F01-T1-2: bll doctor --json conforms to BLLDoctorReport top-level schema keys."""
    res = run_bll(["doctor", "--json"])
    data = res.json_data
    required_keys = [
        "timestamp_utc",
        "os_name",
        "kernel_release",
        "architecture",
        "selected_backend",
        "capabilities",
        "all_requirements_met",
        "remediation_steps",
    ]
    for key in required_keys:
        assert key in data, f"Missing required top-level key '{key}' in doctor report"


def test_doctor_reports_known_platform_architecture():
    """F01-T1-3: Probed OS and architecture are non-empty and recognized."""
    res = run_bll(["doctor", "--json"])
    data = res.json_data
    assert data["os_name"] in ("Darwin", "Linux", "Windows"), f"Unexpected OS: {data['os_name']}"
    assert isinstance(data["architecture"], str) and len(data["architecture"]) > 0
    assert isinstance(data["kernel_release"], str) and len(data["kernel_release"]) > 0


def test_doctor_capabilities_schema():
    """F01-T1-4: Capabilities dictionary covers all 8 required tools with available boolean."""
    res = run_bll(["doctor", "--json"])
    caps = res.json_data.get("capabilities", {})
    required_tools = ["netns", "tc", "iproute2", "ping", "irtt", "iperf3", "duckdb", "pyarrow"]
    for tool in required_tools:
        assert tool in caps, f"Tool '{tool}' missing from capabilities report"
        assert "available" in caps[tool], f"Capability '{tool}' missing 'available' boolean field"
        assert isinstance(caps[tool]["available"], bool)


def test_doctor_human_readable_output():
    """F01-T1-5: bll doctor without --json outputs human-readable summary text."""
    res = run_bll(["doctor"])
    assert res.exit_code == 0
    assert "Doctor Probe" in res.stdout or "Backend:" in res.stdout
    assert len(res.stdout.strip()) > 0
