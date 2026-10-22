"""
Feature 19: Cost-Optimal Next Measurement Selector (Boundary & Corner Cases)
Tier 2: Boundary & Corner Cases (>=5 test cases)
"""

import pytest
from e2e_tests.harness import run_bll


def test_next_measurement_null_when_resolved(near_fifo_run):
    """F19-T2-1: When bottleneck is resolved, next_measurement is strictly null."""
    run_dir, _ = near_fifo_run
    res = run_bll(["infer", str(run_dir), "--vantage", "full_observer", "--json"])
    assert res.exit_code == 0
    if not res.json_data["abstained"]:
        assert res.json_data["next_measurement"] is None


def test_next_measurement_string_type_when_suggested(near_fifo_run):
    """F19-T2-2: When suggested, next_measurement is a non-empty string."""
    run_dir, _ = near_fifo_run
    res = run_bll(["infer", str(run_dir), "--vantage", "remote_only", "--json"])
    assert res.exit_code == 0
    if res.json_data["abstained"]:
        rec = res.json_data["next_measurement"]
        assert isinstance(rec, str) and len(rec) > 0


def test_next_measurement_healthy_baseline_null(healthy_run):
    """F19-T2-3: In healthy link, no further measurement is needed."""
    run_dir, _ = healthy_run
    res = run_bll(["infer", str(run_dir), "--json"])
    assert res.exit_code == 0
    assert res.json_data["next_measurement"] is None


def test_next_measurement_fixed_delay_null(fixed_delay_run):
    """F19-T2-4: In fixed propagation delay negative control, next_measurement is null."""
    run_dir, _ = fixed_delay_run
    res = run_bll(["infer", str(run_dir), "--json"])
    assert res.exit_code == 0
    assert res.json_data["next_measurement"] is None


def test_next_measurement_deterministic_recommendation(near_fifo_run):
    """F19-T2-5: The same ambiguous run consistently suggests the identical next test."""
    run_dir, _ = near_fifo_run
    recs = [
        run_bll(["infer", str(run_dir), "--vantage", "remote_only", "--json"]).json_data["next_measurement"]
        for _ in range(3)
    ]
    assert len(set(recs)) == 1
