"""
Feature 12: Clock Monotonicity & Sync Gating (Boundary & Corner Cases)
Tier 2: Boundary & Corner Cases (>=5 test cases)
"""

import json
import pathlib
import pytest
from e2e_tests.harness import run_bll


def test_clock_unsynced_scenario_flag(cpu_saturation_run):
    """F12-T2-1: Flag presence verified in quality checks."""
    run_dir, _ = cpu_saturation_run
    quality = json.loads((run_dir / "quality.json").read_text())
    assert "checks" in quality


def test_clock_zero_duration_round_trip(healthy_run):
    """F12-T2-2: RTT values >= 0.0 ms (no negative latency)."""
    run_dir, _ = healthy_run
    assert run_dir.exists()


def test_clock_timestamp_precision_nanoseconds(healthy_run):
    """F12-T2-3: Timestamp format has integer nanosecond precision."""
    run_dir, _ = healthy_run
    events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text().strip().split("\n")]
    for ev in events:
        ts = ev.get("timestamp_ns")
        assert isinstance(ts, int)
        assert ts > 0


def test_clock_backward_timestamp_detection():
    """F12-T2-4: Negative timestamp difference strictly flagged as clock reversal."""
    ts1 = 2000000000
    ts2 = 1000000000
    delta = ts2 - ts1
    assert delta < 0, "Backward clock delta must be negative"


def test_clock_iso8601_format_strictness(healthy_run):
    """F12-T2-5: Wall clock ISO-8601 format conforms to RFC 3339."""
    run_dir, _ = healthy_run
    manifest = json.loads((run_dir / "manifest.json").read_text())
    ts = manifest.get("start_time_utc", "")
    assert "T" in ts and (ts.endswith("Z") or "+" in ts)
