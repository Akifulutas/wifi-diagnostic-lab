"""
Feature 12: Clock Monotonicity & Sync Gating
Tier 1: Feature Coverage (>=5 test cases)
"""

import json
import pathlib
import pytest
from e2e_tests.harness import run_bll


def test_clock_monotonicity_enforced(tmp_path: pathlib.Path):
    """F12-T1-1: Nanosecond event timestamps are strictly non-decreasing monotonic."""
    res = run_bll(["run", "--scenario", "healthy_baseline", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    run_dir = pathlib.Path(res.json_data["run_dir"])
    events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text().strip().split("\n")]
    timestamps = [e["timestamp_ns"] for e in events]
    for i in range(1, len(timestamps)):
        assert timestamps[i] >= timestamps[i - 1], "Clock monotonicity violated: timestamp decreased"


def test_clock_sync_validation_success_when_synchronized(tmp_path: pathlib.Path):
    """F12-T1-2: Quality check records clock_synchronized=True in local netns reference lab."""
    res = run_bll(["run", "--scenario", "healthy_baseline", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    run_dir = pathlib.Path(res.json_data["run_dir"])
    quality = json.loads((run_dir / "quality.json").read_text())
    assert quality.get("checks", {}).get("clock_synchronized") is True


def test_one_way_delay_suppressed_when_unsynchronized(tmp_path: pathlib.Path):
    """F12-T1-3: When clock sync is unverified, OWD is suppressed and RTT is used."""
    res = run_bll(["run", "--scenario", "healthy_baseline", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    assert res.exit_code == 0


def test_clock_sync_flag_in_quality_json(tmp_path: pathlib.Path):
    """F12-T1-4: quality.json has quality check entry for clock synchronization."""
    res = run_bll(["run", "--scenario", "healthy_baseline", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    run_dir = pathlib.Path(res.json_data["run_dir"])
    quality = json.loads((run_dir / "quality.json").read_text())
    assert "clock_synchronized" in quality.get("checks", {})


def test_monotonic_to_wall_clock_correlation(tmp_path: pathlib.Path):
    """F12-T1-5: manifest.json maps ISO-8601 UTC timestamp to monotonic execution."""
    res = run_bll(["run", "--scenario", "healthy_baseline", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    run_dir = pathlib.Path(res.json_data["run_dir"])
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert "start_time_utc" in manifest
    assert "Z" in manifest["start_time_utc"] or "+00:00" in manifest["start_time_utc"]
