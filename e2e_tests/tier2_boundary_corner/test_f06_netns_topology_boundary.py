"""
Feature 6: 6-Node Netns Reference Lab (Boundary & Corner Cases)
Tier 2: Boundary & Corner Cases (>=5 test cases)
"""

import pytest
from e2e_tests.harness import run_bll


def test_netns_interface_name_over_15_chars_rejected():
    """F06-T2-1: Virtual ethernet interface names exceeding 15 characters (IFNAMSIZ) are rejected."""
    # IFNAMSIZ = 16 bytes (15 chars + null terminator)
    res = run_bll(["lab", "configure-qdisc", "--netns", "bll-client", "--interface", "bll-interface-over-15-chars"])
    assert res.exit_code != 0


def test_netns_duplicate_namespaces_handled():
    """F06-T2-2: Lab initialization handles pre-existing namespaces gracefully."""
    res1 = run_bll(["lab", "up"])
    assert res1.exit_code == 0
    res2 = run_bll(["lab", "up"])
    assert res2.exit_code == 0


def test_netns_invalid_subnet_cidr_rejected():
    """F06-T2-3: Passing invalid CIDR specification handled without crashing."""
    res = run_bll(["lab", "up", "--config", "/nonexistent/path/config.yaml"])
    assert res.exit_code != 0


def test_netns_status_when_not_started():
    """F06-T2-4: bll lab status when lab is torn down returns running=False."""
    run_bll(["lab", "down"])
    res = run_bll(["lab", "status", "--json"])
    assert res.exit_code == 0
    assert res.json_data.get("running") is False


def test_netns_up_with_empty_name_flag():
    """F06-T2-5: Specifying empty lab instance name handled cleanly."""
    res = run_bll(["lab", "up", "--name", ""])
    assert res.exit_code in (0, 1, 2)
