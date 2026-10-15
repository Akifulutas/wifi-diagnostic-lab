"""Mock experiment generator modeling FRITZ!Box 7530 AX and M1 Pro Wi-Fi 6 characteristics.

Enables reproducible testing, parser validation, and offline analysis when traveling
or before physical testbed access is available.
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Tuple

from wifi_lab.models import ConditionConfig, Direction, HardwareProfile, Outcome, RunManifest


def generate_mock_run(
    run_id: str,
    condition: ConditionConfig,
    repetition_index: int,
    day_label: str = "day1",
    seed: int = 42,
    simulate_failure: bool = False,
) -> Tuple[str, str, RunManifest]:
    """Generates realistic iperf3 JSON and macOS ping output matching 802.11ax 80MHz channel conditions."""
    rng = random.Random(seed + repetition_index * 100 + (1 if condition.direction == Direction.UPLOAD else 2))

    manifest = RunManifest(
        schema_version="1.0.0",
        run_id=run_id,
        timestamp_utc="2026-10-15T12:00:00Z",
        repetition_index=repetition_index,
        day_label=day_label,
        condition=condition,
        hardware=HardwareProfile(),
        outcome=Outcome.OK if not simulate_failure else Outcome.TOOL_ERROR,
        failure_reason=None if not simulate_failure else "Simulated transient socket timeout during handshake",
        raw_files={"iperf": "iperf_raw.json", "ping": "ping_raw.txt"},
        metadata={"generator": "mock_wifi6_engine", "seed": seed},
    )

    if simulate_failure:
        err_json = json.dumps({"error": "error - unable to connect to server: Connection timed out"})
        err_ping = "PING 192.168.178.50 (192.168.178.50): 56 data bytes\nRequest timeout for icmp_seq 0\n"
        return err_json, err_ping, manifest

    # Physics-based parameters for M1 Pro (2x2 MIMO, 80MHz, 1200 Mbps theoretical PHY)
    # Gigabit Ethernet server interface creates an ~940 Mbps TCP payload ceiling.
    if condition.position_id == "L1":
        # Line-of-sight near AP (High SNR ~42 dB, MCS 11)
        base_tp = 810.0 if condition.direction == Direction.DOWNLOAD else 755.0
        tp_jitter = rng.uniform(-25.0, 25.0)
        tp_mbps = base_tp + tp_jitter
        retransmits = rng.randint(2, 14)

        idle_rtt_base = 2.4
        idle_jitter = 0.5
        load_rtt_base = 32.0  # Bufferbloat under load
        load_jitter = 12.0
    else:
        # L2: 8.5m across drywall (Lower SNR ~24 dB, MCS 7-8, airtime contention & rate fallback)
        base_tp = 485.0 if condition.direction == Direction.DOWNLOAD else 430.0
        tp_jitter = rng.uniform(-35.0, 35.0)
        tp_mbps = base_tp + tp_jitter
        retransmits = rng.randint(25, 85)

        idle_rtt_base = 4.2
        idle_jitter = 1.1
        load_rtt_base = 82.0  # Significant buffer queueing + MAC retries
        load_jitter = 35.0

    receiver_bps = tp_mbps * 1_000_000.0
    sender_bps = (tp_mbps + rng.uniform(2.0, 8.0)) * 1_000_000.0
    duration_s = condition.load_duration_s + rng.uniform(0.01, 0.05)

    reverse_flag = 1 if condition.direction == Direction.DOWNLOAD else 0

    iperf_data = {
        "start": {
            "test_start": {
                "protocol": "TCP",
                "num_streams": condition.streams,
                "reverse": reverse_flag,
            }
        },
        "end": {
            "streams": [
                {
                    "sender": {
                        "bits_per_second": round(sender_bps, 2),
                        "retransmits": retransmits,
                    },
                    "receiver": {
                        "bits_per_second": round(receiver_bps, 2),
                        "seconds": round(duration_s, 2),
                    },
                }
            ],
            "sum_sent": {
                "bits_per_second": round(sender_bps, 2),
                "retransmits": retransmits,
            },
            "sum_received": {
                "bits_per_second": round(receiver_bps, 2),
                "seconds": round(duration_s, 2),
            },
        },
    }
    iperf_raw = json.dumps(iperf_data, indent=2)

    # Generate synthetic macOS ping output across phases
    # Total nominal duration = idle (30s) + warmup (3s) + load (60s) + recovery (30s) = 123s
    # At interval 0.2s, that is ~615 scheduled probes
    total_time = condition.idle_duration_s + condition.warmup_duration_s + condition.load_duration_s + condition.recovery_duration_s
    probe_count = int(total_time / condition.ping_interval_s)

    t_warmup = condition.idle_duration_s
    t_load = condition.idle_duration_s + condition.warmup_duration_s
    t_recovery = condition.idle_duration_s + condition.warmup_duration_s + condition.load_duration_s

    ping_lines = ["PING 192.168.178.50 (192.168.178.50): 56 data bytes"]
    rtt_recorded = []
    received_count = 0

    for seq in range(probe_count):
        t_rel = seq * condition.ping_interval_s

        # Packet loss probability
        loss_prob = 0.005 if condition.position_id == "L1" else 0.025
        if t_rel >= t_load and t_rel < t_recovery:
            loss_prob *= 2.0  # higher loss during congestion

        if rng.random() < loss_prob:
            ping_lines.append(f"Request timeout for icmp_seq {seq}")
            continue

        if t_rel < t_warmup:
            # Idle
            rtt = max(1.2, rng.gauss(idle_rtt_base, idle_jitter))
        elif t_rel < t_load:
            # Warm-up (ramp up)
            alpha = (t_rel - t_warmup) / max(0.1, condition.warmup_duration_s)
            target = idle_rtt_base + alpha * (load_rtt_base - idle_rtt_base)
            rtt = max(2.0, rng.gauss(target, idle_jitter * 2))
        elif t_rel < t_recovery:
            # Measured Load (Bufferbloat plateau)
            rtt = max(5.0, rng.gauss(load_rtt_base, load_jitter))
        else:
            # Recovery (Buffer draining back to idle)
            alpha = min(1.0, (t_rel - t_recovery) / 5.0)  # drains in ~5s
            target = load_rtt_base - alpha * (load_rtt_base - idle_rtt_base)
            rtt = max(1.5, rng.gauss(target, idle_jitter))

        rtt_recorded.append(rtt)
        received_count += 1
        ping_lines.append(f"64 bytes from 192.168.178.50: icmp_seq={seq} ttl=64 time={rtt:.3f} ms")

    # Add ping summary footer
    loss_pct = round((1.0 - (received_count / probe_count)) * 100.0, 1)
    min_rtt = min(rtt_recorded) if rtt_recorded else 0.0
    avg_rtt = sum(rtt_recorded) / len(rtt_recorded) if rtt_recorded else 0.0
    max_rtt = max(rtt_recorded) if rtt_recorded else 0.0
    stddev = math.sqrt(sum((x - avg_rtt) ** 2 for x in rtt_recorded) / len(rtt_recorded)) if rtt_recorded else 0.0

    ping_lines.append("")
    ping_lines.append("--- 192.168.178.50 ping statistics ---")
    ping_lines.append(f"{probe_count} packets transmitted, {received_count} packets received, {loss_pct}% packet loss")
    ping_lines.append(f"round-trip min/avg/max/stddev = {min_rtt:.3f}/{avg_rtt:.3f}/{max_rtt:.3f}/{stddev:.3f} ms")

    ping_raw = "\n".join(ping_lines)
    return iperf_raw, ping_raw, manifest
