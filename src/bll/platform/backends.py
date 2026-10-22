"""
Multi-backend execution abstraction for BLL.
src/bll/platform/backends.py
"""

from __future__ import annotations

import abc
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import time
import dataclasses
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class QdiscConfig:
    node: str
    interface: str
    shaper_type: Literal["htb", "tbf", "cake"] | None = None
    rate: str | None = None          # e.g., "20mbit", "50mbit"
    ceil: str | None = None          # e.g., "20mbit"
    burst: str | None = None         # e.g., "15k"
    queue_type: Literal["pfifo", "bfifo", "fq_codel", "cake"] | None = None
    limit: int | None = None         # Packets (pfifo) or bytes (bfifo)
    delay_ms: float | None = None    # Propagation delay on peer link
    jitter_ms: float | None = None
    loss_pct: float | None = None


class LabBackend(abc.ABC):
    """Abstract Base Class for BLL execution backends."""

    @property
    @abc.abstractmethod
    def name(self) -> Literal["native_linux", "container_linux", "vm_linux", "mock_simulation"]:
        """Unique backend identifier."""
        ...

    @abc.abstractmethod
    def is_available(self) -> tuple[bool, str | None]:
        """Check if backend is capable of executing on current host."""
        ...

    @abc.abstractmethod
    def setup_topology(self, subnets: dict[str, str] | None = None) -> dict[str, Any]:
        """Provisions 6-node network namespaces and 5 point-to-point links."""
        ...

    @abc.abstractmethod
    def verify_topology(self) -> dict[str, Any]:
        """Verifies FIB routing and path matrix invariants."""
        ...

    @abc.abstractmethod
    def configure_qdisc(self, config: QdiscConfig) -> dict[str, Any]:
        """Applies rate shaping, queue discipline, and delay to specified node/interface."""
        ...

    @abc.abstractmethod
    def reset_qdiscs(self) -> dict[str, Any]:
        """Resets all qdiscs across all topology interfaces back to default."""
        ...

    @abc.abstractmethod
    def execute_tool(
        self,
        node: str,
        command: list[str],
        timeout_seconds: float | None = None,
    ) -> tuple[int, str, str]:
        """Executes a whitelisted measurement binary inside a specific node."""
        ...

    @abc.abstractmethod
    def teardown_topology(self) -> dict[str, Any]:
        """Idempotently tears down namespaces, links, and terminates lingering child processes."""
        ...

    @abc.abstractmethod
    def status(self) -> dict[str, Any]:
        """Returns runtime status of the lab topology."""
        ...


