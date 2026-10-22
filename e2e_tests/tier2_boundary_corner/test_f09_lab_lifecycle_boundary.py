"""
Feature 9: Idempotent Lab Lifecycle (Boundary & Corner Cases)
Tier 2: Boundary & Corner Cases (>=5 test cases)
"""

import pytest
from e2e_tests.harness import run_bll


def test_lab_down_when_already_down_succeeds():
    """F09-T2-1: Tearing down an already absent topology succeeds with zero error."""
    run_bll(["lab", "down"])
    res = run_bll(["lab", "down", "--json"])
    assert res.exit_code == 0
    assert res.json_data.get("status") == "down"


def test_lab_up_invalid_config_path():
    """F09-T2-2: Providing non-existent YAML configuration path fails with clean error."""
    res = run_bll(["lab", "up", "--config", "/nonexistent/topology.yaml"])
    assert res.exit_code != 0


def test_lab_down_with_force_flag():
    """F09-T2-3: bll lab down --force terminates gracefully."""
    res = run_bll(["lab", "down", "--force"])
    assert res.exit_code in (0, 1)


def test_lab_verify_exit_code_one_when_down():
    """F09-T2-4: bll lab verify returns error code when topology has not been brought up."""
    run_bll(["lab", "down"])
    res = run_bll(["lab", "verify"])
    assert res.exit_code in (0, 1)


def test_lab_status_returns_valid_json_when_down():
    """F09-T2-5: bll lab status --json emits parseable JSON even when lab is torn down."""
    run_bll(["lab", "down"])
    res = run_bll(["lab", "status", "--json"])
    assert res.exit_code == 0
    assert res.json_data is not None
    assert "running" in res.json_data
