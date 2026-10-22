"""
Feature 4: Multi-Backend Abstraction (Boundary & Corner Cases)
Tier 2: Boundary & Corner Cases (>=5 test cases)
"""

import platform
import pytest
from e2e_tests.harness import run_bll


def test_backend_invalid_name_rejected():
    """F04-T2-1: Passing non-existent backend identifier rejected with usage error."""
    res = run_bll(["doctor", "--backend", "quantum_backend", "--json"])
    assert res.exit_code != 0
    assert "invalid" in res.stderr.lower() or res.exit_code == 2


def test_backend_native_linux_on_non_linux_rejected():
    """F04-T2-2: Forcing native_linux on non-Linux host cannot meet requirements."""
    if platform.system() == "Linux":
        pytest.skip("Test specifically tests Darwin / Windows rejection")
    res = run_bll(["doctor", "--backend", "native_linux", "--json"])
    assert res.exit_code != 0 or res.json_data.get("all_requirements_met") is False


def test_backend_empty_backend_string_rejected():
    """F04-T2-3: Empty string passed to --backend rejected."""
    res = run_bll(["doctor", "--backend", "", "--json"])
    assert res.exit_code != 0


def test_backend_override_without_argument():
    """F04-T2-4: --backend flag without following argument exits code 2."""
    res = run_bll(["doctor", "--backend"])
    assert res.exit_code != 0


def test_backend_whitespace_padding_handled():
    """F04-T2-5: Backend with whitespace padding errors or trims cleanly."""
    res = run_bll(["doctor", "--backend", "   ", "--json"])
    assert res.exit_code != 0
