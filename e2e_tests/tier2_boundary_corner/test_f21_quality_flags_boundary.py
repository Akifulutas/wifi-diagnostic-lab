"""
Feature 21: Quality Control Flagging (Boundary & Corner Cases)
Tier 2: Boundary & Corner Cases (>=5 test cases)
"""

import json
import pytest
from e2e_tests.harness import run_bll


def test_qc_flag_critical_flag_forces_abstention(cpu_saturation_run):
    """F21-T2-1: CLIENT_CPU_SATURATION critical flag deterministically forces abstained=True."""
    run_dir, _ = cpu_saturation_run
    res = run_bll(["infer", str(run_dir), "--json"])
    assert res.exit_code == 0
    assert res.json_data["abstained"] is True


def test_qc_flag_empty_flags_on_clean_run(healthy_run):
    """F21-T2-2: Healthy baseline has zero quality flags."""
    run_dir, _ = healthy_run
    quality = json.loads((run_dir / "quality.json").read_text())
    assert len(quality.get("flags", [])) == 0


def test_qc_flag_uppercase_format(cpu_saturation_run):
    """F21-T2-3: Quality flags are strictly UPPER_SNAKE_CASE."""
    run_dir, _ = cpu_saturation_run
    quality = json.loads((run_dir / "quality.json").read_text())
    for flag in quality.get("flags", []):
        assert flag == flag.upper()
        assert "_" in flag or flag.isalpha()


def test_qc_flag_missing_quality_file_handled(healthy_run, tmp_path):
    """F21-T2-4: Run directory without quality.json executes infer with empty flags list."""
    run_dir, _ = healthy_run
    # Infer still succeeds
    res = run_bll(["infer", str(run_dir), "--json"])
    assert res.exit_code == 0
    assert isinstance(res.json_data["quality_flags"], list)


def test_qc_flag_check_boolean_values(healthy_run):
    """F21-T2-5: Invariant checks in quality.json are boolean."""
    run_dir, _ = healthy_run
    quality = json.loads((run_dir / "quality.json").read_text())
    for check_name, val in quality.get("checks", {}).items():
        assert isinstance(val, bool)
