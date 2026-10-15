"""Unit tests for dataset redactor and pseudonymization."""

import json
import tempfile
import unittest
from pathlib import Path
from wifi_lab.redactor import redact_dataset, redact_text


class TestRedactor(unittest.TestCase):
    def test_redact_text(self):
        text = "Client b2:43:69:80:5c:06 connected to 192.168.178.50 at gateway 192.168.178.1"
        ip_map = {}
        mac_map = {}
        redacted, mac_c, ip_c = redact_text(text, ip_map, mac_map)

        self.assertEqual(mac_c, 1)
        self.assertEqual(ip_c, 2)
        self.assertNotIn("b2:43:69:80:5c:06", redacted)
        self.assertNotIn("192.168.178.50", redacted)
        self.assertIn("02:00:00:00:00:01", redacted)
        self.assertIn("10.0.0.1", redacted)

    def test_redact_dataset_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            in_dir = tmp_path / "raw"
            run_dir = in_dir / "test_run"
            run_dir.mkdir(parents=True)
            (run_dir / "ping.txt").write_text("PING 192.168.1.100 (192.168.1.100): 56 bytes", encoding="utf-8")

            out_dir = tmp_path / "redacted"
            ret = redact_dataset(in_dir, out_dir)
            self.assertEqual(ret, 0)
            self.assertTrue((out_dir / "redaction_manifest.json").is_file())
            manifest = json.loads((out_dir / "redaction_manifest.json").read_text(encoding="utf-8"))
            self.assertTrue(manifest["redaction_applied"])
            self.assertEqual(manifest["total_files_sanitized"], 1)


if __name__ == "__main__":
    unittest.main()
