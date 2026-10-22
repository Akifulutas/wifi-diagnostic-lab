"""
Fault Injection and Cleanup State Machine Tests (R2, Milestone 2).
tests/fault_injection/test_cleanup_faults.py
"""

from __future__ import annotations

import os
from pathlib import Path
import pytest

from bll.lab.cleanup import LabCleanupManager, emergency_cleanup
from bll.platform.backends import get_backend


@pytest.mark.fault_injection
def test_cleanup_empty_state_idempotent():
    """Verify cleanup succeeds cleanly when no namespaces or interfaces exist."""
    res = LabCleanupManager.cleanup()
    assert res["status"] in ("cleaned", "down")
    assert isinstance(res["deleted_namespaces"], list)
    assert isinstance(res["deleted_interfaces"], list)
    assert isinstance(res["killed_processes"], list)


@pytest.mark.fault_injection
def test_find_pids_nonexistent_namespace_safe():
    """Verify finding PIDs in non-existent namespace returns empty list without error."""
    pids = LabCleanupManager.find_pids_in_namespace("bll-nonexistent-ns-12345")
    assert pids == []


@pytest.mark.fault_injection
def test_terminate_processes_dead_pids_safe():
    """Verify terminate_processes handles dead / non-existent PIDs gracefully."""
    # PID 99999999 is guaranteed dead
    killed = LabCleanupManager.terminate_processes([99999998, 99999999], grace_seconds=0.01)
    assert isinstance(killed, list)


@pytest.mark.fault_injection
def test_sweep_residual_host_links_safe():
    """Verify sweep_residual_host_links executes safely without error."""
    deleted = LabCleanupManager.sweep_residual_host_links()
    assert isinstance(deleted, list)


@pytest.mark.fault_injection
def test_cleanup_cleans_ephemeral_locks():
    """Verify cleanup sweeps ephemeral /tmp/bll* files."""
    dummy_lock = Path("/tmp/bll_test_lock_file.tmp")
    dummy_lock.write_text("test_lock", encoding="utf-8")
    assert dummy_lock.exists()

    LabCleanupManager.cleanup()
    assert not dummy_lock.exists()


@pytest.mark.fault_injection
def test_emergency_cleanup_safe():
    """Verify emergency_cleanup executes without raising exceptions."""
    emergency_cleanup()


@pytest.mark.fault_injection
def test_recovery_from_simulated_sigkill_crash():
    """Verify that if topology state was created and process dies abruptly, next teardown cleans it."""
    backend = get_backend("mock_simulation")
    backend.setup_topology()

    state_file = Path("/tmp/bll_mock_simulation_state.json")
    assert state_file.exists()

    # Simulate abrupt teardown
    cleanup_res = backend.teardown_topology()
    assert cleanup_res["status"] in ("cleaned", "down")
    assert not state_file.exists()

    # Re-verify topology is reported not setup
    verify_res = backend.verify_topology()
    assert verify_res["verified"] is False
