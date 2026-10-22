"""
Bufferbloat Localization Lab (BLL) - Columnar Parquet Schemas
src/bll/storage/parquet_schemas.py

PyArrow Schema v1.0.0 definitions for all canonical timeseries tables
stored in runs/<run_id>/samples/*.parquet.
"""

from __future__ import annotations
import pyarrow as pa


# ============================================================================
# 1. ICMP Ping Telemetry (samples/ping.parquet)
# ============================================================================

PING_SCHEMA = pa.schema([
    # Mandatory DISPATCH fields
    ("timestamp_ns", pa.int64(), False),          # Nanoseconds from CLOCK_MONOTONIC_RAW
    ("seq", pa.int64(), False),                   # ICMP sequence number
    ("rtt_ms", pa.float64(), True),               # Nullable (null on packet loss/timeout)
    ("ttl", pa.int32(), True),                    # Time to live
    ("src_ip", pa.string(), False),               # Source IP address
    ("dst_ip", pa.string(), False),               # Destination IP address
    ("phase", pa.string(), False),                # baseline_idle, saturation_load, recovery

    # Multi-vantage & correlation enrichment
    ("run_id", pa.string(), False),               # Opaque run UUID
    ("vantage_point", pa.string(), False),        # client, observer, router
    ("target", pa.string(), False),               # remote, observer, router
    ("path", pa.string(), False),                 # client_to_remote, client_to_observer, observer_to_remote
    ("lost", pa.bool_(), False),                  # True if packet timed out or dropped
    ("timeout", pa.bool_(), False),               # True if no answer before timeout deadline
    ("dup", pa.bool_(), False),                   # True if duplicate reply observed
    ("timestamp_wall", pa.timestamp("us", tz="UTC"), True), # Wall clock for human logs
])


# ============================================================================
# 2. Isochronous UDP IRTT Telemetry (samples/irtt.parquet)
# ============================================================================

IRTT_SCHEMA = pa.schema([
    # Mandatory DISPATCH fields
    ("timestamp_ns", pa.int64(), False),          # Client send CLOCK_MONOTONIC_RAW
    ("seq", pa.int64(), False),                   # UDP round-trip sequence number
    ("rtt_ms", pa.float64(), True),               # Full round trip time (nullable on loss)
    ("ipdv_ms", pa.float64(), True),              # Instantaneous packet delay variation (jitter)
    ("owd_fwd_ms", pa.float64(), True),           # Forward delay (null if clock sync unproven)
    ("owd_rev_ms", pa.float64(), True),           # Reverse delay (null if clock sync unproven)
    ("lost", pa.bool_(), False),                  # Packet lost in either direction
    ("phase", pa.string(), False),                # baseline_idle, saturation_load, recovery

    # Multi-vantage & correlation enrichment
    ("run_id", pa.string(), False),               # Opaque run UUID
    ("vantage_point", pa.string(), False),        # client, observer
    ("target", pa.string(), False),               # remote, router
    ("src_ip", pa.string(), False),               # Client IP
    ("dst_ip", pa.string(), False),               # Remote server IP
    ("server_processing_ms", pa.float64(), True), # Time spent inside remote IRTT daemon
    ("late", pa.bool_(), False),                  # Arrived after jitter buffer window
    ("out_of_order", pa.bool_(), False),          # Arrived with seq < expected_seq
    ("client_send_wall", pa.timestamp("us", tz="UTC"), True),
])


# ============================================================================
# 3. Throughput Load Generator Telemetry (samples/iperf3.parquet)
# ============================================================================

