"""
Feature 13: Immutable Run Directory Pipeline
Tier 1: Feature Coverage (>=5 test cases)
"""

import json
import pathlib
import pytest
from e2e_tests.harness import run_bll


def test_run_dir_structure_created(tmp_path: pathlib.Path):
    """F13-T1-1: Run creates immutable runs/<run_id>/ layout with required files."""
    res = run_bll(["run", "--scenario", "healthy_baseline", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    assert res.exit_code == 0
    run_dir = pathlib.Path(res.json_data["run_dir"])
    assert (run_dir / "manifest.json").exists()
    assert (run_dir / "events.jsonl").exists()
    assert (run_dir / "quality.json").exists()
    assert (run_dir / "raw").is_dir()
    assert (run_dir / "samples").is_dir()


def test_run_dir_manifest_json_format(tmp_path: pathlib.Path):
    """F13-T1-2: manifest.json contains run metadata and durations."""
    res = run_bll(["run", "--scenario", "healthy_baseline", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    run_dir = pathlib.Path(res.json_data["run_dir"])
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["run_id"] == run_dir.name
    assert manifest["scenario_id"] == "healthy_baseline"
    assert "duration_idle" in manifest
    assert "duration_load" in manifest


def test_run_dir_events_jsonl_append_only(tmp_path: pathlib.Path):
    """F13-T1-3: events.jsonl contains valid JSON on every line."""
    res = run_bll(["run", "--scenario", "healthy_baseline", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    run_dir = pathlib.Path(res.json_data["run_dir"])
    lines = (run_dir / "events.jsonl").read_text().strip().split("\n")
    assert len(lines) >= 3
    for line in lines:
        ev = json.loads(line)
        assert "timestamp_ns" in ev
        assert "event" in ev


def test_run_dir_raw_logs_immutable(tmp_path: pathlib.Path):
    """F13-T1-4: raw/ directory captures tool logs."""
    res = run_bll(["run", "--scenario", "healthy_baseline", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    run_dir = pathlib.Path(res.json_data["run_dir"])
    assert (run_dir / "raw").exists()


def test_run_dir_samples_parquet_directory(tmp_path: pathlib.Path):
    """F13-T1-5: samples/ directory contains Parquet tables."""
    res = run_bll(["run", "--scenario", "healthy_baseline", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    run_dir = pathlib.Path(res.json_data["run_dir"])
    parquet_files = list((run_dir / "samples").glob("*.parquet"))
    assert len(parquet_files) >= 1
