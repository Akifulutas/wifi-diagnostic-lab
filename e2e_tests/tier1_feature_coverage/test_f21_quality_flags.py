"""
Feature 21: Quality Control Flagging
Tier 1: Feature Coverage (>=5 test cases)
"""

import json
import pathlib
import pytest
from e2e_tests.harness import run_bll


def test_qc_flag_cpu_saturation_detected(cpu_saturation_run):
    """F21-T1-1: Host CPU starvation triggers CLIENT_CPU_SATURATION quality flag."""
    run_dir, _ = cpu_saturation_run
    quality = json.loads((run_dir / "quality.json").read_text())
    assert "CLIENT_CPU_SATURATION" in quality.get("flags", [])


def test_qc_flag_pristine_run_zero_flags(healthy_run):
    """F21-T1-2: Healthy reference run has empty quality flags array."""
    run_dir, _ = healthy_run
    quality = json.loads((run_dir / "quality.json").read_text())
    assert len(quality.get("flags", [])) == 0


def test_qc_flag_quality_json_structure(healthy_run):
    """F21-T1-3: quality.json contains run_id, flags array, and checks dictionary."""
    run_dir, _ = healthy_run
    quality = json.loads((run_dir / "quality.json").read_text())
    assert "run_id" in quality
    assert "flags" in quality
    assert "checks" in quality


def test_qc_flag_causes_abstention_in_inference(cpu_saturation_run):
    """F21-T1-4: Quality flag propagates into InferenceOutputContract and triggers abstention."""
    run_dir, _ = cpu_saturation_run
    res = run_bll(["infer", str(run_dir), "--json"])
    assert res.exit_code == 0
    assert "CLIENT_CPU_SATURATION" in res.json_data["quality_flags"]
    assert res.json_data["abstained"] is True


def test_qc_flag_checks_subdict_present(healthy_run):
    """F21-T1-5: Checks subdictionary evaluates core invariant test gates."""
    run_dir, _ = healthy_run
    quality = json.loads((run_dir / "quality.json").read_text())
    checks = quality.get("checks", {})
    assert "clock_synchronized" in checks
    assert "qdisc_verified" in checks
