"""
Feature 20: 12-Scenario Counterexample Suite
Tier 1: Feature Coverage (>=5 test cases)
"""

import pytest
from e2e_tests.harness import run_bll


def test_scenario_list_cli():
    """F20-T1-1: bll run --list-scenarios --json returns all 12 controlled counterexample scenarios."""
    res = run_bll(["run", "--list-scenarios", "--json"])
    assert res.exit_code == 0
    scenarios = res.json_data.get("scenarios", [])
    assert len(scenarios) == 12


def test_scenario_healthy_baseline_definition(tmp_path):
    """F20-T1-2: healthy_baseline scenario runs successfully."""
    res = run_bll(["run", "--scenario", "healthy_baseline", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    assert res.exit_code == 0
    assert res.json_data["scenario_id"] == "healthy_baseline"


def test_scenario_near_fifo_definition(tmp_path):
    """F20-T1-3: residential_dsl_near_fifo scenario runs successfully."""
    res = run_bll(["run", "--scenario", "residential_dsl_near_fifo", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    assert res.exit_code == 0
    assert res.json_data["scenario_id"] == "residential_dsl_near_fifo"


def test_scenario_far_fifo_definition(tmp_path):
    """F20-T1-4: cable_asymmetric_far_fifo scenario runs successfully."""
    res = run_bll(["run", "--scenario", "cable_asymmetric_far_fifo", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    assert res.exit_code == 0
    assert res.json_data["scenario_id"] == "cable_asymmetric_far_fifo"


def test_scenario_fixed_delay_no_queue_definition(tmp_path):
    """F20-T1-5: fixed_propagation_delay_control scenario runs successfully."""
    res = run_bll(["run", "--scenario", "fixed_propagation_delay_control", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    assert res.exit_code == 0
    assert res.json_data["scenario_id"] == "fixed_propagation_delay_control"
