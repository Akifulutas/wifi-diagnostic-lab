# Initial Wi-Fi 6 measurement protocol

Design version 0.1, 14 October 2026. Proposed; no experiment has been conducted. Freeze a version before the first pilot, and record deviations rather than editing past conditions retrospectively.

## Question, endpoints and scope

Measure local TCP receiver throughput and ICMP RTT while the M1 Pro Mac communicates over Wi-Fi through the FRITZ!Box 7530 AX to an Ethernet-connected host on the same LAN. Choose a single 5 GHz configuration first. Confirm the actual association and route before each block.

Upload means Mac → server; download means server → Mac. Run them separately. Ping the same Ethernet server. Gateway RTT can be an additional series, but AP control-plane replies are a different endpoint. ICMP RTT includes both directions and host/AP processing; it is not one-way radio latency or pure MAC service time.

Do not perform throughput collection until a usable Ethernet server is available. [Hardware assessment](hardware.md) lists what is known and what still needs checking.

## Controls and recorded conditions

- Keep client/AP/server, OS/firmware, tool versions, stream count, traffic duration and security mode fixed within a comparison.
- Use two documented positions: L1 near the AP and L2 with an additional recorded distance/obstacle. Assign actual distances after inspecting the space; do not invent a floor plan.
- Keep orientation, laptop height, power mode and background applications consistent. Record deviations and known competing household use.
- Record configured and observed band/channel/width. If band steering, auto-channel behaviour or a disconnection changes the condition, flag the run and inspect it as a separate condition.
- Before the wireless study, attempt a same-client wired reference with Wi-Fi excluded from that route. Record the actual negotiated Ethernet speed and server CPU observations. If the adapter is unavailable, explicitly limit bottleneck attribution.
- Reference sampling: target five runs per direction for the wired condition. These are additional control runs, not part of the 40 wireless runs.

Environmental traffic cannot be fully controlled in a home network. The method supports repeatable procedure and comparable recorded conditions; it does not promise an identical RF environment on another day.

## Within-run phases

| Phase | Planned length | Treatment |
|---|---:|---|
| Idle | 30 s | Ping active; no project throughput load |
| Warm-up | 3 s | TCP load active; excluded from steady-state summaries |
| Measured load | 60 s | One TCP stream in the selected direction plus ping |
| Recovery | 30 s | Throughput load ended; ping continues |

Nominal duration is **123 seconds** plus process and scheduling overhead. Record actual phase events and validate them against the tool's intervals; process creation is not exact traffic onset. Proposed boundary rule: omit RTT observations within one second of a phase boundary from phase summaries, retaining them in raw data and the time series. Record boundary source and timing uncertainty. If timing uncertainty exceeds this guard, flag phase summaries as unresolved rather than silently assigning samples. Proposed ping interval: 0.2 s if the installed macOS utility and local trial support it; otherwise document a fixed supported interval before the pilot. Keep payload and interval constant within a study.

The load phase yields roughly 300 scheduled probes at 0.2 s, before loss and boundary exclusions. This is useful descriptive coverage, not 300 independent experimental replications. Report returned and missing replies and phase duration. RTT quantiles describe returned replies, so also show loss; a missing response is not evidence of low delay. Do not calculate p99 claims from a short pilot. For p95 report sample size, the chosen quantile method and its sensitivity to the limited record; display all run summaries.

