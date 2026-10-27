# Bufferbloat Localization Lab (BLL) — Assumptions & Foundations

This document establishes the scientific foundations, architectural constraints, and engineering decisions governing the Bufferbloat Localization Lab (BLL). In accordance with open-science principles, assumptions are strictly categorized into **Facts**, **Decisions**, **Hypotheses**, and **Unknowns**.

---

## 1. Facts (Empirically Verified & Technical Constraints)

### F1. Linux Kernel Networking & Traffic Control Primitives
- **Network Namespaces (`ip netns`)**: Network namespaces provide complete isolation of network stack state (interfaces, routing tables, socket lists, neighbor tables, and firewall rules) while sharing the host CPU and memory subsystems.
- **Traffic Control (`tc`)**: Linux Traffic Control operates on packet transmission (egress). Ingress queueing disciplines cannot queue packets without queuing intermediate devices (`ifb`). Rate shaping (`tbf`, `htb`), packet queuing (`pfifo`, `bfifo`), active queue management (`fq_codel`, `cake`), and artificial delay/loss (`netem`) are kernel-space qdiscs configured via the netlink interface.
- **Interface Naming Limit**: In the Linux kernel, network interface names are bounded by `IFNAMSIZ` to 16 bytes (15 ASCII characters plus a null terminator). All interface identifiers in BLL must be strictly $\le 15$ characters.
- **Capability Requirements**: Creation of network namespaces, virtual ethernet pairs (`veth`), and `tc` qdisc manipulation requires `CAP_NET_ADMIN` privileges in the initial user namespace.

### F2. macOS / Darwin Platform Invariants & Virtualization
- **Darwin Kernel Incompatibility**: Darwin (macOS XNU) does not support Linux network namespaces, Linux `veth` pairs, or Linux `tc` qdiscs.
- **Local Development Parity**: Running native reference network experiments on macOS requires containerized Linux (e.g., Docker Desktop, Colima, OrbStack, or Lima VM) running with `--cap-add=NET_ADMIN`.
- **Measurement Tool Differences**: macOS native BSD `ping` lacks the `-D` (microsecond epoch timestamp prefix) and `-O` (outstanding request reporting) options present in Linux `iputils-ping`.

### F3. Single-Host Time Coherence in Network Namespaces
- **Shared Kernel Clock**: In standard Linux network namespaces, all namespaces share the host kernel monotonic clock (`CLOCK_MONOTONIC_RAW`) and wall clock (`CLOCK_REALTIME`). Linux does not virtualize the system clock across network namespaces unless unshared time namespaces (`CLONE_NEWTIME`) with non-zero offsets are explicitly constructed.
- **Microsecond Relative Accuracy**: Within a single-host netns reference lab, relative timestamp offsets across namespaces are negligible ($< 1\ \mu\text{s}$), enabling precise causal ordering of packet events.

### F4. Measurement Tool Capabilities & Formats
- **`iperf3`**: Generates bulk TCP and UDP flows and outputs per-interval and summary telemetry in structured JSON (`-J`), including instantaneous throughput, TCP retransmissions, socket congestion window (`snd_cwnd`), and kernel-estimated RTT.
- **`irtt`**: Isochronous Round-Trip Tester measures UDP round-trip time, one-way delay, packet loss, and Instantaneous Packet Delay Variation (IPDV / jitter) using sleep compensation (`--timer=comp`) and structured JSON output.
- **`ping` (`iputils`)**: Emits sub-second interval ICMP echo requests with microsecond timestamps (`-D`) and outstanding probe alerts (`-O`).

---

## 2. Decisions (Architectural Invariants & Explicit Choices)

### D1. Multi-Backend Runtime Abstraction
- BLL shall implement four distinct execution backends:
  1. `NativeLinuxBackend`: Direct Linux execution using `ip netns` and the `bll-lab-helper` privileged daemon.
  2. `ContainerLinuxBackend`: Execution within a privileged Debian/Ubuntu Docker or Colima container for macOS workstations and containerized CI runners.
  3. `VMLinuxBackend`: Ephemeral Linux VM execution via Lima (`limactl`).
  4. `MockSimulationBackend`: In-memory software simulation producing synthetic network events and deterministic Parquet tables for local unit and contract testing without root privileges.

### D2. Unprivileged Controller & Privileged Helper Separation
- The core experiment orchestrator, CLI, telemetry collectors, and inference engine shall run strictly as an unprivileged user.
- All privileged operations (`ip netns add`, `ip link add`, `tc qdisc add`, routing configuration) shall be delegated to a dedicated standalone helper (`bll-lab-helper`).
- The helper shall strictly manage resources prefixed with `bll-`, reject arbitrary shell commands (no `shell=True`), validate parameters with strict regexes, and drop privileges back to the invoking user (`SUDO_UID`) when spawning measurement binaries.

### D3. Decoupled Traffic Control (Shaping vs. Propagation Delay)
- Rate shaping (`tbf`/`htb`) and queue backlog limits (`pfifo`/`bfifo`/`fq_codel`/`cake`) shall be configured exclusively on forwarder egress interfaces (`bll-qn-rtr` and `bll-qf-rem`).
- Pure propagation delay (`netem`) shall be placed exclusively on link peer egress interfaces (`bll-rtr-qn` and `bll-rtr-qf`).
- This physical link decoupling eliminates kernel timer wheel contention between token bucket replenishment and netem delay queuing.