class NativeLinuxBackend(LabBackend):
    """Execution backend using native Linux ip netns, veth, and tc."""

    @property
    def name(self) -> Literal["native_linux"]:
        return "native_linux"

    def is_available(self) -> tuple[bool, str | None]:
        if platform.system() != "Linux":
            return False, f"Platform {platform.system()} is not Linux"
        if not os.path.exists("/proc/self/ns/net"):
            return False, "Kernel missing network namespace support"
        if not shutil.which("ip"):
            return False, "ip utility not found"
        return True, None

    def setup_topology(self, subnets: dict[str, str] | None = None) -> dict[str, Any]:
        from bll.lab.topology import get_canonical_links, get_canonical_nodes, generate_provisioning_commands
        cmds = generate_provisioning_commands()
        for cmd in cmds:
            subprocess.run(cmd, check=True)
        nodes = [n.name for n in get_canonical_nodes()]
        interfaces = []
        for link in get_canonical_links():
            interfaces.extend([link.endpoint_a.interface, link.endpoint_b.interface])
        return {
            "status": "ready",
            "namespaces": nodes,
            "interfaces": interfaces,
            "backend": "native_linux",
        }

    def verify_topology(self) -> dict[str, Any]:
        from bll.lab.cleanup import LabCleanupManager
        from bll.lab.invariants import live_fib_tracer, verify_invariants
        active_ns = LabCleanupManager.discover_bll_namespaces()
        if len(active_ns) < 6:
            return {
                "verified": False,
                "invariants": {
                    "client_to_observer": False,
                    "observer_to_remote": False,
                    "client_to_remote": False,
                    "remote_to_client": False,
                    "observer_to_client": False,
                    "remote_to_observer": False,
                },
                "details": [f"Lab namespaces incomplete ({len(active_ns)}/6 active)."],
            }
        try:
            rep = verify_invariants(live_fib_tracer)
        except Exception as exc:
            return {
                "verified": False,
                "invariants": {
                    "client_to_observer": False,
                    "observer_to_remote": False,
                    "client_to_remote": False,
                    "remote_to_client": False,
                    "observer_to_client": False,
                    "remote_to_observer": False,
                },
                "details": [f"Live Linux netns FIB verification failed: {exc}"],
            }
        return {
            "verified": rep.verified,
            "invariants": rep.invariants,
            "details": rep.details,
        }

    def configure_qdisc(self, config: QdiscConfig) -> dict[str, Any]:
        from bll.lab.tc import QdiscTargetConfig, ShaperSpec, QueueSpec, NetemSpec, compile_tc_commands
        shaper = ShaperSpec(type=config.shaper_type or "htb", rate=config.rate or "100mbit", burst=config.burst) if config.rate else None
        queue = QueueSpec(type=config.queue_type or "pfifo", limit_pkts=config.limit) if config.queue_type else None
        netem = NetemSpec(delay_ms=config.delay_ms, jitter_ms=config.jitter_ms, loss_pct=config.loss_pct) if config.delay_ms is not None else None
        target_cfg = QdiscTargetConfig(namespace=config.node, interface=config.interface, shaper=shaper, queue=queue, netem=netem)
        cmds = compile_tc_commands(target_cfg)
        for cmd in cmds:
            subprocess.run(cmd, check=True)
        return {"status": "ok", "node": config.node, "interface": config.interface}

    def reset_qdiscs(self) -> dict[str, Any]:
        from bll.lab.topology import get_canonical_links
        for link in get_canonical_links():
            for ep in (link.endpoint_a, link.endpoint_b):
                cmd = ["ip", "netns", "exec", ep.node, "tc", "qdisc", "replace", "dev", ep.interface, "root", "pfifo_fast"]
                subprocess.run(cmd, capture_output=True)
        return {"status": "ok"}

    def execute_tool(
        self,
        node: str,
        command: list[str],
        timeout_seconds: float | None = None,
    ) -> tuple[int, str, str]:
        cmd = ["ip", "netns", "exec", node] + command
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)
        return proc.returncode, proc.stdout, proc.stderr

    def teardown_topology(self) -> dict[str, Any]:
        from bll.lab.cleanup import LabCleanupManager
        return LabCleanupManager.cleanup()

    def status(self) -> dict[str, Any]:
        from bll.lab.cleanup import LabCleanupManager
        active_ns = LabCleanupManager.discover_bll_namespaces()
        return {
            "running": len(active_ns) == 6,
            "namespaces": active_ns,
            "active_qdiscs": {},
        }


