# Project: Bufferbloat Localization Lab (BLL)

## Architecture
Bufferbloat Localization Lab (BLL) is an open-science measurement, experiment, and inference system designed to localize loaded network latency to specific network regions using controlled physical evidence, retain set-valued uncertainty when observations are ambiguous, and suggest the cost-optimal subsequent measurement to resolve ambiguity.

### System Overview & Data Flow
```
+---------------------------------------------------------------------------------------------------+
|                                      CLI Entry Point (`bll`)                                      |
+---------------------------------------------------------------------------------------------------+
       |                    |                       |                        |                |
       v                    v                       v                        v                v
  `bll doctor`         `bll lab`              `bll run`                `bll infer`       `bll export`
  (Platform &         (Privileged Helper:   (Phase Engine:           (Deterministic     (RFC 2330 Redactor
   Capability Probe)   Netns & Tc Setup)     ping, irtt, iperf3)       Evidence Engine)  & HTML Reporter)
       |                    |                       |                        |                |
       |                    v                       v                        |                |
       |             [Linux Netns Lab] ----> [Immutable Run Dir] ----------->+                |
       |             - bll-client            `runs/<opaque_run_id>/`         |                |
       |             - bll-qnear             - manifest.json                 |                |
       |             - bll-router            - experiment.yaml               |                |
       |             - bll-observer          - events.jsonl                  |                |
       |             - bll-qfar              - topology.json                 v                |
       |             - bll-remote            - quality.json             [Localization         |
       |                                     - raw/*                    Output Contract]      |
       |                                     - samples/*.parquet             |                |
       |                                                                     v                v
       |                                     [Isolated Ground Truth]    [Evaluator &     [Static Offline
       |                                     `ground_truth/<id>.json`->  Benchmark]       Report / Export]
       |                                     (Physical separation)
+---------------------------------------------------------------------------------------------------+
```

### Key Architectural Pillars
1. **Unprivileged Controller & Privileged Helper Separation (R1, R2)**:
   The experiment runner operates unprivileged. Privileged operations (netns creation, veth configuration, tc qdisc manipulation, routing tables) are strictly delegated to `bll-lab-helper` via UNIX domain socket or sudo wrapper. The helper validates resource names (`bll-` prefix only) and executes array-based commands with zero shell interpolation (`shell=False`).
2. **Decoupled Traffic Control Architecture (R1)**:
   Rate shaping and queue backlog emulation (`tbf`/`htb` + `pfifo`/`bfifo`/`fq_codel`/`cake`) are configured exclusively on forwarder egress towards router/remote. Pure propagation delay (`netem`) is configured on link peer egress, preventing Linux kernel timer wheel distortion.
3. **Phase-Orchestrated Telemetry & Clock Monotonicity (R3)**:
   A 3-phase state machine (Baseline Idle ~20s, Saturation Load ~60s, Recovery ~30s) runs continuous telemetry (`ping`, `irtt`) while modulating traffic generators (`iperf3`). Nanosecond monotonic clocks (`CLOCK_MONOTONIC_RAW`) eliminate NTP time skew. One-way delay is gated on strict cross-host clock synchronization verification.
4. **Physical Ground-Truth Separation & Immutable Parquet Pipeline (R4)**:
   Raw measurements, events, and telemetry are stored immutably in `runs/<run_id>/`. Ground-truth scenario specifications are physically isolated in `ground_truth/<opaque_run_id>.json`. The inference engine has zero access to `ground_truth/`, eliminating label leakage.
5. **Deterministic Set-Valued Inference Engine (R5)**:
   Primary decision paths rely on explainable differential path algebra and queue dynamics (buffer drain time, latency inflation, load association). The engine outputs set-valued candidate regions ($\mathcal{R}_{\text{cand}} \subseteq \{\text{local}, \text{near}, \text{gateway}, \text{far}, \text{remote}\}$) and abstains with an explicit reason whenever observations are ambiguous, followed by cost-optimal next-step recommendations.
6. **Controlled Scenarios, Ablation & Hypothesis Testing (R6)**:
   A 12-scenario counterexample suite validates positive bufferbloat, negative controls (e.g. fixed delay without queue, CPU saturation), and AQM behaviors. A 4-vantage ablation harness rigorously tests hypotheses H1 (wired observer value), H2 (abstention on indistinguishable pairs), and H3 (protocol discrepancy).