### D4. Physical Ground-Truth Isolation & Zero Label Leakage
- Telemetry and experiment data shall be written to immutable run directories `runs/<run_id>/` containing only operational parameters (IPs, durations, ports).
- Ground-truth scenario labels and injected bottleneck parameters shall be written exclusively to `ground_truth/<opaque_run_id>.json`.
- The inference engine (`bll infer`) is physically and logically prohibited from accessing `ground_truth/`. Any code reading `ground_truth/` during inference constitutes an invalidating test failure.
- Only the double-blind evaluator (`bll evaluate`) is permitted to cross-reference `runs/` and `ground_truth/`.

### D5. Deterministic, Set-Valued Differential Path Algebra
- The inference engine shall not employ machine learning or large language models in the primary decision path.
- Localization decisions shall be derived through differential path algebra:
  $$\Delta \text{RTT}(p_{\text{long}}) - \Delta \text{RTT}(p_{\text{short}}) \implies \text{Evidence on differential segment } p_{\text{long}} \setminus p_{\text{short}}$$
- When telemetry cannot discriminate between candidate regions, the engine shall maintain set-valued uncertainty ($S \subseteq C \subseteq \mathcal{R}$) and formally abstain (`abstained = true`, `abstain_reason = "AMBIGUOUS_VANTAGE_COVERAGE"`) rather than issuing an arbitrary or probabilistic guess.

### D6. Three-Phase Orchestration & Clock Monotonicity Gating
- Measurement runs shall follow a 3-phase state machine:
  1. *Baseline Idle* (~20s): Probe-only calibration of unloaded delay ($RTT_0$) and jitter.
  2. *Saturation Load* (~60s): Active throughput load generation forcing queue accumulation.
  3. *Recovery* (~30s): Load cessation observing buffer draining dynamics ($T_{\text{drain}}$).
- All timeseries samples shall record nanosecond monotonic timestamps (`CLOCK_MONOTONIC_RAW`).
- One-way delay (OWD) forward and reverse metrics shall be gated behind strict clock synchronization validation ($\text{maxerror} < 1000\ \mu\text{s}$ or single-host netns confirmation). If unverified, OWD fields are recorded as `NULL`, and the engine relies exclusively on round-trip delay.

### D7. Open Science, Zero-CDN Reporting & RFC 2330 Redaction
- BLL reports shall be generated as self-contained static HTML documents with embedded CSS and inlined SVGs, executing zero external network requests and containing no CDN dependencies.
- Datasets prepared for public dissemination (`bll export --redact`) shall sanitize MAC addresses, private IPv4/IPv6 addresses, SSIDs, and hostnames in compliance with RFC 2330, publishing SHA-256 provenance manifests.

---

## 3. Hypotheses (Empirical Propositions to be Tested)

### H1. Marginal Value of an Independent Wired Observer
- **Proposition**: Adding an independent wired observation vantage point tapped at the router ($V_{\text{observer}\to\text{remote}}$ and $V_{\text{client}\to\text{observer}}$) reduces the candidate region set size $|C|$ by $\ge 50\%$ and increases conditional localization accuracy from $< 50\%$ to $> 95\%$ compared to single-vantage end-to-end RTT ($V_{\text{client}\to\text{remote}}$).
- **Verification Protocol**: Paired Wilcoxon signed-rank test and 95% bootstrap confidence interval across $\ge 50$ runs in the 4-vantage ablation harness.

### H2. Abstention on Indistinguishable Bottleneck Pairs
- **Proposition**: When bottleneck locations are topologically indistinguishable with respect to active vantage points (e.g. gateway egress vs far link ingress under client-only probing), the set-valued inference engine correctly emits `abstained = true` with `abstain_reason = "INDISTINGUISHABLE_TOPOLOGY"`, achieving an over-precision error rate of exactly 0.0%.
- **Verification Protocol**: Execution across Scenarios 11 and 12 (`indistinguishable_pair_a` and `b`) under restricted vantage configurations.

### H3. Protocol Discrepancies under Active Queue Management
- **Proposition**: In networks employing flow-isolating Active Queue Management (e.g., FQ-CoDel, RFC 8290, or CAKE), ICMP ping probes traversing sparse hash queues systematically underestimate loaded TCP latency by $\ge 80\%$, whereas TCP-correlated probes detect true queue sojourn times ($\text{ProtocolBiasRatio} \ge 5.0$).
- **Verification Protocol**: Comparative latency distribution testing between ICMP ping, UDP IRTT, and TCP round-trip telemetry under Scenario 10 (`protocol_difference`).

---

## 4. Unknowns (Open Empirical Questions & Risks)

### U1. Containerized Linux Virtualization Jitter on macOS
- **Question**: To what extent does macOS hypervisor scheduling (Hypervisor.framework / Virtualization.framework in Docker Desktop or Colima) introduce non-deterministic microsecond latency jitter into `tc netem` delay emulation compared to bare-metal Linux kernels?
- **Investigation Plan**: Benchmark idle ping RTT variance between bare-metal Linux and macOS containerized Linux.

### U2. Consumer Router Hardware Offload & AQM Classification
- **Question**: Do commercial off-the-shelf home gateways with hardware flow offloading (e.g. MediaTek NSS, Qualcomm ECM) bypass CPU-based FQ-CoDel / CAKE qdiscs for UDP or ICMP traffic, altering the observability of bufferbloat?
- **Investigation Plan**: Test physical router hardware in future hardware-in-the-loop milestones.

### U3. Multi-Host Wide-Area Clock Drift Rates
- **Question**: In distributed multi-host deployments where client and remote servers reside on separate physical hardware across the Internet, can software NTP achieve the $< 1\text{ ms}$ synchronization required for one-way delay gating, or is hardware PTP (IEEE 1588) mandatory?
- **Investigation Plan**: Evaluate clock offset distributions under varying NTP poll intervals and network jitter in distributed testbeds.
