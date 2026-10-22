"""
Measurement Tool Adapters: ICMP Ping, UDP IRTT, and TCP/UDP iperf3.
src/bll/measurements/adapters.py
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

logger = logging.getLogger("bll.measurements.adapters")


# ============================================================================
# Telemetry Sample Data Models (Matching Parquet Schemas)
# ============================================================================

@dataclass
class PingSample:
    timestamp_ns: int
    seq: int
    rtt_ms: Optional[float]
    ttl: Optional[int]
    src_ip: str
    dst_ip: str
    phase: str
    run_id: str
    vantage_point: str = "client"
    target: str = "remote"
    path: str = "client_to_remote"
    lost: bool = False
    timeout: bool = False
    dup: bool = False
    timestamp_wall: Optional[datetime] = None


@dataclass
class IrttSample:
    timestamp_ns: int
    seq: int
    rtt_ms: Optional[float]
    ipdv_ms: Optional[float]
    owd_fwd_ms: Optional[float]
    owd_rev_ms: Optional[float]
    lost: bool
    phase: str
    run_id: str
    vantage_point: str = "client"
    target: str = "remote"
    src_ip: str = "10.10.1.2"
    dst_ip: str = "10.10.5.2"
    server_processing_ms: Optional[float] = None
    late: bool = False
    out_of_order: bool = False
    client_send_wall: Optional[datetime] = None


@dataclass
class Iperf3Sample:
    timestamp_ns: int
    interval_start: float
    interval_end: float
    bytes_transferred: int
    throughput_bps: float
    retransmits: Optional[int]
    rtt_ms: Optional[float]
    rttvar_ms: Optional[float]
    cwnd_bytes: Optional[int]
    cpu_host_pct: float
    phase: str
    run_id: str
    throughput_mbps: Optional[float] = None
    direction: str = "upload"
    protocol: str = "tcp"
    stream_id: int = 1
    jitter_ms: Optional[float] = None
    lost_packets: Optional[int] = None
    total_packets: Optional[int] = None
    lost_pct: Optional[float] = None
    omitted: bool = False

    def __post_init__(self) -> None:
        if self.throughput_mbps is None and self.throughput_bps is not None:
            self.throughput_mbps = round(self.throughput_bps / 1e6, 4)


@dataclass
class QdiscSample:
    timestamp_ns: int
    netns: str
    interface: str
    qdisc_kind: str
    backlog_bytes: int
    backlog_packets: int
    drops: int
    overlimits: int
    requeues: int
    run_id: str
    phase: str
    handle: str = "1:"
    parent: str = "root"
    bytes_total: int = 0
    packets_total: int = 0
    qlen: int = 0
    timestamp_wall: Optional[datetime] = None


# ============================================================================
# 1. ICMP Ping Adapter
# ============================================================================

class PingAdapter:
    """Orchestrates and parses ICMP ping telemetry."""

    PING_REGEX = re.compile(
        r"(?:(\d+)\s+bytes\s+from\s+([^\s:]+):?\s+)?(?:icmp_)?seq=(\d+)\s+(?:ttl=(\d+)\s+)?time=([\d\.]+)\s*ms",
        re.IGNORECASE,
    )

    def __init__(
        self,
        dst_ip: str,
        src_ip: str = "10.10.1.2",
        interval_s: float = 0.2,
        vantage_point: str = "client",
        target: str = "remote",
        path_name: str = "client_to_remote",
        run_id: str = "run_default",
    ) -> None:
        self.dst_ip = dst_ip
        self.src_ip = src_ip
        self.interval_s = interval_s
        self.vantage_point = vantage_point
        self.target = target
        self.path_name = path_name
        self.run_id = run_id

    def parse_line(self, line: str, current_phase: str, now_ns: int) -> Optional[PingSample]:
        """Parses a single stdout line from ping output."""
        line_clean = line.strip()
        if not line_clean:
            return None

        match = self.PING_REGEX.search(line_clean)
        wall_now = datetime.now(timezone.utc)

        if match:
            seq = int(match.group(3))
            ttl = int(match.group(4)) if match.group(4) else 64
            rtt = float(match.group(5))
            return PingSample(
                timestamp_ns=now_ns,
                seq=seq,
                rtt_ms=rtt,
                ttl=ttl,
                src_ip=self.src_ip,
                dst_ip=self.dst_ip,
                phase=current_phase,
                run_id=self.run_id,
                vantage_point=self.vantage_point,
                target=self.target,
                path=self.path_name,
                lost=False,
                timeout=False,
                dup=("dup" in line_clean.lower()),
                timestamp_wall=wall_now,
            )

        if "timeout" in line_clean.lower() or "no answer" in line_clean.lower():
            # Packet loss / timeout line
            seq_match = re.search(r"(?:icmp_)?seq[= ]+(\d+)", line_clean, re.IGNORECASE)
            seq = int(seq_match.group(1)) if seq_match else 0
            return PingSample(
                timestamp_ns=now_ns,
                seq=seq,
                rtt_ms=None,
                ttl=None,
                src_ip=self.src_ip,
                dst_ip=self.dst_ip,
                phase=current_phase,
                run_id=self.run_id,
                vantage_point=self.vantage_point,
                target=self.target,
                path=self.path_name,
                lost=True,
                timeout=True,
                dup=False,
                timestamp_wall=wall_now,
            )

        return None


# ============================================================================
# 2. UDP IRTT Adapter
# ============================================================================

class IrttAdapter:
    """Orchestrates and parses UDP Isochronous Round-Trip Time telemetry."""

    def __init__(
        self,
        dst_ip: str,
        src_ip: str = "10.10.1.2",
        interval_s: float = 0.05,
        vantage_point: str = "client",
        target: str = "remote",
        run_id: str = "run_default",
    ) -> None:
        self.dst_ip = dst_ip
        self.src_ip = src_ip
        self.interval_s = interval_s
        self.vantage_point = vantage_point
        self.target = target
        self.run_id = run_id

    def parse_json_report(
        self,
        report_data: dict[str, Any],
        current_phase: str,
        clock_sync_verified: bool = False,
    ) -> List[IrttSample]:
        """Parses an IRTT JSON report object into a list of typed IrttSample records."""
        samples: List[IrttSample] = []
        rtt_stats = report_data.get("round_trip", {})
        wall_now = datetime.now(timezone.utc)
        now_ns = time.monotonic_ns()

        # If IRTT emits round-trip intervals or summary
        mean_rtt = float(rtt_stats.get("mean", 25_000_000)) / 1e6
        median_rtt = float(rtt_stats.get("median", 24_500_000)) / 1e6
        ipdv = float(report_data.get("ipdv", {}).get("mean", 500_000)) / 1e6

        # One-way delay is gated: only populated if clock synchronization is verified
        owd_fwd = None
        owd_rev = None
        if clock_sync_verified and "forward" in report_data and "reverse" in report_data:
            owd_fwd = float(report_data["forward"].get("mean", 12_000_000)) / 1e6
            owd_rev = float(report_data["reverse"].get("mean", 12_500_000)) / 1e6

        sample = IrttSample(
            timestamp_ns=now_ns,
            seq=1,
            rtt_ms=median_rtt,
            ipdv_ms=ipdv,
            owd_fwd_ms=owd_fwd,
            owd_rev_ms=owd_rev,
            lost=report_data.get("stats", {}).get("lost", 0) > 0,
            phase=current_phase,
            run_id=self.run_id,
            vantage_point=self.vantage_point,
            target=self.target,
            src_ip=self.src_ip,
            dst_ip=self.dst_ip,
            server_processing_ms=float(report_data.get("server", {}).get("processing_time", 200_000)) / 1e6,
            client_send_wall=wall_now,
        )
        samples.append(sample)
        return samples


# ============================================================================
# 3. iperf3 Load Generator Adapter
# ============================================================================

class Iperf3Adapter:
    """Orchestrates and parses iperf3 JSON telemetry stream."""

    def __init__(
        self,
        server_ip: str,
        direction: str = "upload",
        protocol: str = "tcp",
        bitrate_bps: Optional[float] = None,
        streams: int = 1,
        run_id: str = "run_default",
    ) -> None:
        self.server_ip = server_ip
        self.direction = direction
        self.protocol = protocol
        self.bitrate_bps = bitrate_bps
        self.streams = streams
        self.run_id = run_id

    def parse_json_intervals(
        self,
        report_data: dict[str, Any],
        phase: str = "saturation_load",
    ) -> List[Iperf3Sample]:
        """Parses iperf3 JSON intervals into a sequence of typed Iperf3Sample records."""
        samples: List[Iperf3Sample] = []
        intervals = report_data.get("intervals", [])
        end_data = report_data.get("end", {})
        cpu_host = float(end_data.get("cpu_utilization_percent", {}).get("host_total", 5.0))

        now_ns = time.monotonic_ns()

        for idx, item in enumerate(intervals):
            sum_data = item.get("sum", {})
            start_s = float(sum_data.get("start", 0.0))
            end_s = float(sum_data.get("end", 1.0))
            bytes_transferred = int(sum_data.get("bytes", 0))
            bps = float(sum_data.get("bits_per_second", 0.0))
            retransmits = sum_data.get("retransmits")

            # Extract per-stream socket metrics (rtt, cwnd)
            streams_list = item.get("streams", [])
            rtt_ms = None
            rttvar_ms = None
            cwnd_bytes = None
            if streams_list:
                first_stream = streams_list[0]
                if "rtt" in first_stream:
                    rtt_ms = float(first_stream["rtt"]) / 1000.0  # iperf3 reports rtt in microseconds
                if "rttvar" in first_stream:
                    rttvar_ms = float(first_stream["rttvar"]) / 1000.0
                if "snd_cwnd" in first_stream:
                    cwnd_bytes = int(first_stream["snd_cwnd"])

            sample = Iperf3Sample(
                timestamp_ns=now_ns + int(start_s * 1e9),
                interval_start=start_s,
                interval_end=end_s,
                bytes_transferred=bytes_transferred,
                throughput_bps=bps,
                retransmits=retransmits,
                rtt_ms=rtt_ms,
                rttvar_ms=rttvar_ms,
                cwnd_bytes=cwnd_bytes,
                cpu_host_pct=cpu_host,
                phase=phase,
                run_id=self.run_id,
                direction=self.direction,
                protocol=self.protocol,
                stream_id=1,
            )
            samples.append(sample)

        return samples


# ============================================================================
# 4. TC Qdisc Statistics Poller
# ============================================================================

class QdiscPoller:
    """Polls Linux tc qdisc statistics and parses queue backlog and drops."""

    TC_STATS_REGEX = re.compile(
        r"qdisc\s+([a-z0-9_-]+)\s+([0-9a-f:]+)\s+(?:root|parent\s+([0-9a-f:]+))?.*?"
        r"Sent\s+(\d+)\s+bytes\s+(\d+)\s+pkt.*?"
        r"(?:dropped\s+(\d+))?.*?"
        r"(?:overlimits\s+(\d+))?.*?"
        r"(?:requeues\s+(\d+))?.*?"
        r"(?:backlog\s+(\d+)b\s+(\d+)p)?",
        re.DOTALL | re.IGNORECASE,
    )

    def parse_tc_output(
        self,
        stdout: str,
        netns: str,
        interface: str,
        phase: str,
        run_id: str,
        now_ns: int,
    ) -> Optional[QdiscSample]:
        """Parses `tc -s qdisc show dev <iface>` output."""
        if not stdout:
            return None

        kind = "pfifo"
        kind_match = re.search(r"qdisc\s+([a-z0-9_-]+)", stdout, re.IGNORECASE)
        if kind_match:
            kind = kind_match.group(1).lower()

        handle = "1:"
        handle_match = re.search(r"qdisc\s+[a-z0-9_-]+\s+([0-9a-f:]+)", stdout, re.IGNORECASE)
        if handle_match:
            handle = handle_match.group(1)

        parent = "root"
        if "root" in stdout:
            parent = "root"
        else:
            parent_match = re.search(r"parent\s+([0-9a-f:]+)", stdout, re.IGNORECASE)
            if parent_match:
                parent = parent_match.group(1)

        bytes_total = 0
        pkts_total = 0
        sent_match = re.search(r"Sent\s+(\d+)\s+bytes\s+(\d+)\s+pkt", stdout, re.IGNORECASE)
        if sent_match:
            bytes_total = int(sent_match.group(1))
            pkts_total = int(sent_match.group(2))

        drops = 0
        drop_match = re.search(r"dropped\s+(\d+)", stdout, re.IGNORECASE)
        if drop_match:
            drops = int(drop_match.group(1))

        overlimits = 0
        over_match = re.search(r"overlimits\s+(\d+)", stdout, re.IGNORECASE)
        if over_match:
            overlimits = int(over_match.group(1))

        requeues = 0
        req_match = re.search(r"requeues\s+(\d+)", stdout, re.IGNORECASE)
        if req_match:
            requeues = int(req_match.group(1))

        backlog_bytes = 0
        backlog_packets = 0
        backlog_match = re.search(r"backlog\s+(\d+)b\s+(\d+)p", stdout, re.IGNORECASE)
        if backlog_match:
            backlog_bytes = int(backlog_match.group(1))
            backlog_packets = int(backlog_match.group(2))

        return QdiscSample(
            timestamp_ns=now_ns,
            netns=netns,
            interface=interface,
            qdisc_kind=kind,
            backlog_bytes=backlog_bytes,
            backlog_packets=backlog_packets,
            drops=drops,
            overlimits=overlimits,
            requeues=requeues,
            run_id=run_id,
            phase=phase,
            handle=handle,
            parent=parent,
            bytes_total=bytes_total,
            packets_total=pkts_total,
            qlen=backlog_packets,
            timestamp_wall=datetime.now(timezone.utc),
        )
