"""Unit tests for analysis pipeline and diagnostic engine."""

import csv
import tempfile
import unittest
from pathlib import Path
from wifi_lab.diagnostics import analyze_performance_patterns
from wifi_lab.plots import generate_all_figures


class TestAnalysisAndDiagnostics(unittest.TestCase):
    def test_diagnostic_findings(self):
        sample_rows = [
            {
                "run_id": "L1_download_rep1",
                "position_id": "L1",
                "direction": "download",
                "outcome": "ok",
                "receiver_throughput_mbps": "810.5",
                "delta_rtt_median_ms": "29.2",
                "tcp_retransmits": "10",
                "failure_reason": "",
            },
            {
                "run_id": "L2_download_rep1",
                "position_id": "L2",
                "direction": "download",
                "outcome": "ok",
                "receiver_throughput_mbps": "480.0",
                "delta_rtt_median_ms": "76.4",
                "tcp_retransmits": "65",
                "failure_reason": "",
            },
            {
                "run_id": "L2_upload_rep3",
                "position_id": "L2",
                "direction": "upload",
                "outcome": "tool_error",
                "receiver_throughput_mbps": "",
                "delta_rtt_median_ms": "",
                "tcp_retransmits": "",
                "failure_reason": "Simulated timeout",
            },
        ]
        findings = analyze_performance_patterns(sample_rows)
        self.assertGreaterEqual(len(findings), 3)

        categories = [f.category for f in findings]
        self.assertTrue(any("Plateau" in c for c in categories))
        self.assertTrue(any("Bufferbloat" in c for c in categories))
        self.assertTrue(any("Failure" in c for c in categories))


if __name__ == "__main__":
    unittest.main()
