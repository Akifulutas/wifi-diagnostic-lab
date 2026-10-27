"""
Feature 14: Physical Ground-Truth Separation
Tier 1: Feature Coverage (>=5 test cases)
"""

import json
import pathlib
import pytest
from e2e_tests.harness import run_bll


def test_ground_truth_stored_outside_runs_dir(tmp_path: pathlib.Path):
    """F14-T1-1: Ground truth saved in ground_truth/<id>.json, outside runs/ directory."""
    res = run_bll(["run", "--scenario", "residential_dsl_near_fifo", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    assert res.exit_code == 0
    run_id = res.json_data["run_id"]
    gt_file = tmp_path / "ground_truth" / f"{run_id}.json"
    assert gt_file.exists(), "Ground truth file must exist in ground_truth/ directory"
    assert not (pathlib.Path(res.json_data["run_dir"]) / "ground_truth.json").exists()


def test_run_manifest_has_no_ground_truth_label(tmp_path: pathlib.Path):
    """F14-T1-2: manifest.json contains zero ground-truth labels (zero label leakage)."""
    res = run_bll(["run", "--scenario", "residential_dsl_near_fifo", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    run_dir = pathlib.Path(res.json_data["run_dir"])
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert "bottleneck_region" not in manifest
    assert "injected_queue_delay_ms" not in manifest


def test_inference_cli_refuses_ground_truth_input(tmp_path: pathlib.Path):
    """F14-T1-3: bll infer strictly rejects receiving a path inside ground_truth/."""
    gt_file = tmp_path / "ground_truth" / "fake_run.json"
    gt_file.parent.mkdir(parents=True, exist_ok=True)
    gt_file.write_text("{}")
    res = run_bll(["infer", str(gt_file)])
    assert res.exit_code != 0
    assert "security" in res.stderr.lower() or "prohibited" in res.stderr.lower() or "ground_truth" in res.stderr.lower()


def test_ground_truth_file_content_matches_schema(tmp_path: pathlib.Path):
    """F14-T1-4: ground_truth/<id>.json contains scenario metadata."""
    res = run_bll(["run", "--scenario", "residential_dsl_near_fifo", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    run_id = res.json_data["run_id"]
    gt = json.loads((tmp_path / "ground_truth" / f"{run_id}.json").read_text())
    assert gt["run_id"] == run_id
    assert gt["scenario_id"] == "residential_dsl_near_fifo"


def test_evaluator_is_sole_ground_truth_consumer(lab_env: pathlib.Path):
    """F14-T1-5: Evaluator accepts ground-truth directory for double-blind benchmark scoring."""
    res = run_bll(["evaluate", "--runs-dir", str(lab_env / "runs"), "--ground-truth-dir", str(lab_env / "ground_truth"), "--json"])
    assert res.exit_code == 0
    assert res.json_data.get("gate_passed") is True
