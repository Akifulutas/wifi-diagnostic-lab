"""
Deterministic Inference & Differential Path Algebra Engine (Milestone 4).
src/bll/inference/engine.py

NOTE: In accordance with R4 and R5, this module is strictly prohibited from
reading or accessing files in ground_truth/. Decisions are strictly data-driven
based on RTT telemetry and vantage constraints, with zero scenario_id label leakage.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import duckdb

from bll.storage.schemas import (
    AbstainReason,
    InferenceVerdict,
    QueueEvidenceLevel,
    RegionName,
    VantageProfile,
)

logger = logging.getLogger("bll.inference.engine")


def _extract_path_telemetry(run_path: Path) -> Tuple[Dict[str, float], bool, bool]:
    """Extracts delta RTT per path and detects qdisc queue activity from telemetry tables."""
    deltas: Dict[str, float] = {}
    near_qdisc_active = False
    far_qdisc_active = False

    ping_parquet = run_path / "samples" / "ping.parquet"
    probes_csv = run_path / "probes.csv"
    qdisc_parquet = run_path / "samples" / "qdisc.parquet"

    con = duckdb.connect(":memory:")

    # 1. Ping Parquet Telemetry
    if ping_parquet.exists():
        try:
            schema_info = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{ping_parquet.as_posix()}')").fetchall()
            cols = {row[0].lower() for row in schema_info}
            if "path" in cols:
                query = f"""
                SELECT path, phase,
                       round(median(rtt_ms), 3) as med_rtt,
                       round(quantile_cont(rtt_ms, 0.95), 3) as p95_rtt
                FROM read_parquet('{ping_parquet.as_posix()}')
                WHERE rtt_ms IS NOT NULL
                GROUP BY path, phase
                """
            else:
                query = f"""
                SELECT 'client_to_remote' as path, phase,
                       round(median(rtt_ms), 3) as med_rtt,
                       round(quantile_cont(rtt_ms, 0.95), 3) as p95_rtt
                FROM read_parquet('{ping_parquet.as_posix()}')
                WHERE rtt_ms IS NOT NULL
                GROUP BY phase
                """
            rows = con.execute(query).fetchall()
            path_phases: Dict[str, Dict[str, Dict[str, float]]] = {}
            for row in rows:
                p_name, phase_name, med, p95 = row[0], str(row[1]).lower(), float(row[2]), float(row[3])
                path_phases.setdefault(p_name, {})[phase_name] = {"median": med, "p95": p95}

            for p_name, phases in path_phases.items():
                idle = phases.get("baseline_idle") or phases.get("idle", {})
                load = phases.get("saturation_load") or phases.get("load", {})
                if idle and load:
                    deltas[p_name] = max(0.0, float(load["p95"] - idle["median"]))
                elif load:
                    deltas[p_name] = max(0.0, float(load["p95"]))
        except Exception as e:
            logger.debug(f"Error reading ping.parquet: {e}")

    # 2. Probes CSV Telemetry (Live Home Test fallback)
    elif probes_csv.exists():
        try:
            query = f"""
            SELECT target_name as path, phase,
                   round(median(rtt_ms), 3) as med_rtt,
                   round(quantile_cont(rtt_ms, 0.95), 3) as p95_rtt
            FROM read_csv_auto('{probes_csv.as_posix()}')
            WHERE rtt_ms IS NOT NULL
            GROUP BY target_name, phase
            """
            rows = con.execute(query).fetchall()
            path_phases = {}
            for row in rows:
                p_name, phase_name, med, p95 = row[0], str(row[1]).lower(), float(row[2]), float(row[3])
                path_phases.setdefault(p_name, {})[phase_name] = {"median": med, "p95": p95}

            for p_name, phases in path_phases.items():
                idle = phases.get("baseline_idle") or phases.get("idle", {})
                load = phases.get("saturation_load") or phases.get("load", {})
                if idle and load:
                    deltas[p_name] = max(0.0, float(load["p95"] - idle["median"]))
                elif load:
                    deltas[p_name] = max(0.0, float(load["p95"]))
        except Exception as e:
            logger.debug(f"Error reading probes.csv: {e}")

    # 3. Linux TC Qdisc Statistics
    if qdisc_parquet.exists():
        try:
            q_query = f"""
            SELECT interface, netns, max(backlog_bytes) as max_backlog, max(drops) as max_drops
            FROM read_parquet('{qdisc_parquet.as_posix()}')
            GROUP BY interface, netns
            """
            q_rows = con.execute(q_query).fetchall()
            for r in q_rows:
                iface, nns, backlog, drops = str(r[0]), str(r[1]), (r[2] or 0), (r[3] or 0)
                if backlog > 0 or drops > 0:
                    combined = f"{iface}_{nns}".lower()
                    if "near" in combined:
                        near_qdisc_active = True
                    if "far" in combined:
                        far_qdisc_active = True
        except Exception as e:
            logger.debug(f"Error reading qdisc.parquet: {e}")

    con.close()
    return deltas, near_qdisc_active, far_qdisc_active


def run_inference(
    run_dir: Path | str,
    vantage_profile: str = "full_observer",
) -> InferenceVerdict:
    """Executes deterministic differential path algebra over an immutable run directory.

    Strictly forbids accessing ground_truth/ to prevent label leakage.
    Derives verdicts entirely from telemetry metrics and vantage constraints,
    without any string inspection of scenario_id.
    """
    run_path = Path(run_dir)
    if "ground_truth" in run_path.parts:
        raise PermissionError("Label leakage violation: inference engine cannot access ground_truth/")

    manifest_file = run_path / "manifest.json"
    if not manifest_file.exists():
        raise FileNotFoundError(f"Missing manifest.json in {run_path}")

    manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
    run_id = manifest_data.get("run_id", run_path.name)

    # Deterministic timestamp derived from immutable manifest
    raw_ts = manifest_data.get("timestamp_utc") or manifest_data.get("start_time_utc")
    if raw_ts:
        try:
            ts_utc = datetime.fromisoformat(str(raw_ts).replace("Z", "+00:00"))
        except Exception:
            ts_utc = datetime(2026, 10, 21, 0, 0, 0, tzinfo=timezone.utc)
    else:
        ts_utc = datetime(2026, 10, 21, 0, 0, 0, tzinfo=timezone.utc)

    # Read quality flags if present
    quality_file = run_path / "quality.json"
    quality_flags: List[str] = []
    if quality_file.exists():
        try:
            q_data = json.loads(quality_file.read_text(encoding="utf-8"))
            raw_flags = q_data.get("flags", [])
            if isinstance(raw_flags, list):
                quality_flags = [str(f).upper() for f in raw_flags]
            elif isinstance(raw_flags, dict):
                quality_flags = [k.upper() for k, v in raw_flags.items() if v]
        except Exception:
            pass

    # Normalize vantage profile
    try:
        vantage_enum = VantageProfile(vantage_profile)
    except ValueError:
        vantage_enum = VantageProfile.FULL_OBSERVER

    # 1. Critical Quality Flag Gating (Forces Abstention)
    if "CLIENT_CPU_SATURATION" in quality_flags or "MISSING_PHASE" in quality_flags:
        return InferenceVerdict(
            run_id=run_id,
            timestamp_utc=ts_utc,
            vantage_profile=vantage_enum,
            latency_increase_observed=True,
            load_association=0.0,
            supported_regions=[],
            not_excluded_regions=[
                RegionName.LOCAL_HOST,
                RegionName.NEAR_LINK,
                RegionName.GATEWAY_NODE,
                RegionName.FAR_LINK,
                RegionName.REMOTE_HOST,
            ],
            queue_evidence=QueueEvidenceLevel.NONE,
            quality_flags=quality_flags,
            abstained=True,
            abstain_reason=f"Quality check failure: {','.join(quality_flags)}",
            next_measurement="repeat_test_with_unloaded_cpu",
            supporting_run_ids=[run_id],
        )

    # 2. Extract Data-Driven Telemetry Metrics
    deltas, near_qdisc_active, far_qdisc_active = _extract_path_telemetry(run_path)

    # Empty run guard: missing or zero probe samples must trigger abstention on any run (zero label leakage)
    if not deltas and not near_qdisc_active and not far_qdisc_active:
        return InferenceVerdict(
            run_id=run_id,
            timestamp_utc=ts_utc,
            vantage_profile=vantage_enum,
            latency_increase_observed=False,
            load_association=0.0,
            supported_regions=[],
            not_excluded_regions=[
                RegionName.NEAR_LINK,
                RegionName.GATEWAY_NODE,
                RegionName.FAR_LINK,
            ],
            queue_evidence=QueueEvidenceLevel.NONE,
            quality_flags=quality_flags,
            abstained=True,
            abstain_reason="INSUFFICIENT_TELEMETRY: No valid probe samples found in run",
            next_measurement="repeat_test_with_probing_enabled",
            supporting_run_ids=[run_id],
        )

    # Segregate paths by topological segment
    near_paths = [p for p in deltas if any(k in p.lower() for k in ("near", "gateway", "wifi", "client_to_gateway", "client_to_observer"))]
    far_paths = [p for p in deltas if any(k in p.lower() for k in ("far", "wan", "remote_hop", "observer_to_remote"))]
    e2e_paths = [p for p in deltas if any(k in p.lower() for k in ("client_to_remote", "e2e", "default")) or p.lower() == "remote"]

    delta_near = max([deltas[p] for p in near_paths], default=0.0)
    delta_far = max([deltas[p] for p in far_paths], default=0.0)
    delta_e2e = max([deltas[p] for p in e2e_paths], default=(max(deltas.values(), default=0.0)))
    delta_max = max(delta_near, delta_far, delta_e2e)

    # 3. Bufferbloat Detection Threshold (RFC 2330 / BLL Invariant: Delta RTT <= 5ms is Non-Queue / Clean)
    if delta_max <= 5.0 and not near_qdisc_active and not far_qdisc_active:
        return InferenceVerdict(
            run_id=run_id,
            timestamp_utc=ts_utc,
            vantage_profile=vantage_enum,
            latency_increase_observed=False,
            load_association=0.05,
            supported_regions=[],
            not_excluded_regions=[],
            queue_evidence=QueueEvidenceLevel.NONE,
            quality_flags=quality_flags,
            abstained=False,
            abstain_reason=None,
            next_measurement=None,
            supporting_run_ids=[run_id],
        )

    # 4. Latency Inflation Confirmed
    queue_evidence = QueueEvidenceLevel.STRONG if delta_max > 50.0 else QueueEvidenceLevel.MODERATE
    load_assoc = round(min(0.98, 0.85 + (delta_max / 1000.0)), 2)

    # 5. Differential Path Algebra Filtered by Vantage Profile
    if vantage_enum == VantageProfile.REMOTE_ONLY:
        # Remote-only vantage cannot discriminate near-link, gateway, or far-link queueing
        return InferenceVerdict(
            run_id=run_id,
            timestamp_utc=ts_utc,
            vantage_profile=vantage_enum,
            latency_increase_observed=True,
            load_association=load_assoc,
            supported_regions=[],
            not_excluded_regions=[RegionName.NEAR_LINK, RegionName.GATEWAY_NODE, RegionName.FAR_LINK],
            queue_evidence=queue_evidence,
            quality_flags=quality_flags,
            abstained=True,
            abstain_reason="Ambiguous vantage coverage: remote RTT cannot discriminate between near-link and far-link bottleneck",
            next_measurement="probe_gateway_ping_rtt",
            supporting_run_ids=[run_id],
        )

    elif vantage_enum in (VantageProfile.GATEWAY_REMOTE, VantageProfile.LOCAL_REMOTE):
        # Near vantage available (client-to-gateway)
        if delta_near > 5.0:
            return InferenceVerdict(
                run_id=run_id,
                timestamp_utc=ts_utc,
                vantage_profile=vantage_enum,
                latency_increase_observed=True,
                load_association=load_assoc,
                supported_regions=[RegionName.NEAR_LINK],
                not_excluded_regions=[RegionName.NEAR_LINK],
                queue_evidence=queue_evidence,
                quality_flags=quality_flags,
                abstained=False,
                abstain_reason=None,
                next_measurement=None,
                supporting_run_ids=[run_id],
            )
        else:
            # Downstream bottleneck; gateway vs far link requires wired observer tap
            cand = [RegionName.GATEWAY_NODE, RegionName.FAR_LINK] if delta_far > 5.0 else [RegionName.NEAR_LINK, RegionName.GATEWAY_NODE]
            return InferenceVerdict(
                run_id=run_id,
                timestamp_utc=ts_utc,
                vantage_profile=vantage_enum,
                latency_increase_observed=True,
                load_association=load_assoc,
                supported_regions=[],
                not_excluded_regions=cand,
                queue_evidence=queue_evidence,
                quality_flags=quality_flags,
                abstained=True,
                abstain_reason="Topology ambiguity: cannot distinguish gateway egress vs access link without observer tap",
                next_measurement="deploy_wired_observer_tap",
                supporting_run_ids=[run_id],
            )

    else:
        # FULL_OBSERVER vantage
        if len(far_paths) == 0:
            return InferenceVerdict(
                run_id=run_id,
                timestamp_utc=ts_utc,
                vantage_profile=vantage_enum,
                latency_increase_observed=True,
                load_association=load_assoc,
                supported_regions=[],
                not_excluded_regions=[RegionName.NEAR_LINK, RegionName.GATEWAY_NODE],
                queue_evidence=queue_evidence,
                quality_flags=quality_flags,
                abstained=True,
                abstain_reason="Topology ambiguity: cannot distinguish gateway egress vs access link without observer tap",
                next_measurement="deploy_wired_observer_tap",
                supporting_run_ids=[run_id],
            )

        near_bloat = delta_near > 5.0
        far_bloat = delta_far > 5.0

        if near_bloat and far_bloat:
            supported = [RegionName.NEAR_LINK, RegionName.FAR_LINK]
            return InferenceVerdict(
                run_id=run_id,
                timestamp_utc=ts_utc,
                vantage_profile=vantage_enum,
                latency_increase_observed=True,
                load_association=load_assoc,
                supported_regions=supported,
                not_excluded_regions=supported,
                queue_evidence=queue_evidence,
                quality_flags=quality_flags,
                abstained=False,
                abstain_reason=None,
                next_measurement=None,
                supporting_run_ids=[run_id],
            )
        elif near_bloat and not far_bloat:
            return InferenceVerdict(
                run_id=run_id,
                timestamp_utc=ts_utc,
                vantage_profile=vantage_enum,
                latency_increase_observed=True,
                load_association=load_assoc,
                supported_regions=[RegionName.NEAR_LINK],
                not_excluded_regions=[RegionName.NEAR_LINK],
                queue_evidence=queue_evidence,
                quality_flags=quality_flags,
                abstained=False,
                abstain_reason=None,
                next_measurement=None,
                supporting_run_ids=[run_id],
            )
        elif not near_bloat and far_bloat:
            return InferenceVerdict(
                run_id=run_id,
                timestamp_utc=ts_utc,
                vantage_profile=vantage_enum,
                latency_increase_observed=True,
                load_association=load_assoc,
                supported_regions=[RegionName.FAR_LINK],
                not_excluded_regions=[RegionName.FAR_LINK],
                queue_evidence=queue_evidence,
                quality_flags=quality_flags,
                abstained=False,
                abstain_reason=None,
                next_measurement=None,
                supporting_run_ids=[run_id],
            )
        else:
            # Only end-to-end telemetry was captured; segment probes are missing
            return InferenceVerdict(
                run_id=run_id,
                timestamp_utc=ts_utc,
                vantage_profile=vantage_enum,
                latency_increase_observed=True,
                load_association=load_assoc,
                supported_regions=[],
                not_excluded_regions=[RegionName.NEAR_LINK, RegionName.GATEWAY_NODE, RegionName.FAR_LINK],
                queue_evidence=queue_evidence,
                quality_flags=quality_flags,
                abstained=True,
                abstain_reason="Ambiguous vantage coverage: remote RTT cannot discriminate between near-link and far-link bottleneck",
                next_measurement="probe_gateway_ping_rtt",
                supporting_run_ids=[run_id],
            )


class DeterministicEngine:
    """Class wrapper providing object-oriented inference interface for benchmarks and evaluation."""

    def __init__(self, **kwargs: Any) -> None:
        pass

    def infer(self, run_dir: Path | str, vantage_profile: str = "full_observer") -> InferenceVerdict:
        return run_inference(run_dir=run_dir, vantage_profile=vantage_profile)

    def __call__(self, run_dir: Path | str, vantage_profile: str = "full_observer") -> InferenceVerdict:
        return run_inference(run_dir=run_dir, vantage_profile=vantage_profile)
