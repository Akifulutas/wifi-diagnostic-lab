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

    # Command: analyse
    analyse_parser = subparsers.add_parser("analyse", help="Process raw measurement logs into tables and figures")
    analyse_parser.add_argument("--input", "-i", type=Path, default=Path("data/raw/pilot"), help="Input directory containing raw runs")
    analyse_parser.add_argument("--output", "-o", type=Path, default=Path("data/processed/pilot"), help="Output directory for processed CSVs")
    analyse_parser.add_argument("--figures", "-f", type=Path, default=Path("results/figures"), help="Output directory for publication figures")

    # Command: suggest
    suggest_parser = subparsers.add_parser("suggest", help="Analyze run summaries using WiSlow-inspired diagnostic rules")
    suggest_parser.add_argument("--input", "-i", type=Path, default=Path("data/processed/pilot/run_summary.csv"), help="Processed run summary CSV")

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
    elif args.subcommand == "analyse":
        from wifi_lab.analysis import run_analysis_pipeline
        return run_analysis_pipeline(input_dir=args.input, output_dir=args.output, figures_dir=args.figures)
    elif args.subcommand == "suggest":
        from wifi_lab.diagnostics import run_diagnostics
        return run_diagnostics(summary_csv=args.input)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