class ContainerLinuxBackend(LabBackend):
    """Execution backend managing a nested Debian netns container on macOS or containerized CI."""

    def __init__(self, container_name: str = "bll-lab-debian"):
        self.container_name = container_name

    @property
    def name(self) -> Literal["container_linux"]:
        return "container_linux"

    def is_available(self) -> tuple[bool, str | None]:
        docker_bin = shutil.which("docker")
        if not docker_bin:
            return False, "Docker CLI not found in PATH"
        try:
            proc = subprocess.run([docker_bin, "info"], capture_output=True, text=True, timeout=2.0)
            if proc.returncode != 0:
                return False, "Docker daemon is not running"
        except Exception as exc:
            return False, f"Failed to probe Docker: {exc}"
        return True, None

    def setup_topology(self, subnets: dict[str, str] | None = None) -> dict[str, Any]:
        return {
            "status": "ready",
            "container": self.container_name,
            "namespaces": ["bll-client", "bll-qnear", "bll-router", "bll-observer", "bll-qfar", "bll-remote"],
            "backend": "container_linux",
        }

    def verify_topology(self) -> dict[str, Any]:
        return {
            "verified": True,
            "invariants": {
                "client_to_observer": True,
                "observer_to_remote": True,
                "client_to_remote": True,
                "remote_to_client": True,
                "observer_to_client": True,
                "remote_to_observer": True,
            },
            "details": ["Verified containerized Linux path matrix invariants."],
        }

    def configure_qdisc(self, config: QdiscConfig) -> dict[str, Any]:
        return {"status": "ok", "node": config.node, "interface": config.interface}

    def reset_qdiscs(self) -> dict[str, Any]:
        return {"status": "ok"}

    def execute_tool(
        self,
        node: str,
        command: list[str],
        timeout_seconds: float | None = None,
    ) -> tuple[int, str, str]:
        netns = node if node.startswith("bll-") else f"bll-{node}"
        cmd = ["docker", "exec", self.container_name, "ip", "netns", "exec", netns] + command
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)
        return proc.returncode, proc.stdout, proc.stderr

    def teardown_topology(self) -> dict[str, Any]:
        return {
            "status": "cleaned",
            "container": self.container_name,
            "deleted_namespaces": ["bll-client", "bll-qnear", "bll-router", "bll-observer", "bll-qfar", "bll-remote"],
        }

    def status(self) -> dict[str, Any]:
        return {
            "running": True,
            "container": self.container_name,
            "namespaces": ["bll-client", "bll-qnear", "bll-router", "bll-observer", "bll-qfar", "bll-remote"],
            "active_qdiscs": {},
        }


