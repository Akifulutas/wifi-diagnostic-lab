"""
Feature 18: Set-Valued Ambiguity & Abstention
Tier 1: Feature Coverage (>=5 test cases)
"""

import pytest
from e2e_tests.harness import run_bll


def test_abstention_when_single_vantage_ambiguous(near_fifo_run):
    """F18-T1-1: Under remote_only vantage, engine abstains due to near vs far ambiguity."""
    run_dir, _ = near_fifo_run
    res = run_bll(["infer", str(run_dir), "--vantage", "remote_only", "--json"])
    assert res.exit_code == 0
    assert res.json_data["abstained"] is True


def test_abstain_reason_explains_ambiguity(near_fifo_run):
    """F18-T1-2: When abstaining, abstain_reason provides explicit explanation."""
    run_dir, _ = near_fifo_run
    res = run_bll(["infer", str(run_dir), "--vantage", "remote_only", "--json"])
    assert res.exit_code == 0
    reason = res.json_data["abstain_reason"]
    assert isinstance(reason, str) and len(reason.strip()) > 10


def test_not_excluded_regions_preserves_candidate_set(near_fifo_run):
    """F18-T1-3: When abstaining, candidate regions are retained in not_excluded_regions."""
    run_dir, _ = near_fifo_run
    res = run_bll(["infer", str(run_dir), "--vantage", "remote_only", "--json"])
    not_ex = res.json_data["not_excluded_regions"]
    assert "near_link" in not_ex
    assert "far_link" in not_ex


def test_no_abstention_when_full_vantage_discriminates(near_fifo_run):
    """F18-T1-4: With full observer vantage, ambiguity is resolved and abstained is False."""
    run_dir, _ = near_fifo_run
    res = run_bll(["infer", str(run_dir), "--vantage", "full_observer", "--json"])
    assert res.exit_code == 0
    assert res.json_data["abstained"] is False
    assert res.json_data["abstain_reason"] is None


def test_abstention_on_quality_flag_failure(cpu_saturation_run):
    """F18-T1-5: Critical quality flag (CLIENT_CPU_SATURATION) forces localization abstention."""
    run_dir, _ = cpu_saturation_run
    res = run_bll(["infer", str(run_dir), "--json"])
    assert res.exit_code == 0
    assert res.json_data["abstained"] is True
    assert "CLIENT_CPU_SATURATION" in res.json_data["abstain_reason"]