7. **Open Science & Privacy (R7)**:
   Zero-CDN static offline HTML reports with inlined SVGs; RFC 2330 privacy-preserving redaction engine (`bll export --redact`) with SHA-256 provenance manifests; double-blind benchmark evaluator.

---

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | `bll doctor --json` | Discovers local platform, kernel capabilities, virtualization, and tool binaries (ping, irtt, iperf3, tc) | M1 | R1, R2, Day 1 |
| 2 | Core Assumptions Doc | `docs/assumptions.md` separating facts, decisions, hypotheses, and unknowns | M1 | Day 1 |
| 3 | Schema v1 Definitions | JSON Schema and PyArrow contracts for manifest, events, quality, ground_truth, parquet, and inference | M1 | Day 1, R4, R5 |
| 4 | Multi-Backend Abstraction | NativeLinuxBackend, ContainerLinuxBackend (macOS Docker/Lima), and MockSimulationBackend | M1 | R1, R2 |
| 5 | Privileged Helper `bll-lab-helper` | Hardened JSON-RPC helper with `bll-` prefix gating, zero shell execution, and privilege dropping | M2 | R2, Day 2 |
| 6 | 6-Node Netns Reference Lab | `bll-client`, `bll-qnear`, `bll-router`, `bll-observer`, `bll-qfar`, `bll-remote` over 5 point-to-point `/30` subnets | M2 | R1, Day 2 |
| 7 | Path Matrix Invariant Verification | Automated FIB route & interface verification ensuring path isolation (Client->Observer, Observer->Remote, Client->Remote) | M2 | R1, Day 2 |
| 8 | Decoupled Tc Shaping & Netem | Forwarder egress rate shaping (`tbf`/`htb`) + queue (`pfifo`/`bfifo`/`fq_codel`/`cake`) + peer `netem` delay | M2 | R1, Day 2 |
| 9 | Idempotent Lab Lifecycle | `bll lab up`, `bll lab verify`, and `bll lab down` with 100% leak-free cleanup under normal exit, crash, and SIGKILL | M2 | R2, Day 2, 2-Week Gate |
| 10 | Measurement Adapters | Standardized adapters for `ping` (ICMP), `irtt` (UDP isochronous RTT/loss/IPDV), and `iperf3` (TCP/UDP load) | M3 | R3, Day 3 |
| 11 | Multi-Phase Measurement Engine | 3-phase execution (Baseline Idle ~20s, Saturation Load ~60s, Recovery ~30s) across upload, download, and bidir | M3 | R3, Day 3 |
| 12 | Clock Monotonicity & Sync Gating | Nanosecond monotonic clock tracking; strict cross-host clock sync validation before publishing one-way delay | M3 | R3 |
| 13 | Immutable Run Directory Pipeline | `runs/<run_id>/` saving `manifest.json`, `experiment.yaml`, `events.jsonl`, `tool-versions.json`, `topology.json`, `quality.json`, `raw/*`, `samples/*.parquet` | M3 | R4, Day 3 |
| 14 | Physical Ground-Truth Separation | Isolated storage in `ground_truth/<opaque_run_id>.json` with zero label leakage to inference engine | M3 | R4, 2-Week Gate |
| 15 | DuckDB Telemetry Analytics | High-performance SQL queries over PyArrow Parquet tables (`ping`, `irtt`, `iperf3`, `qdisc`, `system`) | M3 | R4 |
| 16 | Differential Path Algebra Engine | Set-valued deterministic evidence rules without ML or LLM in primary decision path | M4 | R5 |
| 17 | Output Contract & JSON Schema v1 | Schema v1.0.0 output contract including `latency_increase_observed`, `supported_regions`, `queue_evidence`, etc. | M4 | R5 |
| 18 | Set-Valued Ambiguity & Abstention | Explicit abstention when vantage points cannot discriminate candidate regions (e.g. gateway vs access link vs upstream) | M4 | R5 |
| 19 | Cost-Optimal Next Measurement Selector | Recommends lowest-cost discriminating test to resolve ambiguity across 5 cost tiers | M4 | R5 |
| 20 | 12-Scenario Counterexample Suite | Controlled netns test scenarios (healthy, near FIFO, far FIFO, dual FIFO, fixed delay, CPU delay, AQMs, indistinguishable pairs) | M5 | R6, 2-Week Gate |
| 21 | Quality Control Flagging | 8 flags (`MISSING_PHASE`, `UNREACHED_LOAD`, `ROUTE_CHANGE`, `UNVERIFIED_QDISC`, `OBSERVER_UNAVAILABLE`, etc.) | M5 | R6 |
| 22 | 4-Vantage Ablation Harness | Evaluates inference accuracy across (1) Remote RTT only, (2) Gateway+Remote, (3) Local+Remote, (4) Local+Remote+Observer | M5 | R6, 8-Week Benchmark |
| 23 | Statistical Hypothesis Verification | Rigorous verification of H1 (observer marginal value with 95% CI), H2 (abstention on indistinguishable pairs), and H3 (protocol discrepancy) | M5 | R6, 8-Week Benchmark |
| 24 | Static Zero-CDN HTML & JSON Reporting | Single-command offline reporting with inlined SVGs and complete absence of external network dependencies | M6 | R7, Day 3, 8-Week Benchmark |
| 25 | RFC 2330 Redaction Engine | `bll export --redact` scrubbing private MACs, IPs, SSIDs, and credentials with SHA-256 provenance manifest | M6 | R7, 8-Week Benchmark |
| 26 | Double-Blind Benchmark Evaluator | `bll evaluate` scoring third-party inference algorithms against locked reference datasets (CLE, RSC, FPR, DC, CSR) | M6 | R7, 8-Week Benchmark |
| 27 | Full E2E Test Suite Pass (Tiers 1-4) | Passing 100% of requirement-derived opaque-box E2E tests generated by E2E Testing Track | M7 | Final Milestone Phase 1 |
| 28 | Adversarial Coverage Hardening (Tier 5) | White-box adversarial testing by Challenger agents closing all remaining edge cases and verifying 8-week criteria | M7 | Final Milestone Phase 2 |

