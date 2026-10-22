"""
Decoupled Traffic Control Architecture for BLL.
src/bll/lab/tc.py
"""

from __future__ import annotations

import dataclasses
import re
from typing import Any, Dict, List, Literal, Optional, Tuple


@dataclasses.dataclass(frozen=True)
class ShaperSpec:
    type: Literal["htb", "tbf", "cake"]
    rate: str                        # e.g. "20mbit", "100mbit"
    ceil: Optional[str] = None       # e.g. "20mbit"
    burst: Optional[str] = None      # e.g. "15k", "32k"


@dataclasses.dataclass(frozen=True)
class QueueSpec:
    type: Literal["pfifo", "bfifo", "fq_codel", "cake", "noqueue"]
    limit_pkts: Optional[int] = None      # for pfifo
    limit_bytes: Optional[int] = None     # for bfifo
    target_ms: Optional[float] = None     # for fq_codel (e.g. 5.0)
    interval_ms: Optional[float] = None   # for fq_codel (e.g. 100.0)
    extra_params: Dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class NetemSpec:
    delay_ms: float
    jitter_ms: Optional[float] = None
    distribution: Optional[Literal["normal", "uniform", "pareto", "paretonormal"]] = None
    loss_pct: Optional[float] = None
    reorder_pct: Optional[float] = None


@dataclasses.dataclass(frozen=True)
class QdiscTargetConfig:
    namespace: str = ""
    interface: str = ""
    shaper: Optional[ShaperSpec] = None
    queue: Optional[QueueSpec] = None
    netem: Optional[NetemSpec] = None


def parse_rate_to_bps(rate_str: str) -> int:
    """Parses rate strings (e.g., '20mbit', '100kbit', '1gbit') to bits per second."""
    rate_str = rate_str.strip().lower()
    match = re.match(r"^(\d+(?:\.\d+)?)\s*([kmg]?bit|[kmg]?bps)?$", rate_str)
    if not match:
        raise ValueError(f"Invalid rate specification: '{rate_str}'")
    val = float(match.group(1))
    unit = match.group(2) or "bit"
    multipliers = {
        "bit": 1,
        "bps": 1,
        "kbit": 1_000,
        "kbps": 1_000,
        "mbit": 1_000_000,
        "mbps": 1_000_000,
        "gbit": 1_000_000_000,
        "gbps": 1_000_000_000,
    }
    return int(val * multipliers.get(unit, 1_000_000))


def calculate_burst_bytes(rate_bps: int) -> int:
    """Calculates safe token bucket burst size avoiding Linux kernel EINVAL."""
    return max(1600, int(rate_bps / 800))


def build_fifo_shaper(
    rate: str,
    limit_pkts: int = 500,
    burst: Optional[str] = None,
    namespace: str = "",
    interface: str = "",
) -> QdiscTargetConfig:
    """Builds an unmanaged FIFO bufferbloat queue on a forwarder egress interface."""
    rate_bps = parse_rate_to_bps(rate)
    burst_bytes = calculate_burst_bytes(rate_bps)
    burst_str = burst or f"{burst_bytes}b"
    return QdiscTargetConfig(
        namespace=namespace,
        interface=interface,
        shaper=ShaperSpec(type="htb", rate=rate, ceil=rate, burst=burst_str),
        queue=QueueSpec(type="pfifo", limit_pkts=limit_pkts),
    )


def build_bfifo_shaper(
    rate: str,
    limit_bytes: int = 2097152,
    burst: Optional[str] = None,
    namespace: str = "",
    interface: str = "",
) -> QdiscTargetConfig:
    """Builds a byte-limited FIFO bufferbloat queue on a forwarder egress interface."""
    rate_bps = parse_rate_to_bps(rate)
    burst_bytes = calculate_burst_bytes(rate_bps)
    burst_str = burst or f"{burst_bytes}b"
    return QdiscTargetConfig(
        namespace=namespace,
        interface=interface,
        shaper=ShaperSpec(type="htb", rate=rate, ceil=rate, burst=burst_str),
        queue=QueueSpec(type="bfifo", limit_bytes=limit_bytes),
    )


def build_fq_codel_shaper(
    rate: str,
    target_ms: float = 5.0,
    interval_ms: float = 100.0,
    namespace: str = "",
    interface: str = "",
) -> QdiscTargetConfig:
    """Builds an active queue management (FQ-CoDel) shaper on a forwarder egress interface."""
    rate_bps = parse_rate_to_bps(rate)
    burst_bytes = calculate_burst_bytes(rate_bps)
    return QdiscTargetConfig(
        namespace=namespace,
        interface=interface,
        shaper=ShaperSpec(type="htb", rate=rate, ceil=rate, burst=f"{burst_bytes}b"),
        queue=QueueSpec(type="fq_codel", target_ms=target_ms, interval_ms=interval_ms),
    )


