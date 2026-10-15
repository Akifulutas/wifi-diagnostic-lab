"""Data models, schemas, and outcome definitions for Wi-Fi Diagnostic Lab."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class Outcome(str, Enum):
    OK = "ok"
    TOOL_ERROR = "tool_error"
    TIMEOUT = "timeout"
    PARSE_ERROR = "parse_error"
    CONDITION_CHANGED = "condition_changed"


class Phase(str, Enum):
    IDLE = "idle"
    WARMUP = "warmup"
    LOAD = "load"
    RECOVERY = "recovery"
    BOUNDARY = "boundary"


class Direction(str, Enum):
    UPLOAD = "upload"      # Client -> Server
    DOWNLOAD = "download"  # Server -> Client


@dataclass
class HardwareProfile:
    client_device: str = "MacBook Pro (M1 Pro, 2021)"
    client_os: str = "macOS"
    client_wifi_card: str = "Broadcom BCM4387 / Apple Silicon Wi-Fi 6"
    ap_model: str = "FRITZ!Box 7530 AX"
    ap_firmware: str = "FRITZ!OS 7.8x/8.0x"
    server_device: str = "Gigabit Ethernet Host"
    server_os: str = "Linux / Unix"


@dataclass
class ConditionConfig:
    position_id: str              # "L1" or "L2"
    position_description: str     # e.g., "1m Line of Sight" vs "8m 1 wall"
    direction: Direction          # upload or download
    protocol: str = "TCP"
    streams: int = 1
    band: str = "5 GHz"
    channel: Optional[int] = 116
    channel_width_mhz: int = 80
    idle_duration_s: float = 30.0
    warmup_duration_s: float = 3.0
    load_duration_s: float = 60.0
    recovery_duration_s: float = 30.0
    ping_interval_s: float = 0.2


@dataclass
class RunManifest:
    schema_version: str = "1.0.0"
    run_id: str = ""
    timestamp_utc: str = ""
    repetition_index: int = 1
    day_label: str = "day1"
    condition: ConditionConfig = field(default_factory=lambda: ConditionConfig("L1", "Near AP", Direction.DOWNLOAD))
    hardware: HardwareProfile = field(default_factory=HardwareProfile)
    outcome: Outcome = Outcome.OK
    failure_reason: Optional[str] = None
    raw_files: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        d = asdict(self)
        d["condition"]["direction"] = self.condition.direction.value
        d["outcome"] = self.outcome.value
        return json.dumps(d, indent=2)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunManifest:
        cond_data = data.get("condition", {})
        cond_data["direction"] = Direction(cond_data.get("direction", "download"))
        condition = ConditionConfig(**cond_data)

        hw_data = data.get("hardware", {})
        hardware = HardwareProfile(**hw_data)

        return cls(
            schema_version=data.get("schema_version", "1.0.0"),
            run_id=data.get("run_id", ""),
            timestamp_utc=data.get("timestamp_utc", ""),
            repetition_index=data.get("repetition_index", 1),
            day_label=data.get("day_label", "day1"),
            condition=condition,
            hardware=hardware,
            outcome=Outcome(data.get("outcome", "ok")),
            failure_reason=data.get("failure_reason"),
            raw_files=data.get("raw_files", {}),
            metadata=data.get("metadata", {}),
        )


@dataclass
class RTTSample:
    run_id: str
    seq: int
    timestamp_rel_s: float
    phase: Phase
    rtt_ms: Optional[float]  # None indicates loss/timeout
    is_boundary_guarded: bool = False


@dataclass
class RunSummaryRow:
    run_id: str
    day_label: str
    position_id: str
    direction: str
    repetition: int
    outcome: str
    # Throughput metrics (decimal Mbps)
    receiver_throughput_mbps: Optional[float] = None
    sender_throughput_mbps: Optional[float] = None
    tcp_retransmits: Optional[int] = None
    # Latency metrics (ms)
    idle_rtt_median_ms: Optional[float] = None
    idle_rtt_p95_ms: Optional[float] = None
    loaded_rtt_median_ms: Optional[float] = None
    loaded_rtt_p95_ms: Optional[float] = None
    recovery_rtt_median_ms: Optional[float] = None
    # Bufferbloat delta (loaded median - idle median)
    delta_rtt_median_ms: Optional[float] = None
    # Loss counts
    sent_probes: int = 0
    received_probes: int = 0
    loss_rate_pct: float = 0.0
    failure_reason: str = ""
