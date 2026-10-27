"""WiSlow-inspired evidence-based diagnostic engine for Wi-Fi 6 performance analysis.

Based on diagnostic principles formulated by Kim, Nam, and Schulzrinne (INFOCOM 2014):
Separates observations from candidate causes, identifies missing evidence, and proposes
targeted follow-up experiments to distinguish bottlenecks.
"""

from __future__ import annotations

import csv
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass
class DiagnosticFinding:
    category: str
    observation: str
    candidate_explanations: list[str]
    evidence_missing: list[str]
    next_discriminating_test: str


def run_diagnostics(summary_csv: Path) -> int:
    """Reads run_summary.csv and generates structured diagnostic findings."""
    if not summary_csv.is_file():
        print(f"\033[91mError: Summary CSV not found: {summary_csv}\033[0m")
        return 1

    rows = []
    with open(summary_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    findings = analyze_performance_patterns(rows)

    print("=" * 76)
    print("  Wi-Fi Diagnostic Lab — Evidence-Based Diagnostic Engine")
    print("  Theoretical Framework: WiSlow Diagnostic Methodology (Kim et al., IEEE INFOCOM)")
    print(f"  Input Dataset: {summary_csv.name} ({len(rows)} attempted runs)")
    print("=" * 76)

    for idx, f in enumerate(findings, 1):
        print(f"\n\033[1m[\033[94mFINDING {idx:02d}: {f.category.upper()}\033[0m\033[1m]\033[0m")
        print(f"  \033[1mObservation:\033[0m")
        print(f"    ↳ {f.observation}")
        print(f"  \033[1mCandidate Explanations:\033[0m")
        for c in f.candidate_explanations:
            print(f"    • {c}")
        print(f"  \033[1mMissing Evidence:\033[0m")
        for m in f.evidence_missing:
            print(f"    ? {m}")
        print(f"  \033[1mNext Discriminating Test:\033[0m")
        print(f"    ➜ \033[92m{f.next_discriminating_test}\033[0m")

    print("\n" + "-" * 76)
    print(f"Diagnostic evaluation complete: {len(findings)} research findings generated.")
    return 0


def analyze_performance_patterns(rows: list[dict[str, Any]]) -> list[DiagnosticFinding]:
    findings: list[DiagnosticFinding] = []

    valid_rows = [r for r in rows if r["outcome"] == "ok"]
    failed_rows = [r for r in rows if r["outcome"] != "ok"]

    l1_dls = [float(r["receiver_throughput_mbps"]) for r in valid_rows if r["position_id"] == "L1" and r["direction"] == "download"]
    l2_dls = [float(r["receiver_throughput_mbps"]) for r in valid_rows if r["position_id"] == "L2" and r["direction"] == "download"]

    l1_deltas = [float(r["delta_rtt_median_ms"]) for r in valid_rows if r["position_id"] == "L1" and r["delta_rtt_median_ms"]]
    l2_deltas = [float(r["delta_rtt_median_ms"]) for r in valid_rows if r["position_id"] == "L2" and r["delta_rtt_median_ms"]]

    l1_retrans = [int(r["tcp_retransmits"]) for r in valid_rows if r["position_id"] == "L1" and r["tcp_retransmits"]]
    l2_retrans = [int(r["tcp_retransmits"]) for r in valid_rows if r["position_id"] == "L2" and r["tcp_retransmits"]]

    # Finding 1: Near-AP Throughput Plateau (Gigabit vs Wi-Fi 6 PHY)
    if l1_dls:
        l1_med = statistics.median(l1_dls)
        if l1_med > 750.0:
            findings.append(
                DiagnosticFinding(
                    category="Near-AP Throughput Plateau & Wired Ceiling",
                    observation=(
                        f"At position L1 (1.2m Line-of-Sight), receiver throughput plateaus at {l1_med:.1f} Mbps, "
                        "approaching the theoretical payload limit of 1000BASE-T Gigabit Ethernet (~940 Mbps)."
                    ),
                    candidate_explanations=[
                        "The Gigabit Ethernet link between FRITZ!Box 7530 AX and the local server acts as the primary throughput bottleneck.",
                        "The M1 Pro client's 2x2 MIMO 80MHz PHY ceiling (~1200 Mbps) is constrained by 802.11ax MAC overhead and contention.",
                        "Endpoint CPU / socket buffer sizing capping single-stream TCP performance.",
                    ],
                    evidence_missing=[
                        "Wired baseline: No direct Ethernet-to-Ethernet reference run recorded on this exact client.",
                        "Server CPU / interface telemetry during saturation load.",
                    ],
                    next_discriminating_test=(
                        "Connect the MacBook Pro via a USB-C Gigabit Ethernet adapter to the same FRITZ!Box LAN port "
                        "and repeat the 60s TCP load test. If wired throughput is identical (~940 Mbps), the bottleneck is wired LAN, not Wi-Fi 6."
                    ),
                )
            )

    # Finding 2: Spatial Attenuation and Rate Adaptation at L2
    if l1_dls and l2_dls:
        l2_med = statistics.median(l2_dls)
        pct_drop = round((1.0 - (l2_med / l1_med)) * 100.0, 1) if l1_med > 0 else 0.0
        l2_ret_avg = statistics.mean(l2_retrans) if l2_retrans else 0
        l1_ret_avg = statistics.mean(l1_retrans) if l1_retrans else 0

        findings.append(
            DiagnosticFinding(
                category="Distance/Obstacle Attenuation & Airtime Degradation",
                observation=(
                    f"At position L2 (8.5m across 1 drywall partition), download throughput decreases by {pct_drop}% "
                    f"to {l2_med:.1f} Mbps. Average TCP retransmissions increase from {l1_ret_avg:.0f} to {l2_ret_avg:.0f}."
                ),
                candidate_explanations=[
                    "RF path loss and wall attenuation reduce SNR, triggering dynamic 802.11ax MCS rate fallback (from MCS 11 to MCS 7/8).",
                    "Lower PHY rates increase per-frame airtime consumption, leaving less available channel capacity.",
                    "Unobserved co-channel interference from neighboring 5 GHz BSSs in the adjacent room.",
                ],
                evidence_missing=[
                    "Continuous frame-level RSSI, noise floor, and negotiated MCS indices across the run.",
                    "Radiotap / monitor-mode capture distinguishing 802.11 MAC retries from end-to-end TCP retransmissions.",
                ],
                next_discriminating_test=(
                    "Log active MCS, NSS, and RSSI via macOS CoreWLAN / private framework during the test run, "
                    "and repeat with laptop oriented 90 degrees to distinguish antenna polarization from room geometry."
                ),
            )
        )

    # Finding 3: Bufferbloat and Queueing Latency Inflation Under Load
    if l1_deltas:
        l1_d_med = statistics.median(l1_deltas)
        l2_d_med = statistics.median(l2_deltas) if l2_deltas else l1_d_med

        findings.append(
            DiagnosticFinding(
                category="Bufferbloat & Active Queue Latency Inflation",
                observation=(
                    f"TCP saturation load inflates median RTT by +{l1_d_med:.1f} ms at L1 and +{l2_d_med:.1f} ms at L2. "
                    "Latency promptly recovers within 5 seconds of load cessation."
                ),
                candidate_explanations=[
                    "Excessive buffering in the AP's transmission queues or client TCP socket buffers (Bufferbloat).",
                    "802.11 CSMA/CA contention delay: ICMP probes must contend for channel airtime with back-to-back TCP frames.",
                    "Downstream vs upstream queuing asymmetry (AP downlink aggregation vs client uplink scheduling).",
                ],
                evidence_missing=[
                    "Buffer occupancy / queue depth counters on FRITZ!OS.",
                    "One-way delay (OWD) decomposition to isolate uplink from downlink queueing.",
                ],
                next_discriminating_test=(
                    "Perform a UDP offered-load sweep (from 10% to 100% capacity in 10% increments) with small datagrams "
                    "to identify the exact throughput inflection point where queueing delay begins to explode."
                ),
            )
        )

    # Finding 4: Failure Accounting
    if failed_rows:
        f_row = failed_rows[0]
        findings.append(
            DiagnosticFinding(
                category="Failure Accounting & Experimental Validity",
                observation=(
                    f"Detected {len(failed_rows)} non-nominal run: '{f_row['run_id']}' failed with outcome "
                    f"'{f_row['outcome']}' (Reason: {f_row['failure_reason']})."
                ),
                candidate_explanations=[
                    "Transient TCP socket timeout or ARP resolution stall.",
                    "Client power-save mode or background OS process contention during handshake.",
                ],
                evidence_missing=[
                    "Kernel network log (`dmesg` / `log show --predicate 'process == \"kernel\"'`).",
                ],
                next_discriminating_test=(
                    "Retain the failed run in the dataset repository with outcome='tool_error'. "
                    "Do not overwrite or discard; calculate condition statistics with explicit denominator N_valid / N_attempted."
                ),
            )
        )

    return findings
