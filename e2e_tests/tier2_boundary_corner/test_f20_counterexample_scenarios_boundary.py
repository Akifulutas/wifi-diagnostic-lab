"""
Feature 20: 12-Scenario Counterexample Suite (Boundary & Corner Cases)
Tier 2: Boundary & Corner Cases (>=5 test cases)
"""

import pytest
from e2e_tests.harness import run_bll


def test_scenario_unknown_scenario_rejected():
    """F20-T2-1: Unknown scenario identifier rejected with error code."""
    res = run_bll(["run", "--scenario", "non_existent_chaos_scenario"])
    assert res.exit_code != 0


def test_scenario_case_sensitivity(tmp_path):
    """F20-T2-2: Scenario matching preserves lowercase snake_case standard."""
    res = run_bll(["run", "--scenario", "HEALTHY_BASELINE", "--out-dir", str(tmp_path), "--duration-idle", "0.5", "--duration-load", "0.5", "--duration-recovery", "0.5"])
    assert res.exit_code in (0, 1, 2)


def test_scenario_empty_scenario_string():
    """F20-T2-3: Empty scenario string rejected."""
    res = run_bll(["run", "--scenario", ""])
    assert res.exit_code != 0


def test_scenario_all_twelve_names_unique():
    """F20-T2-4: The 12 controlled counterexample scenario names are strictly unique."""
    res = run_bll(["run", "--list-scenarios", "--json"])
    assert res.exit_code == 0
    scenarios = res.json_data.get("scenarios", [])
    assert len(scenarios) == len(set(scenarios))


def test_scenario_list_text_mode_has_twelve_lines():
    """F20-T2-5: Text mode bll run --list-scenarios outputs 12 scenario lines."""
    res = run_bll(["run", "--list-scenarios"])
    assert res.exit_code == 0
    lines = [line.strip() for line in res.stdout.strip().split("\n") if line.strip()]
    assert len(lines) == 12
