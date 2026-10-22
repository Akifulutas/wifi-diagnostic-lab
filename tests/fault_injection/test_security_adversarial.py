"""
Empirical Security & Fault Injection Challenge Suite.
tests/fault_injection/test_security_adversarial.py

Authored by Challenger M2-2 to empirically verify:
1. Shell injection penetration and command rejection in bll-lab-helper.
2. Path traversal rejection and non-bll namespace/interface gating.
3. Parameter boundary validation in configure_qdisc (rate, limit, loss).
4. Daemon crash resilience against malformed network bytes (DoS).
5. Fault injection and teardown reliability under SIGINT, simulated SIGKILL, stubborn processes, and timeouts.
"""

from __future__ import annotations

import os
import signal
import socket
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from bll.helper.security import (
    FORBIDDEN_SHELL_CHARS,
    SecurityValidationError,
    validate_no_shell_metachars,
    validate_resource_name,
    validate_tool_command,
)
from bll.helper.server import HelperServer, main as helper_main
from bll.lab.cleanup import LabCleanupManager, emergency_cleanup
from bll.platform.backends import get_backend


# ============================================================================
# 1. Shell Injection & Command Execution Security Penetration
# ============================================================================

@pytest.mark.fault_injection
def test_resource_name_rejects_command_injection_and_traversal():
    """Verify validate_resource_name strictly rejects command injections and path traversals."""
    malicious_inputs = [
        "; rm -rf /",
        "rm -rf /",
        "; ls -la",
        "| cat",
        "$(whoami)",
        "`whoami`",
        "test; reboot",
        "test & reboot",
        "test && reboot",
        "test > /tmp/pwn",
        "test < /etc/passwd",
        "bll-$(whoami)",
        "../../../etc/shadow",
        "bll-../../../etc/shadow",
        "bll-test/sub",
        "bll-test\\sub",
        "prod-net",
        "host-eth0",
        "eth0",
        "lo",
        "docker0",
        "bll-this-namespace-name-is-way-too-long-exceeding-limit",
    ]
    for payload in malicious_inputs:
        with pytest.raises(SecurityValidationError):
            validate_resource_name(payload, kind="namespace")


@pytest.mark.fault_injection
def test_resource_name_interface_fifteen_char_limit():
    """Verify validate_resource_name strictly rejects interface names exceeding 15 chars."""
    with pytest.raises(SecurityValidationError) as excinfo:
        validate_resource_name("bll-1234567890123", kind="interface")
    assert "IFNAMSIZ" in str(excinfo.value) or "exceeds" in str(excinfo.value)


@pytest.mark.fault_injection
def test_validate_no_shell_metachars_rejects_all_control_chars():
    """Verify validate_no_shell_metachars rejects all specified shell control characters."""
    for ch in ";`&|$()<>\n\r\0*?[]{}~!#\"'":
        with pytest.raises(SecurityValidationError):
            validate_no_shell_metachars(f"prefix{ch}suffix")


@pytest.mark.fault_injection
def test_validate_no_shell_metachars_rejects_backslash():
    """Verify validate_no_shell_metachars rejects backslash escape character."""
    with pytest.raises(SecurityValidationError):
        validate_no_shell_metachars("escape\\seq")


@pytest.mark.fault_injection
def test_exec_tool_rejects_unwhitelisted_binaries():
    """Verify validate_tool_command rejects arbitrary unwhitelisted binaries."""
    for bad_cmd in [
        ["rm", "-rf", "/"],
        ["sh", "-c", "id"],
        ["bash", "-c", "whoami"],
        ["python3", "-c", "exit(0)"],
        ["curl", "https://example.com"],
        ["nc", "-l", "8080"],
    ]:
        with pytest.raises(SecurityValidationError):
            validate_tool_command(bad_cmd)


@pytest.mark.fault_injection
def test_exec_tool_rejects_command_injection_in_arguments():
    """Verify validate_tool_command rejects shell injection in arguments of whitelisted tools."""
    for bad_args in [
        ["ping", "-c", "1", "; rm -rf /"],
        ["ping", "-c", "1", "| cat"],
        ["ping", "-c", "1", "$(whoami)"],
        ["ping", "-c", "1", "`whoami`"],
        ["ping", "-c", "1", "test; reboot"],
        ["ping", "-c", "1", "10.10.5.2 & touch /tmp/pwn"],
    ]:
        with pytest.raises(SecurityValidationError):
            validate_tool_command(bad_args)


