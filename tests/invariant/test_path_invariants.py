"""
Automated Path Matrix Invariant Verification Tests (R1, Milestone 2).
tests/invariant/test_path_invariants.py
"""

from __future__ import annotations

import ipaddress
import re
import pytest

from bll.lab.invariants import (
    InvariantCheckResult,
    InvariantModel,
    PathMatrixVerificationReport,
    verify_invariants,
)
from bll.lab.topology import (
    BLL_NAMESPACES,
    CANONICAL_SUBNETS,
    EndpointSpec,
    LinkSpec,
    NodeSpec,
    RouteSpec,
    build_topology_snapshot,
    get_canonical_links,
    get_canonical_nodes,
)
from bll.storage.schemas import TopologySnapshot


@pytest.mark.invariant
def test_interface_names_ifnamsiz_compliance():
    """Verify that all virtual ethernet interface names strictly comply with IFNAMSIZ <= 15 chars."""
    links = get_canonical_links()
    pattern = re.compile(r"^bll-[a-z0-9\-]{1,11}$")

    assert len(links) == 5
    for link in links:
        for ep in (link.endpoint_a, link.endpoint_b):
            assert len(ep.interface) <= 15, f"Interface '{ep.interface}' exceeds IFNAMSIZ 15 characters"
            assert pattern.match(ep.interface), f"Interface '{ep.interface}' does not match prefix regex"


@pytest.mark.invariant
def test_subnets_disjoint_and_p2p():
    """Verify that all 5 subnets are /30 point-to-point subnets and do not overlap."""
    networks = [ipaddress.IPv4Network(s) for s in CANONICAL_SUBNETS]
    assert len(networks) == 5

    for net in networks:
        assert net.prefixlen == 30, f"Subnet {net} is not /30"
        assert net.num_addresses == 4

    # Verify pair-wise disjointness
    for i in range(len(networks)):
        for j in range(i + 1, len(networks)):
            assert not networks[i].overlaps(networks[j]), f"Subnets {networks[i]} and {networks[j]} overlap"


@pytest.mark.invariant
def test_invariant_1_client_to_observer():
    """Invariant 1: Client -> Observer traverses Q_near, does NOT traverse Q_far."""
    model = InvariantModel()
    path = model.trace_route("bll-client", "10.10.3.2")

    assert path == ["bll-client", "bll-qnear", "bll-router", "bll-observer"]
    assert "bll-qnear" in path
    assert "bll-qfar" not in path


@pytest.mark.invariant
def test_invariant_2_observer_to_remote():
    """Invariant 2: Observer -> Remote does NOT traverse Q_near, traverses Q_far."""
    model = InvariantModel()
    path = model.trace_route("bll-observer", "10.10.5.2")

    assert path == ["bll-observer", "bll-router", "bll-qfar", "bll-remote"]
    assert "bll-qfar" in path
    assert "bll-qnear" not in path


@pytest.mark.invariant
def test_invariant_3_client_to_remote():
    """Invariant 3: Client -> Remote traverses both Q_near and Q_far, does NOT traverse Observer."""
    model = InvariantModel()
    path = model.trace_route("bll-client", "10.10.5.2")

    assert path == ["bll-client", "bll-qnear", "bll-router", "bll-qfar", "bll-remote"]
    assert "bll-qnear" in path
    assert "bll-qfar" in path
    assert "bll-observer" not in path


@pytest.mark.invariant
def test_reverse_invariants():
    """Verify reverse return path invariants."""
    model = InvariantModel()

    # Observer -> Client: traverses Q_near, NOT Q_far
    path_o_c = model.trace_route("bll-observer", "10.10.1.2")
    assert "bll-qnear" in path_o_c
    assert "bll-qfar" not in path_o_c

    # Remote -> Observer: traverses Q_far, NOT Q_near
    path_r_o = model.trace_route("bll-remote", "10.10.3.2")
    assert "bll-qfar" in path_r_o
    assert "bll-qnear" not in path_r_o

    # Remote -> Client: traverses both Q_far and Q_near
    path_r_c = model.trace_route("bll-remote", "10.10.1.2")
    assert "bll-qfar" in path_r_c
    assert "bll-qnear" in path_r_c
    assert "bll-observer" not in path_r_c


@pytest.mark.invariant
def test_verify_invariants_engine_pass():
    """Verify that verify_invariants returns verified=True and all invariants True."""
    report = verify_invariants()
    assert report.verified is True
    assert report.invariants["client_to_observer"] is True
    assert report.invariants["observer_to_remote"] is True
    assert report.invariants["client_to_remote"] is True
    assert len(report.checks) in (3, 6)


@pytest.mark.invariant
def test_adversarial_route_tampering():
    """Adversarial test: Tampering with route to bypass Q_near causes invariant check failure."""
    def tampered_tracer(src: str, dst: str) -> list[str]:
        if src == "bll-client" and dst == "10.10.3.2":
            # Illegal shortcut bypassing Q_near directly to router
            return ["bll-client", "bll-router", "bll-observer"]
        model = InvariantModel()
        return model.trace_route(src, dst)

    report = verify_invariants(tampered_tracer)
    assert report.verified is False
    assert report.invariants["client_to_observer"] is False
    assert report.invariants["observer_to_remote"] is True
    assert report.invariants["client_to_remote"] is True


@pytest.mark.invariant
def test_transit_forwarding_disabled_raises_error():
    """Verify that if a transit node has forwarding_enabled=False, InvariantModel raises RuntimeError."""
    model = InvariantModel()
    # Maliciously disable forwarding on Q_near
    qn = model.nodes["bll-qnear"]
    tampered_qn = NodeSpec(
        name=qn.name,
        role=qn.role,
        forwarding_enabled=False,
        routes=qn.routes,
    )
    model.nodes["bll-qnear"] = tampered_qn

    with pytest.raises(RuntimeError, match="forwarding disabled"):
        model.trace_route("bll-client", "10.10.3.2")


@pytest.mark.invariant
def test_topology_snapshot_schema_validity():
    """Verify that build_topology_snapshot() produces a valid TopologySnapshot model."""
    snap = build_topology_snapshot("bll-test-snapshot")
    assert isinstance(snap, TopologySnapshot)
    assert snap.topology_name == "bll-test-snapshot"
    assert len(snap.nodes) == 6
    assert len(snap.links) == 5

    # Test serialization to JSON and back
    json_str = snap.model_dump_json()
    reconstructed = TopologySnapshot.model_validate_json(json_str)
    assert reconstructed.topology_name == "bll-test-snapshot"
    assert len(reconstructed.nodes) == 6
