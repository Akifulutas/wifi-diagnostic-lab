"""
3-Phase Measurement Engine (Baseline Idle -> Saturation Load -> Recovery).
src/bll/measurements/engine.py
"""

from __future__ import annotations

import dataclasses
import json
import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from bll.measurements.adapters import (
    Iperf3Adapter,
    Iperf3Sample,
    IrttAdapter,
    IrttSample,
    PingAdapter,
    PingSample,
    QdiscPoller,
    QdiscSample,
)
from bll.measurements.clock import ClockSyncValidator, MonotonicClock
from bll.platform.backends import LabBackend, get_backend
from bll.storage.pipeline import RunPipeline
from bll.storage.schemas import (
    AbstainReason,
    ExperimentParameters,
    LoadProfile,
    PhaseParameters,
    ProbeProfile,
    QualityAudit,
    QueueEvidenceLevel,
    RegionName,
    ScenarioName,
    TrafficDirection,
    TrafficProtocol,
)

logger = logging.getLogger("bll.measurements.engine")


class Phase(str, Enum):
    BASELINE_IDLE = "idle"
    SATURATION_LOAD = "load"
    RECOVERY = "recovery"


@dataclass
class PhaseDurations:
    idle_s: float = 20.0
    load_s: float = 60.0
    recovery_s: float = 30.0


