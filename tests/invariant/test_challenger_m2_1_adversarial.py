"""
Empirical Adversarial Test Suite for Path Matrix Invariants and Routing (M2-1).
tests/invariant/test_challenger_m2_1_adversarial.py
"""

from __future__ import annotations

import ipaddress
import re
import pytest
from pydantic import ValidationError

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
from bll.storage.schemas import InterfaceConfig, LinkConfig, RouteConfig, TopologySnapshot


# ============================================================================
# Category 1: IFNAMSIZ and Interface Name Limits
# ============================================================================

def test_ifnamsiz_canonical_interfaces():
    """All canonical link interfaces must be <= 15 chars and conform to bll- prefix."""
    links = get_canonical_links()
    pattern = re.compile(r"^bll-[a-z0-9\-]{1,11}$")
    for link in links:
        for ep in (link.endpoint_a, link.endpoint_b):
            assert len(ep.interface) <= 15, f"Interface {ep.interface} exceeds 15 chars"
            assert pattern.match(ep.interface) is not None, f"Interface {ep.interface} invalid format"


@pytest.mark.parametrize("ifname,valid", [
    ("bll-12345678901", True),   # exactly 15 chars
    ("bll-cli-qn", True),        # 10 chars
    ("bll-obs-rtr", True),       # 11 chars
    ("bll-123456789012", False), # 16 chars (exceeds IFNAMSIZ)
    ("bll-toolonginterface", False), # 20 chars
    ("eth0", False),             # missing bll- prefix
    ("bll-", False),             # too short (4 chars)
    ("bll-CLI-QN", False),       # uppercase rejected
    ("bll-cli_qn", False),       # underscore rejected
    ("bll-cli.qn", False),       # dot rejected
    ("", False),                 # empty string rejected
    ("bll-cli\x00qn", False),    # null byte rejected
])
def test_endpoint_spec_interface_validation(ifname: str, valid: bool):
    """EndpointSpec must strictly accept valid IFNAMSIZ names and reject invalid ones."""
    if valid:
        ep = EndpointSpec(node="bll-client", interface=ifname, ipv4="10.10.1.2/30")
        assert ep.interface == ifname
    else:
        with pytest.raises(ValueError):
            EndpointSpec(node="bll-client", interface=ifname, ipv4="10.10.1.2/30")


def test_interface_config_schema_validation():
    """Pydantic InterfaceConfig must reject names exceeding 15 chars or wrong pattern."""
    # 15 chars valid
    cfg = InterfaceConfig(name="bll-12345678901", ipv4_address="10.10.1.1")
    assert cfg.name == "bll-12345678901"

    # 16 chars invalid
    with pytest.raises(ValidationError):
        InterfaceConfig(name="bll-123456789012", ipv4_address="10.10.1.1")

    # Missing bll- prefix
    with pytest.raises(ValidationError):
        InterfaceConfig(name="eth0", ipv4_address="10.10.1.1")


# ============================================================================
# Category 2: Routing Table Corruptions & Invariant Detection
# ============================================================================

def test_divert_client_to_observer_through_qfar():
    """Diverting Client->Observer traffic through Q_far must violate invariant 1."""
    def distorted_tracer(src: str, dst: str) -> list[str]:
        if src == "bll-client" and dst == "10.10.3.2":
            # Corrupted route: sends to Q_near -> router -> Q_far -> router -> observer
            return ["bll-client", "bll-qnear", "bll-router", "bll-qfar", "bll-router", "bll-observer"]
        model = InvariantModel()
        return model.trace_route(src, dst)

    report = verify_invariants(distorted_tracer)
    assert report.verified is False
    assert report.invariants["client_to_observer"] is False
    assert report.invariants["observer_to_remote"] is True
    assert report.invariants["client_to_remote"] is True


def test_divert_observer_to_remote_through_qnear():
    """Diverting Observer->Remote traffic through Q_near must violate invariant 2."""
    def distorted_tracer(src: str, dst: str) -> list[str]:
        if src == "bll-observer" and dst == "10.10.5.2":
            # Corrupted route: sends to router -> Q_near -> router -> Q_far -> remote
            return ["bll-observer", "bll-router", "bll-qnear", "bll-router", "bll-qfar", "bll-remote"]
        model = InvariantModel()
        return model.trace_route(src, dst)

    report = verify_invariants(distorted_tracer)
    assert report.verified is False
    assert report.invariants["client_to_observer"] is True
    assert report.invariants["observer_to_remote"] is False
    assert report.invariants["client_to_remote"] is True


