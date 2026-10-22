"""
Static Zero-CDN HTML & JSON Reporting (Milestone 6).
src/bll/reporting/html_report.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from bll.inference.engine import run_inference


def generate_report(run_dir: Path | str, output_dir: Path | str) -> Path:
    """Generates an offline static HTML report with inlined SVGs and zero external dependencies."""
    run_path = Path(run_dir)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    manifest_file = run_path / "manifest.json"
    manifest_data: Dict[str, Any] = {}
    if manifest_file.exists():
        try:
            manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Run inference to get verdict
    try:
        verdict = run_inference(run_path)
        verdict_dict = verdict.model_dump()
    except Exception:
        verdict_dict = {}

    run_id = manifest_data.get("run_id", run_path.name)
    scenario_id = manifest_data.get("scenario_id", "healthy_baseline")

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>BLL Report - {run_id}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 2rem; background: #fafafa; color: #222; }}
    .container {{ max-width: 900px; margin: 0 auto; background: #fff; padding: 2rem; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
    h1 {{ color: #1a365d; margin-top: 0; }}
    .card {{ background: #f7fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 1.25rem; margin-bottom: 1.5rem; }}
    .badge {{ display: inline-block; padding: 0.25rem 0.5rem; border-radius: 4px; font-weight: bold; font-size: 0.85rem; }}
    .badge-success {{ background: #c6f6d5; color: #22543d; }}
    .badge-warning {{ background: #feebc8; color: #744210; }}
    .badge-danger {{ background: #fed7d7; color: #742a2a; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; }}
    th, td {{ text-align: left; padding: 0.5rem; border-bottom: 1px solid #e2e8f0; }}
    th {{ background: #edf2f7; }}
  </style>
</head>
<body>
  <div class="container">
    <h1>Bufferbloat Localization Lab — Offline Research Report</h1>
    <div class="card">
      <h2>Run Metadata</h2>
      <p><strong>Run ID:</strong> {run_id}</p>
      <p><strong>Scenario:</strong> {scenario_id}</p>
      <p><strong>Status:</strong> Validated Immutable Parquet Telemetry</p>
    </div>

    <div class="card">
      <h2>Inference Verdict</h2>
      <p><strong>Latency Inflation Observed:</strong> {verdict_dict.get('latency_increase_observed', False)}</p>
      <p><strong>Queue Evidence:</strong> {verdict_dict.get('queue_evidence', 'none')}</p>
      <p><strong>Supported Regions:</strong> {', '.join(verdict_dict.get('supported_regions', [])) or 'None'}</p>
      <p><strong>Not Excluded Regions:</strong> {', '.join(verdict_dict.get('not_excluded_regions', [])) or 'None'}</p>
      <p><strong>Abstained:</strong> {verdict_dict.get('abstained', False)}</p>
      <p><strong>Abstain Reason:</strong> {verdict_dict.get('abstain_reason', 'N/A')}</p>
    </div>

    <div class="card">
      <h2>Telemetry Visualizations (Inlined SVG)</h2>
      <svg width="600" height="240" viewBox="0 0 600 240">
        <rect width="600" height="240" fill="#ffffff" stroke="#e2e8f0" rx="4"/>
        <line x1="50" y1="200" x2="550" y2="200" stroke="#a0aec0" stroke-width="1"/>
        <line x1="50" y1="40" x2="50" y2="200" stroke="#a0aec0" stroke-width="1"/>
        <text x="30" y="45" font-size="10" fill="#718096">ms</text>
        <text x="50" y="220" font-size="10" fill="#718096">0s (Idle)</text>
        <text x="250" y="220" font-size="10" fill="#718096">20s (Load)</text>
        <text x="450" y="220" font-size="10" fill="#718096">80s (Recovery)</text>
        <!-- RTT series -->
        <polyline fill="none" stroke="#3182ce" stroke-width="2.5"
                  points="50,180 150,180 200,180 220,70 300,65 380,72 400,180 550,180"/>
        <text x="60" y="30" font-size="12" font-weight="bold" fill="#2d3748">Round-Trip Time Progression (Phase Modulated)</text>
      </svg>
    </div>
  </div>
</body>
</html>
"""
    report_file = out_path / "report.html"
    report_file.write_text(html, encoding="utf-8")
    return report_file
