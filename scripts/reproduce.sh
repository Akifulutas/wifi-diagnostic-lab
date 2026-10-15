#!/usr/bin/env bash
# ==============================================================================
# Wi-Fi Diagnostic Lab — End-to-End Reproduction Script
# Executes unit tests, pre-flight environment checks, data collection (replay),
# statistical processing, publication figure rendering, and diagnostic rules.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${SCRIPT_DIR}"

export PYTHONPATH="${SCRIPT_DIR}/src"

# Detect Python 3.11+ executable
if [ -x "/opt/homebrew/bin/python3" ]; then
    PYTHON_BIN="/opt/homebrew/bin/python3"
elif [ -x "${SCRIPT_DIR}/.venv/bin/python3" ]; then
    PYTHON_BIN="${SCRIPT_DIR}/.venv/bin/python3"
else
    PYTHON_BIN="python3"
fi

echo "========================================================================"
echo "  Wi-Fi Diagnostic Lab — Automated Reproduction Pipeline"
echo "  Using Python runtime: $(${PYTHON_BIN} --version) (${PYTHON_BIN})"
echo "========================================================================"

# Step 1: Run Unit Tests
echo -e "\n[1/5] Running automated test suite..."
${PYTHON_BIN} -m unittest discover -s tests -v

# Step 2: Run Pre-Flight Doctor
echo -e "\n[2/5] Running environment doctor..."
${PYTHON_BIN} -m wifi_lab doctor || true

# Step 3: Run Pilot Experiment (Mock/Replay mode for offline determinism)
echo -e "\n[3/6] Executing 12-run pilot collection..."
rm -rf data/raw/pilot/*
${PYTHON_BIN} -m wifi_lab collect --mock --config configs/pilot.toml --output data/raw/pilot

# Step 4: Run Statistical Analysis & Render Figures
echo -e "\n[4/5] Executing analysis pipeline & rendering SVG research figures..."
${PYTHON_BIN} -m wifi_lab analyse --input data/raw/pilot --output data/processed/pilot --figures results/figures

# Step 5: Run WiSlow-inspired Diagnostic Engine
echo -e "\n[5/6] Executing diagnostic recommender..."
${PYTHON_BIN} -m wifi_lab suggest --input data/processed/pilot/run_summary.csv

# Step 6: Generate Standalone Interactive HTML Dashboard
echo -e "\n[6/6] Compiling interactive HTML research dashboard..."
${PYTHON_BIN} -m wifi_lab report --summary data/processed/pilot/run_summary.csv --figures results/figures --output results/report.html

echo -e "\n========================================================================"
echo "  [SUCCESS] All pipeline stages reproduced successfully!"
echo "  - Processed CSVs: data/processed/pilot/"
echo "  - Figures (SVG):  results/figures/"
echo "  - HTML Dashboard: results/report.html"
echo "  - Research Report: docs/report.md"
echo "  - Protocol Labs:  docs/protocol-labs/"
echo "========================================================================"
