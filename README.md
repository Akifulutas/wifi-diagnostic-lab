# Wi-Fi Diagnostic Lab & Bufferbloat Localization Engine

[![Python 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue.svg)](https://www.python.org/)
[![Test Suite](https://img.shields.io/badge/test%20pyramid-unit%20%26%20e2e%20passing-green.svg)]()
[![Hardware Testbed](https://img.shields.io/badge/live%20telemetry-Wi--Fi%206%20%2B%20FRITZ!Box-blueviolet.svg)]()
[![Inference Engine](https://img.shields.io/badge/inference-set--valued%20abstention-orange.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A student research and experimental engineering testbed for investigating **Wi-Fi 6/7 throughput dynamics**, **loaded latency (Bufferbloat)**, and **evidence-based network bottleneck localization**.

> **Project Context & Scope:** Developed as an undergraduate research project (RWTH Aachen University) exploring edge network diagnostics. The project combines real-world residential Wi-Fi 6 empirical probing with an emulated reference testbed (`bll`) to evaluate how much bottleneck localization is mathematically justifiable under constrained vantage points without router firmware modifications.

This repository combines:
1. **Empirical Residential Wi-Fi 6 Telemetry:** Live dual-vantage measurements across real physical hardware (Apple Silicon M1 Pro client $\leftrightarrow$ AVM FRITZ!Box 7530 AX AP).
2. **Bufferbloat Localization Lab (BLL):** A controlled reference testbed using Linux network namespaces (`ip netns`), decoupled traffic control (`tc`), differential path algebra, and a deterministic set-valued inference engine that maintains uncertainty (abstention) when evidence is incomplete.

---

## 🎯 Research Questions

1. **Spatial Attenuation & Local Bufferbloat:** *How does physical distance and drywall obstruction (Line-of-Sight vs. Non-Line-of-Sight) alter 802.11ax MCS index, airtime consumption, and queue buildup during active TCP saturation?*
2. **Differential Path Localization:** *Using low-cost edge measurements without router firmware modification, can we reliably differentiate queueing in the local Wi-Fi hop from queueing on the upstream WAN access link (NetCologne DS-Lite)?*
3. **Abstention Under Ambiguity:** *When observation vantage points are insufficient to isolate a specific link, can the inference engine explicitly abstain and recommend the minimum-cost discriminating measurement rather than guessing?*

---

## 🔬 Empirical Residential Wi-Fi 6 Findings (Live Hardware)

Measurements executed live on **macOS 27 (Darwin)** with an **M1 Pro client** connected to an **AVM FRITZ!Box 7530 AX** (5 GHz, Channel 48, 80 MHz channel width):

| Metric | Position 1 (L1: Near AP, LOS) | Position 2 (L2: Adjacent Room, NLOS) | Impact / Physical Mechanism |
| :--- | :---: | :---: | :---: |
| **Physical RSSI / Noise** | **-52 dBm / -88 dBm** | **-72 dBm / -89 dBm** | 20 dB RF path loss through drywall |
| **Signal-to-Noise Ratio (SNR)** | **36 dB** (Clean link) | **17 dB** (Contention boundary) | 19 dB degradation in channel quality |
| **802.11ax MCS Rate** | **MCS 10** (1024-QAM) | **MCS 2** (QPSK) | Dynamic rate adaptation fallback |
| **Physical Link Capacity** | **1134.0 Mbps** | **136.0 Mbps** | **88% capacity reduction** |
| **Idle Wi-Fi RTT (p95)** | **4.4 ms** | **4.3 ms** | Unloaded baseline appears identical |
| **Loaded Wi-Fi RTT (p95)** | **58.5 ms** | **118.9 ms** | **2x queue latency inflation** |
| **Wi-Fi Hop Bloat ($\Delta RTT_{\text{wifi}}$)** | **+54.1 ms** | **+114.6 ms** | Longer airtime drives AP queue inflation |
| **Total End-to-End Bloat** | **+98.0 ms** | **+128.0 ms** | p95 latency under 43–47 Mbps TCP load |
| **Localization Verdict** | `COMPOUND_BOTTLENECK` | `COMPOUND_BOTTLENECK` | **+114.6 ms loaded delay on local Wi-Fi hop vs. +13.4 ms on WAN link** |

> **Scientific Grounding:** At L2, even though idle ping is pristine (~2.7 ms), loaded traffic causes severe bufferbloat (+114.6 ms) solely on the wireless link because MCS 2 drastically increases packet transmission time (airtime), backing up packets in the 802.11 MAC software queue.

Raw live time-series runs and provenance manifests are archived immutably in:
`data/raw/live_home_runs/`

---

## 🏛️ System Architecture

The unified codebase consists of two complementary subsystems:

```text
wifi-diagnostic-lab/
├── src/
│   ├── wifi_lab/                  # Wi-Fi Diagnostic Suite (WiSlow-inspired)
│   │   ├── cli.py                 # wifi-lab CLI (doctor, collect, analyse, suggest, mlo-sim, report)
│   │   ├── runner.py              # Multi-phase execution and offline replay engine
│   │   ├── analysis.py            # Statistical aggregation and phase-guarded metrics
│   │   ├── diagnostics.py         # WiSlow evidence-based diagnostic rules
│   │   ├── mlo_sim.py             # Wi-Fi 7 (802.11be) Multi-Link Operation queue simulator
│   │   └── redactor.py            # RFC 2330 pseudonymization and hashing engine
│   └── bll/                       # Bufferbloat Localization Lab (Reference Engine)
│       ├── cli.py                 # bll CLI (doctor, lab, run, infer, export, report)
│       ├── topology/              # 6-node netns topology & LPM path verification
│       ├── helper/                # Hardened JSON-RPC privileged helper daemon
│       ├── measurements/          # Adapters (ping, irtt, iperf3) & 3-phase engine
│       ├── storage/               # DuckDB analytics over immutable Parquet tables
│       ├── inference/             # Differential path algebra & set-valued abstention
│       └── evaluation/            # Counterexample benchmark & hypothesis testing (H1, H2, H3)
├── scripts/
│   ├── live_home_test.py          # Standalone macOS dual-vantage live home test runner
│   └── reproduce.sh               # One-click reproduction script
├── tests/                         # 195 Unit, Contract, Invariant & Fault Injection tests
└── e2e_tests/                     # 285 End-to-End Acceptance tests across Milestones 1–7
```

---

## 🔬 Bufferbloat Localization Lab (BLL) Capabilities

1. **Controlled Reference Lab Topology:** Emulated 6-node topology (`client`, `q_near`, `router`, `observer`, `q_far`, `remote`) using Linux `ip netns` and decoupled `tc` rate shaping (TBF/HTB) + explicit buffer queueing (`pfifo`/`bfifo`) + delay (`netem`).
2. **Set-Valued Deterministic Inference:** Evaluates differential path latency ($\Delta RTT_{\text{wifi}}$ vs. $\Delta RTT_{\text{wan}}$). If vantage points cannot definitively isolate the queue (e.g. access link vs gateway egress without an observer tap), the engine maintains uncertainty:
   $$\mathcal{R}_{\text{cand}} = \{\text{near\_link}, \text{gateway\_node}\}, \quad \text{abstained} = \text{True}$$
3. **Counterexample Suite & Quality Control:** 12 controlled counterexample scenarios (healthy baseline, near FIFO, far FIFO, dual FIFO, fixed delay without queue, loss without queue, endpoint CPU bottleneck, AQM active, protocol discrepancies) and 8 automated QC sanity gates.
4. **Zero Label Leakage:** Ground truth configurations are physically stored in `ground_truth/` and strictly decoupled from the inference pipeline.
5. **RFC 2330 Anonymization:** Scrubs private MACs (`02:00:00:xx:xx:xx`), IPs (`192.0.2.0/24`), and SSIDs with a cryptographically verifiable SHA-256 provenance manifest.

---

## ⚡ Quickstart & Usage

### 1. Environment Setup

Install with [uv](https://github.com/astral-sh/uv) (recommended) or standard virtualenv:

```bash
uv venv .venv
source .venv/bin/activate
uv pip install -e ".[dev,analysis]"
```

### 2. Verify System Readiness

```bash
# Check Wi-Fi diagnostic environment
wifi-lab doctor

# Check Bufferbloat Localization Lab backend and tool readiness
bll doctor --json
```

### 3. Run Live Residential Wi-Fi 6 Test (No Dongle Required)

Execute a 30-second 3-phase dual-vantage test (Idle $\to$ Load $\to$ Recovery) measuring local gateway RTT vs. remote WAN RTT:

```bash
# Position 1: Line-of-sight near router
python3 scripts/live_home_test.py --position L1 --idle 8 --load 15 --recovery 7

# Position 2: Move to an adjacent room / non-line-of-sight
python3 scripts/live_home_test.py --position L2 --idle 8 --load 15 --recovery 7

# Ingest and visualize empirical live runs into publication figures
wifi-lab analyze data/raw/live_home_runs --output-dir results/figures
```

### 4. Run the Test Pyramid (Unit & End-to-End Suites)

```bash
# Unit, contract, invariant, and fault injection tests (196 tests)
pytest tests/

# End-to-End benchmark acceptance suite across Milestones 1–7 (286 tests)
python3 e2e_tests/run_e2e.py
```

### 5. Run Controlled Reference Benchmark & Export Report

```bash
# Execute counterexample suite via mock simulation or native Linux backend
bll run --backend mock_simulation --config configs/pilot.toml --output runs/pilot_01

# Run deterministic inference engine
bll infer --run-dir runs/pilot_01

# Export sanitized dataset complying with RFC 2330
bll export --run-dir runs/pilot_01 --output export/redacted_dataset --redact

# Generate offline zero-CDN HTML research report
bll report --run-dir runs/pilot_01 --output results/bll_report.html
```

---

## 📚 Scientific References

- **Kim, K., Nam, Y., & Schulzrinne, H.** (2014). *WiSlow: A Wi-Fi Network Performance Troubleshooting Tool for End Users.* IEEE INFOCOM.
- **Nichols, K., & Jacobson, V.** (2012). *Controlling Queue Delay (CoDel).* ACM Queue, 10(5).
- **Høiland-Jørgensen, T., et al.** (2014). *The Flent Network Testing Tool.* Netdev 0.1.
- **Gettys, J., & Nichols, K.** (2011). *Bufferbloat: Dark Buffers in the Internet.* Communications of the ACM, 55(1).
- **Paxson, V., Almes, G., Mahdavi, J., & Mathis, M.** (1998). *Framework for IP Performance Metrics.* IETF RFC 2330.

---

## 📜 License
MIT License. Developed by Akif Ulutaş (RWTH Aachen University).
