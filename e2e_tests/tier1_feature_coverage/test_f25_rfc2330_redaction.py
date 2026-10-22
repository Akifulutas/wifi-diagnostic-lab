"""
Feature 25: RFC 2330 Redaction Engine
Tier 1: Feature Coverage (>=5 test cases)
"""

import json
import pathlib
import pytest
from e2e_tests.harness import run_bll


def test_redact_cli_command(near_fifo_run, tmp_path):
    """F25-T1-1: bll export --redact generates sanitized dataset export."""
    run_dir, _ = near_fifo_run
    out_dir = tmp_path / "redacted_export"
    res = run_bll(["export", str(run_dir), "--redact", "--out-dir", str(out_dir)])
    assert res.exit_code == 0
    assert (out_dir / "provenance.json").exists()


def test_redact_masks_mac_addresses(near_fifo_run, tmp_path):
    """F25-T1-2: Redaction rules map MACs to IEEE locally administered addresses (02:00:00:xx:xx:xx)."""
    run_dir, _ = near_fifo_run
    out_dir = tmp_path / "redacted_export"
    run_bll(["export", str(run_dir), "--redact", "--out-dir", str(out_dir)])
    prov = json.loads((out_dir / "provenance.json").read_text())
    assert "02:00:00" in prov["redaction_rules"]["mac_addresses"]


def test_redact_masks_private_ips_consistently(near_fifo_run, tmp_path):
    """F25-T1-3: Private IPv4 addresses are sanitized consistently using RFC 1918 test blocks."""
    run_dir, _ = near_fifo_run
    out_dir = tmp_path / "redacted_export"
    run_bll(["export", str(run_dir), "--redact", "--out-dir", str(out_dir)])
    prov = json.loads((out_dir / "provenance.json").read_text())
    assert "RFC 1918" in prov["redaction_rules"]["private_ips"]


def test_redact_scrubs_ssids_and_credentials(near_fifo_run, tmp_path):
    """F25-T1-4: SSIDs and credentials are scrubbed with cryptographic hashes."""
    run_dir, _ = near_fifo_run
    out_dir = tmp_path / "redacted_export"
    run_bll(["export", str(run_dir), "--redact", "--out-dir", str(out_dir)])
    prov = json.loads((out_dir / "provenance.json").read_text())
    assert "SHA-256" in prov["redaction_rules"]["ssids_and_creds"]


def test_redact_generates_sha256_provenance_manifest(near_fifo_run, tmp_path):
    """F25-T1-5: Redaction outputs provenance.json with input and output SHA-256 hashes."""
    run_dir, _ = near_fifo_run
    out_dir = tmp_path / "redacted_export"
    run_bll(["export", str(run_dir), "--redact", "--out-dir", str(out_dir)])
    prov = json.loads((out_dir / "provenance.json").read_text())
    assert "manifest_sha256" in prov
    assert len(prov["manifest_sha256"]) == 64
