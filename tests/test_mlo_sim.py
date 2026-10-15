"""Unit tests for Wi-Fi 7 Multi-Link Operation (MLO) simulation."""

import tempfile
import unittest
from pathlib import Path
from wifi_lab.mlo_sim import run_mlo_simulation


class TestMLOSim(unittest.TestCase):
    def test_mlo_simulation_metrics(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fig_path = Path(tmpdir) / "mlo_test.svg"
            res = run_mlo_simulation(packet_count=500, seed=123, output_figure=fig_path)

            self.assertEqual(res.total_packets, 500)
            self.assertGreater(res.single_link_p95_ms, res.mlo_p95_ms)
            self.assertGreater(res.p95_reduction_pct, 50.0)
            self.assertTrue(fig_path.is_file())
            content = fig_path.read_text(encoding="utf-8")
            self.assertIn("<svg", content)
            self.assertIn("Multi-Link Operation", content)


if __name__ == "__main__":
    unittest.main()