IPERF3_SCHEMA = pa.schema([
    # Mandatory DISPATCH fields
    ("timestamp_ns", pa.int64(), False),          # End of interval timestamp in monotonic ns
    ("interval_start", pa.float64(), False),      # Seconds from load phase start
    ("interval_end", pa.float64(), False),        # Seconds from load phase start
    ("bytes_transferred", pa.int64(), False),     # Bytes transferred during this interval
    ("throughput_bps", pa.float64(), False),      # Instantaneous bits per second
    ("throughput_mbps", pa.float64(), True),      # Instantaneous megabits per second
    ("retransmits", pa.int32(), True),            # TCP segments retransmitted (null for UDP)
    ("rtt_ms", pa.float64(), True),               # Kernel TCP estimated smoothed RTT
    ("rttvar_ms", pa.float64(), True),            # Kernel TCP RTT variance
    ("cwnd_bytes", pa.int64(), True),             # Congestion window size in bytes
    ("cpu_host_pct", pa.float64(), False),        # Host total CPU % during interval
    ("phase", pa.string(), False),                # saturation_load (or recovery transition)

    # Multi-stream & correlation enrichment
    ("run_id", pa.string(), False),               # Opaque run UUID
    ("direction", pa.string(), False),            # upload, download, bidir_tx, bidir_rx
    ("protocol", pa.string(), False),             # tcp, udp
    ("stream_id", pa.int32(), False),             # Stream socket descriptor index
    ("jitter_ms", pa.float64(), True),            # UDP jitter (null for TCP)
    ("lost_packets", pa.int32(), True),           # UDP lost packets (null for TCP)
    ("total_packets", pa.int32(), True),          # UDP total packets (null for TCP)
    ("lost_pct", pa.float64(), True),             # UDP loss percentage (null for TCP)
    ("omitted", pa.bool_(), False),               # True if interval was during warm-up
])


# ============================================================================
# 4. Linux TC Qdisc Statistics Telemetry (samples/qdisc.parquet)
# ============================================================================

QDISC_SCHEMA = pa.schema([
    # Mandatory DISPATCH fields
    ("timestamp_ns", pa.int64(), False),          # Monotonic timestamp of tc poll
    ("netns", pa.string(), False),                # Namespace name (bll-qnear, bll-qfar, bll-router)
    ("interface", pa.string(), False),            # Linux interface name (e.g. bll-qn-rtr)
    ("qdisc_kind", pa.string(), False),           # tbf, pfifo, bfifo, netem, fq_codel, cake
    ("backlog_bytes", pa.int64(), False),         # Instantaneous bytes queued in RAM
    ("backlog_packets", pa.int64(), False),       # Instantaneous packets queued in RAM
    ("drops", pa.int64(), False),                 # Cumulative tail drops / AQM drops
    ("overlimits", pa.int64(), False),            # Cumulative rate-limiting overlimits
    ("requeues", pa.int64(), False),              # Device busy requeues

    # Configuration & correlation enrichment
    ("run_id", pa.string(), False),               # Opaque run UUID
    ("phase", pa.string(), False),                # baseline_idle, saturation_load, recovery
    ("handle", pa.string(), False),               # e.g. "1:", "10:"
    ("parent", pa.string(), False),               # e.g. "root", "1:1"
    ("bytes_total", pa.int64(), False),           # Cumulative bytes transmitted
    ("packets_total", pa.int64(), False),         # Cumulative packets transmitted
    ("qlen", pa.int32(), False),                  # Current queue length
    ("timestamp_wall", pa.timestamp("us", tz="UTC"), True),
])


# ============================================================================
# 5. System Health & CPU Telemetry (samples/system.parquet)
# ============================================================================

SYSTEM_SCHEMA = pa.schema([
    # Mandatory DISPATCH fields
    ("timestamp_ns", pa.int64(), False),          # Monotonic timestamp of sample
    ("netns", pa.string(), False),                # Host or namespace identifier
    ("cpu_user_pct", pa.float64(), False),        # User-space CPU utilization percent
    ("cpu_system_pct", pa.float64(), False),      # Kernel system CPU utilization percent
    ("mem_used_bytes", pa.int64(), False),        # Memory used in bytes
    ("context_switches", pa.int64(), False),      # Monotonic context switch counter

    # Health & correlation enrichment
    ("run_id", pa.string(), False),               # Opaque run UUID
    ("phase", pa.string(), False),                # baseline_idle, saturation_load, recovery
    ("cpu_idle_pct", pa.float64(), False),        # CPU idle percent
    ("mem_available_bytes", pa.int64(), False),   # Available memory in bytes
    ("timestamp_wall", pa.timestamp("us", tz="UTC"), True),
])


# Registry mapping canonical sample table names to PyArrow schemas
TABLE_SCHEMAS: dict[str, pa.Schema] = {
    "ping": PING_SCHEMA,
    "irtt": IRTT_SCHEMA,
    "iperf3": IPERF3_SCHEMA,
    "qdisc": QDISC_SCHEMA,
    "system": SYSTEM_SCHEMA,
}
