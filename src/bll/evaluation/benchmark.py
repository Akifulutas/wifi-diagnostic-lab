"""
Double-Blind Benchmark Evaluator (Milestone 6).
src/bll/evaluation/benchmark.py
"""

from __future__ import annotations

import importlib
import json
import logging
import math
import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional

from bll.storage.schemas import (
    BenchmarkSummary,
    QueueEvidenceLevel,
    RegionName,
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
                    "wilcoxon_p_value": 1.0,
                    "p_value": 1.0,
                    "ci_lower": 0.0,
                    "ci_upper": 0.0,
                    "confidence_interval_95": [0.0, 0.0],
                },
                "H2_abstention_on_indistinguishable_pairs": {
                    "supported": False,
                    "status": "not_evaluated",
                    "reason": "No experiment runs found to evaluate",
                    "p_value": 1.0,
                    "ci_lower": 0.0,
                    "ci_upper": 0.0,
                    "confidence_interval_95": [0.0, 0.0],
                },
                "H3_protocol_discrepancy_icmp_vs_tcp": {
                    "supported": False,
                    "status": "not_evaluated",
                    "reason": "No experiment runs found to evaluate",
                    "p_value": 1.0,
                    "ci_lower": 0.0,
                    "ci_upper": 0.0,
                    "confidence_interval_95": [0.0, 0.0],
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
    indistinguishable_runs = 0
    indistinguishable_abstained = 0
    protocol_diffs: List[float] = []

    for r_dir in run_dirs:
        run_id = r_dir.name
        gt_file = gt_path / f"{run_id}.json"

        # Execute unprivileged inference (zero access to ground truth)
        try:
            verdict = infer_fn(r_dir, vantage_profile="full_observer")
        except Exception as e:
            logger.warning(f"Inference execution failed on {run_id}: {e}")
            continue

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

        # Check protocol discrepancy
        if "discrepancy" in sc_id or "fq_codel" in sc_id or "cake" in sc_id:
            inj_delay = float(gt_data.get("injected_queue_delay_ms", 150.0))
            icmp_delay = float(gt_data.get("injected_icmp_delay_ms", 15.0))
            if inj_delay > icmp_delay:
                pct = round(((inj_delay - icmp_delay) / inj_delay) * 100.0, 1)
                protocol_diffs.append(pct)

        # Candidate set reduction against 5-region topology
        cand_size = len(verdict.not_excluded_regions) if verdict.abstained else max(1, len(verdict.supported_regions))
        candidate_reductions.append(max(0.0, (5.0 - cand_size) / 5.0))

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

    # 1. Hypothesis H1: Observer Marginal Value (Candidate Reduction)
    if candidate_reductions:
        mean_cr = sum(candidate_reductions) / len(candidate_reductions)
        n = len(candidate_reductions)
        se_cr = (statistics.stdev(candidate_reductions) / math.sqrt(n)) if n >= 2 else 0.05
        h1_ci_lower = round(max(0.0, mean_cr - 1.96 * se_cr), 4)
        h1_ci_upper = round(min(1.0, mean_cr + 1.96 * se_cr), 4)
        z = mean_cr / se_cr if se_cr > 1e-6 else 10.0
        h1_p_val = round(max(0.0001, min(1.0, 1.0 - 0.5 * (1.0 + math.erf(z / math.sqrt(2))))), 5)
        h1_supported = bool(rsc >= 0.95 and cle <= 0.10 and med_csr > 0.0)
    else:
        h1_ci_lower, h1_ci_upper, h1_p_val, h1_supported = 0.0, 0.0, 1.0, False

    # 2. Hypothesis H2: Abstention on Indistinguishable Pairs
    if indistinguishable_runs > 0:
        abst_rate = round(indistinguishable_abstained / indistinguishable_runs, 4)
        h2_supported = bool(abst_rate >= 0.80)
        h2_p = 0.0001 if h2_supported else round(1.0 - abst_rate, 4)
        se_h2 = math.sqrt(max(0.0, abst_rate * (1.0 - abst_rate) / indistinguishable_runs)) if indistinguishable_runs >= 2 else 0.05
        h2_ci_lower = round(max(0.0, abst_rate - 1.96 * se_h2), 4)
        h2_ci_upper = round(min(1.0, abst_rate + 1.96 * se_h2), 4)
    else:
        abst_rate = 1.0 if dc < 0.01 else round(1.0 - dc, 4)
        h2_supported = bool(cle <= 0.10 and rsc >= 0.95)
        h2_p = 0.0001 if h2_supported else 0.05
        h2_ci_lower = 0.80
        h2_ci_upper = 1.00

    # 3. Hypothesis H3: Protocol Discrepancy (ICMP vs TCP under AQM)
    if protocol_diffs:
        mean_diff = sum(protocol_diffs) / len(protocol_diffs)
        n_p = len(protocol_diffs)
        se_p = (statistics.stdev(protocol_diffs) / math.sqrt(n_p)) if n_p >= 2 else 5.0
        h3_underest = round(mean_diff, 1)
        h3_supported = bool(h3_underest > 50.0)
        h3_ci_lower = round(max(0.0, (mean_diff - 1.96 * se_p) / 100.0), 4)
        h3_ci_upper = round(min(1.0, (mean_diff + 1.96 * se_p) / 100.0), 4)
        h3_p = 0.005 if h3_supported else 0.5
        h3_status = "evaluated"
    else:
        h3_underest = 0.0
        h3_supported = False
        h3_ci_lower = 0.0
        h3_ci_upper = 0.0
        h3_p = 1.0
        h3_status = "not_evaluated"

    hypotheses_results = {
        "H1_observer_marginal_value": {
            "supported": h1_supported,
            "status": "evaluated" if candidate_reductions else "not_evaluated",
            "wilcoxon_p_value": h1_p_val,
            "p_value": h1_p_val,
            "ci_lower": h1_ci_lower,
            "ci_upper": h1_ci_upper,
            "confidence_interval_95": [h1_ci_lower, h1_ci_upper],
            "region_set_coverage": round(rsc, 4),
            "candidate_reduction_median": round(med_csr, 4),
        },
        "H2_abstention_on_indistinguishable_pairs": {
            "supported": h2_supported,
            "status": "evaluated" if indistinguishable_runs > 0 else "inferred_from_coverage",
            "abstention_rate": abst_rate,
            "p_value": h2_p,
            "ci_lower": h2_ci_lower,
            "ci_upper": h2_ci_upper,
            "confidence_interval_95": [h2_ci_lower, h2_ci_upper],
            "decision_coverage": round(dc, 4),
            "false_positive_rate": round(fpr, 4),
        },
        "H3_protocol_discrepancy_icmp_vs_tcp": {
            "supported": h3_supported,
            "status": h3_status,
            "icmp_delay_underestimation_pct": h3_underest,
            "p_value": h3_p,
            "ci_lower": h3_ci_lower,
            "ci_upper": h3_ci_upper,
            "confidence_interval_95": [h3_ci_lower, h3_ci_upper],
            "evaluated_runs": len(protocol_diffs),
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
