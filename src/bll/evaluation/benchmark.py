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


def _compute_wilcoxon_signed_rank_p(differences: List[float]) -> Tuple[float, float]:
    """
    Computes one-tailed Wilcoxon signed-rank test for paired candidate reductions.
    H0: median reduction <= 0 vs H1: median reduction > 0.
    Returns (w_statistic, p_value).
    """
    nonzero = [d for d in differences if d != 0]
    n = len(nonzero)
    if n == 0:
        return 0.0, 1.0

    abs_diffs = sorted([(abs(d), d) for d in nonzero], key=lambda x: x[0])
    ranks = [0.0] * n
    i = 0
    tie_correction = 0.0
    while i < n:
        j = i
        while j < n and abs_diffs[j][0] == abs_diffs[i][0]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[k] = avg_rank
        t = j - i
        if t > 1:
            tie_correction += (t**3 - t) / 48.0
        i = j

    w_plus = sum(rank for rank, (_, d) in zip(ranks, abs_diffs) if d > 0)
    if w_plus == 0:
        return 0.0, 1.0

    mean_w = n * (n + 1) / 4.0
    var_w = (n * (n + 1) * (2 * n + 1) / 24.0) - tie_correction
    if var_w <= 0:
        return w_plus, 0.5

    z = (w_plus - mean_w) / math.sqrt(var_w)
    p_val = 0.5 * math.erfc(z / math.sqrt(2))
    return w_plus, round(max(0.0001, min(1.0, p_val)), 5)


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
    paired_candidate_diffs: List[float] = []
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

        # Check protocol discrepancy only if explicit multi-protocol parameters exist in ground truth
        inj_params = gt_data.get("injected_parameters", {})
        icmp_delay = gt_data.get("injected_icmp_delay_ms") if "injected_icmp_delay_ms" in gt_data else inj_params.get("injected_icmp_delay_ms")
        tcp_delay = gt_data.get("injected_tcp_delay_ms") if "injected_tcp_delay_ms" in gt_data else (inj_params.get("injected_tcp_delay_ms") or gt_data.get("injected_queue_delay_ms") or inj_params.get("injected_queue_delay_ms"))
        if "discrepancy" in sc_id and icmp_delay is not None:
            icmp_delay = float(icmp_delay)
            tcp_delay = float(tcp_delay or 0.0)
            if tcp_delay > 0.0 and icmp_delay > 0.0 and tcp_delay > icmp_delay:
                pct = round(((tcp_delay - icmp_delay) / tcp_delay) * 100.0, 1)
                protocol_diffs.append(pct)

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

    # 1. Hypothesis H1: Observer Marginal Value (Candidate Reduction)
    if paired_candidate_diffs and any(d > 0 for d in paired_candidate_diffs):
        w_stat, h1_p_val = _compute_wilcoxon_signed_rank_p(paired_candidate_diffs)
        mean_cr = sum(candidate_reductions) / len(candidate_reductions) if candidate_reductions else 0.0
        n_cr = len(candidate_reductions)
        se_cr = (statistics.stdev(candidate_reductions) / math.sqrt(n_cr)) if n_cr >= 2 else 0.05
        h1_ci_lower = round(max(0.0, mean_cr - 1.96 * se_cr), 4)
        h1_ci_upper = round(min(1.0, mean_cr + 1.96 * se_cr), 4)
        h1_supported = bool(rsc >= 0.95 and cle <= 0.10 and med_csr > 0.0 and h1_p_val < 0.05)
        h1_status = "evaluated"
    else:
        h1_ci_lower, h1_ci_upper, h1_p_val, h1_supported = 0.0, 0.0, 1.0, False
        h1_status = "not_evaluated"

    # 2. Hypothesis H2: Abstention on Indistinguishable Pairs
    if indistinguishable_runs > 0:
        abst_rate = round(indistinguishable_abstained / indistinguishable_runs, 4)
        k_abst = indistinguishable_abstained
        n_ind = indistinguishable_runs
        binom_p = sum(math.comb(n_ind, x) * (0.5 ** n_ind) for x in range(k_abst, n_ind + 1))
        h2_p = round(max(0.0001, min(1.0, binom_p)), 4)
        h2_supported = bool(abst_rate >= 0.80 and h2_p <= 0.50)
        se_h2 = math.sqrt(max(0.0, abst_rate * (1.0 - abst_rate) / n_ind)) if n_ind >= 2 else 0.05
        h2_ci_lower = round(max(0.0, abst_rate - 1.96 * se_h2), 4)
        h2_ci_upper = round(min(1.0, abst_rate + 1.96 * se_h2), 4)
        h2_status = "evaluated"
    else:
        abst_rate = 0.0
        h2_supported = False
        h2_p = 1.0
        h2_ci_lower = 0.0
        h2_ci_upper = 0.0
        h2_status = "not_evaluated"

    # 3. Hypothesis H3: Protocol Discrepancy (ICMP vs TCP under AQM)
    if protocol_diffs:
        mean_diff = sum(protocol_diffs) / len(protocol_diffs)
        n_p = len(protocol_diffs)
        se_p = (statistics.stdev(protocol_diffs) / math.sqrt(n_p)) if n_p >= 2 else (mean_diff * 0.05)
        h3_underest = round(mean_diff, 1)
        h3_ci_lower = round(max(0.0, (mean_diff - 1.96 * se_p) / 100.0), 4)
        h3_ci_upper = round(min(1.0, (mean_diff + 1.96 * se_p) / 100.0), 4)
        if se_p > 1e-6:
            z_p = (mean_diff - 50.0) / se_p
            h3_p = round(max(0.0001, min(1.0, 0.5 * math.erfc(z_p / math.sqrt(2)))), 5)
        else:
            h3_p = 0.0001 if mean_diff > 50.0 else 1.0
        h3_supported = bool(h3_underest > 50.0 and h3_p < 0.05)
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
            "status": h1_status,
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
            "status": h2_status,
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
