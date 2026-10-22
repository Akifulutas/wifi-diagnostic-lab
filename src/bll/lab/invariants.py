"""
Automated Path Matrix Invariant Verification Engine.
src/bll/lab/invariants.py
"""

from __future__ import annotations

import ipaddress
import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field


class InvariantCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invariant_name: str
    passed: bool
    source_node: str
    destination_node: str
    target_ip: str
    expected_traversals: list[str]
    forbidden_traversals: list[str]
    actual_traversed_nodes: list[str]
    details: str


class PathMatrixVerificationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verified: bool
    invariants: dict[str, bool]
    checks: list[InvariantCheckResult]
    timestamp_utc: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: list[str] = Field(default_factory=list)


class InvariantModel:
    """Pure-Python graph model verifying routing invariants via Longest Prefix Match."""

    def __init__(self) -> None:
        from bll.lab.topology import get_canonical_links, get_canonical_nodes
        self.nodes = {n.name: n for n in get_canonical_nodes()}
        self.links = get_canonical_links()
        self.if_to_peer: dict[tuple[str, str], tuple[str, str]] = {}
        self.ip_to_node: dict[str, str] = {}

        for link in self.links:
            ip_a = link.endpoint_a.ipv4.split("/")[0]
            ip_b = link.endpoint_b.ipv4.split("/")[0]
            self.ip_to_node[ip_a] = link.endpoint_a.node
            self.ip_to_node[ip_b] = link.endpoint_b.node
            self.if_to_peer[(link.endpoint_a.node, link.endpoint_a.interface)] = (
                link.endpoint_b.node,
                link.endpoint_b.interface,
            )
            self.if_to_peer[(link.endpoint_b.node, link.endpoint_b.interface)] = (
                link.endpoint_a.node,
                link.endpoint_a.interface,
            )

    def trace_route(self, src_node: str, dst_ip: str, max_hops: int = 10) -> list[str]:
        """Traces the ordered sequence of traversed nodes for dst_ip starting at src_node."""
        current_node = src_node
        path = [current_node]
        target_addr = ipaddress.IPv4Address(dst_ip)

        for _ in range(max_hops):
            node_spec = self.nodes.get(current_node)
            if not node_spec:
                break

            # Check if target_ip is directly configured on one of current_node's interfaces
            if self.ip_to_node.get(dst_ip) == current_node:
                break

            # If transit node, verify forwarding is enabled
            if current_node != src_node and not node_spec.forwarding_enabled:
                raise RuntimeError(f"Transit node '{current_node}' has forwarding disabled")

            # Route lookup: Longest Prefix Match (LPM)
            best_len = -1
            chosen_route = None

            for route in node_spec.routes:
                net = ipaddress.IPv4Network(route.destination_cidr)
                if target_addr in net:
                    if net.prefixlen > best_len:
                        best_len = net.prefixlen
                        chosen_route = route

            # Also check directly connected subnets
            for link in self.links:
                if link.endpoint_a.node == current_node:
                    net = ipaddress.IPv4Network(link.subnet)
                    if target_addr in net and net.prefixlen > best_len:
                        best_len = net.prefixlen
                        chosen_route = type("DirectRoute", (), {"gateway_ip": None, "interface": link.endpoint_a.interface})()
                elif link.endpoint_b.node == current_node:
                    net = ipaddress.IPv4Network(link.subnet)
                    if target_addr in net and net.prefixlen > best_len:
                        best_len = net.prefixlen
                        chosen_route = type("DirectRoute", (), {"gateway_ip": None, "interface": link.endpoint_b.interface})()

            if not chosen_route:
                raise RuntimeError(f"No route to host {dst_ip} from node '{current_node}'")

            # Resolve peer node connected to interface
            peer_info = self.if_to_peer.get((current_node, chosen_route.interface))
            if not peer_info:
                raise RuntimeError(f"Interface '{chosen_route.interface}' has no connected peer")

            next_node, _ = peer_info
            path.append(next_node)
            current_node = next_node

            if self.ip_to_node.get(dst_ip) == current_node:
                break

        return path


