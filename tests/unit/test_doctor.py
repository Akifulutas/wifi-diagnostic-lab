"""
Unit tests for BLL platform discovery and capability probes (bll.platform.doctor).
tests/unit/test_doctor.py
"""

from __future__ import annotations

import platform
import pytest

from bll.platform.doctor import (
    BLLDoctorReport,
    HostInfo,
    SystemCapability,
    generate_remediation,
    probe_duckdb,
    probe_host,
    probe_iperf3,
    probe_irtt,
    probe_netns,
    probe_ping,
    probe_pyarrow,
    probe_tc,
    run_doctor,
    select_backend,
)


@pytest.mark.unit
def test_probe_host_returns_real_system_info():
    """Verify probe_host collects authentic platform parameters."""
    host = probe_host()
    assert host.os_name in ("Darwin", "Linux", "Windows")
    assert len(host.kernel_release) > 0
    assert len(host.architecture) > 0
    assert host.python_version.startswith("3.")


@pytest.mark.unit
def test_probe_ping_returns_valid_capability():
    """Verify ping probe reports available binary and details."""
    ping_cap = probe_ping()
    assert ping_cap.available is True
    assert ping_cap.path is not None
    assert "flavor" in ping_cap.details
    assert ping_cap.details["flavor"] in ("bsd", "iputils", "unknown")


@pytest.mark.unit
def test_probe_tc_non_linux_or_linux():
    """Verify tc probe behavior on Darwin vs Linux."""
    tc_cap = probe_tc()
    if platform.system() != "Linux":
        assert tc_cap.available is False
        assert tc_cap.path is None
    else:
        # On Linux, checks tc binary and module status
        assert isinstance(tc_cap.details.get("modules", {}), dict)


@pytest.mark.unit
def test_probe_netns_darwin_vs_linux():
    """Verify netns probe reports false on Darwin."""
    netns_cap = probe_netns()
    if platform.system() != "Linux":
        assert netns_cap.available is False
        assert netns_cap.details.get("supported_natively") is False


@pytest.mark.unit
def test_probe_duckdb_and_pyarrow():
    """Verify Python analytical engine probes detect installed modules."""
    duckdb_cap = probe_duckdb()
    assert duckdb_cap.available is True
    assert duckdb_cap.version is not None
    assert duckdb_cap.details.get("python_module") is True

    pyarrow_cap = probe_pyarrow()
    assert pyarrow_cap.available is True
    assert pyarrow_cap.version is not None
    assert pyarrow_cap.details.get("python_module") is True


@pytest.mark.unit
def test_backend_selector_explicit_override():
    """Verify that explicit override takes precedence."""
    host = HostInfo(os_name="Linux", kernel_release="6.1.0", architecture="x86_64", python_version="3.14.0")
    caps = {
        "netns": SystemCapability(available=True),
        "tc": SystemCapability(available=True),
    }
    backend = select_backend(host, caps, explicit_override="mock_simulation")
    assert backend == "mock_simulation"

    with pytest.raises(ValueError, match="Unknown backend"):
        select_backend(host, caps, explicit_override="invalid_backend")


@pytest.mark.unit
def test_backend_selector_native_linux_vs_mock():
    """Verify native_linux is selected on Linux when netns and tc are available."""
    host = HostInfo(os_name="Linux", kernel_release="6.1.0", architecture="x86_64", python_version="3.14.0")
    caps = {
        "netns": SystemCapability(available=True),
        "tc": SystemCapability(available=True),
    }
    assert select_backend(host, caps) == "native_linux"

    # Missing tc falls back to mock or container
    caps_missing = {
        "netns": SystemCapability(available=True),
        "tc": SystemCapability(available=False),
        "docker": SystemCapability(available=False),
    }
    assert select_backend(host, caps_missing) == "mock_simulation"


@pytest.mark.unit
def test_remediation_generation_for_mock():
    """Verify remediation steps generated for mock simulation."""
    host = HostInfo(os_name="Darwin", kernel_release="24.0.0", architecture="arm64", python_version="3.14.0")
    caps = {
        "duckdb": SystemCapability(available=True),
        "pyarrow": SystemCapability(available=True),
    }
    req_met, steps = generate_remediation("mock_simulation", host, caps)
    assert req_met is True
    assert any("Mock Simulation" in step for step in steps)


@pytest.mark.unit
def test_run_doctor_report_generation():
    """Verify run_doctor produces a complete, compliant BLLDoctorReport."""
    report = run_doctor(target_backend="mock_simulation")
    assert isinstance(report, BLLDoctorReport)
    assert report.selected_backend == "mock_simulation"
    assert report.all_requirements_met is True
    assert "netns" in report.capabilities
    assert "tc" in report.capabilities
    assert "iproute2" in report.capabilities
    assert "ping" in report.capabilities
    assert "irtt" in report.capabilities
    assert "iperf3" in report.capabilities
    assert "duckdb" in report.capabilities
    assert "pyarrow" in report.capabilities
