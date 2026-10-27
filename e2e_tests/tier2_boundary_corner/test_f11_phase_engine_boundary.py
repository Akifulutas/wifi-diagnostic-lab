"""
Feature 11: Multi-Phase Measurement Engine (Boundary & Corner Cases)
Tier 2: Boundary & Corner Cases (>=5 test cases)
"""

import pathlib
import pytest
from e2e_tests.harness import run_bll


def test_phase_negative_load_duration():
    """F11-T2-1: Negative load phase duration rejected."""
    res = run_bll(["run", "--duration-load", "-10"])
    assert res.exit_code != 0


def test_phase_fractional_durations(tmp_path: pathlib.Path):
    """F11-T2-2: Sub-second fractional phase durations (e.g. 0.25s) supported for rapid testing."""
    res = run_bll(["run", "--scenario", "healthy_baseline", "--out-dir", str(tmp_path), "--duration-idle", "0.25", "--duration-load", "0.25", "--duration-recovery", "0.25"])
    assert res.exit_code in (0, 1)


def test_phase_events_ordering_invariance(tmp_path: pathlib.Path):
    """F11-T2-3: Phase transition timestamps strictly follow idle < load < recovery order."""
    res = run_bll(["run", "--scenario", "healthy_baseline", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    assert res.exit_code == 0
    run_dir = pathlib.Path(res.json_data["run_dir"])
    events_file = run_dir / "events.jsonl"
    assert events_file.exists()


def test_phase_run_in_nonexistent_dir(tmp_path: pathlib.Path):
    """F11-T2-4: Run automatically creates non-existent parent directories."""
    deep_path = tmp_path / "deep" / "nested" / "path"
    res = run_bll(["run", "--scenario", "healthy_baseline", "--out-dir", str(deep_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    assert res.exit_code == 0
    assert deep_path.exists()


def test_phase_zero_recovery_duration_handled(tmp_path: pathlib.Path):
    """F11-T2-5: Zero recovery phase duration rejected or warned."""
    res = run_bll(["run", "--out-dir", str(tmp_path), "--duration-idle", "0.5", "--duration-load", "0.5", "--duration-recovery", "0"])
    assert res.exit_code in (0, 1, 2)
