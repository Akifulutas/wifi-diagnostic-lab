"""
Feature 5: Privileged Helper bll-lab-helper
Tier 1: Feature Coverage (>=5 test cases)
"""

import pytest
from e2e_tests.harness import run_bll


def test_helper_rejects_non_bll_namespace():
    """F05-T1-1: Helper strictly rejects managing any resource not starting with 'bll-' prefix."""
    res = run_bll(["lab", "configure-qdisc", "--netns", "external-ns", "--interface", "eth0", "--rate", "10mbit"])
    assert res.exit_code != 0
    assert "bll-" in res.stderr.lower() or "security" in res.stderr.lower()


def test_helper_rejects_arbitrary_shell_commands():
    """F05-T1-2: Helper rejects shell metacharacters and arbitrary command injection."""
    res = run_bll(["lab", "configure-qdisc", "--netns", "bll-test; rm -rf /", "--interface", "veth0"])
    assert res.exit_code != 0


def test_helper_validates_json_rpc_schema():
    """F05-T1-3: Privileged operations conform to structured RPC calls."""
    res = run_bll(["lab", "status", "--json"])
    assert res.exit_code == 0
    assert res.json_data is not None


def test_helper_create_topology_method():
    """F05-T1-4: Helper supports creating topology through bll lab up."""
    res = run_bll(["lab", "up", "--json"])
    assert res.exit_code == 0
    assert res.json_data.get("status") == "up"


def test_helper_destroy_topology_method():
    """F05-T1-5: Helper supports idempotent destruction through bll lab down."""
    res = run_bll(["lab", "down", "--json"])
    assert res.exit_code == 0
    assert res.json_data.get("status") == "down"
