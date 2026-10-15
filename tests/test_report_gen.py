"""Unit tests for HTML dashboard generator."""

import tempfile
import unittest
from pathlib import Path
from wifi_lab.report_gen import generate_html_report


class TestReportGen(unittest.TestCase):
    def test_generate_html_report(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            summary_csv = tmp_path / "run_summary.csv"
            summary_csv.write_text(
                "run_id,day_label,position_id,direction,repetition,outcome,receiver_throughput_mbps,sender_throughput_mbps,tcp_retransmits,idle_rtt_median_ms,idle_rtt_p95_ms,loaded_rtt_median_ms,loaded_rtt_p95_ms,recovery_rtt_median_ms,delta_rtt_median_ms,sent_probes,received_probes,loss_rate_pct,failure_reason\n"
                "L1_dl_1,day1,L1,download,1,ok,810.5,815.2,10,2.4,3.2,31.5,52.1,2.5,29.1,615,611,0.6,\n",
                encoding="utf-8"
            )
            figures_dir = tmp_path / "figures"
            figures_dir.mkdir()
            (figures_dir / "fig1_throughput_by_condition.svg").write_text("<svg></svg>", encoding="utf-8")
            (figures_dir / "fig2_rtt_ecdf.svg").write_text("<svg></svg>", encoding="utf-8")
            (figures_dir / "fig3_rtt_timeseries.svg").write_text("<svg></svg>", encoding="utf-8")
            (figures_dir / "fig4_loaded_delta_rtt.svg").write_text("<svg></svg>", encoding="utf-8")

            out_html = tmp_path / "report.html"
            ret = generate_html_report(summary_csv, figures_dir, out_html)
            self.assertEqual(ret, 0)
            self.assertTrue(out_html.is_file())
            content = out_html.read_text(encoding="utf-8")
            self.assertIn("Wi-Fi Diagnostic Lab", content)
            self.assertIn("810.5", content)


if __name__ == "__main__":
    unittest.main()
