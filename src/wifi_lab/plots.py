"""Publication-quality figure generation for Wi-Fi Diagnostic Lab.

Generates standalone, scalable vector graphics (SVG) compatible with GitHub,
LaTeX documents, and modern browsers without requiring heavy external dependencies.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any


def generate_all_figures(summary_csv_path: Path, rtt_samples_csv_path: Path, figures_dir: Path) -> None:
    figures_dir.mkdir(parents=True, exist_ok=True)

    summary_rows = _load_summary_csv(summary_csv_path)
    rtt_samples = _load_rtt_samples_csv(rtt_samples_csv_path)

    # 1. Throughput by condition
    fig1_path = figures_dir / "fig1_throughput_by_condition.svg"
    _plot_fig1_throughput(summary_rows, fig1_path)
    print(f"  ↳ Rendered: {fig1_path}")

    # 2. Latency ECDF (Idle vs Loaded)
    fig2_path = figures_dir / "fig2_rtt_ecdf.svg"
    _plot_fig2_ecdf(rtt_samples, fig2_path)
    print(f"  ↳ Rendered: {fig2_path}")

    # 3. Phase-labelled time series
    fig3_path = figures_dir / "fig3_rtt_timeseries.svg"
    _plot_fig3_timeseries(rtt_samples, fig3_path)
    print(f"  ↳ Rendered: {fig3_path}")

    # 4. Loaded-minus-Idle Delta RTT (Bufferbloat index)
    fig4_path = figures_dir / "fig4_loaded_delta_rtt.svg"
    _plot_fig4_delta_rtt(summary_rows, fig4_path)
    print(f"  ↳ Rendered: {fig4_path}")


def _load_summary_csv(path: Path) -> list[dict[str, Any]]:
    rows = []
    if not path.is_file():
        return rows
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    return rows


def _load_rtt_samples_csv(path: Path) -> list[dict[str, Any]]:
    samples = []
    if not path.is_file():
        return samples
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            samples.append(r)
    return samples


def _plot_fig1_throughput(rows: list[dict[str, Any]], out_path: Path) -> None:
    """Figure 1: Receiver Throughput across Positions & Directions with Gigabit Ethernet ceiling."""
    valid_rows = [r for r in rows if r["outcome"] == "ok" and r["receiver_throughput_mbps"]]

    # Group by (position, direction)
    groups: dict[str, list[float]] = {
        "L1 DL": [],
        "L1 UL": [],
        "L2 DL": [],
        "L2 UL": [],
    }
    for r in valid_rows:
        pos = r["position_id"]
        d = "DL" if r["direction"] == "download" else "UL"
        key = f"{pos} {d}"
        if key in groups:
            groups[key].append(float(r["receiver_throughput_mbps"]))

    # SVG Canvas
    w, h = 800, 500
    pad_l, pad_r, pad_t, pad_b = 90, 40, 70, 70
    plot_w = w - pad_l - pad_r
    plot_h = h - pad_t - pad_b
    max_y = 1000.0  # Mbps

    def y_to_px(val: float) -> float:
        return pad_t + plot_h * (1.0 - (val / max_y))

    svg = [
        f'<svg width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg" style="background:#ffffff;font-family:system-ui,-apple-system,sans-serif;">',
        f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
        f'<text x="{w/2}" y="32" text-anchor="middle" font-size="18" font-weight="bold" fill="#0f172a">Fig 1: Local TCP Receiver Throughput by Position &amp; Direction</text>',
        f'<text x="{w/2}" y="52" text-anchor="middle" font-size="13" fill="#64748b">FRITZ!Box 7530 AX (5 GHz, 80 MHz) ── M1 Pro MacBook ── Gigabit Ethernet Host</text>',
    ]

    # Gridlines and Y-axis
    for y_val in [0, 200, 400, 600, 800, 1000]:
        py = y_to_px(y_val)
        svg.append(f'<line x1="{pad_l}" y1="{py}" x2="{pad_l+plot_w}" y2="{py}" stroke="#e2e8f0" stroke-width="1"/>')
        svg.append(f'<text x="{pad_l-15}" y="{py+5}" text-anchor="end" font-size="12" fill="#475569">{y_val}</text>')

    # Gigabit Ethernet theoretical payload ceiling line (~940 Mbps)
    ceil_py = y_to_px(940.0)
    svg.append(f'<line x1="{pad_l}" y1="{ceil_py}" x2="{pad_l+plot_w}" y2="{ceil_py}" stroke="#dc2626" stroke-dasharray="6,4" stroke-width="2"/>')
    svg.append(f'<text x="{pad_l+plot_w-10}" y="{ceil_py-8}" text-anchor="end" font-size="11" font-weight="600" fill="#dc2626">Gigabit LAN Payload Ceiling (~940 Mbps)</text>')

    # Plot Bars & Jittered Points
    keys = list(groups.keys())
    col_w = plot_w / len(keys)
    colors = ["#2563eb", "#3b82f6", "#059669", "#10b981"]

    for i, (k, vals) in enumerate(groups.items()):
        cx = pad_l + i * col_w + col_w / 2
        med = (sum(vals) / len(vals)) if vals else 0.0

        bar_h = plot_h * (med / max_y)
        bar_y = pad_t + plot_h - bar_h
        bar_w = col_w * 0.55

        # Bar
        svg.append(f'<rect x="{cx-bar_w/2}" y="{bar_y}" width="{bar_w}" height="{bar_h}" fill="{colors[i]}" rx="4" opacity="0.85"/>')

        # Median text
        if med > 0:
            svg.append(f'<text x="{cx}" y="{bar_y-10}" text-anchor="middle" font-size="13" font-weight="bold" fill="#0f172a">{med:.1f} Mbps</text>')

        # Scatter points
        for v in vals:
            py = y_to_px(v)
            svg.append(f'<circle cx="{cx}" cy="{py}" r="4" fill="#ffffff" stroke="{colors[i]}" stroke-width="2"/>')

        # X-axis label
        svg.append(f'<text x="{cx}" y="{pad_t+plot_h+25}" text-anchor="middle" font-size="13" font-weight="600" fill="#1e293b">{k}</text>')

    # Y-axis label
    svg.append(f'<text x="25" y="{pad_t+plot_h/2}" text-anchor="middle" font-size="13" font-weight="600" fill="#334155" transform="rotate(-90 25 {pad_t+plot_h/2})">Receiver Throughput (Mbps)</text>')
    svg.append('</svg>')

    out_path.write_text("\n".join(svg), encoding="utf-8")


def _plot_fig2_ecdf(samples: list[dict[str, Any]], out_path: Path) -> None:
    """Figure 2: Empirical Cumulative Distribution Function (ECDF) of Latency (Idle vs Loaded)."""
    idle_rtts = [float(s["rtt_ms"]) for s in samples if s["phase"] == "idle" and s["rtt_ms"] and not _to_bool(s["is_boundary_guarded"])]
    loaded_rtts = [float(s["rtt_ms"]) for s in samples if s["phase"] == "load" and s["rtt_ms"] and not _to_bool(s["is_boundary_guarded"])]

    idle_rtts.sort()
    loaded_rtts.sort()

    w, h = 800, 500
    pad_l, pad_r, pad_t, pad_b = 90, 40, 70, 70
    plot_w = w - pad_l - pad_r
    plot_h = h - pad_t - pad_b
    max_x = 120.0  # ms

    def x_to_px(val: float) -> float:
        clamped = min(max_x, max(0.0, val))
        return pad_l + plot_w * (clamped / max_x)

    def y_to_px(prob: float) -> float:
        return pad_t + plot_h * (1.0 - prob)

    svg = [
        f'<svg width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg" style="background:#ffffff;font-family:system-ui,-apple-system,sans-serif;">',
        f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
        f'<text x="{w/2}" y="32" text-anchor="middle" font-size="18" font-weight="bold" fill="#0f172a">Fig 2: Latency ECDF — Idle Baseline vs. Loaded Network</text>',
        f'<text x="{w/2}" y="52" text-anchor="middle" font-size="13" fill="#64748b">Empirical Cumulative Distribution Function (ECDF) across all valid pilot runs</text>',
    ]

    # Gridlines
    for y_val in [0.0, 0.25, 0.5, 0.75, 1.0]:
        py = y_to_px(y_val)
        svg.append(f'<line x1="{pad_l}" y1="{py}" x2="{pad_l+plot_w}" y2="{py}" stroke="#e2e8f0" stroke-width="1"/>')
        svg.append(f'<text x="{pad_l-15}" y="{py+5}" text-anchor="end" font-size="12" fill="#475569">{y_val:.2f}</text>')

    for x_val in [0, 20, 40, 60, 80, 100, 120]:
        px = x_to_px(x_val)
        svg.append(f'<line x1="{px}" y1="{pad_t}" x2="{px}" y2="{pad_t+plot_h}" stroke="#e2e8f0" stroke-width="1"/>')
        svg.append(f'<text x="{px}" y="{pad_t+plot_h+20}" text-anchor="middle" font-size="12" fill="#475569">{x_val} ms</text>')

    # Helper to draw ECDF step path
    def make_ecdf_path(data: list[float], stroke_color: str, label: str) -> str:
        if not data:
            return ""
        n = len(data)
        pts = []
        for idx, val in enumerate(data):
            prob = (idx + 1) / n
            px = x_to_px(val)
            py = y_to_px(prob)
            pts.append((px, py))

        # Sample points to keep SVG size optimal
        stride = max(1, len(pts) // 300)
        downsampled = pts[::stride] + [pts[-1]]
        d_str = f"M {pad_l} {pad_t+plot_h} " + " ".join(f"L {p[0]:.1f} {p[1]:.1f}" for p in downsampled)
        return f'<path d="{d_str}" fill="none" stroke="{stroke_color}" stroke-width="3"/>'

    if idle_rtts:
        svg.append(make_ecdf_path(idle_rtts, "#059669", "Idle Baseline"))
    if loaded_rtts:
        svg.append(make_ecdf_path(loaded_rtts, "#dc2626", "Under Load"))

    # Legend
    svg.append(f'<rect x="{pad_l+plot_w-220}" y="{pad_t+15}" width="200" height="70" fill="#f8fafc" stroke="#cbd5e1" rx="4"/>')
    svg.append(f'<line x1="{pad_l+plot_w-200}" y1="{pad_t+35}" x2="{pad_l+plot_w-170}" y2="{pad_t+35}" stroke="#059669" stroke-width="3"/>')
    svg.append(f'<text x="{pad_l+plot_w-160}" y="{pad_t+39}" font-size="12" font-weight="600" fill="#0f172a">Idle Baseline (RTT &lt; 5ms)</text>')
    svg.append(f'<line x1="{pad_l+plot_w-200}" y1="{pad_t+60}" x2="{pad_l+plot_w-170}" y2="{pad_t+60}" stroke="#dc2626" stroke-width="3"/>')
    svg.append(f'<text x="{pad_l+plot_w-160}" y="{pad_t+64}" font-size="12" font-weight="600" fill="#0f172a">Loaded (Bufferbloat tail)</text>')

    # Labels
    svg.append(f'<text x="{pad_l+plot_w/2}" y="{pad_t+plot_h+50}" text-anchor="middle" font-size="13" font-weight="600" fill="#334155">ICMP Round-Trip Time (RTT in ms)</text>')
    svg.append(f'<text x="25" y="{pad_t+plot_h/2}" text-anchor="middle" font-size="13" font-weight="600" fill="#334155" transform="rotate(-90 25 {pad_t+plot_h/2})">Cumulative Probability P(X &lt;= x)</text>')
    svg.append('</svg>')

    out_path.write_text("\n".join(svg), encoding="utf-8")


def _plot_fig3_timeseries(samples: list[dict[str, Any]], out_path: Path) -> None:
    """Figure 3: Multi-Phase RTT Time Series (Idle -> Warmup -> Load -> Recovery)."""
    # Pick the first valid L1 download run
    l1_dl_runs = sorted(list(set(s["run_id"] for s in samples if "L1_download" in s["run_id"])))
    chosen_run = l1_dl_runs[0] if l1_dl_runs else (samples[0]["run_id"] if samples else "")
    run_samples = [s for s in samples if s["run_id"] == chosen_run and s["rtt_ms"]]

    w, h = 850, 480
    pad_l, pad_r, pad_t, pad_b = 80, 40, 70, 70
    plot_w = w - pad_l - pad_r
    plot_h = h - pad_t - pad_b
    max_t = 125.0
    max_rtt = 70.0

    def t_to_px(t: float) -> float:
        return pad_l + plot_w * (min(max_t, t) / max_t)

    def rtt_to_px(rtt: float) -> float:
        return pad_t + plot_h * (1.0 - (min(max_rtt, rtt) / max_rtt))

    svg = [
        f'<svg width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg" style="background:#ffffff;font-family:system-ui,-apple-system,sans-serif;">',
        f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
        f'<text x="{w/2}" y="32" text-anchor="middle" font-size="18" font-weight="bold" fill="#0f172a">Fig 3: Latency Time-Series across Four Measurement Phases</text>',
        f'<text x="{w/2}" y="52" text-anchor="middle" font-size="13" fill="#64748b">Run ID: {chosen_run} (L1 Download, 60s steady-state TCP load)</text>',
    ]

    # Shaded phase bands
    # Idle: 0-30s
    x_idle_end = t_to_px(30.0)
    svg.append(f'<rect x="{pad_l}" y="{pad_t}" width="{x_idle_end-pad_l}" height="{plot_h}" fill="#f0fdf4" opacity="0.9"/>')
    svg.append(f'<text x="{pad_l + (x_idle_end-pad_l)/2}" y="{pad_t+25}" text-anchor="middle" font-size="12" font-weight="bold" fill="#166534">IDLE (30s)</text>')

    # Warmup: 30-33s
    x_warm_end = t_to_px(33.0)
    svg.append(f'<rect x="{x_idle_end}" y="{pad_t}" width="{x_warm_end-x_idle_end}" height="{plot_h}" fill="#fef9c3" opacity="0.9"/>')

    # Load: 33-93s
    x_load_end = t_to_px(93.0)
    svg.append(f'<rect x="{x_warm_end}" y="{pad_t}" width="{x_load_end-x_warm_end}" height="{plot_h}" fill="#fef2f2" opacity="0.9"/>')
    svg.append(f'<text x="{x_warm_end + (x_load_end-x_warm_end)/2}" y="{pad_t+25}" text-anchor="middle" font-size="12" font-weight="bold" fill="#991b1b">MEASURED LOAD (60s TCP)</text>')

    # Recovery: 93-123s
    x_rec_end = t_to_px(123.0)
    svg.append(f'<rect x="{x_load_end}" y="{pad_t}" width="{x_rec_end-x_load_end}" height="{plot_h}" fill="#eff6ff" opacity="0.9"/>')
    svg.append(f'<text x="{x_load_end + (x_rec_end-x_load_end)/2}" y="{pad_t+25}" text-anchor="middle" font-size="12" font-weight="bold" fill="#1e40af">RECOVERY (30s)</text>')

    # Gridlines
    for rtt_val in [0, 20, 40, 60]:
        py = rtt_to_px(rtt_val)
        svg.append(f'<line x1="{pad_l}" y1="{py}" x2="{pad_l+plot_w}" y2="{py}" stroke="#cbd5e1" stroke-width="1"/>')
        svg.append(f'<text x="{pad_l-15}" y="{py+5}" text-anchor="end" font-size="12" fill="#475569">{rtt_val} ms</text>')

    for t_val in [0, 30, 60, 90, 120]:
        px = t_to_px(t_val)
        svg.append(f'<line x1="{px}" y1="{pad_t}" x2="{px}" y2="{pad_t+plot_h}" stroke="#cbd5e1" stroke-width="1"/>')
        svg.append(f'<text x="{px}" y="{pad_t+plot_h+20}" text-anchor="middle" font-size="12" fill="#475569">{t_val}s</text>')

    # Scatter ping samples
    pts = []
    for s in run_samples:
        t = float(s["timestamp_rel_s"])
        r = float(s["rtt_ms"])
        px = t_to_px(t)
        py = rtt_to_px(r)
        pts.append((px, py))
        dot_color = "#991b1b" if (33.0 <= t < 93.0) else "#166534"
        svg.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="2.5" fill="{dot_color}" opacity="0.75"/>')

    # Rolling trend line
    if len(pts) > 5:
        trend_pts = []
        window = 10
        for i in range(len(pts) - window):
            avg_x = sum(p[0] for p in pts[i:i+window]) / window
            avg_y = sum(p[1] for p in pts[i:i+window]) / window
            trend_pts.append((avg_x, avg_y))

        d_str = f"M {trend_pts[0][0]:.1f} {trend_pts[0][1]:.1f} " + " ".join(f"L {p[0]:.1f} {p[1]:.1f}" for p in trend_pts)
        svg.append(f'<path d="{d_str}" fill="none" stroke="#0f172a" stroke-width="2.5"/>')

    # Labels
    svg.append(f'<text x="{pad_l+plot_w/2}" y="{pad_t+plot_h+50}" text-anchor="middle" font-size="13" font-weight="600" fill="#334155">Elapsed Experiment Time (seconds)</text>')
    svg.append(f'<text x="25" y="{pad_t+plot_h/2}" text-anchor="middle" font-size="13" font-weight="600" fill="#334155" transform="rotate(-90 25 {pad_t+plot_h/2})">Probe RTT (ms)</text>')
    svg.append('</svg>')

    out_path.write_text("\n".join(svg), encoding="utf-8")


def _plot_fig4_delta_rtt(rows: list[dict[str, Any]], out_path: Path) -> None:
    """Figure 4: Loaded-minus-Idle Delta RTT (Bufferbloat queueing latency index)."""
    valid_rows = [r for r in rows if r["outcome"] == "ok" and r["delta_rtt_median_ms"]]

    groups: dict[str, list[float]] = {
        "L1 DL": [],
        "L1 UL": [],
        "L2 DL": [],
        "L2 UL": [],
    }
    for r in valid_rows:
        pos = r["position_id"]
        d = "DL" if r["direction"] == "download" else "UL"
        key = f"{pos} {d}"
        if key in groups:
            groups[key].append(float(r["delta_rtt_median_ms"]))

    w, h = 800, 480
    pad_l, pad_r, pad_t, pad_b = 90, 40, 70, 70
    plot_w = w - pad_l - pad_r
    plot_h = h - pad_t - pad_b
    max_y = 100.0  # ms

    def y_to_px(val: float) -> float:
        return pad_t + plot_h * (1.0 - (val / max_y))

    svg = [
        f'<svg width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg" style="background:#ffffff;font-family:system-ui,-apple-system,sans-serif;">',
        f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
        f'<text x="{w/2}" y="32" text-anchor="middle" font-size="18" font-weight="bold" fill="#0f172a">Fig 4: Bufferbloat Impact — Loaded-minus-Idle RTT Delta (\u0394 RTT)</text>',
        f'<text x="{w/2}" y="52" text-anchor="middle" font-size="13" fill="#64748b">Additional queueing delay introduced by saturation TCP load (\u0394 = RTT_loaded - RTT_idle)</text>',
    ]

    for y_val in [0, 20, 40, 60, 80, 100]:
        py = y_to_px(y_val)
        svg.append(f'<line x1="{pad_l}" y1="{py}" x2="{pad_l+plot_w}" y2="{py}" stroke="#e2e8f0" stroke-width="1"/>')
        svg.append(f'<text x="{pad_l-15}" y="{py+5}" text-anchor="end" font-size="12" fill="#475569">{y_val} ms</text>')

    keys = list(groups.keys())
    col_w = plot_w / len(keys)
    colors = ["#f97316", "#ea580c", "#dc2626", "#b91c1c"]

    for i, (k, vals) in enumerate(groups.items()):
        cx = pad_l + i * col_w + col_w / 2
        med = (sum(vals) / len(vals)) if vals else 0.0

        bar_h = plot_h * (med / max_y)
        bar_y = pad_t + plot_h - bar_h
        bar_w = col_w * 0.55

        svg.append(f'<rect x="{cx-bar_w/2}" y="{bar_y}" width="{bar_w}" height="{bar_h}" fill="{colors[i]}" rx="4" opacity="0.85"/>')

        if med > 0:
            svg.append(f'<text x="{cx}" y="{bar_y-10}" text-anchor="middle" font-size="13" font-weight="bold" fill="#0f172a">+{med:.1f} ms</text>')

        for v in vals:
            py = y_to_px(v)
            svg.append(f'<circle cx="{cx}" cy="{py}" r="4" fill="#ffffff" stroke="{colors[i]}" stroke-width="2"/>')

        svg.append(f'<text x="{cx}" y="{pad_t+plot_h+25}" text-anchor="middle" font-size="13" font-weight="600" fill="#1e293b">{k}</text>')

    svg.append(f'<text x="25" y="{pad_t+plot_h/2}" text-anchor="middle" font-size="13" font-weight="600" fill="#334155" transform="rotate(-90 25 {pad_t+plot_h/2})">Extra Delay \u0394 RTT (ms)</text>')
    svg.append('</svg>')

    out_path.write_text("\n".join(svg), encoding="utf-8")


def _to_bool(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    return str(val).lower() in ("true", "1", "yes")
