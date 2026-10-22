"""
Feature 8: Decoupled Tc Shaping & Netem
Tier 1: Feature Coverage (>=5 test cases)
"""

import pytest
from e2e_tests.harness import run_bll


@pytest.fixture(autouse=True)
def ensure_lab_up():
    run_bll(["lab", "up"])


def test_tc_config_command_success():
    """F08-T1-1: bll lab configure-qdisc configures rate and queue discipline."""
    res = run_bll(["lab", "configure-qdisc", "--netns", "bll-qnear", "--interface", "bll-qn-rtr", "--rate", "20mbit", "--qdisc", "pfifo", "--json"])
    assert res.exit_code == 0
    assert res.json_data.get("status") == "ok"


def test_forwarder_egress_rate_shaping():
    """F08-T1-2: Forwarder egress rate shaping accepts bandwidth rate string."""
    res = run_bll(["lab", "configure-qdisc", "--netns", "bll-qfar", "--interface", "bll-qf-rem", "--rate", "50mbit", "--json"])
    assert res.exit_code == 0


def test_bufferbloat_queue_disciplines():
    """F08-T1-3: Supports pfifo, bfifo, fq_codel, and cake qdisc algorithms."""
    for qdisc in ["pfifo", "bfifo", "fq_codel", "cake"]:
        res = run_bll(["lab", "configure-qdisc", "--netns", "bll-qnear", "--interface", "bll-qn-rtr", "--rate", "100mbit", "--qdisc", qdisc, "--json"])
        assert res.exit_code == 0, f"Failed configuring qdisc {qdisc}: {res.stderr}"


def test_peer_interface_netem_delay():
    """F08-T1-4: Pure propagation delay (netem) can be applied to link peer interface."""
    res = run_bll(["lab", "configure-qdisc", "--netns", "bll-router", "--interface", "bll-rtr-qn", "--delay", "25ms", "--json"])
    assert res.exit_code == 0


def test_reset_qdiscs_restores_default():
    """F08-T1-5: bll lab reset-qdiscs clears custom shaping rules back to default."""
    res = run_bll(["lab", "reset-qdiscs", "--json"])
    assert res.exit_code == 0
    assert res.json_data.get("status") == "ok"
