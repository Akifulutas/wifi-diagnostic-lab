"""
6-Node Network Namespace Reference Lab Topology Specification.
src/bll/lab/topology.py
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from bll.storage.schemas import (
    InterfaceConfig,
    LinkConfig,
    PathInvariants,
    RouteConfig,
    TopologyNode,
    TopologySnapshot,
)

# Canonical 6 namespaces
BLL_NAMESPACES = (
    "bll-client",
    "bll-qnear",
    "bll-router",
    "bll-observer",
    "bll-qfar",
    "bll-remote",
)

# Canonical 5 point-to-point /30 subnets
SUBNET_CLIENT_QNEAR = "10.10.1.0/30"
SUBNET_QNEAR_ROUTER = "10.10.2.0/30"
SUBNET_ROUTER_OBSERVER = "10.10.3.0/30"
SUBNET_ROUTER_QFAR = "10.10.4.0/30"
SUBNET_QFAR_REMOTE = "10.10.5.0/30"

CANONICAL_SUBNETS = [
    SUBNET_CLIENT_QNEAR,
    SUBNET_QNEAR_ROUTER,
    SUBNET_ROUTER_OBSERVER,
    SUBNET_ROUTER_QFAR,
    SUBNET_QFAR_REMOTE,
]

# Interface name validation (IFNAMSIZ <= 15 and bll- prefix)
IFNAME_REGEX = re.compile(r"^bll-[a-z0-9\-]{1,11}$")


@dataclass(frozen=True)
class EndpointSpec:
    node: str
    interface: str
    ipv4: str  # CIDR e.g. "10.10.1.2/30"

    def __post_init__(self) -> None:
        if len(self.interface) > 15:
            raise ValueError(f"Interface '{self.interface}' exceeds IFNAMSIZ (15 chars)")
        if not IFNAME_REGEX.match(self.interface):
            raise ValueError(f"Interface '{self.interface}' must match ^bll-[a-z0-9\\-]{{1,11}}$")


@dataclass(frozen=True)
class LinkSpec:
    link_id: str
    subnet: str
    endpoint_a: EndpointSpec
    endpoint_b: EndpointSpec


@dataclass(frozen=True)
class RouteSpec:
    destination_cidr: str
    gateway_ip: str | None
    interface: str


@dataclass(frozen=True)
class NodeSpec:
    name: str
    role: Literal["client", "near_bottleneck", "router", "observer", "far_bottleneck", "remote_target"]
    forwarding_enabled: bool
    rp_filter: int = 0
    routes: list[RouteSpec] = field(default_factory=list)


def get_canonical_links() -> list[LinkSpec]:
    """Returns the 5 canonical /30 point-to-point links."""
    return [
        LinkSpec(
            link_id="L1_client_qnear",
            subnet=SUBNET_CLIENT_QNEAR,
            endpoint_a=EndpointSpec(node="bll-client", interface="bll-cli-qn", ipv4="10.10.1.2/30"),
            endpoint_b=EndpointSpec(node="bll-qnear", interface="bll-qn-cli", ipv4="10.10.1.1/30"),
        ),
        LinkSpec(
            link_id="L2_qnear_router",
            subnet=SUBNET_QNEAR_ROUTER,
            endpoint_a=EndpointSpec(node="bll-qnear", interface="bll-qn-rtr", ipv4="10.10.2.1/30"),
            endpoint_b=EndpointSpec(node="bll-router", interface="bll-rtr-qn", ipv4="10.10.2.2/30"),
        ),
        LinkSpec(
            link_id="L3_router_observer",
            subnet=SUBNET_ROUTER_OBSERVER,
            endpoint_a=EndpointSpec(node="bll-router", interface="bll-rtr-obs", ipv4="10.10.3.1/30"),
            endpoint_b=EndpointSpec(node="bll-observer", interface="bll-obs-rtr", ipv4="10.10.3.2/30"),
        ),
        LinkSpec(
            link_id="L4_router_qfar",
            subnet=SUBNET_ROUTER_QFAR,
            endpoint_a=EndpointSpec(node="bll-router", interface="bll-rtr-qf", ipv4="10.10.4.1/30"),
            endpoint_b=EndpointSpec(node="bll-qfar", interface="bll-qf-rtr", ipv4="10.10.4.2/30"),
        ),
        LinkSpec(
            link_id="L5_qfar_remote",
            subnet=SUBNET_QFAR_REMOTE,
            endpoint_a=EndpointSpec(node="bll-qfar", interface="bll-qf-rem", ipv4="10.10.5.1/30"),
            endpoint_b=EndpointSpec(node="bll-remote", interface="bll-rem-qf", ipv4="10.10.5.2/30"),
        ),
    ]


def get_canonical_nodes() -> list[NodeSpec]:
    """Returns the 6 canonical node configurations with static routing tables."""
    return [
        NodeSpec(
            name="bll-client",
            role="client",
            forwarding_enabled=False,
            routes=[
                RouteSpec(destination_cidr="0.0.0.0/0", gateway_ip="10.10.1.1", interface="bll-cli-qn"),
            ],
        ),
        NodeSpec(
            name="bll-qnear",
            role="near_bottleneck",
            forwarding_enabled=True,
            routes=[
                RouteSpec(destination_cidr="0.0.0.0/0", gateway_ip="10.10.2.2", interface="bll-qn-rtr"),
            ],
        ),
        NodeSpec(
            name="bll-router",
            role="router",
            forwarding_enabled=True,
            routes=[
                RouteSpec(destination_cidr="10.10.1.0/30", gateway_ip="10.10.2.1", interface="bll-rtr-qn"),
                RouteSpec(destination_cidr="10.10.5.0/30", gateway_ip="10.10.4.2", interface="bll-rtr-qf"),
            ],
        ),
        NodeSpec(
            name="bll-observer",
            role="observer",
            forwarding_enabled=False,
            routes=[
                RouteSpec(destination_cidr="0.0.0.0/0", gateway_ip="10.10.3.1", interface="bll-obs-rtr"),
            ],
        ),
        NodeSpec(
            name="bll-qfar",
            role="far_bottleneck",
            forwarding_enabled=True,
            routes=[
                RouteSpec(destination_cidr="0.0.0.0/0", gateway_ip="10.10.4.1", interface="bll-qf-rtr"),
            ],
        ),
        NodeSpec(
            name="bll-remote",
            role="remote_target",
            forwarding_enabled=False,
            routes=[
                RouteSpec(destination_cidr="0.0.0.0/0", gateway_ip="10.10.5.1", interface="bll-rem-qf"),
            ],
        ),
    ]


def generate_provisioning_commands() -> list[list[str]]:
    """Generates ordered, injection-free command arrays for Linux netns setup."""
    commands: list[list[str]] = []
    nodes = get_canonical_nodes()
    links = get_canonical_links()

    # 1. Create namespaces and bring up loopback
    for node in nodes:
        commands.append(["ip", "netns", "add", node.name])
        commands.append(["ip", "-n", node.name, "link", "set", "lo", "up"])
        commands.append([
            "ip", "netns", "exec", node.name,
            "sysctl", "-w", f"net.ipv4.ip_forward={1 if node.forwarding_enabled else 0}",
        ])
        commands.append(["ip", "netns", "exec", node.name, "sysctl", "-w", "net.ipv4.conf.all.rp_filter=0"])
        commands.append(["ip", "netns", "exec", node.name, "sysctl", "-w", "net.ipv4.conf.default.rp_filter=0"])

    # 2. Create veth pairs and move into target namespaces
    for link in links:
        ep_a = link.endpoint_a
        ep_b = link.endpoint_b
        commands.append(["ip", "link", "add", ep_a.interface, "type", "veth", "peer", "name", ep_b.interface])
        commands.append(["ip", "link", "set", ep_a.interface, "netns", ep_a.node])
        commands.append(["ip", "link", "set", ep_b.interface, "netns", ep_b.node])
        commands.append(["ip", "-n", ep_a.node, "addr", "add", ep_a.ipv4, "dev", ep_a.interface])
        commands.append(["ip", "-n", ep_a.node, "link", "set", ep_a.interface, "up"])
        commands.append(["ip", "-n", ep_b.node, "addr", "add", ep_b.ipv4, "dev", ep_b.interface])
        commands.append(["ip", "-n", ep_b.node, "link", "set", ep_b.interface, "up"])
        commands.append(["ip", "netns", "exec", ep_a.node, "sysctl", "-w", f"net.ipv4.conf.{ep_a.interface}.rp_filter=0"])
        commands.append(["ip", "netns", "exec", ep_b.node, "sysctl", "-w", f"net.ipv4.conf.{ep_b.interface}.rp_filter=0"])

    # 3. Apply static routes
    for node in nodes:
        for route in node.routes:
            if route.gateway_ip:
                commands.append([
                    "ip", "-n", node.name, "route", "add",
                    route.destination_cidr, "via", route.gateway_ip, "dev", route.interface,
                ])
            else:
                commands.append([
                    "ip", "-n", node.name, "route", "add",
                    route.destination_cidr, "dev", route.interface,
                ])

    return commands


def build_topology_snapshot(
    topology_name: str = "bll-default",
    invariants: PathInvariants | None = None,
) -> TopologySnapshot:
    """Creates a validated TopologySnapshot matching Schema v1.0.0."""
    links = get_canonical_links()
    nodes = get_canonical_nodes()

    snap_links = [
        LinkConfig(
            link_id=link.link_id,
            subnet=link.subnet,
            node_a=link.endpoint_a.node,
            interface_a=link.endpoint_a.interface,
            ip_a=link.endpoint_a.ipv4.split("/")[0],
            node_b=link.endpoint_b.node,
            interface_b=link.endpoint_b.interface,
            ip_b=link.endpoint_b.ipv4.split("/")[0],
        )
        for link in links
    ]

    snap_nodes = []
    for node in nodes:
        node_interfaces = []
        for link in links:
            if link.endpoint_a.node == node.name:
                node_interfaces.append(
                    InterfaceConfig(
                        name=link.endpoint_a.interface,
                        ipv4_address=link.endpoint_a.ipv4.split("/")[0],
                        peer_node=link.endpoint_b.node,
                        peer_interface=link.endpoint_b.interface,
                    )
                )
            elif link.endpoint_b.node == node.name:
                node_interfaces.append(
                    InterfaceConfig(
                        name=link.endpoint_b.interface,
                        ipv4_address=link.endpoint_b.ipv4.split("/")[0],
                        peer_node=link.endpoint_a.node,
                        peer_interface=link.endpoint_a.interface,
                    )
                )

        node_routes = [
            RouteConfig(
                destination_cidr=r.destination_cidr,
                gateway_ip=r.gateway_ip,
                interface=r.interface,
            )
            for r in node.routes
        ]

        snap_nodes.append(
            TopologyNode(
                name=node.name,
                role=node.role,
                forwarding_enabled=node.forwarding_enabled,
                interfaces=node_interfaces,
                routes=node_routes,
            )
        )

    return TopologySnapshot(
        topology_name=topology_name,
        timestamp_utc=datetime.now(timezone.utc),
        nodes=snap_nodes,
        links=snap_links,
        qdiscs=[],
        invariants_verified=invariants or PathInvariants(
            client_to_observer=False,
            observer_to_remote=False,
            client_to_remote=False,
        ),
    )
