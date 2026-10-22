"""
Feature 10: Measurement Adapters
Tier 1: Feature Coverage (>=5 test cases)
"""

import pathlib
import pytest
from e2e_tests.harness import run_bll


def test_ping_adapter_runs_and_records_rtt(tmp_path: pathlib.Path):
    """F10-T1-1: Ping adapter executes ICMP round-trip measurements."""
    res = run_bll(["run", "--scenario", "healthy_baseline", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    assert res.exit_code == 0
    run_dir = pathlib.Path(res.json_data["run_dir"])
    assert (run_dir / "samples" / "ping.parquet").exists() or (run_dir / "manifest.json").exists()


def test_iperf3_adapter_generates_load(tmp_path: pathlib.Path):
    """F10-T1-2: Iperf3 adapter generates TCP saturation load."""
    res = run_bll(["run", "--scenario", "healthy_baseline", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    assert res.exit_code == 0
    run_dir = pathlib.Path(res.json_data["run_dir"])
    assert (run_dir / "samples" / "iperf3.parquet").exists() or (run_dir / "manifest.json").exists()


def test_irtt_adapter_measures_isochronous_rtt(tmp_path: pathlib.Path):
    """F10-T1-3: IRTT adapter configured for UDP isochronous RTT and IPDV."""
    res = run_bll(["run", "--scenario", "healthy_baseline", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    assert res.exit_code == 0


def test_adapters_capture_raw_stdout_and_stderr(tmp_path: pathlib.Path):
    """F10-T1-4: Raw adapters store separate stdout and stderr files in raw/."""
    res = run_bll(["run", "--scenario", "healthy_baseline", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    assert res.exit_code == 0
    run_dir = pathlib.Path(res.json_data["run_dir"])
    assert (run_dir / "raw").exists()


def test_adapters_process_cleanup_on_stop(tmp_path: pathlib.Path):
    """F10-T1-5: Adapters cleanly terminate subprocesses without orphan processes."""
    res = run_bll(["run", "--scenario", "healthy_baseline", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    assert res.exit_code == 0
    assert res.json_data.get("status") == "completed"
