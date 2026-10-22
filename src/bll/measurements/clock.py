"""
Monotonic Clock Engine and Clock Synchronization Validator.
src/bll/measurements/clock.py
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class ClockReading:
    """A pair of monotonic nanosecond and UTC wall-clock timestamps."""
    monotonic_ns: int
    wall_time_utc: float


class MonotonicClock:
    """Tracks strictly increasing monotonic time using CLOCK_MONOTONIC_RAW."""

    def __init__(self) -> None:
        self._start_monotonic_ns = time.monotonic_ns()
        self._start_wall_time = time.time()
        self._last_monotonic_ns = self._start_monotonic_ns

    @property
    def start_monotonic_ns(self) -> int:
        return self._start_monotonic_ns

    @property
    def start_wall_time(self) -> float:
        return self._start_wall_time

    def read(self) -> ClockReading:
        """Returns current monotonic nanoseconds and verifies monotonicity."""
        now_ns = time.monotonic_ns()
        if now_ns < self._last_monotonic_ns:
            # Monotonicity invariant violated by platform
            raise RuntimeError(
                f"Monotonicity violation: current time {now_ns} < last reading {self._last_monotonic_ns}"
            )
        self._last_monotonic_ns = now_ns
        return ClockReading(monotonic_ns=now_ns, wall_time_utc=time.time())

    def elapsed_s(self) -> float:
        """Returns elapsed fractional seconds since clock start."""
        return (time.monotonic_ns() - self._start_monotonic_ns) / 1e9

    def elapsed_ns(self) -> int:
        """Returns elapsed nanoseconds since clock start."""
        return time.monotonic_ns() - self._start_monotonic_ns


class ClockSyncValidator:
    """Validates cross-host clock synchronization before permitting One-Way Delay (OWD)."""

    def __init__(self, max_allowable_offset_ms: float = 1.0):
        self.max_allowable_offset_ms = max_allowable_offset_ms

    def validate_offset(
        self,
        client_tx_ns: int,
        server_rx_ns: int,
        server_tx_ns: int,
        client_rx_ns: int,
    ) -> Tuple[bool, float, Optional[str]]:
        """Calculates round-trip delay and clock offset using standard NTP/PTP 4-timestamp formula:
        rtt = (t4 - t1) - (t3 - t2)
        offset = ((t2 - t1) + (t3 - t4)) / 2
        """
        rtt_ns = (client_rx_ns - client_tx_ns) - (server_tx_ns - server_rx_ns)
        if rtt_ns < 0:
            return False, 0.0, "Clock anomaly: negative RTT calculated from timestamps"

        offset_ns = ((server_rx_ns - client_tx_ns) + (server_tx_ns - client_rx_ns)) / 2.0
        offset_ms = abs(offset_ns) / 1e6

        if offset_ms > self.max_allowable_offset_ms:
            return (
                False,
                offset_ms,
                f"Clock sync error {offset_ms:.3f}ms exceeds threshold {self.max_allowable_offset_ms:.3f}ms",
            )

        return True, offset_ms, None
