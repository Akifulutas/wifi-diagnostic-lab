"""Statistical analysis pipeline generating run summaries and sample tables."""

from __future__ import annotations

import csv
from datetime import datetime
import json
import statistics
from pathlib import Path
from typing import Optional

from wifi_lab.models import Outcome, Phase, RunManifest, RunSummaryRow
from wifi_lab.parsers.iperf import parse_iperf_json
from wifi_lab.parsers.ping_macos import parse_macos_ping
from wifi_lab.plots import generate_all_figures


def run_analysis_pipeline(input_dir: Path, output_dir: Path, figures_dir: Path) -> int:
    """Processes all raw runs in input_dir, creates CSV summaries, and produces figures."""
    if not input_dir.is_dir():
        print(f"\033[91mError: Input directory {input_dir} not found.\033[0m")
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    summary_rows: list[RunSummaryRow] = []
    all_rtt_samples: list[dict] = []

    run_dirs = sorted([d for d in input_dir.iterdir() if d.is_dir()])
    if not run_dirs:
        print(f"\033[93mNo run directories found in {input_dir}\033[0m")
        return 0

    print("=" * 72)
    print(f"  Wi-Fi Diagnostic Lab — Analysis Pipeline")
    print(f"  Input: {input_dir} ({len(run_dirs)} runs discovered)")
    print(f"  Output: {output_dir} | Figures: {figures_dir}")
    print("=" * 72)

    for r_dir in run_dirs:
        manifest_path = r_dir / "manifest.json"
        if not manifest_path.is_file():
            continue

        try:
            m_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[WARN] Skipping unreadable manifest in {r_dir}: {e}")
            continue

        probes_csv_path = r_dir / "probes.csv"
        # Support live home telemetry format (probes.csv / wifi_telemetry manifest)
        if "wifi_telemetry" in m_data or probes_csv_path.is_file():
            run_id = m_data.get("run_id", r_dir.name)
            pos_id = m_data.get("position", "L1" if "L2" not in run_id else "L2")
            net_info = m_data.get("network", {})
            tp = float(net_info.get("load_throughput_mbps", 0.0))
            stats = m_data.get("statistics", {})
            e2e = stats.get("end_to_end", {})

            if probes_csv_path.is_file():
                try:
                    with open(probes_csv_path, "r", encoding="utf-8") as f:
                        rows = list(csv.DictReader(f))
                        t_start: datetime | None = None
                        for row in rows:
                            ts_str = row.get("timestamp_utc", "")
                            if ts_str:
                                try:
                                    t_val = datetime.fromisoformat(ts_str)
                                    if t_start is None or t_val < t_start:
                                        t_start = t_val
                                except Exception:
                                    pass

                        for row in rows:
                            if "remote" in row.get("target_name", "").lower() or "1.1.1.1" in row.get("target_ip", ""):
                                rtt_val = float(row["rtt_ms"]) if row.get("rtt_ms") else None
                                rel_s = 0.0
                                if t_start and row.get("timestamp_utc"):
                                    try:
                                        t_probe = datetime.fromisoformat(row["timestamp_utc"])
                                        rel_s = round((t_probe - t_start).total_seconds(), 3)
                                    except Exception:
                                        rel_s = 0.0

                                all_rtt_samples.append({
                                    "run_id": run_id,
                                    "seq": int(row.get("seq", 0)),
                                    "timestamp_rel_s": rel_s,
                                    "phase": row.get("phase", "idle"),
                                    "rtt_ms": rtt_val if rtt_val is not None else "",
                                    "is_boundary_guarded": False,
                                })
                except Exception:
                    pass

            idle_med = e2e.get("idle", {}).get("median_ms")
            idle_p95 = e2e.get("idle", {}).get("p95_ms")
            load_med = e2e.get("load", {}).get("median_ms")
            load_p95 = e2e.get("load", {}).get("p95_ms")
            recv_med = e2e.get("recovery", {}).get("median_ms")
            delta_med = e2e.get("delta_median_ms")
            total_probes = sum(e2e.get(p, {}).get("count", 0) for p in ("idle", "load", "recovery"))

            outcome_val = "ok" if tp > 0.0 else "failed_load"
            fail_msg = "" if tp > 0.0 else "Throughput reached 0.0 Mbps (load generation incomplete)"

            row = RunSummaryRow(
                run_id=run_id,
                day_label="live_home",
                position_id=pos_id,
                direction="download",
                repetition=1,
                outcome=outcome_val,
                receiver_throughput_mbps=tp,
                sender_throughput_mbps=tp,
                tcp_retransmits=0,
                idle_rtt_median_ms=round(idle_med, 3) if idle_med is not None else None,
                idle_rtt_p95_ms=round(idle_p95, 3) if idle_p95 is not None else None,
                loaded_rtt_median_ms=round(load_med, 3) if load_med is not None else None,
                loaded_rtt_p95_ms=round(load_p95, 3) if load_p95 is not None else None,
                recovery_rtt_median_ms=round(recv_med, 3) if recv_med is not None else None,
                delta_rtt_median_ms=round(delta_med, 3) if delta_med is not None else None,
                sent_probes=total_probes,
                received_probes=total_probes,
                loss_rate_pct=0.0,
                failure_reason=fail_msg,
            )
            summary_rows.append(row)
            continue

        try:
            manifest = RunManifest.from_dict(m_data)
        except Exception as e:
            print(f"[WARN] Skipping corrupted manifest in {r_dir}: {e}")
            continue

        iperf_file = r_dir / manifest.raw_files.get("iperf", "iperf_raw.json")
        ping_file = r_dir / manifest.raw_files.get("ping", "ping_raw.txt")

        # Parse Ping output
        ping_summary = None
        if ping_file.is_file():
            ping_text = ping_file.read_text(encoding="utf-8")
            ping_summary = parse_macos_ping(
                raw_text=ping_text,
                run_id=manifest.run_id,
                idle_s=manifest.condition.idle_duration_s,
                warmup_s=manifest.condition.warmup_duration_s,
                load_s=manifest.condition.load_duration_s,
                recovery_s=manifest.condition.recovery_duration_s,
                boundary_guard_s=1.0,
                nominal_interval_s=manifest.condition.ping_interval_s,
            )
            # Accumulate samples
            for s in ping_summary.samples:
                all_rtt_samples.append({
                    "run_id": s.run_id,
                    "seq": s.seq,
                    "timestamp_rel_s": s.timestamp_rel_s,
                    "phase": s.phase.value,
                    "rtt_ms": s.rtt_ms if s.rtt_ms is not None else "",
                    "is_boundary_guarded": s.is_boundary_guarded,
                })

        # Parse iperf3 output if run succeeded
        iperf_res = None
        if manifest.outcome == Outcome.OK and iperf_file.is_file():
            try:
                iperf_text = iperf_file.read_text(encoding="utf-8")
                iperf_res = parse_iperf_json(iperf_text, expected_direction=manifest.condition.direction.value)
            except Exception as e:
                manifest.outcome = Outcome.PARSE_ERROR
                manifest.failure_reason = f"Failed to parse iperf JSON: {e}"

        # Calculate phase-specific RTT metrics (excluding boundary-guarded probes)
        idle_rtts: list[float] = []
        loaded_rtts: list[float] = []
        recovery_rtts: list[float] = []

        if ping_summary:
            for s in ping_summary.samples:
                if s.is_boundary_guarded or s.rtt_ms is None:
                    continue
                if s.phase == Phase.IDLE:
                    idle_rtts.append(s.rtt_ms)
                elif s.phase == Phase.LOAD:
                    loaded_rtts.append(s.rtt_ms)
                elif s.phase == Phase.RECOVERY:
                    recovery_rtts.append(s.rtt_ms)

        idle_med = statistics.median(idle_rtts) if idle_rtts else None
        idle_p95 = _calculate_p95(idle_rtts) if idle_rtts else None

        loaded_med = statistics.median(loaded_rtts) if loaded_rtts else None
        loaded_p95 = _calculate_p95(loaded_rtts) if loaded_rtts else None

        recovery_med = statistics.median(recovery_rtts) if recovery_rtts else None

        delta_rtt = (loaded_med - idle_med) if (loaded_med is not None and idle_med is not None) else None

        row = RunSummaryRow(
            run_id=manifest.run_id,
            day_label=manifest.day_label,
            position_id=manifest.condition.position_id,
            direction=manifest.condition.direction.value,
            repetition=manifest.repetition_index,
            outcome=manifest.outcome.value,
            receiver_throughput_mbps=iperf_res.receiver_mbps if iperf_res else None,
            sender_throughput_mbps=iperf_res.sender_mbps if iperf_res else None,
            tcp_retransmits=iperf_res.retransmits if iperf_res else None,
            idle_rtt_median_ms=round(idle_med, 3) if idle_med else None,
            idle_rtt_p95_ms=round(idle_p95, 3) if idle_p95 else None,
            loaded_rtt_median_ms=round(loaded_med, 3) if loaded_med else None,
            loaded_rtt_p95_ms=round(loaded_p95, 3) if loaded_p95 else None,
            recovery_rtt_median_ms=round(recovery_med, 3) if recovery_med else None,
            delta_rtt_median_ms=round(delta_rtt, 3) if delta_rtt is not None else None,
            sent_probes=ping_summary.transmitted if ping_summary else 0,
            received_probes=ping_summary.received if ping_summary else 0,
            loss_rate_pct=ping_summary.loss_rate_pct if ping_summary else 0.0,
            failure_reason=manifest.failure_reason or "",
        )
        summary_rows.append(row)

    # Write run_summary.csv
    summary_csv_path = output_dir / "run_summary.csv"
    with open(summary_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "run_id", "day_label", "position_id", "direction", "repetition", "outcome",
            "receiver_throughput_mbps", "sender_throughput_mbps", "tcp_retransmits",
            "idle_rtt_median_ms", "idle_rtt_p95_ms", "loaded_rtt_median_ms", "loaded_rtt_p95_ms",
            "recovery_rtt_median_ms", "delta_rtt_median_ms", "sent_probes", "received_probes",
            "loss_rate_pct", "failure_reason",
        ])
        for r in summary_rows:
            writer.writerow([
                r.run_id, r.day_label, r.position_id, r.direction, r.repetition, r.outcome,
                r.receiver_throughput_mbps if r.receiver_throughput_mbps is not None else "",
                r.sender_throughput_mbps if r.sender_throughput_mbps is not None else "",
                r.tcp_retransmits if r.tcp_retransmits is not None else "",
                r.idle_rtt_median_ms if r.idle_rtt_median_ms is not None else "",
                r.idle_rtt_p95_ms if r.idle_rtt_p95_ms is not None else "",
                r.loaded_rtt_median_ms if r.loaded_rtt_median_ms is not None else "",
                r.loaded_rtt_p95_ms if r.loaded_rtt_p95_ms is not None else "",
                r.recovery_rtt_median_ms if r.recovery_rtt_median_ms is not None else "",
                r.delta_rtt_median_ms if r.delta_rtt_median_ms is not None else "",
                r.sent_probes, r.received_probes, r.loss_rate_pct, r.failure_reason,
            ])

    # Write rtt_samples.csv
    rtt_csv_path = output_dir / "rtt_samples.csv"
    with open(rtt_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["run_id", "seq", "timestamp_rel_s", "phase", "rtt_ms", "is_boundary_guarded"])
        for s in all_rtt_samples:
            writer.writerow([s["run_id"], s["seq"], s["timestamp_rel_s"], s["phase"], s["rtt_ms"], s["is_boundary_guarded"]])

    print(f"Generated: {summary_csv_path} ({len(summary_rows)} rows)")
    print(f"Generated: {rtt_csv_path} ({len(all_rtt_samples)} sample records)")

    # Produce research figures
    print("-" * 72)
    print("Generating 4 publication-quality research figures...")
    generate_all_figures(summary_csv_path, rtt_csv_path, figures_dir)
    print("-" * 72)
    print("Analysis pipeline successfully finished!")
    return 0


def _calculate_p95(data: list[float]) -> float:
    if not data:
        return 0.0
    if len(data) == 1:
        return data[0]
    sorted_data = sorted(data)
    # 95th percentile index
    idx = int(0.95 * len(sorted_data))
    return sorted_data[min(idx, len(sorted_data) - 1)]
