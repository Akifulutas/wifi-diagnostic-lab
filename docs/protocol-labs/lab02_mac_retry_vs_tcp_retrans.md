# Protocol Lab 02: 802.11 MAC Retries vs. Layer 4 TCP Retransmissions

**Author:** Akif Ulutaş (RWTH Aachen University)  
**Topic:** Cross-Layer Network Diagnostics: Link-Layer ARQ vs. Transport ARQ  
**Context:** Wi-Fi Diagnostic Lab Foundations

---

### 1. The Fundamental Cross-Layer Confusion

A frequent point of confusion in wireless performance evaluation is equating **802.11 MAC-layer frame retries** with **TCP segment retransmissions**. While both mechanisms provide Automatic Repeat reQuest (ARQ), they operate on fundamentally different timescales, scopes, and layers of the protocol stack:

```text
[ Transport Layer (L4) ]   TCP Segment Retransmission  (End-to-End: Mac <-> Server)
         |                 Timescale: 200 ms - seconds. Triggered by packet drop / 3 DupACKs.
         ▼
[ Network Layer (L3) ]     IP Routing & Forwarding
         |
         ▼
[ Link Layer (L2) ]        802.11 MAC Frame Retry      (Hop-by-Hop: Mac <-> AP)
                           Timescale: microseconds. Triggered by missing SIFS BlockAck.
```

---

### 2. Mechanics of 802.11 Link-Layer ARQ

Unlike wired Ethernet (802.3), which relies on CSMA/CD and assumes low bit-error rates without per-frame MAC acknowledgements, the wireless medium is inherently unreliable due to multipath fading, interference, and collisions.

1. **Immediate Acknowledgement:** Under 802.11, every unicast data frame requires an explicit acknowledgement (ACK or Block ACK) from the receiver within a Short Inter-Frame Space (SIFS, $\approx 16\,\mu\text{s}$ on 5 GHz).
2. **Short/Long Retry Limit:** If an ACK is not received, the sender's physical layer assumes a collision or channel error. It increments its local MAC retry counter (up to `dot11ShortRetryLimit`, default 7) and doubles its contention window ($CW$).
3. **Invisibility to Higher Layers:** As long as the MAC succeeds within 7 attempts, **Layer 3 (IP) and Layer 4 (TCP) never see a packet loss**. 
4. **The Latency Cost (Jitter):** Even though no packet was dropped, those 4–5 MAC retries and exponential backoffs introduce several milliseconds of local delay. To TCP, this appears as sudden, unexplained **RTT jitter**!

---

### 3. When Link-Layer ARQ Fails: The Cascade to TCP

When a frame exhausts its retry limit (e.g. 7 retries failed due to deep RF null or wall obstruction):
1. The 802.11 MAC layer drops the frame.
2. The IP packet encapsulated inside that frame is permanently lost on the wireless hop.
3. **TCP Detection:** The TCP sender discovers the missing sequence number either via:
   - **Fast Retransmit:** Receipt of 3 duplicate ACKs from the receiver ($SACK$).
   - **RTO Timeout:** Expiration of the retransmission timer ($RTO$).
4. **TCP Penalization:** TCP assumes network congestion! It:
   - Halves its Congestion Window (`cwnd`).
   - Resets slow-start threshold (`ssthresh`).
   - Throttles throughput dramatically.

---

### 4. Airtime Contention and The "Slow Client" Curse

In 802.11ax, airtime is a shared, zero-sum resource:
- At position **L1 (Near-AP)**: Client uses MCS 11 ($1024\text{-QAM}$, code rate 5/6). Transmitting a $1500\text{ byte}$ frame takes $\approx 15\,\mu\text{s}$.
- At position **L2 (Far-AP, NLOS)**: Due to path loss, client drops to MCS 7 ($64\text{-QAM}$). Transmitting the same $1500\text{ byte}$ frame takes $\approx 65\,\mu\text{s}$.
- If L2 undergoes 4 MAC retries, transmitting that single packet consumes:

$$\text{Airtime}_{\text{L2}} \approx 4 \times 65\,\mu\text{s} = 260\,\mu\text{s} \quad (\approx 17\times \text{ the airtime of L1!})$$

**Diagnostic Insight:** In Wi-Fi networks, a distant client with high MAC retry counts does not just suffer alone; it monopolizes channel airtime, starving other stations and inflating RTT for everyone on the BSS.
