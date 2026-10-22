"""
Feature 4: Multi-Backend Abstraction
Tier 1: Feature Coverage (>=5 test cases)
"""

import platform
import pytest
from e2e_tests.harness import run_bll


def test_backend_selection_native_linux_on_linux():
    """F04-T1-1: Probed backend on Linux selects native_linux (or container/mock if unprivileged)."""
    if platform.system() != "Linux":
        pytest.skip("Test requires Linux platform")
    res = run_bll(["doctor", "--json"])
    assert res.exit_code == 0
    assert res.json_data["selected_backend"] in ("native_linux", "container_linux", "mock_simulation")


def test_backend_darwin_fallback():
    """F04-T1-2: On macOS/Darwin, default backend is container_linux, vm_linux, or mock_simulation."""
    if platform.system() != "Darwin":
        pytest.skip("Test requires Darwin platform")
    res = run_bll(["doctor", "--json"])
    assert res.exit_code == 0
    backend = res.json_data["selected_backend"]
    assert backend in ("container_linux", "vm_linux", "mock_simulation")


def test_backend_flag_override_mock():
    """F04-T1-3: --backend mock_simulation forces mock simulation backend."""
    res = run_bll(["doctor", "--backend", "mock_simulation", "--json"])
    assert res.exit_code == 0
    assert res.json_data["selected_backend"] == "mock_simulation"


def test_mock_backend_reports_all_tools_simulated():
    """F04-T1-4: In mock_simulation backend, requirements are satisfied via simulation."""
    res = run_bll(["doctor", "--backend", "mock_simulation", "--json"])
    assert res.exit_code == 0
    assert res.json_data["all_requirements_met"] is True


def test_backend_remediation_guidance():
    """F04-T1-5: Doctor report contains remediation steps when non-mock environment has missing tools."""
    res = run_bll(["doctor", "--json"])
    assert "remediation_steps" in res.json_data
    assert isinstance(res.json_data["remediation_steps"], list)