---

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Core Schemas, Platform Discovery & Assumptions | `bll doctor --json`, `docs/assumptions.md`, Schema v1 definitions, multi-backend abstraction | none | DONE |
| M2 | Privileged Helper & Netns Reference Topology | `bll-lab-helper`, 6-node netns topology, path matrix invariants, decoupled tc, idempotent `bll lab` lifecycle | M1 | DONE |
| M3 | Measurement Adapters, Phase Engine & Immutable Pipeline | Adapters (ping, irtt, iperf3), 3-phase engine, monotonic clocks, `runs/<run_id>/`, DuckDB/Parquet, physical ground-truth isolation | M1, M2 | DONE |
| M4 | Deterministic Inference Engine, Ambiguity & Next Measurement | Differential path algebra, JSON Schema v1.0.0 output contract, queue evidence scoring, set-valued abstention, next measurement selector | M1, M3 | DONE |
| M5 | 12-Scenario Counterexample Suite, Quality Control & Ablations | 12 core scenarios, 8 QC flags, 4-vantage ablation harness, statistical testing of H1, H2, and H3 | M2, M3, M4 | DONE |
| M6 | Open-Science Reporting, RFC 2330 Redaction & Benchmark Evaluator | Zero-CDN static HTML/JSON report, RFC 2330 redaction (`bll export --redact`), double-blind `bll evaluate` benchmark | M3, M4, M5 | DONE |
| M7 | Final Milestone: 100% E2E Test Pass & Adversarial Hardening | Phase 1: Pass 100% of E2E tests (Tiers 1-4). Phase 2: Adversarial coverage hardening (Tier 5) verifying all 8-Week Release Benchmark Criteria | M1-M6, E2E Test Track | DONE |

---

## Interface Contracts

