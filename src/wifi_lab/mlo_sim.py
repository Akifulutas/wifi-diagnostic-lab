"""Wi-Fi 7 (802.11be) Multi-Link Operation (MLO) latency and scheduling simulation.

Models packet-to-link scheduling across asymmetric channels (e.g. 5 GHz vs. 6 GHz)
demonstrating latency smoothing and tail-delay reduction as described in Carrascosa et al. (2023).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple


@dataclass
class MLOResult:
    total_packets: int
    single_link_median_ms: float
    single_link_p95_ms: float
    single_link_max_ms: float
    mlo_median_ms: float
    mlo_p95_ms: float
    mlo_max_ms: float
    p95_reduction_pct: float
    mlo_throughput_gain_pct: float


def run_mlo_simulation(
    packet_count: int = 2000,
    seed: int = 42,
    output_figure: Path | None = None,
) -> MLOResult:
    """Simulates single-link vs. Wi-Fi 7 MLO (5 GHz + 6 GHz) packet-level latency under asymmetric channel load."""
    rng = random.Random(seed)

    # Channel parameters:
    # Link 1 (5 GHz): 80 MHz, higher background contention (occupancy = 45%), base service time = 0.8 ms
    # Link 2 (6 GHz): 160 MHz, pristine spectrum, lower contention (occupancy = 12%), base service time = 0.4 ms
    p_busy_link1 = 0.45
    p_busy_link2 = 0.12

    service_time_link1 = 0.8  # ms
    service_time_link2 = 0.4  # ms

    # Track link free times
    time_link1_free = 0.0
    time_link2_free = 0.0
    time_single_free = 0.0

    single_link_delays: List[float] = []
    mlo_delays: List[float] = []

    current_arrival = 0.0

    for i in range(packet_count):
        # Bursty packet arrivals (mean inter-arrival = 1.4 ms)
        inter_arrival = rng.expovariate(1.0 / 1.4)
        current_arrival += inter_arrival

        # ---------------------------------------------------------
        # 1. Baseline: Single Link (5 GHz only)
        # ---------------------------------------------------------
        # Contention backoff if channel is busy
        contention_delay_single = rng.uniform(0.3, 1.8) if rng.random() < p_busy_link1 else 0.0
        start_tx_single = max(current_arrival, time_single_free) + contention_delay_single
        finish_tx_single = start_tx_single + service_time_link1 + rng.gauss(0.05, 0.02)
        time_single_free = finish_tx_single
        single_link_delays.append(finish_tx_single - current_arrival)

        # ---------------------------------------------------------
        # 2. Wi-Fi 7 MLO: Joint First-Available-Link Scheduling
        # ---------------------------------------------------------
        contention_delay_l1 = rng.uniform(0.3, 1.8) if rng.random() < p_busy_link1 else 0.0
        contention_delay_l2 = rng.uniform(0.1, 0.6) if rng.random() < p_busy_link2 else 0.0

        avail_l1 = max(current_arrival, time_link1_free) + contention_delay_l1
        avail_l2 = max(current_arrival, time_link2_free) + contention_delay_l2

        if avail_l2 <= avail_l1:
            # Route to Link 2 (6 GHz)
            finish_tx_mlo = avail_l2 + service_time_link2 + rng.gauss(0.05, 0.01)
            time_link2_free = finish_tx_mlo
        else:
            # Route to Link 1 (5 GHz)
            finish_tx_mlo = avail_l1 + service_time_link1 + rng.gauss(0.1, 0.03)
            time_link1_free = finish_tx_mlo

        mlo_delays.append(finish_tx_mlo - current_arrival)

    # Statistical Evaluation
    single_sorted = sorted(single_link_delays)
    mlo_sorted = sorted(mlo_delays)

    single_med = single_sorted[len(single_sorted) // 2]
    single_p95 = single_sorted[int(0.95 * len(single_sorted))]
    single_max = single_sorted[-1]

    mlo_med = mlo_sorted[len(mlo_sorted) // 2]
    mlo_p95 = mlo_sorted[int(0.95 * len(mlo_sorted))]
    mlo_max = mlo_sorted[-1]

    p95_reduction = round((1.0 - (mlo_p95 / single_p95)) * 100.0, 1)
    tp_gain = round(((1.0 / mlo_med) / (1.0 / single_med) - 1.0) * 100.0, 1)

    result = MLOResult(
        total_packets=packet_count,
        single_link_median_ms=round(single_med, 2),
        single_link_p95_ms=round(single_p95, 2),
        single_link_max_ms=round(single_max, 2),
        mlo_median_ms=round(mlo_med, 2),
        mlo_p95_ms=round(mlo_p95, 2),
        mlo_max_ms=round(mlo_max, 2),
        p95_reduction_pct=p95_reduction,
        mlo_throughput_gain_pct=tp_gain,
    )

    print("=" * 72)
    print("  Wi-Fi 7 (802.11be) Multi-Link Operation (MLO) Simulation")
    print(f"  Packets modeled: {packet_count} | Contention: Link 1 (5GHz, 45%), Link 2 (6GHz, 12%)")
    print("=" * 72)
    print(f"  Single Link (Wi-Fi 6 5GHz)  : Median {result.single_link_median_ms} ms | p95 {result.single_link_p95_ms} ms | Max {result.single_link_max_ms} ms")
    print(f"  Wi-Fi 7 MLO (5GHz + 6GHz)   : Median {result.mlo_median_ms} ms | p95 {result.mlo_p95_ms} ms | Max {result.mlo_max_ms} ms")
    print(f"  \033[92mTail Latency (p95) Reduction: -{result.p95_reduction_pct}%\033[0m")
    print("-" * 72)

    if output_figure:
        _render_mlo_figure(single_sorted, mlo_sorted, result, output_figure)
        print(f"  ↳ Rendered MLO publication figure: {output_figure}")

    return result


def _render_mlo_figure(single_sorted: List[float], mlo_sorted: List[float], res: MLOResult, out_path: Path) -> None:
    w, h = 800, 500
    pad_l, pad_r, pad_t, pad_b = 90, 40, 70, 70
    plot_w = w - pad_l - pad_r
    plot_h = h - pad_t - pad_b
    max_x = 15.0  # ms

    def x_to_px(val: float) -> float:
        clamped = min(max_x, max(0.0, val))
        return pad_l + plot_w * (clamped / max_x)

    def y_to_px(prob: float) -> float:
        return pad_t + plot_h * (1.0 - prob)

    svg = [
        f'<svg width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg" style="background:#ffffff;font-family:system-ui,-apple-system,sans-serif;">',
        f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
        f'<text x="{w/2}" y="32" text-anchor="middle" font-size="18" font-weight="bold" fill="#0f172a">Fig 5: Wi-Fi 7 Multi-Link Operation (MLO) vs. Single-Link Latency ECDF</text>',
        f'<text x="{w/2}" y="52" text-anchor="middle" font-size="13" fill="#64748b">Asymmetric Contention Simulation: Link 1 (5GHz, 45% busy) + Link 2 (6GHz, 12% busy)</text>',
    ]

    for y_val in [0.0, 0.25, 0.5, 0.75, 1.0]:
        py = y_to_px(y_val)
        svg.append(f'<line x1="{pad_l}" y1="{py}" x2="{pad_l+plot_w}" y2="{py}" stroke="#e2e8f0" stroke-width="1"/>')
        svg.append(f'<text x="{pad_l-15}" y="{py+5}" text-anchor="end" font-size="12" fill="#475569">{y_val:.2f}</text>')

    for x_val in [0, 3, 6, 9, 12, 15]:
        px = x_to_px(float(x_val))
        svg.append(f'<line x1="{px}" y1="{pad_t}" x2="{px}" y2="{pad_t+plot_h}" stroke="#e2e8f0" stroke-width="1"/>')
        svg.append(f'<text x="{px}" y="{pad_t+plot_h+20}" text-anchor="middle" font-size="12" fill="#475569">{x_val} ms</text>')

    def make_ecdf_path(data: List[float], stroke_color: str) -> str:
        n = len(data)
        pts = [(x_to_px(v), y_to_px((idx + 1) / n)) for idx, v in enumerate(data)]
        stride = max(1, len(pts) // 300)
        downsampled = pts[::stride] + [pts[-1]]
        d_str = f"M {pad_l} {pad_t+plot_h} " + " ".join(f"L {p[0]:.1f} {p[1]:.1f}" for p in downsampled)
        return f'<path d="{d_str}" fill="none" stroke="{stroke_color}" stroke-width="3"/>'

    svg.append(make_ecdf_path(single_sorted, "#dc2626"))  # Red: Single Link
    svg.append(make_ecdf_path(mlo_sorted, "#2563eb"))     # Blue: MLO

    # Legend
    svg.append(f'<rect x="{pad_l+plot_w-260}" y="{pad_t+15}" width="240" height="90" fill="#f8fafc" stroke="#cbd5e1" rx="4"/>')
    svg.append(f'<line x1="{pad_l+plot_w-240}" y1="{pad_t+35}" x2="{pad_l+plot_w-210}" y2="{pad_t+35}" stroke="#dc2626" stroke-width="3"/>')
    svg.append(f'<text x="{pad_l+plot_w-200}" y="{pad_t+39}" font-size="12" font-weight="600" fill="#0f172a">Single Link (5 GHz, p95={res.single_link_p95_ms}ms)</text>')
    svg.append(f'<line x1="{pad_l+plot_w-240}" y1="{pad_t+60}" x2="{pad_l+plot_w-210}" y2="{pad_t+60}" stroke="#2563eb" stroke-width="3"/>')
    svg.append(f'<text x="{pad_l+plot_w-200}" y="{pad_t+64}" font-size="12" font-weight="600" fill="#0f172a">Wi-Fi 7 MLO (5+6 GHz, p95={res.mlo_p95_ms}ms)</text>')
    svg.append(f'<text x="{pad_l+plot_w-240}" y="{pad_t+85}" font-size="11" font-weight="bold" fill="#059669">&Delta; p95 Reduction: -{res.p95_reduction_pct}%</text>')

    svg.append(f'<text x="{pad_l+plot_w/2}" y="{pad_t+plot_h+50}" text-anchor="middle" font-size="13" font-weight="600" fill="#334155">Packet Transfer Latency (ms)</text>')
    svg.append(f'<text x="25" y="{pad_t+plot_h/2}" text-anchor="middle" font-size="13" font-weight="600" fill="#334155" transform="rotate(-90 25 {pad_t+plot_h/2})">Cumulative Probability</text>')
    svg.append('</svg>')

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(svg), encoding="utf-8")