@pytest.mark.fault_injection
def test_exec_tool_rejects_fake_binary_in_tmp_or_relative_path():
    """Verify validate_tool_command rejects paths pointing outside whitelisted system binary paths."""
    fake_ping = Path("/tmp/ping")
    try:
        fake_ping.write_text("#!/bin/sh\necho PWNED\n", encoding="utf-8")
        fake_ping.chmod(fake_ping.stat().st_mode | stat.S_IEXEC)

        # An attacker should NOT be able to run /tmp/ping or ../../../../bin/ping
        with pytest.raises(SecurityValidationError):
            validate_tool_command(["/tmp/ping", "-c", "1"])

        with pytest.raises(SecurityValidationError):
            validate_tool_command(["../../../../bin/ping", "-c", "1"])

    finally:
        fake_ping.unlink(missing_ok=True)


# ============================================================================
# 2. Qdisc Configuration Security & Parameter Boundaries
# ============================================================================

@pytest.mark.fault_injection
def test_configure_qdisc_rejects_command_injection_and_path_traversal_in_rate():
    """Verify HelperServer.rpc_configure_qdisc rejects traversal and injection in rate."""
    server = HelperServer(backend_runner=get_backend("mock_simulation"))

    for bad_rate in [
        "rm -rf /",
        "../../../etc/shadow",
        "50mbit extra_arg",
        "20mbit; reboot",
        "20mbit|cat",
    ]:
        req = {
            "jsonrpc": "2.0",
            "id": "q1",
            "method": "configure_qdisc",
            "params": {"netns": "bll-client", "interface": "bll-cli-qn", "rate": bad_rate},
        }
        res = server.dispatch(req)
        assert "error" in res, f"configure_qdisc accepted invalid rate '{bad_rate}'"


@pytest.mark.fault_injection
def test_configure_qdisc_rejects_invalid_limit_and_loss():
    """Verify HelperServer.rpc_configure_qdisc rejects invalid limits and negative/excessive loss."""
    server = HelperServer(backend_runner=get_backend("mock_simulation"))

    for param, bad_val in [
        ("limit", -100),
        ("limit", "rm -rf /"),
        ("limit", "not_a_number"),
        ("loss", -5.0),
        ("loss", 150.0),
        ("loss", "rm -rf /"),
    ]:
        req = {
            "jsonrpc": "2.0",
            "id": "q2",
            "method": "configure_qdisc",
            "params": {"netns": "bll-client", "interface": "bll-cli-qn", param: bad_val},
        }
        res = server.dispatch(req)
        assert "error" in res, f"configure_qdisc accepted invalid {param}='{bad_val}'"


# ============================================================================
# 3. Helper Daemon Network Resilience & DoS Prevention
# ============================================================================

@pytest.mark.fault_injection
def test_helper_socket_server_resilience_to_malformed_utf8():
    """Verify HelperServer socket loop does not terminate upon receiving malformed UTF-8 bytes."""
    sock_path = "/tmp/test_bll_helper_resilience.sock"
    if Path(sock_path).exists():
        Path(sock_path).unlink()

    server_thread = threading.Thread(
        target=helper_main,
        args=(["--socket", sock_path, "--backend", "mock_simulation"],),
        daemon=True,
    )
    server_thread.start()
    time.sleep(0.2)

    try:
        assert Path(sock_path).exists(), "Socket was not created by helper daemon"

        # Send malformed bytes
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(sock_path)
        client.sendall(b"\xff\xfe\x00malformed_bytes\n")
        client.close()

        time.sleep(0.2)

        # Daemon should still be alive and accept subsequent valid connection
        assert server_thread.is_alive(), "Helper daemon crashed on invalid UTF-8 bytes"

        client2 = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client2.connect(sock_path)
        req = '{"jsonrpc": "2.0", "id": "probe", "method": "status", "params": {}}\n'
        client2.sendall(req.encode("utf-8"))
        resp_data = client2.recv(4096)
        client2.close()
        assert resp_data, "Helper daemon failed to reply after handling malformed bytes"

    finally:
        if Path(sock_path).exists():
            Path(sock_path).unlink()


