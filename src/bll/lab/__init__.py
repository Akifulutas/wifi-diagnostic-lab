"""
Reference Lab and Topology Management for Bufferbloat Localization Lab (BLL).
src/bll/lab/__init__.py
"""

from bll.lab.cleanup import LabCleanupManager, emergency_cleanup
from bll.lab.helper_client import (
    HelperClient,
    HelperRPCError,
    HelperTransport,
    MockTransport,
    SubprocessTransport,
    UnixSocketTransport,
    get_default_transport,
)
from bll.lab.invariants import (
    InvariantCheckResult,
    InvariantModel,
    PathMatrixVerificationReport,
    live_fib_tracer,
    verify_invariants,
)
from bll.lab.tc import (
    NetemSpec,
    QdiscTargetConfig,
    QueueSpec,
    ShaperSpec,
    build_bfifo_shaper,
    build_cake_shaper,
    build_fifo_shaper,
    build_fixed_delay_no_queue,
    build_fq_codel_shaper,
    build_netem_delay,
    calculate_burst_bytes,
    compile_tc_commands,
    parse_rate_to_bps,
)
from bll.lab.topology import (
    BLL_NAMESPACES,
    CANONICAL_SUBNETS,
    EndpointSpec,
    LinkSpec,
    NodeSpec,
    RouteSpec,
    build_topology_snapshot,
    generate_provisioning_commands,
    get_canonical_links,
    get_canonical_nodes,
)

__all__ = [
    "BLL_NAMESPACES",
    "CANONICAL_SUBNETS",
    "EndpointSpec",
    "HelperClient",
    "HelperRPCError",
    "HelperTransport",
    "InvariantCheckResult",
    "InvariantModel",
    "LabCleanupManager",
    "LinkSpec",
    "MockTransport",
    "NetemSpec",
    "NodeSpec",
    "PathMatrixVerificationReport",
    "QdiscTargetConfig",
    "QueueSpec",
    "RouteSpec",
    "ShaperSpec",
    "SubprocessTransport",
    "UnixSocketTransport",
    "build_bfifo_shaper",
    "build_cake_shaper",
    "build_fifo_shaper",
    "build_fixed_delay_no_queue",
    "build_fq_codel_shaper",
    "build_netem_delay",
    "build_topology_snapshot",
    "calculate_burst_bytes",
    "compile_tc_commands",
    "emergency_cleanup",
    "generate_provisioning_commands",
    "get_canonical_links",
    "get_canonical_nodes",
    "get_default_transport",
    "live_fib_tracer",
    "parse_rate_to_bps",
    "verify_invariants",
]