### 1. `bll.platform` ↔ `bll.cli` (`bll doctor --json`)
```python
class SystemCapability(pydantic.BaseModel):
    available: bool
    version: str | None = None
    path: str | None = None
    details: dict[str, Any] = pydantic.Field(default_factory=dict)

class BLLDoctorReport(pydantic.BaseModel):
    timestamp_utc: str
    os_name: str  # "Darwin", "Linux"
    kernel_release: str
    architecture: str
    selected_backend: Literal["native_linux", "container_linux", "vm_linux", "mock_simulation"]
    capabilities: dict[str, SystemCapability]  # netns, tc, iproute2, ping, irtt, iperf3, duckdb, pyarrow
    all_requirements_met: bool
    remediation_steps: list[str] = pydantic.Field(default_factory=list)
```

### 2. `bll.lab` ↔ `bll.helper` (JSON-RPC over UNIX Domain Socket / Sudo)
```python
# Helper Request Envelope
class HelperRequest(pydantic.BaseModel):
    method: Literal["create_topology", "verify_topology", "destroy_topology", "configure_qdisc", "reset_qdiscs", "exec_tool"]
    params: dict[str, Any]
    request_id: str

# Methods:
# - create_topology(params={"topology_name": "bll-default", "subnets": [...]}) -> {"status": "ok", "namespaces": [...], "interfaces": [...]}
# - verify_topology(params={"topology_name": "bll-default"}) -> {"verified": bool, "invariants": {"client_to_observer": bool, "observer_to_remote": bool, "client_to_remote": bool}, "details": list[str]}
# - destroy_topology(params={"topology_name": "bll-default"}) -> {"status": "ok", "deleted_namespaces": [...]}
# - configure_qdisc(params={"netns": str, "interface": str, "qdisc_type": str, "rate": str, "limit_bytes": int, ...}) -> {"status": "ok"}
# - exec_tool(params={"netns": str, "command": list[str], "user": str, "timeout_seconds": float}) -> {"exit_code": int, "stdout": str, "stderr": str}
```

### 3. `bll.pipeline` ↔ `bll.inference` (Run Directory & Data Contract)
```python
# Inference Engine receives strictly:
def run_inference(run_dir: pathlib.Path, vantage_profile: Literal["remote_only", "gateway_remote", "local_remote", "full_observer"] = "full_observer") -> InferenceOutputContract:
    """Reads ONLY runs/<run_id>/ (manifest.json, quality.json, topology.json, samples/*.parquet).
    Physically and logically prohibited from accessing ground_truth/."""
```

### 4. `bll.inference` Output Contract (JSON Schema v1.0.0)
```python
class QueueEvidenceLevel(str, enum.Enum):
    NONE = "none"
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"

class InferenceOutputContract(pydantic.BaseModel):
    run_id: str
    vantage_profile: str
    latency_increase_observed: bool
    load_association: float  # Pearson / Spearman correlation in [-1.0, 1.0]
    supported_regions: list[str]  # Subsets of {"local_host", "near_link", "gateway_node", "far_link", "remote_host"}
    not_excluded_regions: list[str]
    queue_evidence: QueueEvidenceLevel
    quality_flags: list[str]
    abstained: bool
    abstain_reason: str | None
    next_measurement: str | None
    supporting_run_ids: list[str]
```

### 5. `bll.evaluator` Benchmark Contract
```python
class ScenarioEvaluationResult(pydantic.BaseModel):
    run_id: str
    scenario_id: str
    ground_truth_region: str | None
    predicted_supported_regions: list[str]
    predicted_not_excluded_regions: list[str]
    abstained: bool
    abstain_reason: str | None
    is_correct: bool  # ground_truth_region in predicted_supported_regions (or correct negative control)
    is_false_positive: bool  # detected bufferbloat on negative control
    candidate_set_size: int

class BenchmarkSummary(pydantic.BaseModel):
    total_runs: int
    conditional_localization_error: float  # CLE <= 0.10
    region_set_coverage: float            # RSC >= 0.95
    negative_control_fpr: float            # FPR <= 0.05
    decision_coverage: float               # DC >= 0.70
    median_candidate_reduction: float      # CSR >= 0.50
    hypotheses_results: dict[str, Any]    # H1, H2, H3 p-values and confidence intervals
    gate_passed: bool
```

---

