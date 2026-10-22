"""
Netns Topology Provisioning and Helper Integration Tests.
tests/netns/test_netns_topology.py
"""

from __future__ import annotations

import pytest

from bll.helper.security import SecurityValidationError, validate_resource_name, validate_tool_command
from bll.helper.server import HelperServer
from bll.lab.helper_client import HelperClient, HelperRPCError, MockTransport
from bll.lab.topology import (
    BLL_NAMESPACES,
    CANONICAL_SUBNETS,
    EndpointSpec,
    LinkSpec,
    generate_provisioning_commands,
    get_canonical_links,
    get_canonical_nodes,
)
from bll.platform.backends import get_backend


@pytest.mark.netns
def test_canonical_nodes_structure():
    """Verify the 6 canonical node configurations and forwarding flags."""
    nodes = get_canonical_nodes()
    assert len(nodes) == 6
    node_names = [n.name for n in nodes]
    assert node_names == list(BLL_NAMESPACES)

    # Transit nodes must have forwarding enabled, end nodes disabled
    forwarding_map = {n.name: n.forwarding_enabled for n in nodes}
    assert forwarding_map["bll-client"] is False
    assert forwarding_map["bll-qnear"] is True
    assert forwarding_map["bll-router"] is True
    assert forwarding_map["bll-observer"] is False
    assert forwarding_map["bll-qfar"] is True
    assert forwarding_map["bll-remote"] is False


@pytest.mark.netns
def test_canonical_links_structure():
    """Verify the 5 canonical point-to-point links and interface pairs."""
    links = get_canonical_links()
    assert len(links) == 5

    link_ids = [l.link_id for l in links]
    assert link_ids == [
        "L1_client_qnear",
        "L2_qnear_router",
        "L3_router_observer",
        "L4_router_qfar",
        "L5_qfar_remote",
    ]


@pytest.mark.netns
def test_provisioning_commands_generation():
    """Verify that generate_provisioning_commands() produces valid array commands."""
    commands = generate_provisioning_commands()
    assert len(commands) > 20

    # Ensure no command contains shell metacharacters
    forbidden = set(";`&|$()<>\n\r*?[]{}")
    for cmd in commands:
        assert isinstance(cmd, list)
        for arg in cmd:
            assert not any(ch in forbidden for ch in str(arg))

    # Verify rp_filter=0 configuration is emitted for namespaces and interfaces
    rp_commands = [c for c in commands if "rp_filter=0" in " ".join(c)]
    assert len(rp_commands) >= 12


@pytest.mark.netns
def test_helper_client_lifecycle():
    """Verify HelperClient topology creation, verification, status, and destruction."""
    client = HelperClient(transport=MockTransport())

    # 1. Create topology
    create_res = client.create_topology()
    assert create_res.get("status") in ("ready", "up")
    assert len(create_res.get("namespaces", [])) == 6
    assert len(create_res.get("interfaces", [])) == 10

    # 2. Status
    status_res = client.status()
    assert status_res.get("running") is True
    assert len(status_res.get("namespaces", [])) == 6

    # 3. Verify
    verify_res = client.verify_topology()
    assert verify_res.get("verified") is True
    assert verify_res.get("invariants", {}).get("client_to_observer") is True

    # 4. Exec tool
    code, stdout, stderr = client.exec_tool("bll-client", ["ping", "-c", "2", "10.10.5.2"])
    assert code == 0
    assert "ping statistics" in stdout

    # 5. Destroy
    destroy_res = client.destroy_topology()
    assert destroy_res.get("status") in ("cleaned", "down")


@pytest.mark.netns
def test_helper_server_json_rpc_dispatch():
    """Verify HelperServer JSON-RPC 2.0 error handling and response formatting."""
    server = HelperServer(backend_runner=get_backend("mock_simulation"))

    # Invalid JSON-RPC missing version
    resp1 = server.dispatch({"method": "status", "id": 1})
    assert resp1["error"]["code"] == -32600

    # Unknown method
    resp2 = server.dispatch({"jsonrpc": "2.0", "method": "nonexistent_method", "id": 2})
    assert resp2["error"]["code"] == -32601

    # Security violation (non-bll prefix)
    resp3 = server.dispatch({
        "jsonrpc": "2.0",
        "method": "configure_qdisc",
        "params": {"netns": "host-ns", "interface": "eth0"},
        "id": 3,
    })
    assert resp3["error"]["code"] == -32001

    # Security violation (shell injection)
    resp4 = server.dispatch({
        "jsonrpc": "2.0",
        "method": "configure_qdisc",
        "params": {"netns": "bll-node; id", "interface": "bll-if0"},
        "id": 4,
    })
    assert resp4["error"]["code"] == -32001

    # Invalid params (zero rate)
    resp5 = server.dispatch({
        "jsonrpc": "2.0",
        "method": "configure_qdisc",
        "params": {"netns": "bll-qnear", "interface": "bll-qn-rtr", "rate": "0kbit"},
        "id": 5,
    })
    assert resp5["error"]["code"] == -32602
