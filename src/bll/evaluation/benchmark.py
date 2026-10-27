"""
Double-Blind Benchmark Evaluator (Milestone 6).
src/bll/evaluation/benchmark.py
"""

from __future__ import annotations

import importlib
import json
import logging
import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional

from bll.storage.schemas import (
    BenchmarkSummary,
    ScenarioEvaluationResult,
)

logger = logging.getLogger("bll.evaluation.benchmark")


def evaluate_benchmark_suite(
    runs_dir: Path | str,
    ground_truth_dir: Path | str,
    algorithm_import_path: str = "bll.inference.engine:run_inference",
) -> BenchmarkSummary:
    """Evaluates inference algorithms against physically isolated reference ground truth."""
    runs_path = Path(runs_dir)
    gt_path = Path(ground_truth_dir)

    # 1. Dynamically import and instantiate algorithm under evaluation
    if ":" in algorithm_import_path:
        mod_name, target_name = algorithm_import_path.split(":", 1)
    else:
        mod_name, target_name = algorithm_import_path.rsplit(".", 1)

    try:
        mod = importlib.import_module(mod_name)
        target = getattr(mod, target_name)
        if callable(target):
            if isinstance(target, type):
                inst = target()
                infer_fn = getattr(inst, "infer", inst)
            else:
                infer_fn = target
        else:
            raise TypeError(f"Target {target_name} in {mod_name} is not callable")
    except Exception as e:
        logger.error(f"Failed to load inference algorithm from '{algorithm_import_path}': {e}")
        raise

    if not runs_path.exists():
        run_dirs = []
    else:
        run_dirs = sorted([d for d in runs_path.iterdir() if d.is_dir()])

    if not run_dirs:
        return BenchmarkSummary(
            total_runs=0,
            conditional_localization_error=0.0,
            region_set_coverage=0.0,
            negative_control_fpr=0.0,
            decision_coverage=0.0,
            median_candidate_reduction=0.0,
            hypotheses_results={
                "H1_observer_marginal_value": {
                    "supported": False,
                    "status": "not_evaluated",
                    "reason": "No experiment runs found to evaluate",
                    "statistical_validation": "deferred_to_large_sample_trials",
                },
                "H2_abstention_on_indistinguishable_pairs": {
                    "supported": False,
                    "status": "not_evaluated",
                    "reason": "No experiment runs found to evaluate",
                    "statistical_validation": "deferred_to_large_sample_trials",
                },
                "H3_protocol_discrepancy_icmp_vs_tcp": {
                    "supported": False,
                    "status": "not_evaluated",
                    "reason": "No experiment runs found to evaluate",
                    "statistical_validation": "deferred_to_large_sample_trials",
                },
            },
            gate_passed=False,
        )

    results: List[ScenarioEvaluationResult] = []
    total_runs = len(run_dirs)
    false_positives = 0
    negative_controls = 0
    localization_errors = 0
    non_abstained = 0
    coverage_hits = 0
    candidate_reductions: List[float] = []
    paired_candidate_diffs: List[float] = []
    indistinguishable_runs = 0
    indistinguishable_abstained = 0
    protocol_diffs: List[float] = []
    synthetic_expected_diffs: List[float] = []

    for r_dir in run_dirs:
        run_id = r_dir.name
        gt_file = gt_path / f"{run_id}.json"

        # Execute unprivileged inference (zero access to ground truth)
        try:
            verdict = infer_fn(r_dir, vantage_profile="full_observer")
        except Exception as e:
            logger.warning(f"Inference execution failed on {run_id}: {e}")
            continue

        # Execute unprivileged inference with remote-only vantage (to evaluate observer marginal value)
        try:
            verdict_remote = infer_fn(r_dir, vantage_profile="remote_only")
        except Exception:
            verdict_remote = None

        gt_data: Dict[str, Any] = {}
        if gt_file.exists():
            try:
                gt_data = json.loads(gt_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        expected_regions = gt_data.get("bottleneck_regions", [])
        if not expected_regions and gt_data.get("bottleneck_region"):
            expected_regions = [gt_data["bottleneck_region"]]
        expected_latency = gt_data.get("expected_latency_increase", False)
        injected_delay = float(gt_data.get("injected_queue_delay_ms", 0.0))

        # Check indistinguishable / ambiguous scenario
        sc_id = str(gt_data.get("scenario_id", "") or r_dir.name).lower()
        if "indistinguishable" in sc_id or len(expected_regions) > 1:
            indistinguishable_runs += 1
            if verdict.abstained:
                indistinguishable_abstained += 1

        # Check protocol discrepancy strictly from paired empirical ICMP and TCP telemetry
        if "discrepancy" in sc_id:
            measured_diff: Optional[float] = None
            ping_parquet = r_dir / "samples" / "ping.parquet"
            iperf3_parquet = r_dir / "samples" / "iperf3.parquet"
            tcp_probe_parquet = r_dir / "samples" / "tcp_probe.parquet"
            if ping_parquet.exists() and (iperf3_parquet.exists() or tcp_probe_parquet.exists()):
                try:
                    import duckdb
                    con = duckdb.connect(":memory:")
                    rows = con.execute(f"""
                        SELECT phase, median(rtt_ms)
                        FROM read_parquet('{ping_parquet.as_posix()}')
                        WHERE rtt_ms IS NOT NULL
                        GROUP BY phase
                    """).fetchall()
                    ph_map = {str(r[0]).lower(): float(r[1]) for r in rows if r[1] is not None}
                    idle_icmp = ph_map.get("idle") if "idle" in ph_map else ph_map.get("baseline_idle")
                    load_icmp = ph_map.get("load") if "load" in ph_map else ph_map.get("saturation_load")

                    tcp_load_rtt: Optional[float] = None
                    tcp_idle_rtt: Optional[float] = None
                    for tcp_pq in (iperf3_parquet, tcp_probe_parquet):
                        if not tcp_pq.exists():
                            continue
                        cols = [c[0] for c in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{tcp_pq.as_posix()}')").fetchall()]
                        if "rtt_ms" not in cols or "phase" not in cols:
                            continue
                        tcp_rows = con.execute(f"""
                            SELECT phase, median(rtt_ms)
                            FROM read_parquet('{tcp_pq.as_posix()}')
                            WHERE rtt_ms IS NOT NULL
                            GROUP BY phase
                        """).fetchall()
                        tcp_map = {str(r[0]).lower(): float(r[1]) for r in tcp_rows if r[1] is not None}
                        t_load = tcp_map.get("load") if "load" in tcp_map else tcp_map.get("saturation_load")
                        t_idle = tcp_map.get("idle") if "idle" in tcp_map else tcp_map.get("baseline_idle")
                        if t_load is not None:
                            tcp_load_rtt = t_load
                            tcp_idle_rtt = t_idle
                            break

                    if idle_icmp is not None and load_icmp is not None and tcp_load_rtt is not None:
                        icmp_delta = max(0.0, load_icmp - idle_icmp)
                        base_tcp = tcp_idle_rtt if tcp_idle_rtt is not None else idle_icmp
                        tcp_delta = max(0.0, tcp_load_rtt - base_tcp)
                        if tcp_delta > 0.0 and tcp_delta >= icmp_delta:
                            measured_diff = round(((tcp_delta - icmp_delta) / tcp_delta) * 100.0, 1)
                except Exception:
                    pass

            if measured_diff is not None:
                protocol_diffs.append(measured_diff)

            # Record scenario injection expectations separately (never used as empirical measurement)
            inj_params = gt_data.get("injected_parameters", {})
            icmp_inj = gt_data.get("injected_icmp_delay_ms") if "injected_icmp_delay_ms" in gt_data else inj_params.get("injected_icmp_delay_ms")
            tcp_inj = gt_data.get("injected_tcp_delay_ms") if "injected_tcp_delay_ms" in gt_data else (inj_params.get("injected_tcp_delay_ms") or gt_data.get("injected_queue_delay_ms") or inj_params.get("injected_queue_delay_ms"))
            if icmp_inj is not None and tcp_inj is not None:
                icmp_inj_f = float(icmp_inj)
                tcp_inj_f = float(tcp_inj or 0.0)
                if tcp_inj_f > 0.0 and icmp_inj_f >= 0.0 and tcp_inj_f > icmp_inj_f:
                    synthetic_expected_diffs.append(round(((tcp_inj_f - icmp_inj_f) / tcp_inj_f) * 100.0, 1))

        # Candidate set reduction against 5-region topology
        cand_size = len(verdict.not_excluded_regions) if verdict.abstained else max(1, len(verdict.supported_regions))
        candidate_reductions.append(max(0.0, (5.0 - cand_size) / 5.0))

        if verdict_remote is not None:
            cand_size_remote = len(verdict_remote.not_excluded_regions) if verdict_remote.abstained else max(1, len(verdict_remote.supported_regions))
            paired_candidate_diffs.append(float(cand_size_remote - cand_size))

        is_neg_ctrl = (not expected_latency and injected_delay <= 0.0) or len(expected_regions) == 0
        if is_neg_ctrl:
            negative_controls += 1
            if verdict.latency_increase_observed or len(verdict.supported_regions) > 0:
                false_positives += 1
        else:
            if not verdict.abstained:
                non_abstained += 1
                supported_names = set(r.value if hasattr(r, "value") else str(r) for r in verdict.supported_regions)
                expected_names = set(r.value if hasattr(r, "value") else str(r) for r in expected_regions)
                if not supported_names.intersection(expected_names):
                    localization_errors += 1

            # Region-set coverage: ground truth must be in not_excluded_regions (or supported if not abstained)
            all_not_excl = set(r.value if hasattr(r, "value") else str(r) for r in verdict.not_excluded_regions)
            if not verdict.abstained and verdict.supported_regions:
                all_not_excl.update(r.value if hasattr(r, "value") else str(r) for r in verdict.supported_regions)
            expected_names = set(r.value if hasattr(r, "value") else str(r) for r in expected_regions)
            if any(r in all_not_excl for r in expected_names):
                coverage_hits += 1

    cle = (localization_errors / max(1, non_abstained)) if non_abstained > 0 else 0.0
    active_bottlenecks = total_runs - negative_controls
    rsc = (coverage_hits / max(1, active_bottlenecks)) if active_bottlenecks > 0 else 1.0
    fpr = (false_positives / max(1, negative_controls)) if negative_controls > 0 else 0.0
    dc = (non_abstained / max(1, total_runs)) if total_runs > 0 else 0.0
    med_csr = statistics.median(candidate_reductions) if candidate_reductions else 0.0

    gate_passed = (cle <= 0.10) and (rsc >= 0.95) and (fpr <= 0.05) and (total_runs > 0)

    # 1. Descriptive Empirical Evaluation H1: Observer Marginal Value (Candidate Reduction)
    if paired_candidate_diffs and any(d > 0 for d in paired_candidate_diffs):
        pos_reductions = [d for d in paired_candidate_diffs if d > 0]
        h1_supported = bool(len(pos_reductions) > 0 and rsc >= 0.95 and cle <= 0.10 and med_csr > 0.0)
        h1_status = "empirically_supported" if h1_supported else "inconclusive"
        h1_note = (
            "Candidate set reduction observed empirically across evaluated runs. Inferential p-values and confidence intervals deferred to high-sample controlled trials (N >= 30)."
            if h1_supported
            else "Observer candidate reduction evaluated, but coverage or localization error thresholds were not met."
        )
    else:
        pos_reductions = []
        h1_supported = False
        h1_status = "not_evaluated"
        h1_note = "No paired observer-vs-remote candidate reductions available to evaluate."

    # 2. Descriptive Empirical Evaluation H2: Abstention on Indistinguishable Pairs
    if indistinguishable_runs > 0:
        abst_rate = round(indistinguishable_abstained / indistinguishable_runs, 4)
        h2_supported = bool(abst_rate >= 0.80)
        h2_status = "empirically_supported" if h2_supported else "inconclusive"
        h2_note = (
            "Abstention on ambiguous topologies observed empirically. Formal statistical hypothesis testing (p < 0.05) deferred to multi-repetition trials (N >= 5)."
            if h2_supported
            else "Indistinguishable topology runs evaluated, but abstention rate was below threshold."
        )
    else:
        abst_rate = 0.0
        h2_supported = False
        h2_status = "not_evaluated"
        h2_note = "No indistinguishable topology runs available to evaluate."

    # 3. Descriptive Empirical Evaluation H3: Protocol Discrepancy (ICMP vs TCP under AQM)
    expected_synthetic_pct: Optional[float] = (
        round(sum(synthetic_expected_diffs) / len(synthetic_expected_diffs), 1)
        if synthetic_expected_diffs
        else None
    )
    if protocol_diffs:
        mean_diff: Optional[float] = round(sum(protocol_diffs) / len(protocol_diffs), 1)
        h3_supported = bool(mean_diff > 50.0)
        h3_status = "empirically_observed" if h3_supported else "inconclusive"
        h3_note = (
            "Flow-queue isolation between sparse ICMP probes and saturation TCP stream observed empirically from paired ICMP and TCP RTT telemetry. Inferential statistical significance testing deferred to live multi-protocol testbed."
            if h3_supported
            else "Comparable ICMP and TCP RTT telemetry evaluated, but measured protocol discrepancy did not exceed threshold."
        )
    else:
        mean_diff = None
        h3_supported = False
        h3_status = "not_evaluated"
        h3_note = (
            "Comparable empirical ICMP and TCP RTT telemetry not available in run samples; scenario injection parameters (if present) are reported separately as expected_synthetic_underestimation_pct and do not constitute empirical observation."
        )

    hypotheses_results = {
        "H1_observer_marginal_value": {
            "supported": h1_supported,
            "status": h1_status,
            "total_runs": total_runs,
            "paired_runs_evaluated": len(paired_candidate_diffs),
            "positive_reduction_runs": len(pos_reductions),
            "observed_candidate_reductions": paired_candidate_diffs,
            "candidate_reduction_median": round(med_csr, 4),
            "region_set_coverage": round(rsc, 4),
            "conditional_localization_error": round(cle, 4),
            "statistical_validation": "deferred_to_large_sample_trials",
            "note": h1_note,
        },
        "H2_abstention_on_indistinguishable_pairs": {
            "supported": h2_supported,
            "status": h2_status,
            "indistinguishable_runs": indistinguishable_runs,
            "indistinguishable_abstained": indistinguishable_abstained,
            "abstention_rate": abst_rate,
            "decision_coverage": round(dc, 4),
            "false_positive_rate": round(fpr, 4),
            "statistical_validation": "deferred_to_large_sample_trials",
            "note": h2_note,
        },
        "H3_protocol_discrepancy_icmp_vs_tcp": {
            "supported": h3_supported,
            "status": h3_status,
            "discrepancy_runs_evaluated": len(protocol_diffs),
            "icmp_delay_underestimation_pct": mean_diff,
            "expected_synthetic_underestimation_pct": expected_synthetic_pct,
            "statistical_validation": "deferred_to_large_sample_trials",
            "note": h3_note,
        },
    }

    return BenchmarkSummary(
        total_runs=total_runs,
        conditional_localization_error=round(cle, 4),
        region_set_coverage=round(rsc, 4),
        negative_control_fpr=round(fpr, 4),
        decision_coverage=round(dc, 4),
        median_candidate_reduction=round(med_csr, 4),
        hypotheses_results=hypotheses_results,
        gate_passed=gate_passed,
    )