## Code Layout
```
/Users/akifulutas/Documents/UROP/bufferbloat-localization-lab/
├── pyproject.toml
├── README.md
├── docs/
│   ├── assumptions.md                     # Facts, decisions, hypotheses, unknowns
│   ├── topology.md                        # Netns topology & path matrix proof
│   └── schemas/                           # Schema v1 documentation
│       ├── manifest.schema.json
│       ├── quality.schema.json
│       ├── ground_truth.schema.json
│       └── inference.schema.json
├── docker/
│   ├── Dockerfile.lab                     # Debian Linux netns testbed for macOS / CI
│   └── docker-compose.yml
├── src/
│   └── bll/
│       ├── __init__.py
│       ├── cli.py                         # Click/Typer CLI entry point
│       ├── platform/                      # Platform discovery, bll doctor, capability probes
│       │   ├── __init__.py
│       │   ├── doctor.py
│       │   └── backends.py                # NativeLinux, ContainerLinux, MockSimulation
│       ├── lab/                           # Topology orchestration, netns, veth, tc
│       │   ├── __init__.py
│       │   ├── topology.py
│       │   ├── tc.py                      # Decoupled shaping & netem
│       │   ├── invariants.py              # Automated path matrix verification
│       │   └── helper_client.py
│       ├── helper/                        # bll-lab-helper privileged daemon
│       │   ├── __init__.py
│       │   ├── server.py                  # Hardened JSON-RPC
│       │   └── security.py                # bll- prefix whitelist & privilege drop
│       ├── adapters/                      # Measurement adapters
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── ping.py                    # ICMP ping adapter
│       │   ├── irtt.py                    # UDP IRTT adapter
│       │   └── iperf3.py                  # TCP/UDP iperf3 adapter
│       ├── runner/                        # Multi-phase execution engine
│       │   ├── __init__.py
│       │   ├── phase_engine.py            # Idle -> Load -> Recovery state machine
│       │   └── clock.py                   # Monotonic nanosecond timing & sync validation
│       ├── storage/                       # Immutable run storage & DuckDB parquet schemas
│       │   ├── __init__.py
│       │   ├── run_dir.py                 # runs/<run_id>/ layout manager
│       │   ├── ground_truth.py            # Physically isolated ground_truth/<id>.json
│       │   └── parquet_schemas.py         # PyArrow & DuckDB analytical schemas
│       ├── inference/                     # Deterministic evidence & localization engine
│       │   ├── __init__.py
│       │   ├── algebra.py                 # Differential path algebra
│       │   ├── engine.py                  # Set-valued localization engine
│       │   ├── abstention.py              # Ambiguity and abstention logic
│       │   └── next_measurement.py        # Cost-optimal test selector
│       ├── scenarios/                     # 12-scenario counterexample definitions
│       │   ├── __init__.py
│       │   ├── definitions.py
│       │   └── runner.py
│       ├── evaluation/                    # Ablation harness & benchmark evaluator
│       │   ├── __init__.py
│       │   ├── ablation.py                # 4-vantage ablation
│       │   ├── hypotheses.py              # H1, H2, H3 statistical verification
│       │   └── benchmark.py               # bll evaluate (CLE, RSC, FPR, DC, CSR)
│       └── reporting/                     # Open-science reporting & redaction
│           ├── __init__.py
│           ├── html_report.py             # Zero-CDN static HTML with inlined SVGs
│           ├── plots.py                   # Pure Python inlined SVG plot generation
│           └── redactor.py                # RFC 2330 privacy-preserving redactor
├── tests/
│   ├── unit/                              # Unit tests (schemas, algebra, redaction, adapters)
│   ├── contract/                          # Contract tests (JSON schemas, helper RPC, parquet)
│   ├── invariant/                         # Invariant tests (path matrix, clock monotonicity)
│   ├── netns/                             # Netns integration tests (requires Linux or container)
│   ├── fault_injection/                   # Fault injection (kill -9, SIGINT, timeout cleanup)
│   └── regression/                        # Determinism & ground-truth non-leakage regression
└── e2e_tests/                             # Opaque-box E2E tests created by E2E Testing Track
    ├── tier1_feature_coverage/
    ├── tier2_boundary_corner/
    ├── tier3_cross_feature/
    ├── tier4_real_world/
    └── run_e2e.py
