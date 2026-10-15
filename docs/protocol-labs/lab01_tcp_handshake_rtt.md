# Protocol Lab 01: TCP Handshake Dynamics, Byte Streams, and RTT Estimation

**Author:** Akif Ulutaş (RWTH Aachen University)  
**Topic:** Transport Layer Protocol Engineering & Latency Metrics  
**Context:** Wi-Fi Diagnostic Lab Foundations

---

### 1. Conceptual Overview

Transmission Control Protocol (TCP, RFC 793 / RFC 9293) provides a reliable, ordered, full-duplex byte stream over an unreliable network layer (IP). Unlike UDP, which transmits independent datagrams, TCP establishes connection state prior to payload exchange and dynamically estimates the network path's Round-Trip Time (RTT) to drive its Retransmission Timeout (RTO) and Congestion Control window (`cwnd`).

```text
       Client (Initiator)                           Server (Listener)
               |                                           |
               | -------- SYN, Seq = X, MSS = 1460 ------> |  (State: SYN_SENT)
               |                                           |
               | <--- SYN-ACK, Seq = Y, Ack = X+1 -------- |  (State: SYN_RCVD)
               |                                           |
               | -------- ACK, Seq = X+1, Ack = Y+1 -----> |  (State: ESTABLISHED)
               |                                           |
               |<============= Handshake RTT =============>|
```

---

### 2. Byte Stream Mechanics and Sequence/ACK Progression

TCP treats payload as a continuous stream of numbered octets:
1. **Initial Sequence Number (ISN):** Generated pseudorandomly by each endpoint to mitigate blind connection spoofing.
2. **Cumulative Acknowledgement:** The `Ack` field indicates the *next byte expected* by the receiver. An acknowledgement of $N$ implies all bytes up to $N-1$ have been successfully received.
3. **TCP Options Negotiated in Handshake:**
   - **MSS (Maximum Segment Size):** Advertised payload ceiling per segment, typically $1460\text{ bytes}$ for IPv4 over Ethernet ($1500\text{ byte MTU} - 20\text{ byte IP} - 20\text{ byte TCP}$).
   - **Window Scale (WS, RFC 7323):** Allows the 16-bit receive window (`rwnd`) to be shifted by up to 14 bits, expanding the maximum advertised window from $64\text{ KB}$ to $1\text{ GB}$—vital for gigabit Wi-Fi 6 links.
   - **SACK Permitted (RFC 2018):** Enables Selective Acknowledgement so that isolated dropped segments can be retransmitted without resending entire windows.
   - **Timestamps (TSopt):** Emits an echo timestamp (`TSval` and `TSecr`) on every segment, providing per-packet RTT samples without ambiguities caused by retransmissions.

---

### 3. Mathematical RTT Estimation: Jacobson/Karels Algorithm

TCP cannot rely on a static retransmission timer; path latency fluctuates due to queueing and wireless scheduling. Standard TCP implementations (RFC 6298) update a Smoothed RTT ($SRTT$) and RTT Variation ($RTTVAR$):

For each newly observed sample $R$:

$$\text{First sample: } SRTT \leftarrow R, \quad RTTVAR \leftarrow \frac{R}{2}$$

$$\text{Subsequent samples: }$$
$$RTTVAR \leftarrow (1 - \beta) \cdot RTTVAR + \beta \cdot |SRTT - R| \quad (\beta = 0.25)$$
$$SRTT \leftarrow (1 - \alpha) \cdot SRTT + \alpha \cdot R \quad (\alpha = 0.125)$$
$$RTO \leftarrow SRTT + \max(G, 4 \cdot RTTVAR) \quad (G = \text{clock granularity})$$

#### Karn’s Rule
If a segment is retransmitted, the sender **must not** use the returning ACK to compute an RTT sample, because the ACK cannot be unambiguously attributed to the original transmission or the retransmission.

---

### 4. Metrics Comparison in Wi-Fi Diagnostic Lab

| Metric | Protocol Layer | Measurement Path | Sensitivity to Bufferbloat |
|---|---|---|---|
| **Handshake RTT** | Transport (L4) | Client TCP stack $\leftrightarrow$ Server TCP stack | Measures single-exchange latency before queueing starts |
| **ICMP Ping RTT** | Network (L3) | End-to-end IP round trip | Highly sensitive; shows packet queuing behind bulk TCP streams |
| **TCP Data Ack Latency** | Transport (L4) | Piggybacked/Delayed ACKs | Distorted by receiver delayed-ACK timers ($40\text{–}200\text{ ms}$) |

**Takeaway for Wi-Fi 6:** In our diagnostic lab, we use concurrent ICMP echo probes at $5\text{ Hz}$ ($0.2\text{ s}$ interval) rather than TCP data ACK timing because ICMP probes are independent datagrams that queue alongside TCP payload without being artificially delayed by TCP socket pacing.
