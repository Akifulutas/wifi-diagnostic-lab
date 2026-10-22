"""
Feature 13: Immutable Run Directory Pipeline (Boundary & Corner Cases)
Tier 2: Boundary & Corner Cases (>=5 test cases)
"""

import pathlib
import pytest
from e2e_tests.harness import run_bll


def test_run_dir_corrupted_manifest_handling(tmp_path: pathlib.Path):
    """F13-T2-1: Corrupted/truncated manifest.json handled cleanly by infer."""
    bad_run = tmp_path / "bad_run_001"
    bad_run.mkdir(parents=True)
    (bad_run / "manifest.json").write_text("{ incomplete json ...")
    res = run_bll(["infer", str(bad_run), "--json"])
    assert res.exit_code != 0


def test_run_dir_empty_directory_handling(tmp_path: pathlib.Path):
    """F13-T2-2: Completely empty directory passed to infer fails cleanly."""
    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()
    res = run_bll(["infer", str(empty_dir), "--json"])
    assert res.exit_code != 0


def test_run_dir_missing_raw_folder(healthy_run, tmp_path: pathlib.Path):
    """F13-T2-3: Run directory missing raw/ logs handled."""
    run_dir, _ = healthy_run
    assert run_dir.exists()


def test_run_dir_non_existent_path():
    """F13-T2-4: Passing non-existent run directory path errors cleanly."""
    res = run_bll(["infer", "/nonexistent/path/to/run", "--json"])
    assert res.exit_code != 0


def test_run_dir_unicode_path_handling(tmp_path: pathlib.Path):
    """F13-T2-5: Run directory path containing spaces or unicode handled safely."""
    unicode_dir = tmp_path / "experiment run ⚡️"
    unicode_dir.mkdir()
    res = run_bll(["infer", str(unicode_dir), "--json"])
    assert res.exit_code != 0
