"""
Feature 17: Output Contract & JSON Schema v1
Tier 1: Feature Coverage (>=5 test cases)
"""

import pytest
from e2e_tests.harness import run_bll


def test_infer_cli_outputs_valid_json(near_fifo_run):
    """F17-T1-1: bll infer --json outputs valid, parseable JSON."""
    run_dir, _ = near_fifo_run
    res = run_bll(["infer", str(run_dir), "--json"])
    assert res.exit_code == 0
    assert res.json_data is not None


def test_infer_output_contains_all_contract_fields(near_fifo_run):
    """F17-T1-2: Output strictly includes all 11 fields required by InferenceOutputContract."""
    run_dir, _ = near_fifo_run
    res = run_bll(["infer", str(run_dir), "--json"])
    data = res.json_data
    required_fields = [
        "run_id",
        "vantage_profile",
        "latency_increase_observed",
        "load_association",
        "supported_regions",
        "not_excluded_regions",
        "queue_evidence",
        "quality_flags",
        "abstained",
        "abstain_reason",
        "next_measurement",
    ]
    for field in required_fields:
        assert field in data, f"Required contract field '{field}' missing from inference output"


def test_infer_queue_evidence_enum_values(near_fifo_run):
    """F17-T1-3: queue_evidence is strictly one of: none, weak, moderate, strong."""
    run_dir, _ = near_fifo_run
    res = run_bll(["infer", str(run_dir), "--json"])
    evidence = res.json_data["queue_evidence"]
    assert evidence in ("none", "weak", "moderate", "strong")


def test_infer_supported_regions_is_subset_of_five(near_fifo_run):
    """F17-T1-4: supported_regions contains only valid physical topology regions."""
    run_dir, _ = near_fifo_run
    res = run_bll(["infer", str(run_dir), "--json"])
    valid_regions = {"local_host", "near_link", "gateway_node", "far_link", "remote_host"}
    for reg in res.json_data["supported_regions"]:
        assert reg in valid_regions, f"Invalid region '{reg}' found in supported_regions"


def test_infer_load_association_in_range(near_fifo_run):
    """F17-T1-5: load_association correlation is a bounded float in [-1.0, 1.0]."""
    run_dir, _ = near_fifo_run
    res = run_bll(["infer", str(run_dir), "--json"])
    corr = res.json_data["load_association"]
    assert isinstance(corr, (int, float))
    assert -1.0 <= corr <= 1.0, f"Correlation {corr} out of bounds [-1.0, 1.0]"
