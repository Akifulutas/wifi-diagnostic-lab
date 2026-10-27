# Wi-Fi Diagnostic Lab & Bufferbloat Localization Engine

[![Python 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue.svg)](https://www.python.org/)
[![Test Pyramid](https://img.shields.io/badge/pytest-196%20unit%20tests%20passing-brightgreen.svg)]()
[![E2E Verification](https://img.shields.io/badge/e2e%20acceptance-285%20passed%20%7C%201%20skipped-success.svg)]()
[![Hardware Telemetry](https://img.shields.io/badge/empirical%20telemetry-Wi--Fi%206%20%2B%20FRITZ!Box-blueviolet.svg)]()
[![Inference Engine](https://img.shields.io/badge/inference-set--valued%20abstention-orange.svg)]()
[![Privacy Standards](https://img.shields.io/badge/privacy-RFC%202330%20%26%20RFC%205737-informational.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An open-source experimental research testbed and diagnostic system for investigating **Wi-Fi 6 throughput dynamics**, **loaded latency (Bufferbloat)**, and **evidence-based network bottleneck localization under constrained edge vantages**.

> **Academic & Research Context:** Developed as an undergraduate research engineering project at **RWTH Aachen University** (Chair of Computer Science / Network Architectures). This repository investigates how much bottleneck localization is mathematically justifiable from edge measurements alone without router firmware modifications, combining live residential Wi-Fi 6 hardware telemetry with a Linux network-namespace reference testbed.

---

## 📑 Table of Contents

- [Motivation & Problem Statement](#-motivation--problem-statement)
- [Key Empirical Findings (Live Hardware)](#-key-empirical-findings-live-hardware)
- [System Architecture](#-system-architecture)
- [Differential Path Algebra & Inference Theory](#-differential-path-algebra--inference-theory)
- [Controlled Reference Lab & Counterexamples](#-controlled-reference-lab--counterexamples)
- [Quickstart & Usage](#-quickstart--usage)
- [Publication Figures & Visualizations](#-publication-figures--visualizations)
- [Verification & Test Pyramid](#-verification--test-pyramid)
- [Data Provenance & Privacy Ethics](#-data-provenance--privacy-ethics)
- [Academic Context & About the Author](#-academic-context--about-the-author)
- [Scientific References](#-scientific-references)

---

## 🎯 Motivation & Problem Statement

Conventional network speed tests and diagnostic utilities suffer from a fundamental fallacy: they measure latency under active TCP load from a single client endpoint to a cloud server, observe elevated round-trip times (Bufferbloat), and arbitrarily assign blame—often asserting either *"It's your Wi-Fi"* or *"It's your ISP"*.

In real-world residential edge networks, loaded latency can originate in multiple distinct physical layers:
1. **The Wireless Access Link:** Dynamic 802.11 rate adaptation (MCS fallback) caused by drywall attenuation or multipath fading drastically increases packet transmission airtime, backing up packets in the AP transmission queue.
2. **The Residential Gateway:** Egress traffic shaping, CPU exhaustion, or undersized queue limits in customer-premises equipment (CPE).
3. **The Upstream WAN Link:** Oversized drop-tail FIFO buffers at DSLAMs, CMTS, or ISP access nodes.

**The Research Goal:**  
Rather than guessing a single root cause when evidence is incomplete, this project establishes a **set-valued, abstention-capable localization model**. When edge vantage points are insufficient to disambiguate the bottleneck, the engine mathematically retains uncertainty (e.g. $\mathcal{R}_{\text{cand}} = \{\text{near\_link}, \text{gateway\_node}\}$ with `abstained = True`) and explicitly specifies the minimum-cost subsequent measurement (such as deploying a wired observer tap) required to resolve ambiguity.

---

## 🔬 Key Empirical Findings (Live Hardware)

Live residential experiments were conducted on **macOS (Darwin arm64)** using an **Apple Silicon M1 Pro client** connected to an **AVM FRITZ!Box 7530 AX Access Point** (5 GHz UNII-2C, Channel 48, 80 MHz channel width, 802.11ax) across two spatial configurations:
- **Position 1 (L1: Near AP, Line-of-Sight):** 1.2 m distance, clear Fresnel zone.
- **Position 2 (L2: Adjacent Room, Non-Line-of-Sight):** 8.5 m distance, obstructed by interior drywall.

### Measured Telemetry Comparison

| Metric | Position 1 (L1: LOS, 1.2m) | Position 2 (L2: NLOS, 8.5m) | Physical Mechanism & Diagnostic Impact |
| :--- | :---: | :---: | :--- |
| **Physical RSSI / Noise** | **-52 dBm / -88 dBm** | **-72 dBm / -89 dBm** | 20 dB RF path loss through drywall partition |
| **Signal-to-Noise Ratio (SNR)** | **36 dB** (Pristine channel) | **17 dB** (Contention boundary) | 19 dB degradation in channel quality |
| **802.11ax MCS Rate** | **MCS 10** (1024-QAM) | **MCS 2** (QPSK) | AP/Client dynamic rate adaptation fallback |
| **Physical Link Capacity** | **1134.0 Mbps** | **136.0 Mbps** | **88% reduction in wireless PHY capacity** |
| **Idle Wi-Fi RTT (p95)** | **4.4 ms** | **4.3 ms** | Unloaded baseline latency is virtually identical |
| **Loaded Wi-Fi RTT (p95)** | **58.5 ms** | **118.9 ms** | **2x queue latency inflation under TCP load** |
| **Wi-Fi Hop Bloat ($\Delta RTT_{\text{wifi}}$)** | **+54.1 ms** | **+114.6 ms** | Longer packet airtime backs up AP MAC software queue |
| **WAN Access Bloat ($\Delta RTT_{\text{wan}}$)** | **+43.9 ms** | **+13.4 ms** | Access link queueing under concurrent upstream load |
| **Total End-to-End Bloat** | **+98.0 ms** | **+128.0 ms** | Total delay observed by client under saturation load |
| **Localization Verdict** | `COMPOUND_BOTTLENECK` | `COMPOUND_BOTTLENECK` | **+114.6 ms on local Wi-Fi hop vs. +13.4 ms on WAN link** |

> **Key Physical Insight:** An unloaded ping test cannot detect wireless degradation: idle RTT at L2 is ~4.3 ms (identical to L1). However, under active TCP saturation, the lower PHY rate (MCS 2) requires drastically more airtime per frame, causing bufferbloat (+114.6 ms) directly inside the local wireless transmission queue.

Raw time-series telemetry and cryptographically signed manifests are archived in:  
[`data/raw/live_home_runs/`](data/raw/live_home_runs/)

---

## 🏛️ System Architecture

The codebase unifies two complementary experimental environments into a single coherent Python package:

```mermaid
flowchart TD
    subgraph Empirical ["1. Empirical Residential Telemetry (wifi_lab)"]
        LiveScript["scripts/live_home_test.py"] -->|Dual-Vantage Probing| LiveRuns["data/raw/live_home_runs/"]
        LiveRuns -->|Ingest probes.csv| WiFiAnalysis["wifi_lab.analysis"]
        WiFiAnalysis --> WiFiSummary["data/processed/live_home/"]
        WiFiAnalysis --> Figures["results/figures/live_home/*.svg"]
        WiFiSummary --> WiSlowRules["wifi_lab.diagnostics (WiSlow Rules)"]
        MLOSim["wifi_lab.mlo_sim"] --> MLOFig["results/figures/fig5_mlo_vs_single_link.svg"]
    end

    subgraph Controlled ["2. Controlled Reference Lab (bll)"]
        BLLCLI["bll CLI (doctor, run, infer, export, report)"]
        BLLTopology["Linux 6-Node Netns Topology (ip netns + tc)"]
        BLLMeasurements["Concurrent Measurement Engine (iperf3 + ping)"]
        BLLStorage["DuckDB Analytical Storage (Parquet Tables)"]
        BLLInference["Deterministic Set-Valued Inference Engine"]
        BLLBenchmark["Double-Blind Benchmark Evaluator"]
        BLLRedactor["RFC 2330 Privacy Redactor & Static HTML Report"]

        BLLCLI --> BLLTopology
        BLLTopology --> BLLMeasurements
        BLLMeasurements --> BLLStorage
        BLLStorage --> BLLInference
        BLLInference --> BLLBenchmark
        BLLInference --> BLLRedactor
    end
```

### Directory Structure

```text
wifi-diagnostic-lab/
├── src/
│   ├── wifi_lab/                  # Wi-Fi Diagnostic Suite (WiSlow-inspired)
│   │   ├── cli.py                 # CLI interface: doctor, collect, analyze, suggest, mlo-sim, report
│   │   ├── runner.py              # Multi-phase execution and offline replay engine
│   │   ├── analysis.py            # Dual-format statistical parser (probes.csv & raw iperf/ping)
│   │   ├── diagnostics.py         # WiSlow evidence-based diagnostic decision trees
│   │   ├── mlo_sim.py             # Wi-Fi 7 (802.11be) Multi-Link Operation queue simulator
│   │   └── redactor.py            # RFC 2330 pseudonymization and hashing engine
│   └── bll/                       # Bufferbloat Localization Lab (Reference System)
│       ├── cli.py                 # bll CLI: doctor, lab, run, infer, export, report, evaluate
│       ├── topology/              # 6-node netns topology & longest prefix match (LPM) verification
│       ├── helper/                # Hardened JSON-RPC privileged helper daemon
│       ├── measurements/          # Concurrent iperf3 saturation + ping probe engine
│       ├── storage/               # DuckDB analytical layer over immutable Parquet tables
│       ├── inference/             # Differential path algebra & set-valued abstention
│       └── evaluation/            # Counterexample benchmark & hypothesis testing (H1, H2, H3)
├── scripts/
│   ├── live_home_test.py          # Standalone macOS dual-vantage live home test runner
│   └── reproduce.sh               # One-click automated reproduction script
├── data/
│   ├── raw/live_home_runs/        # Empirical physical residential Wi-Fi 6 measurement runs
│   ├── raw/pilot/                 # Synthetic reference pilot runs for pipeline calibration
│   └── processed/                 # Normalized run summary and sample time-series CSVs
├── results/
│   └── figures/                   # Publication-quality vector figures (SVG)
├── tests/                         # 196 Unit, contract, invariant & fault injection tests
└── e2e_tests/                     # 286 End-to-End acceptance tests across Milestones 1–7
```

---

## 📐 Differential Path Algebra & Inference Theory

The inference engine operates on path-level latency inflation under active load compared to an uncontended baseline:

$$\Delta RTT(p) = RTT_{\text{load}, p95}(p) - RTT_{\text{idle}, \text{med}}(p)$$

### Multi-Path Latency Decomposition
In a dual-vantage residential setting:
- **Path 1 (Local Wireless Hop):** $\text{Client} \to \text{Gateway}$
  $$\text{Bloat}_{\text{wifi}} = \Delta RTT(\text{Client} \to \text{Gateway})$$
- **Path 2 (End-to-End Path):** $\text{Client} \to \text{Remote WAN}$
  $$\text{Bloat}_{\text{wan}} = \Delta RTT(\text{Client} \to \text{Remote}) - \Delta RTT(\text{Client} \to \text{Gateway})$$

### Vantage Profiles & Mathematical Abstention

The inference engine strictly honors the observation capability of the vantage configuration without hallucinating labels:

| Vantage Profile | Available Observation Paths | Supported Regions | Inconclusive / Candidate Regions ($\mathcal{R}_{\text{cand}}$) | Abstention Verdict | Recommended Action |
| :--- | :--- | :--- | :--- | :---: | :--- |
| `remote_only` | $\text{Client} \to \text{Remote}$ | `[]` | `[near_link, gateway_node, far_link]` | `True` | `deploy_dual_vantage_probes` |
| `gateway_remote` | $\text{Client} \to \text{Gateway}$, $\text{Client} \to \text{Remote}$ | `[near_link]` or `[far_link]` | `[gateway_node]` (egress vs ingress) | Depends on $\Delta RTT$ | `deploy_wired_observer_tap` |
| `full_observer` | $\text{Client} \to \text{GW}$, $\text{Client} \to \text{Remote}$, $\text{Observer} \to \text{Remote}$ | Exact Region Isolated | `[]` | `False` | Disambiguation complete |

> **Zero Label Leakage Guarantee:** The inference engine strictly inspects measured delay metrics from `samples/ping.parquet` (or `probes.csv`) via DuckDB SQL. It never inspects scenario identifiers, configuration metadata, or ground-truth files during inference.

---

## 🧪 Controlled Reference Lab & Counterexamples

To validate inference reliability, BLL includes a double-blind counterexample benchmark comprising **12 controlled reference scenarios**:

1. `healthy_baseline`: Pristine link with zero induced queueing.
2. `residential_dsl_near_fifo`: Bufferbloat induced strictly at the customer access link (`q_near`).
3. `cable_asymmetric_far_fifo`: Bufferbloat induced at the remote ISP access link (`q_far`).
4. `dual_fifo_contention`: Compound bufferbloat present simultaneously on near and far links.
5. `fixed_propagation_delay_control`: Satellite/propagation delay without packet queueing (validates that fixed delay is not misclassified as bufferbloat).
6. `random_loss_without_queue`: High packet loss without queue buildup (validates loss independence).
7. `endpoint_cpu_bottleneck`: Host CPU saturation simulating processing delay.
8. `aqm_active_fq_codel`: Active Queue Management keeping loaded delay bounded under saturation.
9. `aqm_active_cake`: CAKE queue discipline with bandwidth shaping.
10. `indistinguishable_access_vs_gateway`: Demonstrates legitimate mathematical abstention under missing observer tap.
11. `bursty_cross_traffic`: Transient bursts testing filter resilience.
12. `reverse_path_asymmetry`: Asymmetric routing testing bidirectional delay decomposition.

### Statistical Release Criteria
The benchmark evaluator computes empirical metrics over all reference runs:
- **Conditional Localization Error (CLE):** $\text{CLE} \le 0.10$ (Zero false claims when non-abstained).
- **Region-Set Coverage (RSC):** $\text{RSC} \ge 0.95$ (True bottleneck included in candidate set $\ge 95\%$ of cases).
- **Negative Control False Positive Rate (FPR):** $\text{FPR} \le 0.05$ (Healthy baseline correctly classified as unbloated).

---

## ⚡ Quickstart & Usage

### 1. Installation

Install via standard virtual environment or [uv](https://github.com/astral-sh/uv):

```bash
# Clone the repository
git clone https://github.com/Akifulutas/wifi-diagnostic-lab.git
cd wifi-diagnostic-lab

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install with development and analysis dependencies
pip install -e ".[dev,analysis]"
```

### 2. Verify System Preflight

```bash
# Check Wi-Fi diagnostic environment
wifi-lab doctor

# Check Bufferbloat Localization Lab backend and tool readiness
bll doctor --json
```

### 3. Run Live Residential Probing (macOS / Linux)

Execute a 30-second 3-phase dual-vantage test (8s Idle $\to$ 15s Load $\to$ 7s Recovery) measuring local gateway RTT vs. remote WAN RTT:

```bash
# Near router (Line-of-Sight)
python3 scripts/live_home_test.py --position L1 --idle 8 --load 15 --recovery 7

# Move to an adjacent room (Non-Line-of-Sight)
python3 scripts/live_home_test.py --position L2 --idle 8 --load 15 --recovery 7
```

### 4. Process Live Runs into Publication Figures

```bash
wifi-lab analyze data/raw/live_home_runs \
  --output-dir data/processed/live_home \
  --figures-dir results/figures/live_home
```

### 5. Run Controlled Benchmark & Generate Static HTML Report

```bash
# Execute counterexample suite via simulation backend
bll run --backend mock_simulation --config configs/pilot.toml --output runs/pilot_01

# Execute deterministic inference engine
bll infer --run-dir runs/pilot_01

# Export sanitized dataset complying with RFC 2330 / RFC 5737
bll export --run-dir runs/pilot_01 --output export/redacted_dataset --redact

# Generate zero-CDN offline HTML research report
bll report --run-dir runs/pilot_01 --output results/bll_report.html
```

---

## 📊 Publication Figures & Visualizations

The automated analysis pipeline generates publication-ready vector figures (SVG) directly from measured telemetry:

| Figure | Description | Key Insight |
| :--- | :--- | :--- |
| **[Figure 1](results/figures/live_home/fig1_throughput_by_condition.svg)** | Throughput by Condition & Direction | L1 reaches near GbE ceiling; L2 experiences 39% throughput reduction due to RF path loss. |
| **[Figure 2](results/figures/live_home/fig2_rtt_ecdf.svg)** | Latency Empirical CDF | Bifurcation between idle baseline (< 5 ms) and loaded saturation (> 80 ms). |
| **[Figure 3](results/figures/live_home/fig3_rtt_timeseries.svg)** | 4-Phase Time-Series Dynamics | Shows steady idle baseline, slow-start ramp, saturation plateau, and rapid buffer drain recovery. |
| **[Figure 4](results/figures/live_home/fig4_loaded_delta_rtt.svg)** | Loaded $\Delta RTT$ (Bufferbloat) | Isolates +114.6 ms of queueing delay to the local Wi-Fi hop at L2. |
| **[Figure 5](results/figures/fig5_mlo_vs_single_link.svg)** | Wi-Fi 7 MLO Simulation | Compares Single-Link 5 GHz vs. MLO (2.4 GHz + 5 GHz) queueing latency reduction. |

---

## 🛡️ Verification & Test Pyramid

The repository enforces software engineering and test determinism rules:

```bash
# 1. Unit, Contract, Invariant & Fault Injection Tests (196 tests)
pytest tests/

# 2. End-to-End Acceptance Suite across Milestones 1–7 (286 tests)
python3 e2e_tests/run_e2e.py

# 3. Privacy & Secret Leakage Audit
gitleaks git .
```

**Verification Results:**
- **Unit & Contract Tests:** 196 passed (100% pass rate in ~13s).
- **End-to-End Acceptance Tests:** 285 passed, 1 skipped (requires native Linux `ip netns`), 0 failed.
- **Security & Secrets Scan:** Zero credentials, private keys, or tokens committed.

---

## 🔒 Data Provenance & Privacy Ethics

To comply with open-science principles and privacy standards (RFC 2330 and RFC 5737):
1. **Explicit Data Provenance:** Synthetic pilot runs (`data/raw/pilot/`) are explicitly distinguished from real physical residential measurements (`data/raw/live_home_runs/`).
2. **Deterministic Pseudonymization:** `bll export --redact` scrubs all MAC addresses (`02:00:00:xx:xx:xx`), maps private IPv4 addresses to the documentation subnet (`192.0.2.0/24`), and sanitizes Wi-Fi SSIDs while preserving mathematical delta RTT relationships.
3. **Cryptographic Integrity:** Every experiment run includes an immutable `manifest.json` with SHA-256 digests over all raw logs and analytical tables.

---

## 🎓 Academic Context & About the Author

This project was conceived and developed by **Akif Ulutaş**, an undergraduate Computer Science / Computer Engineering student at **RWTH Aachen University**.

- **Research Interests:** Computer Networks, Wireless Systems, Active Queue Management, Distributed Systems, and Measurement-Driven Diagnostics.
- **Project Purpose:** Created as an independent research engineering testbed in preparation for the **Undergraduate Research Opportunities Programme (UROP)**. It reflects a commitment to reproducible open science, rigorous software architecture, deterministic testing, and continuous learning.

---

## 📚 Scientific References

1. **Kim, K., Nam, Y., & Schulzrinne, H.** (2014). *WiSlow: A Wi-Fi Network Performance Troubleshooting Tool for End Users.* IEEE INFOCOM.
2. **Nichols, K., & Jacobson, V.** (2012). *Controlling Queue Delay (CoDel).* ACM Queue, 10(5), 20–34.
3. **Høiland-Jørgensen, T., Hurtig, P., & Brunstrom, A.** (2014). *The Flent Network Testing Tool.* Netdev 0.1.
4. **Gettys, J., & Nichols, K.** (2011). *Bufferbloat: Dark Buffers in the Internet.* Communications of the ACM, 55(1), 57–65.
5. **Paxson, V., Almes, G., Mahdavi, J., & Mathis, M.** (1998). *Framework for IP Performance Metrics.* IETF RFC 2330.
6. **Almes, G., Kalidindi, S., & Zekauskas, M.** (1999). *A One-way Delay Metric for IPPM.* IETF RFC 2679 / RFC 3393.
7. **Carrascosa, M., Bellalta, B., et al.** (2023). *Wi-Fi Multi-Link Operation: Status and Open Challenges.* IEEE Communications Magazine, 61(12).

---

## 📜 License

MIT License. Copyright (c) 2026 Akif Ulutaş (RWTH Aachen University). See [LICENSE](LICENSE) for details.
