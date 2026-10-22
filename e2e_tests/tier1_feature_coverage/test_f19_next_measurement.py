"""
Feature 19: Cost-Optimal Next Measurement Selector
Tier 1: Feature Coverage (>=5 test cases)
"""

import pytest
from e2e_tests.harness import run_bll


def test_next_measurement_suggested_when_abstained(near_fifo_run):
    """F19-T1-1: When engine abstains, a non-null next_measurement test is recommended."""
    run_dir, _ = near_fifo_run
    res = run_bll(["infer", str(run_dir), "--vantage", "remote_only", "--json"])
    assert res.exit_code == 0
    assert res.json_data["abstained"] is True
    assert res.json_data["next_measurement"] is not None


def test_next_measurement_recommends_gateway_ping_tier2(near_fifo_run):
    """F19-T1-2: Near vs far link ambiguity recommends low-cost gateway ping probe (Tier 2)."""
    run_dir, _ = near_fifo_run
    res = run_bll(["infer", str(run_dir), "--vantage", "remote_only", "--json"])
    assert res.exit_code == 0
    assert "gateway" in res.json_data["next_measurement"]


def test_next_measurement_recommends_observer_tap_tier4(tmp_path):
    """F19-T1-3: Indistinguishable access vs gateway ambiguity recommends router observer tap."""
    res_run = run_bll(["run", "--scenario", "indistinguishable_access_vs_gateway", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    run_dir = res_run.json_data["run_dir"]
    res = run_bll(["infer", run_dir, "--json"])
    assert res.exit_code == 0
    assert "observer" in res.json_data["next_measurement"]


def test_next_measurement_null_when_fully_resolved(near_fifo_run):
    """F19-T1-4: When bottleneck is unambiguously localized, next_measurement is null."""
    run_dir, _ = near_fifo_run
    res = run_bll(["infer", str(run_dir), "--vantage", "full_observer", "--json"])
    assert res.exit_code == 0
    assert res.json_data["abstained"] is False
    assert res.json_data["next_measurement"] is None


def test_next_measurement_selection_cost_efficiency(near_fifo_run):
    """F19-T1-5: Recommends lowest-cost test that discriminates candidates."""
    run_dir, _ = near_fifo_run
    res = run_bll(["infer", str(run_dir), "--vantage", "remote_only", "--json"])
    rec = res.json_data["next_measurement"]
    # Gateway probe is preferred over deploying physical observer tap
    assert "gateway" in rec or "probe" in rec
