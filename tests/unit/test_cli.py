"""
Unit tests for BLL CLI command hierarchy (bll.cli).
tests/unit/test_cli.py
"""

from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import click
import pytest
from click.testing import CliRunner

from bll.cli import main


@pytest.mark.unit
def test_cli_help_displays_subcommands():
    """Verify bll --help displays core subcommands."""
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    for cmd in ["doctor", "lab", "run", "infer", "export", "evaluate"]:
        assert cmd in result.output


@pytest.mark.unit
def test_cli_version_flag():
    """Verify bll --version outputs package version."""
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


@pytest.mark.unit
def test_cli_doctor_json():
    """Verify bll doctor --json outputs valid BLLDoctorReport."""
    runner = CliRunner()
    result = runner.invoke(main, ["doctor", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "selected_backend" in data
    assert "capabilities" in data
    assert "all_requirements_met" in data


@pytest.mark.unit
def test_cli_doctor_human_output():
    """Verify bll doctor outputs formatted diagnostic summary."""
    runner = CliRunner()
    result = runner.invoke(main, ["doctor"])
    assert result.exit_code == 0
    assert "Doctor Probe" in result.output or "Selected Backend:" in result.output


@pytest.mark.unit
def test_cli_global_backend_flag():
    """Verify bll --backend mock_simulation doctor --json selects mock simulation."""
    runner = CliRunner()
    result = runner.invoke(main, ["--backend", "mock_simulation", "doctor", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["selected_backend"] == "mock_simulation"


@pytest.mark.unit
def test_cli_lab_lifecycle_mock():
    """Verify bll lab up, verify, down with mock_simulation backend."""
    runner = CliRunner()

    # Dry-run
    res_dry = runner.invoke(main, ["lab", "up", "--backend", "mock_simulation", "--dry-run"])
    assert res_dry.exit_code == 0
    assert "[Dry Run]" in res_dry.output

    # Lab up
    res_up = runner.invoke(main, ["lab", "up", "--backend", "mock_simulation"])
    assert res_up.exit_code == 0

    # Lab verify
    res_verify = runner.invoke(main, ["lab", "verify", "--backend", "mock_simulation", "--json"])
    assert res_verify.exit_code == 0
    verify_data = json.loads(res_verify.output)
    assert verify_data["verified"] is True
    assert verify_data["invariants"]["client_to_remote"] is True

    # Lab down
    res_down = runner.invoke(main, ["lab", "down", "--backend", "mock_simulation"])
    assert res_down.exit_code == 0
    assert "cleaned" in res_down.output


@pytest.mark.unit
def test_cli_lab_global_backend_propagation():
    """Verify lab up, lab verify, and lab down respect global --backend flag."""
    runner = CliRunner()
    with patch("bll.platform.backends.get_backend") as mock_gb:
        mock_backend = MagicMock()
        mock_backend.setup_topology.return_value = {"status": "ready"}
        mock_backend.verify_topology.return_value = {"verified": True, "invariants": {}}
        mock_backend.teardown_topology.return_value = {"status": "cleaned"}
        mock_gb.return_value = mock_backend

        # Test lab up with global flag
        res_up = runner.invoke(main, ["--backend", "container_linux", "lab", "up"])
        assert res_up.exit_code == 0
        assert mock_gb.call_args[0][0] == "container_linux"

        # Test lab verify with global flag
        res_ver = runner.invoke(main, ["--backend", "container_linux", "lab", "verify", "--json"])
        assert res_ver.exit_code == 0
        assert mock_gb.call_args[0][0] == "container_linux"

        # Test lab down with global flag
        res_down = runner.invoke(main, ["--backend", "container_linux", "lab", "down"])
        assert res_down.exit_code == 0
        assert mock_gb.call_args[0][0] == "container_linux"


@pytest.mark.unit
def test_cli_lab_vm_linux_choice():
    """Verify vm_linux is accepted by lab up, lab verify, and lab down."""
    runner = CliRunner()
    with patch("bll.platform.backends.get_backend") as mock_gb:
        mock_backend = MagicMock()
        mock_backend.setup_topology.return_value = {"status": "ready"}
        mock_backend.verify_topology.return_value = {"verified": True, "invariants": {}}
        mock_backend.teardown_topology.return_value = {"status": "cleaned"}
        mock_gb.return_value = mock_backend

        # Dry-run with vm_linux
        res = runner.invoke(main, ["--backend", "vm_linux", "lab", "up", "--dry-run"])
        assert res.exit_code == 0
        assert "[Dry Run]" in res.output

        # Verify with sub-command flag
        res2 = runner.invoke(main, ["lab", "verify", "--backend", "vm_linux", "--json"])
        assert res2.exit_code == 0
        assert mock_gb.call_args[0][0] == "vm_linux"

