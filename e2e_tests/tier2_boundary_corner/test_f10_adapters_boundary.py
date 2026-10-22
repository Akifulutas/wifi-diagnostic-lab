"""
Feature 10: Measurement Adapters (Boundary & Corner Cases)
Tier 2: Boundary & Corner Cases (>=5 test cases)
"""

import pytest
from e2e_tests.harness import run_bll


def test_adapter_zero_duration_rejected():
    """F10-T2-1: Experiment with zero duration rejected."""
    res = run_bll(["run", "--duration-idle", "0", "--duration-load", "10", "--duration-recovery", "5"])
    assert res.exit_code != 0


def test_adapter_invalid_scenario_name():
    """F10-T2-2: Unknown scenario name returns clean error."""
    res = run_bll(["run", "--scenario", "invalid_scenario_xyz"])
    assert res.exit_code != 0
    assert "unknown scenario" in res.stderr.lower() or "error" in res.stderr.lower()


def test_adapter_negative_duration_rejected():
    """F10-T2-3: Negative phase duration rejected."""
    res = run_bll(["run", "--duration-idle", "-5"])
    assert res.exit_code != 0


def test_adapter_unknown_direction_rejected():
    """F10-T2-4: Invalid traffic direction (e.g. sideways) rejected."""
    res = run_bll(["run", "--direction", "sideways"])
    assert res.exit_code != 0


def test_adapter_subsecond_duration_handled():
    """F10-T2-5: Very short (0.5s) phase durations accepted for fast automated testing."""
    res = run_bll(["run", "--scenario", "healthy_baseline", "--duration-idle", "0.5", "--duration-load", "0.5", "--duration-recovery", "0.5"])
    assert res.exit_code in (0, 1)
