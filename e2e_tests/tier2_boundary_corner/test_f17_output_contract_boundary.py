"""
Feature 17: Output Contract & JSON Schema v1 (Boundary & Corner Cases)
Tier 2: Boundary & Corner Cases (>=5 test cases)
"""

import pytest
from e2e_tests.harness import run_bll


def test_contract_empty_supported_regions(healthy_run):
    """F17-T2-1: Empty array [] is valid for supported_regions when no bottleneck is found."""
    run_dir, _ = healthy_run
    res = run_bll(["infer", str(run_dir), "--json"])
    assert res.exit_code == 0
    assert res.json_data["supported_regions"] == []


def test_contract_queue_evidence_lowercase(near_fifo_run):
    """F17-T2-2: queue_evidence string is strictly lowercase."""
    run_dir, _ = near_fifo_run
    res = run_bll(["infer", str(run_dir), "--json"])
    ev = res.json_data["queue_evidence"]
    assert ev == ev.lower()


def test_contract_load_association_limits(near_fifo_run):
    """F17-T2-3: load_association correlation is strictly bounded in [-1.0, 1.0]."""
    run_dir, _ = near_fifo_run
    res = run_bll(["infer", str(run_dir), "--json"])
    assoc = res.json_data["load_association"]
    assert -1.0 <= assoc <= 1.0


def test_contract_supporting_run_ids_list(near_fifo_run):
    """F17-T2-4: supporting_run_ids is a non-empty list of string run identifiers."""
    run_dir, _ = near_fifo_run
    res = run_bll(["infer", str(run_dir), "--json"])
    run_ids = res.json_data["supporting_run_ids"]
    assert isinstance(run_ids, list)
    assert len(run_ids) >= 1
    assert all(isinstance(rid, str) for rid in run_ids)


def test_contract_boolean_types_strictly_bool(healthy_run):
    """F17-T2-5: Boolean contract fields (latency_increase_observed, abstained) are strict booleans."""
    run_dir, _ = healthy_run
    res = run_bll(["infer", str(run_dir), "--json"])
    assert isinstance(res.json_data["latency_increase_observed"], bool)
    assert isinstance(res.json_data["abstained"], bool)
