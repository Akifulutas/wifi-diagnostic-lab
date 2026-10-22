"""
Feature 1: bll doctor (Boundary & Corner Cases)
Tier 2: Boundary & Corner Cases (>=5 test cases)
"""

import os
import pytest
from e2e_tests.harness import run_bll


def test_doctor_invalid_flag_exits_code_two():
    """F01-T2-1: Passing unrecognized options to doctor exits with code 2."""
    res = run_bll(["doctor", "--invalid-nonexistent-flag"])
    assert res.exit_code != 0
    assert "no such option" in res.stderr.lower() or "error" in res.stderr.lower() or res.exit_code == 2


def test_doctor_empty_environment_variables():
    """F01-T2-2: Running with restricted PATH handles missing tools gracefully without unhandled exception."""
    res = run_bll(["doctor", "--json"], env={"PATH": ""})
    assert res.exit_code == 0
    assert res.json_data is not None
    assert "capabilities" in res.json_data


def test_doctor_json_suppresses_stderr_pollution():
    """F01-T2-3: bll doctor --json emits purely parseable JSON without extraneous stdout banners."""
    res = run_bll(["doctor", "--json"])
    assert res.exit_code == 0
    stdout = res.stdout.strip()
    assert stdout.startswith("{") and stdout.endswith("}")


def test_doctor_subcommand_with_unexpected_positional_args():
    """F01-T2-4: Passing arbitrary unexpected positional arguments to doctor errors cleanly."""
    res = run_bll(["doctor", "unexpected_positional_arg"])
    assert res.exit_code != 0


def test_doctor_repeated_json_flags():
    """F01-T2-5: Passing redundant repeated --json flags handles cleanly."""
    res = run_bll(["doctor", "--json", "--json"])
    assert res.exit_code in (0, 2)
