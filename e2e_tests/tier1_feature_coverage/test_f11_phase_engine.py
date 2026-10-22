"""
Feature 11: Multi-Phase Measurement Engine
Tier 1: Feature Coverage (>=5 test cases)
"""

import json
import pathlib
import pytest
from e2e_tests.harness import run_bll


def test_phase_engine_runs_idle_phase(tmp_path: pathlib.Path):
    """F11-T1-1: Phase engine starts with Baseline Idle phase (~20s)."""
    res = run_bll(["run", "--scenario", "healthy_baseline", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    assert res.exit_code == 0
    run_dir = pathlib.Path(res.json_data["run_dir"])
    events_file = run_dir / "events.jsonl"
    assert events_file.exists()
    lines = [json.loads(line) for line in events_file.read_text().strip().split("\n")]
    phases = [e.get("phase") for e in lines]
    assert "idle" in phases


def test_phase_engine_runs_saturation_load_phase(tmp_path: pathlib.Path):
    """F11-T1-2: Phase engine executes Saturation Load phase (~60s)."""
    res = run_bll(["run", "--scenario", "healthy_baseline", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    run_dir = pathlib.Path(res.json_data["run_dir"])
    lines = [json.loads(line) for line in (run_dir / "events.jsonl").read_text().strip().split("\n")]
    phases = [e.get("phase") for e in lines]
    assert "load" in phases


def test_phase_engine_runs_recovery_phase(tmp_path: pathlib.Path):
    """F11-T1-3: Phase engine executes Recovery phase (~30s) post-load."""
    res = run_bll(["run", "--scenario", "healthy_baseline", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    run_dir = pathlib.Path(res.json_data["run_dir"])
    lines = [json.loads(line) for line in (run_dir / "events.jsonl").read_text().strip().split("\n")]
    phases = [e.get("phase") for e in lines]
    assert "recovery" in phases


def test_phase_engine_supports_upload_direction(tmp_path: pathlib.Path):
    """F11-T1-4: Phase engine supports upstream/upload load condition."""
    res = run_bll(["run", "--scenario", "residential_dsl_near_fifo", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    assert res.exit_code == 0


def test_phase_engine_supports_download_and_bidir(tmp_path: pathlib.Path):
    """F11-T1-5: Phase engine supports downstream and bidirectional load conditions."""
    res = run_bll(["run", "--scenario", "cable_asymmetric_far_fifo", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    assert res.exit_code == 0
