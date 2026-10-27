"""Command-line interface for Wi-Fi Diagnostic Lab."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from wifi_lab.doctor import run_doctor


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wifi-lab",
        description="Wi-Fi Diagnostic Lab: Reproducible throughput, latency, and bottleneck diagnosis.",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # Command: doctor
    doctor_parser = subparsers.add_parser("doctor", help="Inspect local environment and measurement tool readiness")
    doctor_parser.add_argument("--verbose", "-v", action="store_true", help="Show extended telemetry")

    # Command: collect
    collect_parser = subparsers.add_parser("collect", help="Execute measurement runs (live or mock/replay)")
    collect_parser.add_argument("--config", "-c", type=Path, default=Path("configs/pilot.toml"), help="Path to experiment TOML config")
    collect_parser.add_argument("--output", "-o", type=Path, default=Path("data/raw/pilot"), help="Destination directory for raw runs")
    collect_parser.add_argument("--mock", action="store_true", help="Generate realistic synthetic/replay runs for offline dev")
    collect_parser.add_argument("--runs", type=int, default=None, help="Override planned repetition count")

    # Command: analyse / analyze
    analyse_parser = subparsers.add_parser("analyse", aliases=["analyze"], help="Process raw measurement logs into tables and figures")
    analyse_parser.add_argument("input_pos", nargs="?", default=None, help="Input directory (positional shorthand)")
    analyse_parser.add_argument("--input", "--input-dir", "-i", type=Path, default=Path("data/raw/pilot"), help="Input directory containing raw runs")
    analyse_parser.add_argument("--output", "--output-dir", "-o", type=Path, default=Path("data/processed/pilot"), help="Output directory for processed CSVs")
    analyse_parser.add_argument("--figures", "--figures-dir", "-f", type=Path, default=Path("results/figures"), help="Output directory for publication figures")

    # Command: suggest
    suggest_parser = subparsers.add_parser("suggest", help="Analyze run summaries using WiSlow-inspired diagnostic rules")
    suggest_parser.add_argument("--input", "-i", type=Path, default=Path("data/processed/pilot/run_summary.csv"), help="Processed run summary CSV")

    # Command: report
    report_parser = subparsers.add_parser("report", help="Generate standalone interactive HTML research dashboard")
    report_parser.add_argument("--summary", "-s", type=Path, default=Path("data/processed/pilot/run_summary.csv"), help="Processed run summary CSV")
    report_parser.add_argument("--figures", "-f", type=Path, default=Path("results/figures"), help="Directory containing SVG figures")
    report_parser.add_argument("--output", "-o", type=Path, default=Path("results/report.html"), help="Destination path for HTML report")

    # Command: mlo-sim
    mlo_parser = subparsers.add_parser("mlo-sim", help="Simulate Wi-Fi 7 Multi-Link Operation (MLO) latency")
    mlo_parser.add_argument("--packets", "-n", type=int, default=2000, help="Number of packet arrivals to simulate")
    mlo_parser.add_argument("--output", "-o", type=Path, default=Path("results/figures/fig5_mlo_vs_single_link.svg"), help="Output path for MLO SVG figure")

    # Command: redact
    redact_parser = subparsers.add_parser("redact", help="Sanitize private IPs and MACs for ethical public dataset release")
    redact_parser.add_argument("--input", "-i", type=Path, default=Path("data/raw/pilot"), help="Input raw dataset directory")
    redact_parser.add_argument("--output", "-o", type=Path, default=Path("data/raw/pilot_redacted"), help="Output redacted directory")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.subcommand:
        parser.print_help()
        return 0

    if args.subcommand == "doctor":
        return run_doctor(verbose=args.verbose)
    elif args.subcommand == "collect":
        from wifi_lab.runner import execute_collection
        return execute_collection(config_path=args.config, output_dir=args.output, mock=args.mock, runs_override=args.runs)
    elif args.subcommand in ("analyse", "analyze"):
        from wifi_lab.analysis import run_analysis_pipeline
        in_dir = Path(args.input_pos) if args.input_pos else args.input
        return run_analysis_pipeline(input_dir=in_dir, output_dir=args.output, figures_dir=args.figures)
    elif args.subcommand == "suggest":
        from wifi_lab.diagnostics import run_diagnostics
        return run_diagnostics(summary_csv=args.input)
    elif args.subcommand == "report":
        from wifi_lab.report_gen import generate_html_report
        return generate_html_report(summary_csv=args.summary, figures_dir=args.figures, output_html=args.output)
    elif args.subcommand == "mlo-sim":
        from wifi_lab.mlo_sim import run_mlo_simulation
        res = run_mlo_simulation(packet_count=args.packets, output_figure=args.output)
        return 0
    elif args.subcommand == "redact":
        from wifi_lab.redactor import redact_dataset
        return redact_dataset(input_dir=args.input, output_dir=args.output)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
