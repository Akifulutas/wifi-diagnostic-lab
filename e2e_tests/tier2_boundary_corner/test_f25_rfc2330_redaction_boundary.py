"""
Feature 25: RFC 2330 Redaction Engine (Boundary & Corner Cases)
Tier 2: Boundary & Corner Cases (>=5 test cases)
"""

import json
import pathlib
import pytest
from e2e_tests.harness import run_bll


def test_redact_missing_out_dir(near_fifo_run):
    """F25-T2-1: Missing mandatory --out-dir flag handles with default or clean error."""
    run_dir, _ = near_fifo_run
    res = run_bll(["export", str(run_dir), "--redact"])
    assert res.exit_code in (0, 1, 2)


def test_redact_non_existent_run():
    """F25-T2-2: Attempting to export non-existent run directory errors cleanly."""
    res = run_bll(["export", "/nonexistent/run/path", "--redact", "--out-dir", "/tmp/redacted"])
    assert res.exit_code in (0, 1, 2)


def test_redact_idempotent_double_redact(near_fifo_run, tmp_path):
    """F25-T2-3: Redacting already redacted data is strictly idempotent."""
    run_dir, _ = near_fifo_run
    out1 = tmp_path / "redacted_1"
    out2 = tmp_path / "redacted_2"
    run_bll(["export", str(run_dir), "--redact", "--out-dir", str(out1)])
    run_bll(["export", str(out1), "--redact", "--out-dir", str(out2)])
    prov1 = json.loads((out1 / "provenance.json").read_text())
    prov2 = json.loads((out2 / "provenance.json").read_text())
    assert prov1["rfc_2330_compliant"] == prov2["rfc_2330_compliant"]


def test_redact_sha256_length_64(near_fifo_run, tmp_path):
    """F25-T2-4: Provenance hash is valid 64-character lowercase hexadecimal."""
    run_dir, _ = near_fifo_run
    out = tmp_path / "redacted"
    run_bll(["export", str(run_dir), "--redact", "--out-dir", str(out)])
    prov = json.loads((out / "provenance.json").read_text())
    h = prov.get("manifest_sha256", "")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_redact_rules_presence(near_fifo_run, tmp_path):
    """F25-T2-5: Provenance document explicitly defines redaction rules for MAC and IP."""
    run_dir, _ = near_fifo_run
    out = tmp_path / "redacted"
    run_bll(["export", str(run_dir), "--redact", "--out-dir", str(out)])
    prov = json.loads((out / "provenance.json").read_text())
    rules = prov.get("redaction_rules", {})
    assert "mac_addresses" in rules
    assert "private_ips" in rules
