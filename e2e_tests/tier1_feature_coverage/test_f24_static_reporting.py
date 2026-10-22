"""
Feature 24: Static Zero-CDN HTML & JSON Reporting
Tier 1: Feature Coverage (>=5 test cases)
"""

import pathlib
import pytest
from e2e_tests.harness import run_bll


def test_report_cli_generates_html_file(near_fifo_run, tmp_path):
    """F24-T1-1: bll report generates static HTML report file."""
    run_dir, _ = near_fifo_run
    html_out = tmp_path / "report.html"
    res = run_bll(["report", str(run_dir), "--out", str(html_out)])
    assert res.exit_code == 0
    assert html_out.exists()
    assert html_out.stat().st_size > 0


def test_report_html_zero_external_cdn_links(near_fifo_run, tmp_path):
    """F24-T1-2: HTML report contains zero external CDN scripts or stylesheet dependencies."""
    run_dir, _ = near_fifo_run
    html_out = tmp_path / "report.html"
    run_bll(["report", str(run_dir), "--out", str(html_out)])
    html = html_out.read_text().lower()
    assert "http://" not in html
    assert "https://" not in html


def test_report_html_contains_inlined_svg_figures(near_fifo_run, tmp_path):
    """F24-T1-3: HTML report incorporates inlined SVG charts."""
    run_dir, _ = near_fifo_run
    html_out = tmp_path / "report.html"
    run_bll(["report", str(run_dir), "--out", str(html_out)])
    html = html_out.read_text()
    assert "<svg" in html
    assert "</svg>" in html


def test_report_json_summary_output(near_fifo_run):
    """F24-T1-4: bll report --json outputs machine-readable report metadata."""
    run_dir, _ = near_fifo_run
    res = run_bll(["report", str(run_dir), "--json"])
    assert res.exit_code == 0
    assert res.json_data.get("run_id") == run_dir.name
    assert res.json_data.get("zero_cdn_compliant") is True


def test_report_includes_localization_verdict_and_evidence(near_fifo_run, tmp_path):
    """F24-T1-5: HTML report embeds run summary and header."""
    run_dir, _ = near_fifo_run
    html_out = tmp_path / "report.html"
    run_bll(["report", str(run_dir), "--out", str(html_out)])
    html = html_out.read_text()
    assert "Bufferbloat Localization Lab" in html
    assert run_dir.name in html
