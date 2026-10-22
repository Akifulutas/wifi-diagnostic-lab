"""
Bufferbloat Localization Lab (BLL) — Pytest Configuration and Global Fixtures
"""

import pathlib
import pytest
from e2e_tests.harness import run_bll, create_synthetic_run


@pytest.fixture
def cli():
    """Provides the opaque-box CLI execution function."""
    return run_bll


@pytest.fixture
def lab_env(tmp_path: pathlib.Path):
    """Provides an isolated working environment with runs/ and ground_truth/."""
    runs_dir = tmp_path / "runs"
    gt_dir = tmp_path / "ground_truth"
    runs_dir.mkdir(parents=True, exist_ok=True)
    gt_dir.mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def healthy_run(lab_env: pathlib.Path):
    run_dir = lab_env / "runs" / "run_healthy_001"
    gt_file = lab_env / "ground_truth" / "run_healthy_001.json"
    create_synthetic_run(run_dir, gt_file, scenario="healthy_baseline")
    return run_dir, gt_file


@pytest.fixture
def near_fifo_run(lab_env: pathlib.Path):
    run_dir = lab_env / "runs" / "run_near_fifo_001"
    gt_file = lab_env / "ground_truth" / "run_near_fifo_001.json"
    create_synthetic_run(run_dir, gt_file, scenario="residential_dsl_near_fifo")
    return run_dir, gt_file


@pytest.fixture
def far_fifo_run(lab_env: pathlib.Path):
    run_dir = lab_env / "runs" / "run_far_fifo_001"
    gt_file = lab_env / "ground_truth" / "run_far_fifo_001.json"
    create_synthetic_run(run_dir, gt_file, scenario="cable_asymmetric_far_fifo")
    return run_dir, gt_file


@pytest.fixture
def fixed_delay_run(lab_env: pathlib.Path):
    run_dir = lab_env / "runs" / "run_fixed_delay_001"
    gt_file = lab_env / "ground_truth" / "run_fixed_delay_001.json"
    create_synthetic_run(run_dir, gt_file, scenario="fixed_propagation_delay_control")
    return run_dir, gt_file


@pytest.fixture
def cpu_saturation_run(lab_env: pathlib.Path):
    run_dir = lab_env / "runs" / "run_cpu_sat_001"
    gt_file = lab_env / "ground_truth" / "run_cpu_sat_001.json"
    create_synthetic_run(run_dir, gt_file, scenario="endpoint_cpu_saturation_control")
    return run_dir, gt_file
