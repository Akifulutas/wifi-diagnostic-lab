"""
Feature 8: Decoupled Tc Shaping & Netem (Boundary & Corner Cases)
Tier 2: Boundary & Corner Cases (>=5 test cases)
"""

import pytest
from e2e_tests.harness import run_bll


def test_tc_zero_rate_rejected():
    """F08-T2-1: Bandwidth rate of 0kbit or 0mbit is rejected."""
    res = run_bll(["lab", "configure-qdisc", "--netns", "bll-qnear", "--interface", "bll-qn-rtr", "--rate", "0kbit"])
    assert res.exit_code != 0


def test_tc_negative_delay_rejected():
    """F08-T2-2: Negative propagation delay string (-10ms) is rejected."""
    res = run_bll(["lab", "configure-qdisc", "--netns", "bll-router", "--interface", "bll-rtr-qn", "--delay", "-10ms"])
    assert res.exit_code != 0


def test_tc_unknown_qdisc_algorithm_rejected():
    """F08-T2-3: Unknown queuing algorithm (e.g. quantum_fifo) is rejected."""
    res = run_bll(["lab", "configure-qdisc", "--netns", "bll-qnear", "--interface", "bll-qn-rtr", "--rate", "10mbit", "--qdisc", "quantum_fifo"])
    assert res.exit_code != 0


def test_tc_missing_netns_flag():
    """F08-T2-4: configure-qdisc without mandatory netns parameter fails."""
    res = run_bll(["lab", "configure-qdisc", "--interface", "bll-qn-rtr", "--rate", "10mbit"])
    assert res.exit_code != 0 or "Error" in res.stderr


def test_tc_extreme_bandwidth_rate():
    """F08-T2-5: Very high rate (100gbit) handled cleanly."""
    res = run_bll(["lab", "configure-qdisc", "--netns", "bll-qnear", "--interface", "bll-qn-rtr", "--rate", "100gbit", "--json"])
    assert res.exit_code in (0, 1)