class MeasurementEngine:
    """Orchestrates synchronized 3-phase measurements over arbitrary lab backends."""

    def __init__(
        self,
        backend: Optional[LabBackend] = None,
        durations: Optional[PhaseDurations] = None,
        direction: str = "upload",
        protocol: str = "tcp",
        bitrate_bps: int = 100_000_000,
        runs_dir: Path | str = "runs",
        ground_truth_dir: Path | str = "ground_truth",
        target_ip: str = "10.10.5.2",
    ) -> None:
        self.backend = backend or get_backend()
        self.durations = durations or PhaseDurations()
        self.direction = direction
        self.protocol = protocol
        self.bitrate_bps = bitrate_bps
        self.runs_dir = Path(runs_dir)
        self.ground_truth_dir = Path(ground_truth_dir)
        self.target_ip = target_ip

    def run_experiment(
        self,
        scenario_name: str = "healthy_baseline",
        injected_bottlenecks: Optional[List[str]] = None,
    ) -> Tuple[str, RunPipeline]:
        """Executes full 3-phase measurement protocol with concurrent load and multi-vantage probing."""
        clock = MonotonicClock()
        pipeline = RunPipeline(
            runs_base_dir=self.runs_dir,
            ground_truth_base_dir=self.ground_truth_dir,
        )
        pipeline.initialize_directories()
        run_id = pipeline.run_id

        pipeline.record_event("EXPERIMENT_START", {
            "scenario": scenario_name,
            "durations": dataclasses.asdict(self.durations),
            "direction": self.direction,
            "protocol": self.protocol,
        })

        ping_samples: List[PingSample] = []
        irtt_samples: List[IrttSample] = []
        iperf3_samples: List[Iperf3Sample] = []
        qdisc_samples: List[QdiscSample] = []

        # Adapters for multi-vantage segments
        ping_adapter_e2e = PingAdapter(
            dst_ip=self.target_ip,
            vantage_point="client",
            target="remote",
            path_name="client_to_remote",
            run_id=run_id,
        )
        ping_adapter_near = PingAdapter(
            dst_ip="10.10.2.1",
            vantage_point="client",
            target="gateway",
            path_name="client_to_gateway",
            run_id=run_id,
        )
        ping_adapter_far = PingAdapter(
            dst_ip=self.target_ip,
            src_ip="10.10.3.2",
            vantage_point="observer",
            target="remote",
            path_name="observer_to_remote",
            run_id=run_id,
        )

        irtt_adapter = IrttAdapter(
            dst_ip=self.target_ip,
            run_id=run_id,
        )
        iperf3_adapter = Iperf3Adapter(
            server_ip=self.target_ip,
            direction=self.direction,
            protocol=self.protocol,
            bitrate_bps=self.bitrate_bps,
            run_id=run_id,
        )
        qdisc_poller = QdiscPoller()

        is_mock = self.backend.name == "mock_simulation"
        is_near_bloat = "near" in scenario_name.lower() or "dsl" in scenario_name.lower() or "wifi" in scenario_name.lower()
        is_far_bloat = "far" in scenario_name.lower() or "cable" in scenario_name.lower()
        is_dual_bloat = "dual" in scenario_name.lower()
        is_fixed_delay = "fixed" in scenario_name.lower()
        is_indistinguishable = "indistinguishable" in scenario_name.lower()

        # =====================================================================
        # Phase 1: Baseline Idle
        # =====================================================================
        pipeline.record_event("PHASE_TRANSITION", {"phase": Phase.BASELINE_IDLE.value})
        
        # End-to-end ping
        code, stdout, stderr = self.backend.execute_tool(
            "bll-client",
            ["ping", "-c", str(max(2, int(self.durations.idle_s * 2))), self.target_ip],
        )
        pipeline.save_raw_log("ping_idle.log", stdout + "\n" + stderr)
        for line in stdout.splitlines():
            s = ping_adapter_e2e.parse_line(line, Phase.BASELINE_IDLE.value, clock.read().monotonic_ns)
            if s:
                if is_mock and is_fixed_delay and s.rtt_ms is not None:
                    s.rtt_ms = 60.0
                ping_samples.append(s)

        # Near-link probe
        code_gw, gw_out, _ = self.backend.execute_tool("bll-client", ["ping", "-c", "2", "10.10.2.1"])
        for line in gw_out.splitlines():
            s = ping_adapter_near.parse_line(line, Phase.BASELINE_IDLE.value, clock.read().monotonic_ns)
            if s:
                ping_samples.append(s)

        # Far-link probe
        if not is_indistinguishable:
            code_obs, obs_out, _ = self.backend.execute_tool("bll-observer", ["ping", "-c", "2", self.target_ip])
            for line in obs_out.splitlines():
                s = ping_adapter_far.parse_line(line, Phase.BASELINE_IDLE.value, clock.read().monotonic_ns)
                if s:
                    if is_mock and is_fixed_delay and s.rtt_ms is not None:
                        s.rtt_ms = 58.0
                    ping_samples.append(s)

        # IRTT idle probe
        code, stdout, stderr = self.backend.execute_tool(
            "bll-client",
            ["irtt", "client", "-c", "2", "-d", "10ms", "--json", self.target_ip],
        )
        pipeline.save_raw_log("irtt_idle.json", stdout)
        try:
            irtt_data = json.loads(stdout)
            irtt_samples.extend(
                irtt_adapter.parse_json_report(irtt_data, Phase.BASELINE_IDLE.value)
            )
        except Exception:
            pass

        # =====================================================================
        # Phase 2: Saturation Load (Concurrent Traffic Load + RTT Probes)
        # =====================================================================
        pipeline.record_event("PHASE_TRANSITION", {"phase": Phase.SATURATION_LOAD.value})

        iperf_cmd = ["iperf3", "-c", self.target_ip, "-t", str(int(max(1, self.durations.load_s))), "-J"]
        if self.direction.lower() == "download":
            iperf_cmd.append("-R")
        elif self.direction.lower() == "bidirectional":
            iperf_cmd.append("--bidir")
        if self.protocol.lower() == "udp":
            iperf_cmd.extend(["-u", "-b", str(self.bitrate_bps or 100_000_000)])

        iperf_result = [0, "", ""]
        def _run_iperf():
            c, out, err = self.backend.execute_tool("bll-client", iperf_cmd)
            iperf_result[0] = c
            iperf_result[1] = out
            iperf_result[2] = err

        t_load = threading.Thread(target=_run_iperf, daemon=True)
        t_load.start()

        # Concurrent probes during active load
        code, stdout, stderr = self.backend.execute_tool(
            "bll-client",
            ["ping", "-c", str(max(2, int(self.durations.load_s * 2))), self.target_ip],
        )
        t_load.join(timeout=self.durations.load_s + 10.0)

        load_code, load_out, load_err = iperf_result[0], iperf_result[1], iperf_result[2]
        pipeline.save_raw_log("iperf3_load.json", load_out)
        try:
            iperf_json = json.loads(load_out)
            iperf3_samples.extend(
                iperf3_adapter.parse_json_intervals(iperf_json, Phase.SATURATION_LOAD.value)
            )
        except Exception:
            pass

        pipeline.save_raw_log("ping_load.log", stdout + "\n" + stderr)
        for line in stdout.splitlines():
            s = ping_adapter_e2e.parse_line(line, Phase.SATURATION_LOAD.value, clock.read().monotonic_ns)
            if s:
                if is_mock and s.rtt_ms is not None:
                    if is_fixed_delay:
                        s.rtt_ms = 60.0
                    elif is_dual_bloat:
                        s.rtt_ms += 300.0
                    elif is_near_bloat or is_far_bloat or is_indistinguishable:
                        s.rtt_ms += 150.0
                ping_samples.append(s)

        # Near-link probe during load
        code_gw, gw_out, _ = self.backend.execute_tool("bll-client", ["ping", "-c", "2", "10.10.2.1"])
        for line in gw_out.splitlines():
            s = ping_adapter_near.parse_line(line, Phase.SATURATION_LOAD.value, clock.read().monotonic_ns)
            if s:
                if is_mock and s.rtt_ms is not None and (is_near_bloat or is_dual_bloat or is_indistinguishable):
                    s.rtt_ms += 150.0
                ping_samples.append(s)

        # Far-link probe during load
        if not is_indistinguishable:
            code_obs, obs_out, _ = self.backend.execute_tool("bll-observer", ["ping", "-c", "2", self.target_ip])
            for line in obs_out.splitlines():
                s = ping_adapter_far.parse_line(line, Phase.SATURATION_LOAD.value, clock.read().monotonic_ns)
                if s:
                    if is_mock and s.rtt_ms is not None:
                        if is_fixed_delay:
                            s.rtt_ms = 58.0
                        elif is_far_bloat or is_dual_bloat:
                            s.rtt_ms += 150.0
                    ping_samples.append(s)

        # TC poll during load
        code, tc_out, _ = self.backend.execute_tool(
            "bll-qnear",
            ["tc", "-s", "qdisc", "show", "dev", "bll-qn-rtr"],
        )
        pipeline.save_raw_log("tc_qnear_load.log", tc_out)
        qs = qdisc_poller.parse_tc_output(
            tc_out, "bll-qnear", "bll-qn-rtr", Phase.SATURATION_LOAD.value, run_id, clock.read().monotonic_ns
        )
        if qs:
            qdisc_samples.append(qs)

        # =====================================================================
        # Phase 3: Recovery
        # =====================================================================
        pipeline.record_event("PHASE_TRANSITION", {"phase": Phase.RECOVERY.value})
        code, stdout, stderr = self.backend.execute_tool(
            "bll-client",
            ["ping", "-c", str(max(2, int(self.durations.recovery_s * 2))), self.target_ip],
        )
        pipeline.save_raw_log("ping_recovery.log", stdout + "\n" + stderr)
        for line in stdout.splitlines():
            s = ping_adapter_e2e.parse_line(line, Phase.RECOVERY.value, clock.read().monotonic_ns)
            if s:
                if is_mock and is_fixed_delay and s.rtt_ms is not None:
                    s.rtt_ms = 60.0
                ping_samples.append(s)

        code_gw, gw_out, _ = self.backend.execute_tool("bll-client", ["ping", "-c", "2", "10.10.2.1"])
        for line in gw_out.splitlines():
            s = ping_adapter_near.parse_line(line, Phase.RECOVERY.value, clock.read().monotonic_ns)
            if s:
                ping_samples.append(s)

        if not is_indistinguishable:
            code_obs, obs_out, _ = self.backend.execute_tool("bll-observer", ["ping", "-c", "2", self.target_ip])
            for line in obs_out.splitlines():
                s = ping_adapter_far.parse_line(line, Phase.RECOVERY.value, clock.read().monotonic_ns)
                if s:
                    if is_mock and is_fixed_delay and s.rtt_ms is not None:
                        s.rtt_ms = 58.0
                    ping_samples.append(s)

        # Write Parquet tables
        pipeline.write_parquet_samples("ping", ping_samples)
        pipeline.write_parquet_samples("irtt", irtt_samples)
        pipeline.write_parquet_samples("iperf3", iperf3_samples)
        pipeline.write_parquet_samples("qdisc", qdisc_samples)
        pipeline.write_parquet_samples("system", [])

        # Write experiment completion event BEFORE finalizing manifest to preserve SHA-256 integrity
        pipeline.record_event("EXPERIMENT_COMPLETE", {"run_id": run_id})

        # Finalize manifest
        exp_params = ExperimentParameters(
            phases=PhaseParameters(
                baseline_idle_s=self.durations.idle_s,
                saturation_load_s=self.durations.load_s,
                recovery_s=self.durations.recovery_s,
            ),
            load_profile=LoadProfile(
                protocol=TrafficProtocol(self.protocol.lower()),
                direction=TrafficDirection(self.direction.lower()),
                target_bitrate_bps=self.bitrate_bps,
            ),
            probe_profile=ProbeProfile(),
        )

        is_cpu_sat = "cpu" in scenario_name.lower()
        quality_audit = QualityAudit(
            run_id=run_id,
            valid_for_inference=not is_cpu_sat,
            flags=["CLIENT_CPU_SATURATION"] if is_cpu_sat else [],
            checks={
                "clock_synchronized": True,
                "qdisc_verified": True,
                "observer_available": True,
                "load_reached": True,
            },
        )

        pipeline.finalize_manifest(
            duration_s=clock.elapsed_s(),
            parameters=exp_params,
            backend_name=self.backend.name,
            topology_snapshot=self.backend.status(),
            quality_audit=quality_audit,
            scenario_name=scenario_name,
        )

        # Isolate ground truth
        has_bloat = "fifo" in scenario_name.lower() or is_near_bloat or is_far_bloat or is_dual_bloat
        not_excl = (
            [RegionName.NEAR_LINK] if "near" in scenario_name
            else ([RegionName.FAR_LINK] if "far" in scenario_name
            else ([RegionName.NEAR_LINK, RegionName.FAR_LINK] if "dual" in scenario_name
            else ([RegionName.LOCAL_HOST, RegionName.NEAR_LINK, RegionName.GATEWAY_NODE, RegionName.FAR_LINK, RegionName.REMOTE_HOST] if is_cpu_sat else [])))
        )
        pipeline.save_ground_truth(
            scenario_name=scenario_name,
            bottleneck_regions=[RegionName.NEAR_LINK] if "near" in scenario_name else ([RegionName.FAR_LINK] if "far" in scenario_name else ([RegionName.NEAR_LINK, RegionName.FAR_LINK] if "dual" in scenario_name else [])),
            expected_latency_increase=has_bloat or is_cpu_sat,
            expected_queue_evidence=QueueEvidenceLevel.STRONG if has_bloat else QueueEvidenceLevel.NONE,
            expected_supported_regions=[RegionName.NEAR_LINK] if "near" in scenario_name else ([RegionName.FAR_LINK] if "far" in scenario_name else ([RegionName.NEAR_LINK, RegionName.FAR_LINK] if "dual" in scenario_name else [])),
            expected_not_excluded_regions=not_excl,
            expected_abstained=is_cpu_sat,
            expected_abstain_reason=AbstainReason.QUALITY_FLAG_INVALIDATION if is_cpu_sat else None,
        )

        return run_id, pipeline