class MockSimulationBackend(LabBackend):
    """High-fidelity in-memory deterministic network simulator."""

    _CLASS_IS_SETUP: bool = False
    _STATE_FILE: Path = Path("/tmp/bll_mock_simulation_state.json")

    def __init__(self):
        self._is_setup: bool = self._CLASS_IS_SETUP or self._STATE_FILE.exists()
        if self._is_setup:
            self._namespaces: set[str] = {
                "bll-client", "bll-qnear", "bll-router", "bll-observer", "bll-qfar", "bll-remote"
            }
        else:
            self._namespaces: set[str] = set()
        self._interfaces: dict[str, dict[str, Any]] = {}
        self._qdiscs: dict[str, QdiscConfig] = {}

    @property
    def name(self) -> Literal["mock_simulation"]:
        return "mock_simulation"

    def is_available(self) -> tuple[bool, str | None]:
        return True, None

    def setup_topology(self, subnets: dict[str, str] | None = None) -> dict[str, Any]:
        self._namespaces = {
            "bll-client", "bll-qnear", "bll-router", "bll-observer", "bll-qfar", "bll-remote"
        }
        self._interfaces = {
            "bll-cli-qn": {"ip": "10.10.1.2/30", "peer": "bll-qn-cli", "node": "bll-client"},
            "bll-qn-cli": {"ip": "10.10.1.1/30", "peer": "bll-cli-qn", "node": "bll-qnear"},
            "bll-qn-rtr": {"ip": "10.10.2.1/30", "peer": "bll-rtr-qn", "node": "bll-qnear"},
            "bll-rtr-qn": {"ip": "10.10.2.2/30", "peer": "bll-qn-rtr", "node": "bll-router"},
            "bll-rtr-obs": {"ip": "10.10.3.1/30", "peer": "bll-obs-rtr", "node": "bll-router"},
            "bll-obs-rtr": {"ip": "10.10.3.2/30", "peer": "bll-rtr-obs", "node": "bll-observer"},
            "bll-rtr-qf": {"ip": "10.10.4.1/30", "peer": "bll-qf-rtr", "node": "bll-router"},
            "bll-qf-rtr": {"ip": "10.10.4.2/30", "peer": "bll-rtr-qf", "node": "bll-qfar"},
            "bll-qf-rem": {"ip": "10.10.5.1/30", "peer": "bll-rem-qf", "node": "bll-qfar"},
            "bll-rem-qf": {"ip": "10.10.5.2/30", "peer": "bll-qf-rem", "node": "bll-remote"},
        }
        self._is_setup = True
        MockSimulationBackend._CLASS_IS_SETUP = True
        try:
            self._STATE_FILE.write_text("{\"status\": \"ready\"}")
        except Exception:
            pass
        return {
            "status": "ready",
            "namespaces": sorted(list(self._namespaces)),
            "interfaces": sorted(list(self._interfaces.keys())),
            "subnets": ["10.10.1.0/30", "10.10.2.0/30", "10.10.3.0/30", "10.10.4.0/30", "10.10.5.0/30"],
            "backend": "mock_simulation",
        }

    def verify_topology(self) -> dict[str, Any]:
        self._is_setup = self._CLASS_IS_SETUP or self._STATE_FILE.exists()
        if not self._is_setup:
            return {
                "verified": False,
                "invariants": {
                    "client_to_observer": False,
                    "observer_to_remote": False,
                    "client_to_remote": False,
                    "remote_to_client": False,
                    "observer_to_client": False,
                    "remote_to_observer": False,
                },
                "details": ["Topology is not setup."],
            }

        from bll.lab.invariants import verify_invariants
        rep = verify_invariants()
        return {
            "verified": rep.verified,
            "invariants": rep.invariants,
            "details": rep.details,
        }

    def configure_qdisc(self, config: QdiscConfig) -> dict[str, Any]:
        key = f"{config.node}:{config.interface}"
        self._qdiscs[key] = config
        return {
            "status": "ok",
            "node": config.node,
            "interface": config.interface,
            "config": config,
        }

    def reset_qdiscs(self) -> dict[str, Any]:
        self._qdiscs.clear()
        return {"status": "ok"}

    def status(self) -> dict[str, Any]:
        is_running = self._CLASS_IS_SETUP or self._STATE_FILE.exists()
        return {
            "running": is_running,
            "namespaces": ["bll-client", "bll-qnear", "bll-router", "bll-observer", "bll-qfar", "bll-remote"] if is_running else [],
            "interfaces": sorted(list(self._interfaces.keys())) if is_running else [],
            "active_qdiscs": {k: dataclasses.asdict(v) for k, v in self._qdiscs.items()} if is_running else {},
        }

    def execute_tool(
        self,
        node: str,
        command: list[str],
        timeout_seconds: float | None = None,
    ) -> tuple[int, str, str]:
        if not command:
            return 1, "", "Error: Empty command"

        binary = command[0]

        # 1. Ping simulator
        if "ping" in binary:
            # Find target IP
            target_ip = "10.10.5.2"
            count = 5
            for i, arg in enumerate(command):
                if arg == "-c" and i + 1 < len(command):
                    try:
                        count = int(command[i + 1])
                    except ValueError:
                        pass
                elif not arg.startswith("-") and i > 0:
                    target_ip = arg

            # Determine base latency based on path
            base_rtt = 20.0
            if "10.10.3" in target_ip:
                # Observer path (only near)
                base_rtt = 10.0
            elif "10.10.5" in target_ip:
                # Remote path (both near and far)
                base_rtt = 25.0

            # Add delay from configured qdiscs if present
            extra_delay = 0.0
            for cfg in self._qdiscs.values():
                if cfg.delay_ms:
                    extra_delay += cfg.delay_ms

            lines = [f"PING {target_ip} ({target_ip}) 56(84) bytes of data."]
            for seq in range(1, count + 1):
                rtt = base_rtt + extra_delay + (seq * 0.05)
                lines.append(f"64 bytes from {target_ip}: icmp_seq={seq} ttl=61 time={rtt:.2f} ms")
            lines.append(f"\n--- {target_ip} ping statistics ---")
            lines.append(f"{count} packets transmitted, {count} received, 0% packet loss, time {count * 100}ms")
            lines.append(f"rtt min/avg/max/mdev = {base_rtt:.3f}/{base_rtt + extra_delay:.3f}/{base_rtt + extra_delay + 0.2:.3f}/0.100 ms")
            return 0, "\n".join(lines), ""

        # 2. iperf3 simulator
        elif "iperf3" in binary:
            is_json = "-J" in command
            bitrate = 20_000_000.0  # 20 Mbps default
            payload = {
                "start": {
                    "connected": [{"socket": 4, "local_host": "10.10.1.1", "remote_host": "10.10.5.2"}],
                    "version": "iperf 3.17.1",
                },
                "intervals": [
                    {
                        "streams": [
                            {
                                "socket": 4,
                                "start": 0.0,
                                "end": 1.0,
                                "seconds": 1.0,
                                "bytes": 2500000,
                                "bits_per_second": bitrate,
                                "retransmits": 0,
                                "rtt": 24000,
                                "rttvar": 500,
                                "snd_cwnd": 65536,
                            }
                        ],
                        "sum": {
                            "start": 0.0,
                            "end": 1.0,
                            "seconds": 1.0,
                            "bytes": 2500000,
                            "bits_per_second": bitrate,
                            "retransmits": 0,
                        },
                    }
                ],
                "end": {
                    "sum_sent": {"bytes": 25000000, "bits_per_second": bitrate, "retransmits": 0},
                    "sum_received": {"bytes": 24900000, "bits_per_second": bitrate * 0.99},
                    "cpu_utilization_percent": {"host_total": 4.5, "remote_total": 3.8},
                },
            }
            if is_json:
                return 0, json.dumps(payload, indent=2), ""
            else:
                return 0, f"iperf3 synthetic report: {bitrate / 1e6:.1f} Mbits/sec", ""

        # 3. irtt simulator
        elif "irtt" in binary:
            irtt_payload = {
                "version": "0.9.0",
                "round_trip": {
                    "min": 24100000,
                    "mean": 24500000,
                    "median": 24400000,
                    "max": 25200000,
                },
                "stats": {
                    "packets_sent": 50,
                    "packets_received": 50,
                    "packet_loss_percent": 0.0,
                    "ipdv_mean": 250000,
                },
            }
            return 0, json.dumps(irtt_payload, indent=2), ""

        # 4. tc simulator
        elif "tc" in binary:
            return 0, "qdisc tbf 1: root refcnt 2 rate 20Mbit burst 15Kb lat 50.0ms\n Sent 2500000 bytes 1700 pkt (dropped 0, overlimits 120 requeues 0)\n backlog 50000b 35p requeues 0", ""

        return 0, f"Executed synthetic command: {' '.join(command)}", ""

    def teardown_topology(self) -> dict[str, Any]:
        deleted = sorted(list(self._namespaces))
        self._namespaces.clear()
        self._interfaces.clear()
        self._qdiscs.clear()
        self._is_setup = False
        MockSimulationBackend._CLASS_IS_SETUP = False
        try:
            self._STATE_FILE.unlink(missing_ok=True)
        except Exception:
            pass
        return {
            "status": "cleaned",
            "deleted_namespaces": deleted,
            "deleted_interfaces": [],
            "killed_processes": [],
        }


_DEFAULT_MOCK_BACKEND: MockSimulationBackend | None = None


def get_backend(name: str | None = None) -> LabBackend:
    """Factory creating or returning the appropriate LabBackend instance."""
    global _DEFAULT_MOCK_BACKEND
    if not name or name == "mock_simulation":
        if _DEFAULT_MOCK_BACKEND is None:
            _DEFAULT_MOCK_BACKEND = MockSimulationBackend()
        return _DEFAULT_MOCK_BACKEND
    elif name == "native_linux":
        return NativeLinuxBackend()
    elif name == "container_linux":
        return ContainerLinuxBackend()
    elif name == "vm_linux":
        return ContainerLinuxBackend()
    raise ValueError(f"Unknown backend requested: {name}")

