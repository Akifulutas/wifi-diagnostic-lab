"""Unit tests for iperf3 and macOS ping parsers."""

import unittest
from wifi_lab.parsers.iperf import parse_iperf_json
from wifi_lab.parsers.ping_macos import parse_macos_ping
from wifi_lab.models import Phase


MOCK_IPERF_UPLOAD_JSON = """{
  "start": {
    "test_start": {
      "protocol": "TCP",
      "num_streams": 1,
      "reverse": 0
    }
  },
  "end": {
    "streams": [
      {
        "sender": {
          "bits_per_second": 752341200.0,
          "retransmits": 12
        },
        "receiver": {
          "bits_per_second": 748120000.0,
          "seconds": 60.02
        }
      }
    ],
    "sum_sent": {
      "bits_per_second": 752341200.0,
      "retransmits": 12
    },
    "sum_received": {
      "bits_per_second": 748120000.0,
      "seconds": 60.02
    }
  }
}"""

MOCK_IPERF_DOWNLOAD_JSON = """{
  "start": {
    "test_start": {
      "protocol": "TCP",
      "num_streams": 1,
      "reverse": 1
    }
  },
  "end": {
    "sum_sent": {
      "bits_per_second": 820150000.0,
      "retransmits": 3
    },
    "sum_received": {
      "bits_per_second": 815900000.0,
      "seconds": 60.01
    }
  }
}"""

MOCK_PING_OUTPUT = """PING 192.168.178.50 (192.168.178.50): 56 data bytes
64 bytes from 192.168.178.50: icmp_seq=0 ttl=64 time=2.451 ms
64 bytes from 192.168.178.50: icmp_seq=1 ttl=64 time=2.810 ms
Request timeout for icmp_seq 2
64 bytes from 192.168.178.50: icmp_seq=3 ttl=64 time=35.120 ms
64 bytes from 192.168.178.50: icmp_seq=4 ttl=64 time=42.600 ms

--- 192.168.178.50 ping statistics ---
5 packets transmitted, 4 packets received, 20.0% packet loss
round-trip min/avg/max/stddev = 2.451/20.745/42.600/17.920 ms
"""


MOCK_IPERF_UDP_JSON = """{
  "start": {
    "test_start": {
      "protocol": "UDP",
      "num_streams": 1,
      "reverse": 0
    }
  },
  "end": {
    "sum": {
      "bits_per_second": 150000000.0,
      "seconds": 10.0,
      "jitter_ms": 1.245,
      "lost_packets": 15,
      "packets": 12500,
      "lost_percent": 0.12
    }
  }
}"""


class TestParsers(unittest.TestCase):
    def test_parse_iperf_udp(self):
        res = parse_iperf_json(MOCK_IPERF_UDP_JSON, expected_direction="upload")
        self.assertEqual(res.protocol, "UDP")
        self.assertAlmostEqual(res.receiver_mbps, 150.0)
        self.assertAlmostEqual(res.jitter_ms, 1.245)
        self.assertEqual(res.lost_packets, 15)
        self.assertEqual(res.total_packets, 12500)
        self.assertAlmostEqual(res.loss_percent, 0.12)
    def test_parse_iperf_upload(self):
        res = parse_iperf_json(MOCK_IPERF_UPLOAD_JSON, expected_direction="upload")
        self.assertEqual(res.protocol, "TCP")
        self.assertEqual(res.direction, "upload")
        self.assertAlmostEqual(res.receiver_mbps, 748.12, places=2)
        self.assertAlmostEqual(res.sender_mbps, 752.34, places=2)
        self.assertEqual(res.retransmits, 12)
        self.assertAlmostEqual(res.duration_s, 60.02)

    def test_parse_iperf_download(self):
        res = parse_iperf_json(MOCK_IPERF_DOWNLOAD_JSON, expected_direction="download")
        self.assertEqual(res.direction, "download")
        self.assertAlmostEqual(res.receiver_mbps, 815.90, places=2)

    def test_parse_iperf_direction_mismatch(self):
        with self.assertRaises(ValueError):
            parse_iperf_json(MOCK_IPERF_UPLOAD_JSON, expected_direction="download")

    def test_parse_iperf_error_handling(self):
        with self.assertRaises(ValueError):
            parse_iperf_json("{invalid json")

        with self.assertRaises(RuntimeError):
            parse_iperf_json('{"error": "unable to connect to server"}')

    def test_parse_macos_ping(self):
        summary = parse_macos_ping(
            MOCK_PING_OUTPUT,
            run_id="test_run",
            idle_s=0.4,    # seq 0, 1 are idle (rel time 0.0, 0.2)
            warmup_s=0.2,  # seq 2 is warmup (rel time 0.4)
            load_s=0.4,    # seq 3, 4 are load (rel time 0.6, 0.8)
            recovery_s=0.4,
            nominal_interval_s=0.2,
        )
        self.assertEqual(summary.transmitted, 5)
        self.assertEqual(summary.received, 4)
        self.assertAlmostEqual(summary.loss_rate_pct, 20.0)
        self.assertAlmostEqual(summary.min_ms, 2.451)
        self.assertAlmostEqual(summary.max_ms, 42.600)

        # Inspect individual samples
        samples = summary.samples
        self.assertEqual(len(samples), 5)

        # seq 0: idle
        self.assertEqual(samples[0].seq, 0)
        self.assertEqual(samples[0].phase, Phase.IDLE)
        self.assertAlmostEqual(samples[0].rtt_ms, 2.451)

        # seq 2: timeout (null rtt)
        self.assertEqual(samples[2].seq, 2)
        self.assertIsNone(samples[2].rtt_ms)


if __name__ == "__main__":
    unittest.main()
