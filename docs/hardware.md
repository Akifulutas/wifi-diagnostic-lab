# Hardware and measurement capability

Updated: 14 October 2026. This is a capability assessment, not a measurement result. Models were supplied by the project author; installed settings and negotiated links have not been inspected.

| Component | Known capability | Experimental implication |
|---|---|---|
| FRITZ!Box 7530 AX | Wi-Fi 6, 2.4/5 GHz, four Gigabit LAN ports | Suitable for a local Wi-Fi 6 study; Ethernet may cap observed throughput |
| MacBook Pro with M1 Pro | 2021 Pro family; Wi-Fi 6 client | Suitable for the initial client role |
| Local Ethernet server | Not yet confirmed | Required before collecting the planned local dataset |
| Mac Ethernet adapter | Not yet confirmed | Would enable a wired reference using the same client |
| Additional mesh node | Not confirmed | A single AP does not provide a mesh-backhaul experiment |

The [FRITZ product specifications](https://fritz.com/en/products/fritz-box-7530-ax-20002930) list 3x3 MIMO on 5 GHz and 2x2 on 2.4 GHz. Its [PHY-rate table](https://en.fritz.com/service/knowledge-base/dok/FRITZ-Repeater-6000/3539_What-Wi-Fi-speeds-can-be-achieved-with-the-FRITZ-Box/) lists 80 MHz for 5 GHz operation. These are advertised capabilities, not observed application rates.

[Apple's deployment table](https://support.apple.com/en-in/guide/deployment/dep268652e6c/web) lists the 2021 14/16-inch MacBook Pro family with two spatial streams, up to 80 MHz and 1200 Mbps PHY on 5 GHz. Its 2.4 GHz ax row lists 20 MHz and 195 Mbps. Record the actual selected link rather than assuming every maximum is reached.

Derived planning decisions:

- Start with 5 GHz and one Wi-Fi client. An AP with more spatial streams does not make this client use three streams.
- Treat a plateau near the wired path's measured ceiling as a possible measurement limitation. Do not infer unconstrained Wi-Fi capacity from it.
- A later 2.4/5 GHz comparison changes a configuration bundle, potentially including width, channel, interference and PHY rate. It does not isolate frequency alone.
- This equipment does not provide 6 GHz or native Wi-Fi 7/MLO experiments. Those require different verified endpoints. VLP operation needs its own device/operating-class evidence; the band name alone would not establish it.
- Use a separate Ethernet host rather than router USB storage or same-host loopback for the baseline. Storage performance introduces additional components.

Before collecting data, record:

1. Exact Mac model identifier, macOS version, Python and iperf versions.
2. FRITZ!OS version, AP settings, security mode and current channel/width.
3. Actual association band and available link telemetry, including collection method and timestamp.
4. Server model, OS, iperf version, CPU load and negotiated Ethernet speed; check any port power/speed setting.
5. How the selected server route was verified to traverse Wi-Fi during wireless tests.
6. Position IDs, relative distances, obstacles, device height/orientation and power mode.
7. Whether the wired reference can be taken. If unavailable, retain that limitation in the report.

Use aliases for network/device identifiers in published data. Do not upload complete router exports or Wireless Diagnostics archives as project datasets. Manual metadata is acceptable when automation is unavailable; identify it as manual.

## Access contingency

Without the server: protocol labs, parsers and analysis can advance using attributed examples or labelled fixtures. With the server: run the pilot. With server plus Mac Ethernet adapter: add the wired reference. With later access to an appropriate research testbed: consider multi-client, mesh or MLO extensions after the core release.
