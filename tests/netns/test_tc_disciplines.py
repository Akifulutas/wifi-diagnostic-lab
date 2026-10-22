"""
Decoupled Traffic Control Architecture and Parameter Builder Tests.
tests/netns/test_tc_disciplines.py
"""

from __future__ import annotations

import pytest

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


@pytest.mark.netns
def test_rate_parsing_and_burst_calculation():
    """Verify rate parsing to bits/second and safe burst byte sizing."""
    assert parse_rate_to_bps("20mbit") == 20_000_000
    assert parse_rate_to_bps("100kbit") == 100_000
    assert parse_rate_to_bps("1gbit") == 1_000_000_000
    assert parse_rate_to_bps("50mbps") == 50_000_000

    with pytest.raises(ValueError, match="Invalid rate specification"):
        parse_rate_to_bps("invalid_rate")

    burst = calculate_burst_bytes(20_000_000)
    assert burst >= 1600  # Must exceed standard 1500 byte MTU


@pytest.mark.netns
def test_fifo_shaper_builder():
    """Verify packet-limited and byte-limited FIFO shaper configurations."""
    pfifo_cfg = build_fifo_shaper(rate="20mbit", limit_pkts=500, namespace="bll-qnear", interface="bll-qn-rtr")
    assert pfifo_cfg.shaper.type == "htb"
    assert pfifo_cfg.shaper.rate == "20mbit"
    assert pfifo_cfg.queue.type == "pfifo"
    assert pfifo_cfg.queue.limit_pkts == 500
    assert pfifo_cfg.netem is None  # Strict decoupling

    bfifo_cfg = build_bfifo_shaper(rate="50mbit", limit_bytes=2097152, namespace="bll-qfar", interface="bll-qf-rem")
    assert bfifo_cfg.shaper.type == "htb"
    assert bfifo_cfg.queue.type == "bfifo"
    assert bfifo_cfg.queue.limit_bytes == 2097152
    assert bfifo_cfg.netem is None


@pytest.mark.netns
def test_modern_aqm_builders():
    """Verify FQ-CoDel and CAKE parameter builders."""
    fq_cfg = build_fq_codel_shaper(rate="100mbit", target_ms=5.0, interval_ms=100.0, namespace="bll-qnear", interface="bll-qn-rtr")
    assert fq_cfg.shaper.type == "htb"
    assert fq_cfg.queue.type == "fq_codel"
    assert fq_cfg.queue.target_ms == 5.0
    assert fq_cfg.queue.interval_ms == 100.0
    assert fq_cfg.netem is None

    cake_cfg = build_cake_shaper(bandwidth="25mbit", diffserv="diffserv4", namespace="bll-qnear", interface="bll-qn-rtr")
    assert cake_cfg.shaper.type == "cake"
    assert cake_cfg.shaper.rate == "25mbit"
    assert cake_cfg.queue.extra_params.get("diffserv") == "diffserv4"
    assert cake_cfg.netem is None


@pytest.mark.netns
def test_netem_delay_builder_and_validation():
    """Verify netem pure propagation delay configuration and safety bounds."""
    netem_cfg = build_netem_delay(delay_ms=25.0, jitter_ms=2.0, namespace="bll-router", interface="bll-rtr-qn")
    assert netem_cfg.netem.delay_ms == 25.0
    assert netem_cfg.netem.jitter_ms == 2.0
    assert netem_cfg.shaper is None  # Strict decoupling
    assert netem_cfg.queue is None

    # Negative delay rejected
    with pytest.raises(ValueError, match="Delay must be non-negative"):
        build_netem_delay(delay_ms=-5.0)

    # Jitter >= delay / 2 rejected to prevent packet reordering
    with pytest.raises(ValueError, match="Jitter must be less than half of delay"):
        build_netem_delay(delay_ms=10.0, jitter_ms=6.0)


@pytest.mark.netns
def test_negative_control_configuration():
    """Verify fixed_delay_no_queue builds minimal queue forwarder + pure delay peer."""
    fwd_cfg, peer_cfg = build_fixed_delay_no_queue(
        delay_ms=50.0,
        forwarder_netns="bll-qnear",
        forwarder_iface="bll-qn-rtr",
        peer_netns="bll-router",
        peer_iface="bll-rtr-qn",
    )
    # Forwarder must have 1000mbit rate and tiny 5-packet queue limit
    assert fwd_cfg.shaper.rate == "1000mbit"
    assert fwd_cfg.queue.type == "pfifo"
    assert fwd_cfg.queue.limit_pkts == 5
    assert fwd_cfg.netem is None

    # Peer must have pure 50ms delay
    assert peer_cfg.netem.delay_ms == 50.0
    assert peer_cfg.shaper is None
    assert peer_cfg.queue is None


@pytest.mark.netns
def test_compile_tc_commands():
    """Verify compilation of configurations into valid tc CLI commands."""
    pfifo_cfg = build_fifo_shaper(rate="20mbit", limit_pkts=500, namespace="bll-qnear", interface="bll-qn-rtr")
    pfifo_cmds = compile_tc_commands(pfifo_cfg)
    assert len(pfifo_cmds) == 3
    assert pfifo_cmds[0] == ["ip", "netns", "exec", "bll-qnear", "tc", "qdisc", "replace", "dev", "bll-qn-rtr", "root", "handle", "1:", "htb", "default", "1"]
    assert "class" in pfifo_cmds[1]
    assert "pfifo" in pfifo_cmds[2]

    netem_cfg = build_netem_delay(delay_ms=25.0, namespace="bll-router", interface="bll-rtr-qn")
    netem_cmds = compile_tc_commands(netem_cfg)
    assert len(netem_cmds) == 1
    assert netem_cmds[0] == ["ip", "netns", "exec", "bll-router", "tc", "qdisc", "replace", "dev", "bll-rtr-qn", "root", "handle", "1:", "netem", "delay", "25.0ms"]
