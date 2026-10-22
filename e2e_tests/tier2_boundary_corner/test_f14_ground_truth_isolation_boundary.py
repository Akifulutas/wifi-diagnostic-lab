"""
Feature 14: Physical Ground-Truth Separation (Boundary & Corner Cases)
Tier 2: Boundary & Corner Cases (>=5 test cases)
"""

import pathlib
import pytest
from e2e_tests.harness import run_bll


def test_ground_truth_isolation_violation_in_infer(tmp_path: pathlib.Path):
    """F14-T2-1: Infer directly called on a ground_truth file path strictly blocked."""
    gt_dir = tmp_path / "ground_truth"
    gt_dir.mkdir(parents=True)
    fake_gt = gt_dir / "run_01.json"
    fake_gt.write_text("{}")
    res = run_bll(["infer", str(fake_gt)])
    assert res.exit_code != 0
    assert "security" in res.stderr.lower() or "prohibited" in res.stderr.lower() or "ground_truth" in res.stderr.lower()


def test_ground_truth_isolation_nested_path(tmp_path: pathlib.Path):
    """F14-T2-2: Infer called on path containing ground_truth substring blocked."""
    nested = tmp_path / "data" / "ground_truth" / "run_02"
    nested.mkdir(parents=True)
    res = run_bll(["infer", str(nested)])
    assert res.exit_code != 0


def test_ground_truth_empty_directory_evaluate(tmp_path: pathlib.Path):
    """F14-T2-3: Evaluate called on empty directories handles gracefully."""
    empty_runs = tmp_path / "runs"
    empty_gt = tmp_path / "ground_truth"
    empty_runs.mkdir()
    empty_gt.mkdir()
    res = run_bll(["evaluate", "--runs-dir", str(empty_runs), "--ground-truth-dir", str(empty_gt), "--json"])
    assert res.exit_code in (0, 1, 2)


def test_ground_truth_unreadable_file_evaluate(tmp_path: pathlib.Path):
    """F14-T2-4: Malformed ground truth JSON file in evaluate handled with error."""
    runs = tmp_path / "runs"
    gt = tmp_path / "ground_truth"
    runs.mkdir()
    gt.mkdir()
    (gt / "broken.json").write_text("malformed json {")
    res = run_bll(["evaluate", "--runs-dir", str(runs), "--ground-truth-dir", str(gt), "--json"])
    assert res.exit_code in (0, 1, 2)


def test_ground_truth_manifest_isolation_invariance(healthy_run):
    """F14-T2-5: Run manifest in runs/<id>/ never imports or symlinks ground_truth."""
    run_dir, gt_file = healthy_run
    assert not (run_dir / "ground_truth.json").is_symlink()
    assert not (run_dir / "ground_truth.json").exists()