def build_cake_shaper(
    bandwidth: str,
    diffserv: str = "besteffort",
    namespace: str = "",
    interface: str = "",
) -> QdiscTargetConfig:
    """Builds an integrated CAKE shaper/AQM on a forwarder egress interface."""
    return QdiscTargetConfig(
        namespace=namespace,
        interface=interface,
        shaper=ShaperSpec(type="cake", rate=bandwidth),
        queue=QueueSpec(type="cake", extra_params={"diffserv": diffserv}),
    )


def build_netem_delay(
    delay_ms: float,
    jitter_ms: Optional[float] = None,
    loss_pct: Optional[float] = None,
    namespace: str = "",
    interface: str = "",
) -> QdiscTargetConfig:
    """Builds a pure propagation delay discipline on a peer link egress interface."""
    if delay_ms < 0:
        raise ValueError(f"Delay must be non-negative, got {delay_ms}ms")
    if jitter_ms is not None and jitter_ms >= delay_ms / 2.0:
        raise ValueError("Jitter must be less than half of delay to prevent packet reordering")
    return QdiscTargetConfig(
        namespace=namespace,
        interface=interface,
        netem=NetemSpec(
            delay_ms=delay_ms,
            jitter_ms=jitter_ms,
            distribution="normal" if jitter_ms else None,
            loss_pct=loss_pct,
        ),
    )


def build_fixed_delay_no_queue(
    delay_ms: float = 50.0,
    forwarder_netns: str = "",
    forwarder_iface: str = "",
    peer_netns: str = "",
    peer_iface: str = "",
) -> Tuple[QdiscTargetConfig, QdiscTargetConfig]:
    """Builds the negative control pair: minimal buffer forwarder + fixed delay peer."""
    forwarder_cfg = QdiscTargetConfig(
        namespace=forwarder_netns,
        interface=forwarder_iface,
        shaper=ShaperSpec(type="htb", rate="1000mbit", ceil="1000mbit", burst="15k"),
        queue=QueueSpec(type="pfifo", limit_pkts=5),
    )
    peer_cfg = build_netem_delay(
        delay_ms=delay_ms,
        namespace=peer_netns,
        interface=peer_iface,
    )
    return forwarder_cfg, peer_cfg


def compile_tc_commands(config: QdiscTargetConfig) -> List[List[str]]:
    """Compiles a QdiscTargetConfig into an array of array-based tc CLI commands."""
    commands: List[List[str]] = []
    iface = config.interface or "eth0"
    base_prefix = ["tc"]
    if config.namespace:
        base_prefix = ["ip", "netns", "exec", config.namespace, "tc"]

    # 1. Netem configuration on peer
    if config.netem:
        netem = config.netem
        cmd = base_prefix + ["qdisc", "replace", "dev", iface, "root", "handle", "1:", "netem", "delay", f"{netem.delay_ms}ms"]
        if netem.jitter_ms:
            cmd.extend([f"{netem.jitter_ms}ms", "distribution", netem.distribution or "normal"])
        if netem.loss_pct:
            cmd.extend(["loss", f"{netem.loss_pct}%"])
        commands.append(cmd)
        return commands

    # 2. CAKE integrated shaper
    if config.shaper and config.shaper.type == "cake":
        diffserv = config.queue.extra_params.get("diffserv", "besteffort") if config.queue else "besteffort"
        cmd = base_prefix + ["qdisc", "replace", "dev", iface, "root", "cake", "bandwidth", config.shaper.rate, diffserv]
        commands.append(cmd)
        return commands

    # 3. HTB classful shaper with attached leaf queue
    if config.shaper and config.shaper.type == "htb":
        shaper = config.shaper
        commands.append(base_prefix + ["qdisc", "replace", "dev", iface, "root", "handle", "1:", "htb", "default", "1"])
        class_cmd = base_prefix + ["class", "add", "dev", iface, "parent", "1:", "classid", "1:1", "htb", "rate", shaper.rate]
        if shaper.ceil:
            class_cmd.extend(["ceil", shaper.ceil])
        if shaper.burst:
            class_cmd.extend(["burst", shaper.burst])
        commands.append(class_cmd)

        if config.queue:
            q = config.queue
            if q.type == "pfifo":
                commands.append(base_prefix + ["qdisc", "add", "dev", iface, "parent", "1:1", "handle", "10:", "pfifo", "limit", str(q.limit_pkts or 500)])
            elif q.type == "bfifo":
                commands.append(base_prefix + ["qdisc", "add", "dev", iface, "parent", "1:1", "handle", "10:", "bfifo", "limit", str(q.limit_bytes or 2097152)])
            elif q.type == "fq_codel":
                commands.append(base_prefix + ["qdisc", "add", "dev", iface, "parent", "1:1", "handle", "10:", "fq_codel", "target", f"{q.target_ms or 5.0}ms", "interval", f"{q.interval_ms or 100.0}ms"])
        return commands

    # 4. Fallback reset to default
    commands.append(base_prefix + ["qdisc", "replace", "dev", iface, "root", "pfifo_fast"])
    return commands
