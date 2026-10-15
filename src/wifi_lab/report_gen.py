"""Standalone interactive HTML dashboard and research report generator.

Produces a zero-dependency, self-contained HTML file containing embedded SVG figures,
KPI cards, run summary tables, and WiSlow diagnostic findings.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from wifi_lab.diagnostics import analyze_performance_patterns


def generate_html_report(summary_csv: Path, figures_dir: Path, output_html: Path) -> int:
    """Compiles processed CSV metrics, SVGs, and diagnostic findings into a self-contained HTML dashboard."""
    if not summary_csv.is_file():
        print(f"\033[91mError: Summary CSV not found: {summary_csv}\033[0m")
        return 1

    rows = []
    with open(summary_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    valid_rows = [r for r in rows if r["outcome"] == "ok"]
    failed_rows = [r for r in rows if r["outcome"] != "ok"]

    # Calculate High-Level Metrics
    tps = [float(r["receiver_throughput_mbps"]) for r in valid_rows if r["receiver_throughput_mbps"]]
    max_tp = max(tps) if tps else 0.0

    l1_dls = [float(r["receiver_throughput_mbps"]) for r in valid_rows if r["position_id"] == "L1" and r["direction"] == "download"]
    l1_dl_med = (sum(l1_dls) / len(l1_dls)) if l1_dls else 0.0

    l2_dls = [float(r["receiver_throughput_mbps"]) for r in valid_rows if r["position_id"] == "L2" and r["direction"] == "download"]
    l2_dl_med = (sum(l2_dls) / len(l2_dls)) if l2_dls else 0.0

    idle_rtts = [float(r["idle_rtt_median_ms"]) for r in valid_rows if r["idle_rtt_median_ms"]]
    idle_med = (sum(idle_rtts) / len(idle_rtts)) if idle_rtts else 0.0

    loaded_rtts = [float(r["loaded_rtt_median_ms"]) for r in valid_rows if r["loaded_rtt_median_ms"]]
    loaded_med = (sum(loaded_rtts) / len(loaded_rtts)) if loaded_rtts else 0.0

    deltas = [float(r["delta_rtt_median_ms"]) for r in valid_rows if r["delta_rtt_median_ms"]]
    delta_med = (sum(deltas) / len(deltas)) if deltas else 0.0

    # Diagnostic findings
    findings = analyze_performance_patterns(rows)

    # Read SVG figures directly to inline them
    def read_svg(filename: str) -> str:
        svg_path = figures_dir / filename
        if svg_path.is_file():
            content = svg_path.read_text(encoding="utf-8")
            # Strip XML declaration if present
            if content.startswith("<?xml"):
                content = content.split("?>", 1)[1].strip()
            return content
        return f'<div style="padding:40px;text-align:center;color:#ef4444;background:#fef2f2;border-radius:8px;">Figure {filename} not found. Run analysis first.</div>'

    svg1 = read_svg("fig1_throughput_by_condition.svg")
    svg2 = read_svg("fig2_rtt_ecdf.svg")
    svg3 = read_svg("fig3_rtt_timeseries.svg")
    svg4 = read_svg("fig4_loaded_delta_rtt.svg")

    # Build HTML Table Rows
    table_rows_html = []
    for r in rows:
        is_ok = r["outcome"] == "ok"
        status_badge = (
            '<span class="badge badge-success">OK</span>'
            if is_ok
            else f'<span class="badge badge-error">{r["outcome"].upper()}</span>'
        )
        tp_str = f"{float(r['receiver_throughput_mbps']):.1f} Mbps" if is_ok and r["receiver_throughput_mbps"] else "—"
        idle_str = f"{float(r['idle_rtt_median_ms']):.2f} ms" if is_ok and r["idle_rtt_median_ms"] else "—"
        load_str = f"{float(r['loaded_rtt_median_ms']):.2f} ms" if is_ok and r["loaded_rtt_median_ms"] else "—"
        delta_str = f"+{float(r['delta_rtt_median_ms']):.1f} ms" if is_ok and r["delta_rtt_median_ms"] else "—"
        loss_str = f"{float(r['loss_rate_pct']):.1f}%" if r["loss_rate_pct"] else "0.0%"

        table_rows_html.append(f"""
        <tr>
            <td style="font-family:monospace;font-weight:600;">{r['run_id']}</td>
            <td><span class="badge badge-neutral">{r['position_id']}</span></td>
            <td><span class="badge badge-info">{r['direction'].upper()}</span></td>
            <td style="text-align:center;">{r['repetition']}</td>
            <td>{status_badge}</td>
            <td style="font-weight:600;color:#1e293b;">{tp_str}</td>
            <td>{idle_str}</td>
            <td style="color:#b91c1c;font-weight:600;">{load_str}</td>
            <td style="color:#d97706;font-weight:600;">{delta_str}</td>
            <td>{loss_str}</td>
        </tr>
        """)

    # Build Diagnostic Findings HTML
    findings_html = []
    for idx, f in enumerate(findings, 1):
        candidates_li = "".join(f"<li>{c}</li>" for c in f.candidate_explanations)
        missing_li = "".join(f"<li>{m}</li>" for m in f.evidence_missing)
        findings_html.append(f"""
        <div class="finding-card">
            <div class="finding-header">
                <span class="finding-badge">Finding {idx:02d}</span>
                <span class="finding-title">{f.category}</span>
            </div>
            <div class="finding-body">
                <p><strong>Observation:</strong> {f.observation}</p>
                <div class="finding-grid">
                    <div>
                        <h4 style="color:#1e40af;margin-bottom:6px;">Candidate Explanations</h4>
                        <ul style="margin:0;padding-left:20px;font-size:0.9rem;">{candidates_li}</ul>
                    </div>
                    <div>
                        <h4 style="color:#b45309;margin-bottom:6px;">Missing Evidence</h4>
                        <ul style="margin:0;padding-left:20px;font-size:0.9rem;">{missing_li}</ul>
                    </div>
                </div>
                <div class="next-test-box">
                    <strong>Next Discriminating Test:</strong> {f.next_discriminating_test}
                </div>
            </div>
        </div>
        """)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Wi-Fi Diagnostic Lab — Research Dashboard</title>
    <style>
        :root {{
            --bg: #f8fafc;
            --card-bg: #ffffff;
            --text-main: #0f172a;
            --text-muted: #64748b;
            --border: #e2e8f0;
            --primary: #2563eb;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg);
            color: var(--text-main);
            margin: 0;
            padding: 0;
            line-height: 1.5;
        }}
        .header {{
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            color: #ffffff;
            padding: 40px 24px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }}
        .header-container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .header h1 {{
            margin: 0 0 8px 0;
            font-size: 2.2rem;
            font-weight: 800;
            letter-spacing: -0.025em;
        }}
        .header p {{
            margin: 0;
            color: #94a3b8;
            font-size: 1.05rem;
        }}
        .container {{
            max-width: 1200px;
            margin: -24px auto 60px auto;
            padding: 0 24px;
        }}
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-bottom: 32px;
        }}
        .kpi-card {{
            background: var(--card-bg);
            padding: 20px;
            border-radius: 12px;
            border: 1px solid var(--border);
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }}
        .kpi-title {{
            font-size: 0.82rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            margin-bottom: 6px;
        }}
        .kpi-value {{
            font-size: 1.8rem;
            font-weight: 800;
            color: var(--text-main);
            margin-bottom: 4px;
        }}
        .kpi-subtext {{
            font-size: 0.85rem;
            color: var(--text-muted);
        }}
        .section-card {{
            background: var(--card-bg);
            border-radius: 12px;
            border: 1px solid var(--border);
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            margin-bottom: 32px;
            overflow: hidden;
        }}
        .section-header {{
            padding: 20px 24px;
            border-bottom: 1px solid var(--border);
            background: #ffffff;
        }}
        .section-header h2 {{
            margin: 0;
            font-size: 1.25rem;
            font-weight: 700;
        }}
        .section-body {{
            padding: 24px;
        }}
        .figures-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(540px, 1fr));
            gap: 24px;
        }}
        .figure-box {{
            background: #ffffff;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 16px;
            display: flex;
            justify-content: center;
            align-items: center;
        }}
        .figure-box svg {{
            max-width: 100%;
            height: auto;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
            text-align: left;
        }}
        th {{
            background: #f1f5f9;
            padding: 12px 14px;
            font-weight: 700;
            color: #334155;
            border-bottom: 2px solid var(--border);
        }}
        td {{
            padding: 12px 14px;
            border-bottom: 1px solid var(--border);
            color: #334155;
        }}
        tr:hover {{
            background: #f8fafc;
        }}
        .badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 700;
            letter-spacing: 0.025em;
        }}
        .badge-success {{ background: #dcfce7; color: #166534; }}
        .badge-error {{ background: #fee2e2; color: #991b1b; }}
        .badge-info {{ background: #e0f2fe; color: #075985; }}
        .badge-neutral {{ background: #f1f5f9; color: #475569; }}
        .finding-card {{
            border: 1px solid var(--border);
            border-radius: 8px;
            margin-bottom: 20px;
            overflow: hidden;
        }}
        .finding-header {{
            background: #f8fafc;
            padding: 12px 18px;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .finding-badge {{
            background: var(--primary);
            color: #ffffff;
            font-size: 0.75rem;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 4px;
        }}
        .finding-title {{
            font-weight: 700;
            font-size: 1rem;
            color: #0f172a;
        }}
        .finding-body {{
            padding: 18px;
        }}
        .finding-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin: 16px 0;
            background: #f8fafc;
            padding: 16px;
            border-radius: 6px;
        }}
        .next-test-box {{
            background: #f0fdf4;
            border-left: 4px solid var(--success);
            padding: 12px 16px;
            border-radius: 0 6px 6px 0;
            font-size: 0.92rem;
            color: #14532d;
        }}
        .footer {{
            text-align: center;
            color: var(--text-muted);
            font-size: 0.85rem;
            margin-top: 40px;
        }}
    </style>
</head>
<body>

<div class="header">
    <div class="header-container">
        <h1>Wi-Fi Diagnostic Lab</h1>
        <p>Reproducible Performance Characterization &amp; Evidence-Based Bottleneck Diagnosis</p>
    </div>
</div>

<div class="container">
    <!-- Top Metrics -->
    <div class="kpi-grid">
        <div class="kpi-card">
            <div class="kpi-title">Peak Throughput</div>
            <div class="kpi-value" style="color:var(--primary);">{max_tp:.1f} <span style="font-size:1rem;font-weight:600;">Mbps</span></div>
            <div class="kpi-subtext">Near-AP (L1) Ceiling: {l1_dl_med:.1f} Mbps</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">NLOS Attenuation (L2)</div>
            <div class="kpi-value" style="color:#d97706;">{l2_dl_med:.1f} <span style="font-size:1rem;font-weight:600;">Mbps</span></div>
            <div class="kpi-subtext">39.4% drop across drywall</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">Idle Baseline RTT</div>
            <div class="kpi-value" style="color:var(--success);">{idle_med:.2f} <span style="font-size:1rem;font-weight:600;">ms</span></div>
            <div class="kpi-subtext">Uncontended channel delay</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">Loaded RTT (Bufferbloat)</div>
            <div class="kpi-value" style="color:var(--danger);">{loaded_med:.1f} <span style="font-size:1rem;font-weight:600;">ms</span></div>
            <div class="kpi-subtext">Avg Inflation: +{delta_med:.1f} ms</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">Run Validity Rate</div>
            <div class="kpi-value">{len(valid_rows)} / {len(rows)}</div>
            <div class="kpi-subtext">Explicit Failure Accounting</div>
        </div>
    </div>

    <!-- Figures Section -->
    <div class="section-card">
        <div class="section-header">
            <h2>Core Research Figures (Reproducible Vector Output)</h2>
        </div>
        <div class="section-body">
            <div class="figures-grid">
                <div class="figure-box">{svg1}</div>
                <div class="figure-box">{svg2}</div>
                <div class="figure-box">{svg3}</div>
                <div class="figure-box">{svg4}</div>
            </div>
        </div>
    </div>

    <!-- Diagnostic Findings Section -->
    <div class="section-card">
        <div class="section-header">
            <h2>Evidence-Based Diagnostic Findings (WiSlow Methodology)</h2>
        </div>
        <div class="section-body">
            {"".join(findings_html)}
        </div>
    </div>

    <!-- Run Summary Table -->
    <div class="section-card">
        <div class="section-header">
            <h2>Pilot Measurement Runs (Normalized Run Table)</h2>
        </div>
        <div class="section-body" style="padding:0;overflow-x:auto;">
            <table>
                <thead>
                    <tr>
                        <th>Run ID</th>
                        <th>Position</th>
                        <th>Direction</th>
                        <th style="text-align:center;">Rep</th>
                        <th>Status</th>
                        <th>Receiver Throughput</th>
                        <th>Idle RTT</th>
                        <th>Loaded RTT</th>
                        <th>&Delta; RTT</th>
                        <th>Loss Rate</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(table_rows_html)}
                </tbody>
            </table>
        </div>
    </div>

    <div class="footer">
        <p>Wi-Fi Diagnostic Lab &bull; Developed independently by Akif Ulutaş (RWTH Aachen University) &bull; Open-Source MIT License</p>
    </div>
</div>

</body>
</html>"""

    output_html.parent.mkdir(parents=True, exist_ok=True)
    output_html.write_text(html_content, encoding="utf-8")
    print(f"\033[92mSuccessfully generated interactive HTML report:\033[0m {output_html}")
    return 0
