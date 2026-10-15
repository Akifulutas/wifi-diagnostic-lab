# Protocol Lab 03: The Mechanics of Bufferbloat and Queueing Latency

**Author:** Akif Ulutaş (RWTH Aachen University)  
**Topic:** Active Queue Management (AQM), Bufferbloat, and Latency under Load  
**Context:** Wi-Fi Diagnostic Lab Foundations

---

### 1. What is Bufferbloat?

**Bufferbloat** is the undesirable latency inflation caused by oversized, unmanaged FIFO (First-In, First-Out) packet buffers in network interfaces, switches, and consumer wireless access points. 

Historically, hardware manufacturers equipped routers with multi-megabyte RAM buffers to eliminate packet drops under bursty traffic, operating under the naive assumption that *"dropping packets is always bad."*

However, traditional TCP congestion control algorithms (such as TCP Cubic and Reno) rely on **packet drop as the primary feedback signal** to detect channel capacity. When buffers are excessively large, TCP fills the entire queue before a single packet is dropped. Packets sit in buffer queues for hundreds of milliseconds, destroying real-time performance.

```text
[ Incoming TCP Packets ] ──> [======= Huge FIFO Queue (Bufferbloat) =======] ──> [ Bottleneck Link ]
                                     |           |           |
                                  Packet 1    Packet 2    Packet N
                             (Queueing Delay = Buffer Size / Link Rate)
                                     ▲
[ Urgent ICMP / VoIP Probe ] ────────┘  (Trapped behind bulk TCP packets!)
```

---

### 2. Mathematical Model of Queueing Delay

Total one-way packet delay $D_{\text{total}}$ consists of four components:

$$D_{\text{total}} = D_{\text{proc}} + D_{\text{queue}} + D_{\text{trans}} + D_{\text{prop}}$$

- $D_{\text{proc}}$: Processing delay (header parsing, checksums, route lookup, $\approx \mu\text{s}$).
- $D_{\text{prop}}$: Propagation delay ($d / c$, negligible over residential distances, $\approx \text{ns}$).
- $D_{\text{trans}}$: Transmission delay ($L / R$, packet length / link rate, $\approx \mu\text{s}$).
- $D_{\text{queue}}$: Queueing delay:

$$D_{\text{queue}} = \frac{Q(t)}{R_{\text{link}}}$$

Where $Q(t)$ is the instantaneous queue depth in bits and $R_{\text{link}}$ is the egress transmission rate.

#### Numerical Example:
If a home Wi-Fi access point maintains a $4\text{ MB}$ FIFO transmission buffer, and a client moves to an obstructed location where throughput drops to $20\text{ Mbps}$:

$$D_{\text{queue}} = \frac{4 \times 10^6 \times 8\text{ bits}}{20 \times 10^6\text{ bits/sec}} = 1.6\text{ seconds!}$$

A simple ICMP ping or VoIP packet stuck behind this queue will experience **$1600\text{ ms}$ of latency**, rendering interactive applications completely unusable!

---

### 3. Measuring Bufferbloat in Wi-Fi Diagnostic Lab

In `wifi_lab`, we isolate pure queueing latency using a **paired within-run differential metric**:

$$\Delta \text{RTT} = \text{RTT}_{\text{loaded}} - \text{RTT}_{\text{idle}}$$

1. **Idle Phase ($30\text{ s}$):** Measures uncontended baseline latency $D_{\text{proc}} + D_{\text{trans}} + D_{\text{prop}}$ (median $\approx 2.4\text{ ms}$ at L1).
2. **Steady-State Load Phase ($60\text{ s}$):** Measures total latency under saturation TCP traffic $D_{\text{proc}} + D_{\text{trans}} + D_{\text{prop}} + D_{\text{queue}}$ (median $\approx 31.3\text{ ms}$ at L1).
3. **The Delta ($\Delta \text{RTT}$):** Subtracting the idle baseline isolates the exact delay contribution injected by queue buffering ($\Delta \approx +28.9\text{ ms}$ at L1, $+76.0\text{ ms}$ at L2).
4. **Recovery Phase ($30\text{ s}$):** Observes buffer draining dynamics. In our FRITZ!Box 7530 AX pilot, queues consistently drain back to baseline within $4.5\text{ seconds}$ following traffic cessation.

---

### 4. Modern Mitigations

- **Active Queue Management (AQM):** Algorithms like **CoDel** (Controlled Delay, RFC 8289) and **FQ-CoDel** (Fair Queueing CoDel, RFC 8290) monitor queue sojourn time rather than queue depth, selectively dropping or ECN-marking packets only when packets linger in queues longer than a target threshold (e.g. $5\text{ ms}$).
- **BBR Congestion Control:** Modern congestion control designed by Google (Bottleneck Bandwidth and RTT) models the link rate and minimum RTT independently, attempting to operate at the exact knee of the queue curve without inflating buffers.