Check command semantics against the installed [iperf3 manual](https://software.es.net/iperf/invoking.html). A prototype can use normal and reverse TCP tests, one stream, 60 measured seconds, three omitted warm-up seconds and JSON output. Preserve output even on failure. Treat the receiving endpoint's delivered data rate as the throughput metric, with the exact JSON field and version documented. Avoid double-counting aggregate and per-stream records.

## Pilot and main design

| Study | Factors | Planned loaded runs |
|---|---|---:|
| Pilot | 2 positions × 2 directions × 3 repetitions, one day | 12 |
| Main | 2 positions × 2 directions × 5 repetitions × 2 days | 40 |

Idle and recovery are **within every run**. They are not extra independent throughput conditions. The main design has 10 loaded runs per position/direction, split into two day blocks. Do not silently pool a pilot into the main dataset if the protocol changed.

Use balanced blocks: one of each position/direction combination per repetition, with a recorded randomized/counterbalanced order. When moving the client requires batching, record that grouping and rotate/reverse the order between blocks/days. Log the random seed or actual order. Allow a documented settling/rest period between runs and verify reassociation after moving.

The main design takes about 82 minutes of nominal wireless run time; reserve several hours for setup, movement, controls, failures and checks. Exact repetitions are a feasibility target. Assess variability after the pilot; any change to the main sample plan is recorded before that phase, with its rationale.

## Outcomes and failure accounting

Keep one row per attempt: `ok`, `tool_error`, `timeout`, `parse_error`, `condition_changed` or `interrupted`, plus a reason. Predefined primary-analysis exclusions: failed required measurement, unresolvable phase timing or a changed condition. Retain and report these rows. Missing optional telemetry alone does not invalidate a run.

A low throughput or unusually high RTT is not an automatic exclusion. Report planned/attempted/valid counts for every condition. A retry receives a new run ID and references the failed attempt; do not overwrite raw files. Incomplete iperf output is not a valid zero-throughput result. Missing RTT replies are not zero milliseconds.

## Analysis decisions

1. Validate units, endpoint, direction, durations and completeness.
2. Calculate throughput and phase-specific RTT median/p95 per run; show response-loss counts separately. Receiver bits/s converts to decimal Mbps by dividing by 1,000,000.
3. Summarize each position/direction within each day, showing individual runs and median/IQR. Label the unit of replication explicitly.
4. Calculate a within-run loaded-minus-idle RTT difference as a descriptive paired contrast. Fixed phase order can also contain drift; recovery and repeated blocks help inspect it.
5. Show day-specific results before pooled results. A packet-level bootstrap or significance test treating probes as independent is inappropriate here. If interval estimation is added, specify run/block resampling assumptions and the small sample limitation.
6. Compare wireless rates with the measured wired reference. A plateau shared by both paths needs further investigation before claiming the wireless link is saturated.

Four core figures:

- Receiver throughput by position/direction, individual runs, separated or marked by day.
- Idle/loaded RTT ECDFs for declared comparable conditions; identify pooling and counts.
- A phase-labelled RTT time series chosen by a predeclared rule, e.g. the first valid L1 upload run in a named block. Also provide the remaining runs; avoid selecting only the worst-looking example.
- Per-run loaded-minus-idle median/p95 RTT contrasts with day labels.

All figures show units, conditions and denominators. Show enough underlying run data that an ECDF with more packets from one run cannot conceal run-level variation. RTT variation and iperf UDP jitter are distinct metrics.

## One optional extension after the core dataset

Choose **one**: repeat selected conditions on 2.4 GHz, or sweep a documented UDP offered load/datagram size at one location. A band experiment tests a configuration bundle rather than frequency in isolation. A UDP experiment records offered and received rates, loss and the tool's jitter definition. Define new conditions and protocol version before collection.

Single-client TCP data does not demonstrate OFDMA scheduling gains, MU-MIMO gains, native MLO performance, mesh backhaul behaviour or VLP operation. These need further endpoints, telemetry or testbeds. Monitor-mode captures may disrupt association and depend on hardware/driver support; use a separate capture experiment or a dedicated observer where possible. [Wireshark WLAN capture guidance](https://wiki.wireshark.org/CaptureSetup/WLAN)

## Report structure

Question → setup → variables/controls → protocol → provenance → counts/failures → figures/results → alternative explanations → limitations → next experiment. The [IPPM framework](https://datatracker.ietf.org/doc/html/rfc2330) is a methodological reference for explicit metric definitions and measurement context; this small project does not claim standards conformance.