def test_bypass_qnear_on_client_to_remote():
    """Client->Remote bypassing Q_near must violate invariant 3."""
    def distorted_tracer(src: str, dst: str) -> list[str]:
        if src == "bll-client" and dst == "10.10.5.2":
            # Corrupted shortcut bypassing Q_near
            return ["bll-client", "bll-router", "bll-qfar", "bll-remote"]
        model = InvariantModel()
        return model.trace_route(src, dst)

    report = verify_invariants(distorted_tracer)
    assert report.verified is False
    assert report.invariants["client_to_remote"] is False


def test_bypass_qfar_on_client_to_remote():
    """Client->Remote bypassing Q_far must violate invariant 3."""
    def distorted_tracer(src: str, dst: str) -> list[str]:
        if src == "bll-client" and dst == "10.10.5.2":
            # Corrupted shortcut bypassing Q_far
            return ["bll-client", "bll-qnear", "bll-router", "bll-remote"]
        model = InvariantModel()
        return model.trace_route(src, dst)

    report = verify_invariants(distorted_tracer)
    assert report.verified is False
    assert report.invariants["client_to_remote"] is False


def test_divert_client_to_remote_through_observer():
    """Client->Remote path traversing Observer must violate invariant 3."""
    def distorted_tracer(src: str, dst: str) -> list[str]:
        if src == "bll-client" and dst == "10.10.5.2":
            # Corrupted route: sends through Observer
            return ["bll-client", "bll-qnear", "bll-router", "bll-observer", "bll-router", "bll-qfar", "bll-remote"]
        model = InvariantModel()
        return model.trace_route(src, dst)

    report = verify_invariants(distorted_tracer)
    assert report.verified is False
    assert report.invariants["client_to_remote"] is False


# ============================================================================
# Category 3: Vulnerabilities in Current Invariant Verification Engine
# ============================================================================

def test_vulnerability_packet_drop_before_destination_falsely_passes():
    """Verify that packet drop before destination is caught and fails invariant 1."""
    def dropped_packet_tracer(src: str, dst: str) -> list[str]:
        if src == "bll-client" and dst == "10.10.3.2":
            # Packet stopped at bll-qnear and never reached bll-observer
            return ["bll-client", "bll-qnear"]
        model = InvariantModel()
        return model.trace_route(src, dst)

    report = verify_invariants(dropped_packet_tracer)
    inv_passed = report.invariants["client_to_observer"]
    assert inv_passed is False, "Hardened invariant engine correctly caught packet drop"
    assert report.verified is False


def test_vulnerability_routing_loop_falsely_passes_invariant_3():
    """Verify that routing loops are detected and fail invariant 3."""
    model = InvariantModel()
    qf = model.nodes["bll-qfar"]
    # Host route on Q_far pointing back to router
    model.nodes["bll-qfar"] = NodeSpec(
        name=qf.name,
        role=qf.role,
        forwarding_enabled=True,
        routes=[RouteSpec(destination_cidr="10.10.5.2/32", gateway_ip="10.10.4.1", interface="bll-qf-rtr")]
    )
    path = model.trace_route("bll-client", "10.10.5.2")
    assert "bll-remote" not in path
    assert len(path) == 11  # max_hops truncation
    assert path.count("bll-router") > 1  # cycle exists

    report = verify_invariants(model.trace_route)
    assert report.invariants["client_to_remote"] is False
    assert report.verified is False, "Hardened invariant engine correctly rejected routing loop"


def test_vulnerability_unhandled_exception_in_tracer():
    """Verify that tracer exceptions are caught gracefully and return verified=False."""
    def failing_tracer(src: str, dst: str) -> list[str]:
        raise RuntimeError(f"No route to host {dst} from node '{src}'")

    report = verify_invariants(failing_tracer)
    assert report.verified is False
    assert all(passed is False for passed in report.invariants.values())


def test_vulnerability_reverse_paths_not_checked():
    """Verify that reverse return paths are queried and verified."""
    queried_sources: list[str] = []

    def spy_tracer(src: str, dst: str) -> list[str]:
        queried_sources.append(src)
        model = InvariantModel()
        return model.trace_route(src, dst)

    report = verify_invariants(spy_tracer)
    assert report.verified is True
    # bll-remote MUST be queried as a source for reverse return path
    assert "bll-remote" in queried_sources


def test_api_missing_verify_path_matrix_invariants_alias():
    """Verify that verify_path_matrix_invariants alias exists."""
    import bll.lab.invariants as inv_mod
    assert hasattr(inv_mod, "verify_invariants")
    assert hasattr(inv_mod, "verify_path_matrix_invariants"), "verify_path_matrix_invariants alias must exist"
