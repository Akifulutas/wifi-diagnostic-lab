"""Parser for iperf3 JSON outputs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class IperfResult:
    protocol: str
    direction: str  # "upload" or "download"
    receiver_bps: float
    receiver_mbps: float
    sender_bps: float
    sender_mbps: float
    duration_s: float
    retransmits: Optional[int] = None
    streams: int = 1
    raw_error: Optional[str] = None


def parse_iperf_json(raw_text: str, expected_direction: Optional[str] = None) -> IperfResult:
    """Parses iperf3 -J JSON output into structured IperfResult with decimal Mbps conversion.

    1 Mbps = 1,000,000 bits/second.
    Handles both normal (upload) and reverse (download) iperf3 modes.
    """
    if not raw_text or not raw_text.strip():
        raise ValueError("iperf output is empty")

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid iperf3 JSON format: {e}")

    # Check for top-level tool error
    if "error" in data:
        raise RuntimeError(f"iperf3 reported error: {data['error']}")

    start = data.get("start", {})
    end = data.get("end", {})

    test_start = start.get("test_start", {})
    protocol = test_start.get("protocol", "TCP")
    if protocol.upper() != "TCP":
        raise ValueError(f"Unsupported protocol {protocol}; expected TCP")

    reverse = bool(test_start.get("reverse", 0))
    detected_direction = "download" if reverse else "upload"
    if expected_direction and detected_direction != expected_direction.lower():
        raise ValueError(
            f"Direction mismatch: config requested '{expected_direction}', but iperf JSON reverse flag is {reverse} ({detected_direction})"
        )

    # In iperf3 JSON:
    # 'sum_sent' represents the sender side, 'sum_received' represents the receiver side.
    sum_sent = end.get("sum_sent")
    sum_received = end.get("sum_received")

    if not sum_received:
        # Fallback to streams if aggregate sum_received is missing
        streams = end.get("streams", [])
        if streams and "receiver" in streams[0]:
            sum_received = streams[0]["receiver"]

    if not sum_received or "bits_per_second" not in sum_received:
        raise ValueError("Missing receiver throughput data in iperf3 JSON")

    receiver_bps = float(sum_received["bits_per_second"])
    receiver_mbps = receiver_bps / 1_000_000.0

    sender_bps = float(sum_sent.get("bits_per_second", receiver_bps)) if sum_sent else receiver_bps
    sender_mbps = sender_bps / 1_000_000.0

    duration_s = float(sum_received.get("seconds", 0.0))
    retransmits = sum_sent.get("retransmits") if sum_sent else None
    stream_count = len(end.get("streams", [1]))

    return IperfResult(
        protocol=protocol,
        direction=detected_direction,
        receiver_bps=receiver_bps,
        receiver_mbps=round(receiver_mbps, 3),
        sender_bps=sender_bps,
        sender_mbps=round(sender_mbps, 3),
        duration_s=round(duration_s, 2),
        retransmits=retransmits,
        streams=stream_count,
    )
