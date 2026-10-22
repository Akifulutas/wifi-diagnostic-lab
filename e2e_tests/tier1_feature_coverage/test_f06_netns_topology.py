"""
Feature 6: 6-Node Netns Reference Lab
Tier 1: Feature Coverage (>=5 test cases)
"""

import pytest
from e2e_tests.harness import run_bll


def test_lab_up_creates_six_namespaces():
    """F06-T1-1: bll lab up deploys all 6 required network namespaces."""
    res = run_bll(["lab", "up", "--json"])
    assert res.exit_code == 0
    namespaces = res.json_data.get("namespaces", [])
    expected_nodes = ["bll-client", "bll-qnear", "bll-router", "bll-observer", "bll-qfar", "bll-remote"]
    for node in expected_nodes:
        assert node in namespaces, f"Namespace '{node}' missing from lab deployment"


def test_lab_subnets_addressing_plan():
    """F06-T1-2: 5 point-to-point links configured on /30 subnets."""
    res = run_bll(["lab", "up", "--json"])
    assert res.exit_code == 0
    subnets = res.json_data.get("subnets", [])
    expected_subnets = ["10.10.1.0/30", "10.10.2.0/30", "10.10.3.0/30", "10.10.4.0/30", "10.10.5.0/30"]
    for subnet in expected_subnets:
        assert subnet in subnets, f"Subnet '{subnet}' missing from lab configuration"


def test_lab_interface_naming_length():
    """F06-T1-3: All virtual ethernet interface names are <= 15 characters (IFNAMSIZ)."""
    res = run_bll(["lab", "up", "--json"])
    assert res.exit_code == 0
    interfaces = res.json_data.get("interfaces", [])
    for iface in interfaces:
        assert len(iface) <= 15, f"Interface name '{iface}' ({len(iface)} chars) exceeds Linux IFNAMSIZ limit of 15"


def test_lab_status_shows_all_namespaces():
    """F06-T1-4: bll lab status lists running namespaces."""
    run_bll(["lab", "up"])
    res = run_bll(["lab", "status", "--json"])
    assert res.exit_code == 0
    assert res.json_data.get("running") is True
    assert len(res.json_data.get("namespaces", [])) == 6


def test_lab_up_idempotent():
    """F06-T1-5: Repeated bll lab up execution succeeds idempotently."""
    res1 = run_bll(["lab", "up", "--json"])
    assert res1.exit_code == 0
    res2 = run_bll(["lab", "up", "--json"])
    assert res2.exit_code == 0
