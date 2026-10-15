"""Unit tests for data models, manifests, and serialization."""

import json
import unittest
from wifi_lab.models import (
    ConditionConfig,
    Direction,
    HardwareProfile,
    Outcome,
    Phase,
    RunManifest,
    RunSummaryRow,
)


class TestModels(unittest.TestCase):
    def test_run_manifest_serialization(self):
        cond = ConditionConfig(
            position_id="L1",
            position_description="1m LOS",
            direction=Direction.DOWNLOAD,
        )
        manifest = RunManifest(
            run_id="L1_download_rep1_20261015",
            timestamp_utc="2026-10-15T10:00:00Z",
            repetition_index=1,
            condition=cond,
            hardware=HardwareProfile(),
            outcome=Outcome.OK,
            raw_files={"iperf": "iperf_raw.json", "ping": "ping_raw.txt"},
        )
        json_str = manifest.to_json()
        parsed = json.loads(json_str)

        self.assertEqual(parsed["run_id"], "L1_download_rep1_20261015")
        self.assertEqual(parsed["outcome"], "ok")
        self.assertEqual(parsed["condition"]["direction"], "download")

        # Test deserialization
        restored = RunManifest.from_dict(parsed)
        self.assertEqual(restored.run_id, manifest.run_id)
        self.assertEqual(restored.condition.direction, Direction.DOWNLOAD)
        self.assertEqual(restored.outcome, Outcome.OK)

    def test_run_summary_row_fields(self):
        row = RunSummaryRow(
            run_id="test_run_01",
            day_label="day1",
            position_id="L1",
            direction="upload",
            repetition=1,
            outcome="ok",
            receiver_throughput_mbps=750.5,
            idle_rtt_median_ms=3.2,
            loaded_rtt_median_ms=45.8,
            delta_rtt_median_ms=42.6,
        )
        self.assertAlmostEqual(row.delta_rtt_median_ms, 42.6)
        self.assertEqual(row.receiver_throughput_mbps, 750.5)


if __name__ == "__main__":
    unittest.main()
