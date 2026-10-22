"""
Feature 16: Differential Path Algebra Engine
Tier 1: Feature Coverage (>=5 test cases)
"""

import pathlib
import pytest
from e2e_tests.harness import run_bll


def test_differential_algebra_near_bottleneck(near_fifo_run):
    """F16-T1-1: Near FIFO queue delay localized to near_link under full vantage."""
    run_dir, _ = near_fifo_run
    res = run_bll(["infer", str(run_dir), "--vantage", "full_observer", "--json"])
    assert res.exit_code == 0
    assert "near_link" in res.json_data["supported_regions"]
    assert res.json_data["queue_evidence"] in ("moderate", "strong")


def test_differential_algebra_far_bottleneck(far_fifo_run):
    """F16-T1-2: Far FIFO queue delay localized to far_link under full vantage."""
    run_dir, _ = far_fifo_run
    res = run_bll(["infer", str(run_dir), "--vantage", "full_observer", "--json"])
    assert res.exit_code == 0
    assert "far_link" in res.json_data["supported_regions"]
    assert res.json_data["queue_evidence"] in ("moderate", "strong")


def test_differential_algebra_healthy_link(healthy_run):
    """F16-T1-3: Healthy link yields zero queue evidence and empty supported regions."""
    run_dir, _ = healthy_run
    res = run_bll(["infer", str(run_dir), "--json"])
    assert res.exit_code == 0
    assert res.json_data["latency_increase_observed"] is False
    assert res.json_data["queue_evidence"] == "none"
    assert res.json_data["supported_regions"] == []


def test_differential_algebra_fixed_delay_no_queue(fixed_delay_run):
    """F16-T1-4: Fixed propagation delay (netem) correctly discriminated from queue delay."""
    run_dir, _ = fixed_delay_run
    res = run_bll(["infer", str(run_dir), "--json"])
    assert res.exit_code == 0
    assert res.json_data["queue_evidence"] == "none"
    assert res.json_data["supported_regions"] == []


def test_differential_algebra_dual_bottleneck(tmp_path: pathlib.Path):
    """F16-T1-5: Dual FIFO congestion localizes to both near_link and far_link."""
    res_run = run_bll(["run", "--scenario", "dual_fifo_congestion", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    run_dir = pathlib.Path(res_run.json_data["run_dir"])
    res = run_bll(["infer", str(run_dir), "--json"])
    assert res.exit_code == 0
    assert "near_link" in res.json_data["supported_regions"]
    assert "far_link" in res.json_data["supported_regions"]