# ============================================================================
# 4. Fault Injection & Teardown Reliability
# ============================================================================

@pytest.mark.fault_injection
def test_stubborn_process_escalation_to_sigkill():
    """Verify terminate_processes escalates to SIGKILL if process ignores SIGTERM."""
    # Spawn child that explicitly ignores SIGTERM
    proc = subprocess.Popen(
        [sys.executable, "-c", "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)"]
    )
    pid = proc.pid
    try:
        time.sleep(0.1)
        assert proc.poll() is None

        killed = LabCleanupManager.terminate_processes([pid], grace_seconds=0.1)
        time.sleep(0.1)
        assert proc.poll() is not None, f"Stubborn process PID {pid} was not killed!"
        assert pid in killed
    finally:
        if proc.poll() is None:
            proc.kill()


@pytest.mark.fault_injection
def test_simulated_sigkill_crash_recovery():
    """Verify that if process is killed with SIGKILL leaving state dirty, subsequent cleanup purges all."""
    state_file = Path("/tmp/bll_mock_simulation_state.json")
    state_file.write_text('{"status": "ready"}', encoding="utf-8")
    lock_file = Path("/tmp/bll_simulated_crash.lock")
    lock_file.write_text("locked", encoding="utf-8")

    orphan = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    orphan_pid = orphan.pid

    try:
        assert state_file.exists()
        assert lock_file.exists()
        assert orphan.poll() is None

        # Simulate cleanup after crash
        LabCleanupManager.terminate_processes([orphan_pid], grace_seconds=0.1)
        res = LabCleanupManager.cleanup()

        assert not state_file.exists(), "State file leaked after cleanup"
        assert not lock_file.exists(), "Lock file leaked after cleanup"
        assert orphan.poll() is not None, "Orphan process leaked after cleanup"
        assert res["status"] in ("cleaned", "down")
    finally:
        if orphan.poll() is None:
            orphan.kill()


@pytest.mark.fault_injection
def test_sigint_emergency_cleanup_integration():
    """Verify that sending SIGINT to a running BLL CLI process executes emergency_cleanup and exits 130."""
    state_file = Path("/tmp/bll_mock_simulation_state.json")
    state_file.write_text('{"status": "ready"}', encoding="utf-8")
    assert state_file.exists()

    proc = subprocess.Popen(
        [sys.executable, "-c", "import bll.cli, time; print('READY', flush=True); time.sleep(10)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert proc.stdout is not None
    line = proc.stdout.readline()
    assert "READY" in line

    proc.send_signal(signal.SIGINT)
    proc.communicate()

    assert proc.returncode == 130, f"Expected returncode 130 on SIGINT, got {proc.returncode}"
    assert not state_file.exists(), "emergency_cleanup failed to remove state file on SIGINT"


@pytest.mark.fault_injection
def test_cleanup_idempotency_stress():
    """Verify cleanup is 100% idempotent across 20 iterations with simulated locks and dirty states."""
    backend = get_backend("mock_simulation")
    for i in range(20):
        backend.setup_topology()
        lock_file = Path(f"/tmp/bll_stress_lock_{i}.tmp")
        lock_file.write_text("lock", encoding="utf-8")

        res = LabCleanupManager.cleanup()
        assert not lock_file.exists(), f"Lock file {lock_file} leaked"
        assert res["status"] in ("cleaned", "down")


@pytest.mark.fault_injection
def test_exec_tool_timeout_handling_in_helper():
    """Verify that tool timeouts produce structured JSON-RPC error responses rather than unhandled crashes."""
    server = HelperServer(backend_runner=None)

    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["ip", "netns", "exec"], timeout=0.1)):
        res = server.dispatch({
            "jsonrpc": "2.0",
            "id": "t_timeout",
            "method": "exec_tool",
            "params": {"netns": "bll-client", "command": ["ping", "-c", "10", "10.10.5.2"], "timeout_seconds": 0.1},
        })
        assert "error" in res
        assert res["error"]["code"] == -32603
        assert "timed out" in res["error"]["message"].lower() or "timeoutexpired" in res["error"]["message"].lower()
