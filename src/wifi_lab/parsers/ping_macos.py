"""Parser for macOS ICMP ping output and phase alignment."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from wifi_lab.models import Phase, RTTSample


@dataclass
class PingSummary:
    transmitted: int
    received: int
    loss_rate_pct: float
    min_ms: Optional[float] = None
    avg_ms: Optional[float] = None
    max_ms: Optional[float] = None
    stddev_ms: Optional[float] = None
    samples: list[RTTSample] = None


# Regex patterns for macOS ping output
# e.g.: 64 bytes from 192.168.178.50: icmp_seq=0 ttl=64 time=2.451 ms
RE_SUCCESS = re.compile(r"icmp_seq=(\d+)\s+ttl=\d+\s+time=([\d\.]+)\s*ms", re.IGNORECASE)
# e.g.: Request timeout for icmp_seq 1
RE_TIMEOUT = re.compile(r"Request timeout for icmp_seq\s+(\d+)", re.IGNORECASE)
# e.g.: 100 packets transmitted, 98 packets received, 2.0% packet loss
RE_STATS = re.compile(r"(\d+)\s+packets transmitted,\s+(\d+)\s+packets received,\s+([\d\.]+)%\s+packet loss", re.IGNORECASE)
# e.g.: round-trip min/avg/max/stddev = 1.842/4.120/45.210/6.321 ms
RE_RTT_STATS = re.compile(r"round-trip\s+min/avg/max/stddev\s*=\s*([\d\.]+)/([\d\.]+)/([\d\.]+)/([\d\.]+)\s*ms", re.IGNORECASE)


def parse_macos_ping(
    raw_text: str,
    run_id: str = "run_unknown",
    idle_s: float = 30.0,
    warmup_s: float = 3.0,
    load_s: float = 60.0,
    recovery_s: float = 30.0,
    boundary_guard_s: float = 1.0,
    nominal_interval_s: float = 0.2,
) -> PingSummary:
    """Parses macOS ping output, assigns phase labels to each ICMP sequence, and flags boundary guards.

    Phases:
      [0, idle_s)                                   -> IDLE
      [idle_s, idle_s + warmup_s)                   -> WARMUP
      [idle_s + warmup_s, idle_s + warmup_s + load_s)-> LOAD
      >= idle_s + warmup_s + load_s                 -> RECOVERY
    """
    if not raw_text or not raw_text.strip():
        return PingSummary(transmitted=0, received=0, loss_rate_pct=100.0, samples=[])

    samples: list[RTTSample] = []
    transmitted = 0
    received = 0
    loss_rate_pct = 0.0

    min_ms = None
    avg_ms = None
    max_ms = None
    stddev_ms = None

    t_warmup = idle_s
    t_load = idle_s + warmup_s
    t_recovery = idle_s + warmup_s + load_s
    t_end = t_recovery + recovery_s

    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue

        # Check for success ping reply
        m_succ = RE_SUCCESS.search(line)
        if m_succ:
            seq = int(m_succ.group(1))
            rtt_val = float(m_succ.group(2))
            rel_time = seq * nominal_interval_s

            # Determine phase
            phase = _assign_phase(rel_time, t_warmup, t_load, t_recovery)
            is_guard = _is_near_boundary(rel_time, [t_warmup, t_load, t_recovery], boundary_guard_s)

            samples.append(
                RTTSample(
                    run_id=run_id,
                    seq=seq,
                    timestamp_rel_s=round(rel_time, 3),
                    phase=phase,
                    rtt_ms=rtt_val,
                    is_boundary_guarded=is_guard,
                )
            )
            continue

        # Check for timeout / dropped probe
        m_to = RE_TIMEOUT.search(line)
        if m_to:
            seq = int(m_to.group(1))
            rel_time = seq * nominal_interval_s
            phase = _assign_phase(rel_time, t_warmup, t_load, t_recovery)
            is_guard = _is_near_boundary(rel_time, [t_warmup, t_load, t_recovery], boundary_guard_s)

            samples.append(
                RTTSample(
                    run_id=run_id,
                    seq=seq,
                    timestamp_rel_s=round(rel_time, 3),
                    phase=phase,
                    rtt_ms=None,  # Explicitly null
                    is_boundary_guarded=is_guard,
                )
            )
            continue

        # Check for summary stats line
        m_stat = RE_STATS.search(line)
        if m_stat:
            transmitted = int(m_stat.group(1))
            received = int(m_stat.group(2))
            loss_rate_pct = float(m_stat.group(3))
            continue

        m_rtt = RE_RTT_STATS.search(line)
        if m_rtt:
            min_ms = float(m_rtt.group(1))
            avg_ms = float(m_rtt.group(2))
            max_ms = float(m_rtt.group(3))
            stddev_ms = float(m_rtt.group(4))
            continue

    if transmitted == 0 and samples:
        transmitted = len(samples)
        received = sum(1 for s in samples if s.rtt_ms is not None)
        loss_rate_pct = round((1.0 - (received / transmitted)) * 100.0, 2) if transmitted else 0.0

    return PingSummary(
        transmitted=transmitted,
        received=received,
        loss_rate_pct=loss_rate_pct,
        min_ms=min_ms,
        avg_ms=avg_ms,
        max_ms=max_ms,
        stddev_ms=stddev_ms,
        samples=samples,
    )


def _assign_phase(rel_time: float, t_warmup: float, t_load: float, t_recovery: float) -> Phase:
    if rel_time < t_warmup:
        return Phase.IDLE
    elif rel_time < t_load:
        return Phase.WARMUP
    elif rel_time < t_recovery:
        return Phase.LOAD
    else:
        return Phase.RECOVERY


def _is_near_boundary(rel_time: float, boundaries: list[float], guard_window_s: float) -> bool:
    return any(abs(rel_time - b) <= guard_window_s for b in boundaries)
