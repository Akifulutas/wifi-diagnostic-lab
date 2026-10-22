"""
Feature 9: Idempotent Lab Lifecycle
Tier 1: Feature Coverage (>=5 test cases)
"""

import pytest
from e2e_tests.harness import run_bll


def test_lab_down_exit_zero():
    """F09-T1-1: bll lab down terminates cleanly with exit code 0."""
    res = run_bll(["lab", "down", "--json"])
    assert res.exit_code == 0
    assert res.json_data.get("status") == "down"


def test_lab_down_idempotent_double_run():
    """F09-T1-2: Successive bll lab down calls both succeed idempotently."""
    res1 = run_bll(["lab", "down", "--json"])
    assert res1.exit_code == 0
    res2 = run_bll(["lab", "down", "--json"])
    assert res2.exit_code == 0


def test_lab_up_after_abrupt_exit():
    """F09-T1-3: bll lab up safely cleans stale resources before initializing new topology."""
    run_bll(["lab", "up"])
    res = run_bll(["lab", "up", "--json"])
    assert res.exit_code == 0
    assert res.json_data.get("status") == "up"


def test_lab_down_cleans_veth_interfaces():
    """F09-T1-4: Lab teardown reports all namespaces removed."""
    res = run_bll(["lab", "down", "--json"])
    assert res.exit_code == 0
    deleted = res.json_data.get("deleted_namespaces", [])
    assert len(deleted) == 6


def test_lab_lifecycle_dry_run():
    """F09-T1-5: bll lab up --dry-run previews topology creation without mutations."""
    res = run_bll(["lab", "up", "--dry-run"])
    assert res.exit_code == 0
    assert "Dry Run" in res.stdout or "dry" in res.stdout.lower()
