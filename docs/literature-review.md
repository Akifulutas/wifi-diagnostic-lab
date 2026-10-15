# Literature review — initial synthesis

Prepared 14 October 2026 from primary sources. These are initial reading notes and proposed design implications, not results from this repository. Read the methods and limitations before presenting a paper as understood. Paper-specific outcomes apply to the authors' setup.

## Four priority readings

| Source | Evidence and question | Main takeaway | Decision for this project |
|---|---|---|---|
| [Liu and Choi, 2023, A First Look at Wi-Fi 6 in Action](https://liux4189.github.io/files/sigmetric23_wifi6_cameraready.pdf), ACM POMACS 7(1), DOI 10.1145/3579451 | Commodity multi-client testbed; Wi-Fi 6 throughput, latency, energy and security; also contains a simulation component | OFDMA outcomes depend on traffic characteristics, aggregation and number of clients | Record the workload explicitly. Our single-client saturation baseline cannot establish an OFDMA benefit or reproduce their full experiment |
| [Kim, Nam and Schulzrinne, 2014, WiSlow](https://www.cs.columbia.edu/~khkim/papers/kyung_wislow_infocom2014.pdf), IEEE INFOCOM | End-user troubleshooting using probes, packet statistics and collaborating peers | Different causes can create similar symptoms; useful diagnosis needs more evidence than a single speed/RSSI observation | Separate observations from candidate causes. Do not transfer its reported diagnostic accuracy or old OS-capture assumptions to a new implementation |
| [Carrascosa et al., 2023, Wi-Fi Multi-Link Operation](https://arxiv.org/html/2305.02052v1), arXiv v1 | Measured spectrum-occupancy traces drive an MLO state machine/trace-based simulation; includes real application traffic | Link-occupancy asymmetry and packet-to-link assignment can change latency outcomes | Label model-backed results clearly. A future MLO study needs per-link conditions and mode details, rather than only an enabled/disabled checkbox |
| [Rosani et al., 2024, A Software Platform for Testing Multi-Link Operation in Industrial Wi-Fi Networks](https://arxiv.org/html/2411.12077v1), arXiv v1 | Linux-based Virtual MLD prototype with commodity adapters and instrumented timestamps | Prototype observability is useful, while OS/driver timing and implementation choices constrain interpretation | Identify exactly where timestamps are taken. The prototype is not equivalent to native commercial Wi-Fi 7 performance |

## Context and methodology

| Source | Evidence type | How to use it |
|---|---|---|
| [RFC 2330: Framework for IP Performance Metrics](https://datatracker.ietf.org/doc/html/rfc2330) | IETF measurement framework, 1998 | Specify metric, packet type, endpoints, sampling and conditions. Use as methodological guidance; do not claim conformance |
| [ESnet iperf3 manual](https://software.es.net/iperf/invoking.html) | Tool documentation | Check installed-version output semantics, selected endpoint, direction and omitted intervals before writing the parser |
| [Wireshark WLAN capture guide](https://wiki.wireshark.org/CaptureSetup/WLAN) | Capture documentation | Plan around adapter/driver visibility and association constraints; distinguish ordinary IP capture from raw 802.11/Radiotap evidence |
| [WBA/CableLabs/Intel, 26 February 2026, residential MLO field-trial announcement](https://wballiance.com/wba-validates-wifi-7-mlo-reliability-cablelabs-intel/) | Industry announcement describing commercial AP/BE200 eMLSR trials | A current example of device/mode-specific field testing. The announcement was inspected; the full report was not obtained. Do not treat promotional summary numbers as independently reproduced or universally applicable |

The first four readings form the initial research set. The other sources support measurement decisions or provide contemporary context. This is a targeted starting set, not a systematic survey of all Wi-Fi 6/7 research.

## Synthesis for our study

Three questions connect the literature to this project:

1. **Which workload is represented?** Begin with declared single-client TCP traffic and probe RTT. Later traffic/application experiments can change that scope.
2. **What can the platform observe?** Commodity macOS may expose less low-level evidence than an instrumented Linux testbed. Missing telemetry constrains the explanation rather than justifying an invented value.
3. **Which conclusions survive controls?** Compare days, endpoints and wired references before narrowing the bottleneck hypothesis. A repeatable procedure can be useful even when the result is a host/Ethernet limitation.

Our proposed contribution is a small, inspectable measurement workflow plus a controlled home-network case study. It does not claim a previously undiscovered property of Wi-Fi 6/7.

## Reading worksheet

For each priority paper, add an original note identifying:

- Complete citation/version and evidence type: RF measurement, prototype, simulation or analysis.
- Research question and what previous work did not establish.
- AP/client/radio/OS and configured versus observed features.
- Traffic generation, sample/repetition structure, metric and timestamp locations.
- One result and the exact condition supporting it, with section/page reference.
- A limitation or alternative explanation.
- One experiment/control we can adopt and one we cannot reproduce with our hardware.
- A question to ask during a research discussion.

Link to the original paper rather than committing copies or copied figures. If reusing an authors' trace or code later, verify its availability and terms separately; no external dataset has been imported here.

## Learning resources paired with outputs

| Resource | Focus | Original output |
|---|---|---|
| [Kurose/Ross chapter 1 videos](https://gaia.cs.umass.edu/kurose_ross/videos/1/) | 1.4 performance; 1.5 layers | Metric definitions and topology |
| [Chapter 3 videos](https://gaia.cs.umass.edu/kurose_ross/videos/3/) | UDP, TCP and congestion control | Annotated TCP exchange and direction note |
| [Chapter 6 resources](https://gaia.cs.umass.edu/kurose_ross/videos/6/) | 6.3 multiple access | A short explanation connecting contention to airtime |
| [Chapter 7 resources](https://gaia.cs.umass.edu/kurose_ross/videos/7/) | 7.3 802.11 checks; inspected page lists exercises rather than a video | MAC/PHY capability glossary |
| [Wireshark labs](https://gaia.cs.umass.edu/kurose_ross/wireshark.php) | DNS/ARP and TCP | Two short original lab notes with packet-field references |
| [Cisco, Deep Dive Into Wi-Fi 6](https://video.cisco.com/detail/video/6049407419001) | 23:38 vendor technical introduction | OFDMA/MU-MIMO/TWT questions checked against a paper |
| [Apple WWDC21, Reduce network delays for your app](https://developer.apple.com/videos/play/wwdc2021/10239/) | Responsiveness and delay under real network use | A justification for the loaded RTT experiment |

Reading order: networking basics → tool semantics → Wi-Fi 6 paper and WiSlow → MLO trace/prototype papers → current field-testing context. Produce an exercise or design decision after each session.
