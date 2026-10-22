"""
Feature 5: Privileged Helper bll-lab-helper (Boundary & Corner Cases)
Tier 2: Boundary & Corner Cases (>=5 test cases)
"""

import pytest
from e2e_tests.harness import run_bll


def test_helper_command_injection_semicolon_rejected():
    """F05-T2-1: Semicolon command separator in resource parameter strictly rejected."""
    res = run_bll(["lab", "configure-qdisc", "--netns", "bll-node; shutdown -h now", "--interface", "veth0"])
    assert res.exit_code != 0
    assert "security" in res.stderr.lower() or res.exit_code in (1, 2)


def test_helper_pipe_injection_rejected():
    """F05-T2-2: Pipe metacharacter in parameter rejected."""
    res = run_bll(["lab", "configure-qdisc", "--netns", "bll-node|cat /etc/shadow", "--interface", "veth0"])
    assert res.exit_code != 0


def test_helper_path_traversal_in_netns_rejected():
    """F05-T2-3: Directory traversal attempt (../../) in namespace name rejected."""
    res = run_bll(["lab", "configure-qdisc", "--netns", "bll-../../etc", "--interface", "veth0"])
    assert res.exit_code != 0


def test_helper_subshell_dollar_injection_rejected():
    """F05-T2-4: Subshell execution syntax $(id) rejected."""
    res = run_bll(["lab", "configure-qdisc", "--netns", "bll-$(whoami)", "--interface", "veth0"])
    assert res.exit_code != 0


def test_helper_oversized_string_rejected():
    """F05-T2-5: Abnormally long argument (10,000 chars) handled cleanly or rejected."""
    long_str = "bll-" + "a" * 10000
    res = run_bll(["lab", "configure-qdisc", "--netns", long_str, "--interface", "veth0"])
    assert res.exit_code != 0