def live_fib_tracer(src_node: str, dst_ip: str, max_hops: int = 10) -> list[str]:
    """Traces route using live Linux kernel ip route get query."""
    from bll.lab.topology import get_canonical_links
    links = get_canonical_links()
    if_to_peer: dict[tuple[str, str], str] = {}
    ip_to_node: dict[str, str] = {}
    for link in links:
        ip_a = link.endpoint_a.ipv4.split("/")[0]
        ip_b = link.endpoint_b.ipv4.split("/")[0]
        ip_to_node[ip_a] = link.endpoint_a.node
        ip_to_node[ip_b] = link.endpoint_b.node
        if_to_peer[(link.endpoint_a.node, link.endpoint_a.interface)] = link.endpoint_b.node
        if_to_peer[(link.endpoint_b.node, link.endpoint_b.interface)] = link.endpoint_a.node

    current_node = src_node
    path = [current_node]

    for _ in range(max_hops):
        if ip_to_node.get(dst_ip) == current_node:
            break

        proc = subprocess.run(
            ["ip", "-n", current_node, "-j", "route", "get", dst_ip],
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"ip route get failed in {current_node}: {proc.stderr}")

        routes = json.loads(proc.stdout)
        if not routes:
            raise RuntimeError(f"Empty route result in {current_node} for {dst_ip}")

        dev = routes[0].get("dev")
        if not dev:
            raise RuntimeError(f"No egress device in route response: {routes[0]}")

        next_node = if_to_peer.get((current_node, dev))
        if not next_node:
            raise RuntimeError(f"No peer node known for ({current_node}, {dev})")

        path.append(next_node)
        current_node = next_node

        if ip_to_node.get(dst_ip) == current_node:
            break

    return path


def _evaluate_path(
    path: list[str],
    source_node: str,
    destination_node: str,
    expected_traversals: list[str],
    forbidden_traversals: list[str],
) -> tuple[bool, str]:
    """Validates traversed path against reachability, looplessness, and traversal constraints."""
    if not path:
        return False, f"Route trace returned empty path from {source_node} to {destination_node}"
    if path[0] != source_node:
        return False, f"Path origin mismatch: expected {source_node}, started at {path[0]}"
    if path[-1] != destination_node:
        return False, f"Destination not reached: packet terminated at {path[-1]} instead of {destination_node} ({' -> '.join(path)})"
    if len(path) != len(set(path)):
        return False, f"Routing loop detected: path contains repeated nodes ({' -> '.join(path)})"
    for exp in expected_traversals:
        if exp not in path:
            return False, f"Required node {exp} not traversed in path ({' -> '.join(path)})"
    for forb in forbidden_traversals:
        if forb in path:
            return False, f"Forbidden node {forb} traversed in path ({' -> '.join(path)})"
    return True, f"Verified: {source_node} -> {destination_node} ({' -> '.join(path)})"


def verify_invariants(
    tracer_func: Callable[[str, str], list[str]] | None = None,
) -> PathMatrixVerificationReport:
    """Executes verification for all 6 path matrix invariants (3 forward and 3 reverse)."""
    if tracer_func is None:
        model = InvariantModel()
        tracer_func = model.trace_route

    path_specs = [
        # Forward invariants
        (
            "client_to_observer",
            "bll-client",
            "bll-observer",
            "10.10.3.2",
            ["bll-qnear"],
            ["bll-qfar"],
        ),
        (
            "observer_to_remote",
            "bll-observer",
            "bll-remote",
            "10.10.5.2",
            ["bll-qfar"],
            ["bll-qnear"],
        ),
        (
            "client_to_remote",
            "bll-client",
            "bll-remote",
            "10.10.5.2",
            ["bll-qnear", "bll-qfar"],
            ["bll-observer"],
        ),
        # Reverse return invariants
        (
            "remote_to_client",
            "bll-remote",
            "bll-client",
            "10.10.1.2",
            ["bll-qfar", "bll-qnear"],
            ["bll-observer"],
        ),
        (
            "observer_to_client",
            "bll-observer",
            "bll-client",
            "10.10.1.2",
            ["bll-qnear"],
            ["bll-qfar"],
        ),
        (
            "remote_to_observer",
            "bll-remote",
            "bll-observer",
            "10.10.3.2",
            ["bll-qfar"],
            ["bll-qnear"],
        ),
    ]

    checks: list[InvariantCheckResult] = []
    inv_map: dict[str, bool] = {}

    for inv_name, src, dst_node, dst_ip, expected, forbidden in path_specs:
        try:
            path = tracer_func(src, dst_ip)
            passed, detail_msg = _evaluate_path(path, src, dst_node, expected, forbidden)
        except Exception as exc:
            path = []
            passed = False
            detail_msg = f"Failed to trace route from {src} to {dst_ip} ({dst_node}): {exc}"

        checks.append(
            InvariantCheckResult(
                invariant_name=inv_name,
                passed=passed,
                source_node=src,
                destination_node=dst_node,
                target_ip=dst_ip,
                expected_traversals=expected,
                forbidden_traversals=forbidden,
                actual_traversed_nodes=path,
                details=detail_msg,
            )
        )
        inv_map[inv_name] = passed

    all_verified = all(inv_map.values())
    details = [c.details for c in checks]

    return PathMatrixVerificationReport(
        verified=all_verified,
        invariants=inv_map,
        checks=checks,
        details=details,
    )


# Export alias
verify_path_matrix_invariants = verify_invariants
