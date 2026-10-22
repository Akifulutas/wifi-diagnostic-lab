"""
Feature 24: Static Zero-CDN HTML & JSON Reporting (Boundary & Corner Cases)
Tier 2: Boundary & Corner Cases (>=5 test cases)
"""

import pathlib
import pytest
from e2e_tests.harness import run_bll


def test_report_missing_run_dir():
    """F24-T2-1: Missing run directory parameter fails cleanly with usage error."""
    res = run_bll(["report"])
    assert res.exit_code != 0


def test_report_nonexistent_run_dir():
    """F24-T2-2: Providing non-existent run directory path errors cleanly."""
    res = run_bll(["report", "/path/to/nonexistent/run"])
    assert res.exit_code != 0


def test_report_overwrite_existing_html(near_fifo_run, tmp_path):
    """F24-T2-3: Overwriting an existing report file succeeds without prompt."""
    run_dir, _ = near_fifo_run
    html_out = tmp_path / "report.html"
    html_out.write_text("old content")
    res = run_bll(["report", str(run_dir), "--out", str(html_out)])
    assert res.exit_code == 0
    assert "old content" not in html_out.read_text()


def test_report_zero_cdn_no_external_resources(near_fifo_run, tmp_path):
    """F24-T2-4: Scans entire generated HTML to verify zero external web fonts or CDN resources."""
    run_dir, _ = near_fifo_run
    html_out = tmp_path / "report.html"
    run_bll(["report", str(run_dir), "--out", str(html_out)])
    content = html_out.read_text().lower()
    forbidden = ["fonts.googleapis.com", "cdnjs.cloudflare.com", "cdn.jsdelivr.net", "unpkg.com"]
    for cdn in forbidden:
        assert cdn not in content, f"Forbidden external CDN dependency '{cdn}' found in HTML report"


def test_report_nested_output_directory(near_fifo_run, tmp_path):
    """F24-T2-5: Generating report to nested non-existent directory creates directory."""
    run_dir, _ = near_fifo_run
    deep_out = tmp_path / "a" / "b" / "c" / "report.html"
    res = run_bll(["report", str(run_dir), "--out", str(deep_out)])
    assert res.exit_code == 0
    assert deep_out.exists()
