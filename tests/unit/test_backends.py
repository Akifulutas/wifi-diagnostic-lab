"""
Unit tests for BLL execution backends (bll.platform.backends).
tests/unit/test_backends.py
"""

from __future__ import annotations

import json
import pytest

from bll.platform.backends import (
    ContainerLinuxBackend,
    LabBackend,
    MockSimulationBackend,
    NativeLinuxBackend,
    QdiscConfig,
    get_backend,
)


@pytest.mark.unit
def test_backend_factory():
    """Verify get_backend returns the correct backend instance."""
    mock_be = get_backend("mock_simulation")
    assert isinstance(mock_be, MockSimulationBackend)
    assert mock_be.name == "mock_simulation"

    native_be = get_backend("native_linux")
    assert isinstance(native_be, NativeLinuxBackend)
    assert native_be.name == "native_linux"

    container_be = get_backend("container_linux")
    assert isinstance(container_be, ContainerLinuxBackend)
    assert container_be.name == "container_linux"

    with pytest.raises(ValueError, match="Unknown backend"):
        get_backend("nonexistent_backend")


@pytest.mark.unit
def test_mock_simulation_lifecycle():
    """Verify MockSimulationBackend setup, verification, qdisc, and teardown."""
    backend = MockSimulationBackend()

    # Before setup, verification fails
    pre_verify = backend.verify_topology()
    assert pre_verify["verified"] is False

    # Setup topology
    res = backend.setup_topology()
    assert res["status"] == "ready"
    assert len(res["namespaces"]) == 6
    assert len(res["interfaces"]) == 10
    assert "bll-client" in res["namespaces"]
    assert "bll-remote" in res["namespaces"]

    # Verify topology invariants
    verify = backend.verify_topology()
    assert verify["verified"] is True
    inv = verify["invariants"]
    assert inv["client_to_observer"] is True
    assert inv["observer_to_remote"] is True
    assert inv["client_to_remote"] is True

    # Configure qdisc
    qdisc_res = backend.configure_qdisc(
        QdiscConfig(
            node="bll-qnear",
            interface="bll-qn-rtr",
            shaper_type="tbf",
            rate="20mbit",
            delay_ms=15.0,
        )
    )
    assert qdisc_res["status"] == "ok"

    # Reset qdiscs
    reset_res = backend.reset_qdiscs()
    assert reset_res["status"] == "ok"

    # Teardown topology
    teardown_res = backend.teardown_topology()
    assert teardown_res["status"] == "cleaned"
    assert len(teardown_res["deleted_namespaces"]) == 6

    # Idempotent second teardown
    teardown_second = backend.teardown_topology()
    assert teardown_second["status"] == "cleaned"
    assert len(teardown_second["deleted_namespaces"]) == 0


@pytest.mark.unit
def test_mock_simulation_synthetic_tool_execution():
    """Verify mock tool execution returns valid synthetic outputs."""
    backend = MockSimulationBackend()
    backend.setup_topology()

    # Synthetic ping
    code, stdout, stderr = backend.execute_tool("client", ["ping", "-c", "3", "10.10.5.2"])
    assert code == 0
    assert "PING 10.10.5.2" in stdout
    assert "icmp_seq=1" in stdout
    assert "icmp_seq=3" in stdout

    # Synthetic iperf3 JSON
    code, stdout, stderr = backend.execute_tool("client", ["iperf3", "-c", "10.10.5.2", "-J"])
    assert code == 0
    iperf_data = json.loads(stdout)
    assert "intervals" in iperf_data
    assert "sum" in iperf_data["intervals"][0]

    # Synthetic irtt JSON
    code, stdout, stderr = backend.execute_tool("client", ["irtt", "client", "10.10.5.2", "-o", "json"])
    assert code == 0
    irtt_data = json.loads(stdout)
    assert "round_trip" in irtt_data
    assert "stats" in irtt_data

    # Synthetic tc
    code, stdout, stderr = backend.execute_tool("qnear", ["tc", "-s", "qdisc", "show"])
    assert code == 0
    assert "backlog" in stdout


@pytest.mark.unit
def test_native_linux_availability():
    """Verify NativeLinuxBackend availability logic."""
    backend = NativeLinuxBackend()
    is_avail, reason = backend.is_available()
    assert isinstance(is_avail, bool)


@pytest.mark.unit
def test_container_linux_availability():
    """Verify ContainerLinuxBackend availability logic."""
    backend = ContainerLinuxBackend()
    is_avail, reason = backend.is_available()
    assert isinstance(is_avail, bool)
