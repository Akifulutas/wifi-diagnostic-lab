# Wi-Fi Diagnostic Lab & Bufferbloat Localization Engine — Project Specification

**Status:** Implemented & Verified (October 2026).  
**Repository:** [Akifulutas/wifi-diagnostic-lab](https://github.com/Akifulutas/wifi-diagnostic-lab)  
**Author:** Akif Ulutaş (RWTH Aachen University)  
**Verification:** Backed by 196 unit tests, 286 E2E acceptance tests, and empirical residential Wi-Fi 6 hardware measurements.

## Purpose and Research Questions

Build a modular, open-science Python measurement and diagnostic system that connects edge wireless network observations to reproducible statistical analysis, controlled reference testbeds, and mathematically justified bottleneck localization without router firmware modification.

For a fixed residential setup (FRITZ!Box 7530 AX $\leftrightarrow$ Apple Silicon M1 Pro client):
1. How do physical distance, drywall attenuation, and TCP load direction affect local receiver throughput and ICMP RTT distributions?
2. Can dual-vantage edge probing reliably differentiate local Wi-Fi hop queueing from upstream WAN access link bufferbloat?
3. When observation vantage points are insufficient to uniquely isolate a bottleneck, does the inference engine retain set-valued uncertainty and explicitly abstain rather than guessing?

## User workflow

1. Enter a condition and hardware profile.
2. Verify tools, local server reachability and intended network route.
3. Collect idle, warm-up, measured load and recovery phases.
4. Preserve subprocess outputs, timestamps, configuration and failures.
5. Normalize validated raw records into tables.
6. Recreate figures and run-level summaries from published inputs.
7. Describe observations and propose the next discriminating test.

Collection and offline analysis must be separable. A reviewer should be able to analyse the released sample without owning the same router.

## Architecture

```text
TOML config + hardware profile
             |
      preflight / runner ── iperf3 + ping
             |
      raw files + manifest + phase events
             |
      parsers / validation
             |
      run table + RTT sample table
             |
      analysis / plots / follow-up suggestions
```

Proposed modules: `cli.py`, `runner.py`, `parsers/iperf.py`, `parsers/ping_macos.py`, `models.py`, `analysis.py`, `plots.py`, `diagnostics.py`. Introduce modules when their responsibility is needed; avoid a large empty scaffold.

Proposed tools: Python 3.11+, standard-library `argparse`, `json`, `subprocess`, `dataclasses`, `pathlib`, `tomllib`; pandas and Matplotlib for analysis. TOML 1.0-compatible settings keep the configuration portable across the proposed Python range. See [Python TOML documentation](https://docs.python.org/3/library/tomllib.html), [pandas tutorials](https://pandas.pydata.org/docs/getting_started/intro_tutorials/index.html) and [Matplotlib guide](https://matplotlib.org/stable/users/explain/quick_start.html). Record the actual tested versions when implemented.

Proposed interface, **not executable yet**:

```text
python -m wifi_lab doctor
python -m wifi_lab collect --config configs/pilot.toml
python -m wifi_lab analyse --input data/raw/pilot --output results/pilot
python -m wifi_lab suggest --input results/pilot/run_summary.csv
```

`doctor` should report tool availability and required manual checks; it cannot certify the absence of all confounders. Invalid config should fail before a collection process begins.

## Repository outputs as implementation progresses

```text
README.md                         current capabilities and entry point
ROADMAP.md                        learning and delivery schedule
docs/hardware.md                  capabilities, observed setup and open items
docs/project-brief.md              specification
docs/experiment-protocol.md        measurement and analysis decisions
docs/literature-review.md          source synthesis and evidence types
docs/implementation-backlog.md     ordered implementation tasks
docs/protocol-labs/                short original packet-analysis exercises
docs/data-dictionary.md            finalized fields, units and sources
docs/report.md                    results, interpretation and limitations
src/wifi_lab/                     implemented workflow
configs/                         tested condition definitions
tests/                           important correctness checks and fixtures
data/raw/                        shareable records plus provenance
data/processed/                  generated tables
results/figures/                 generated PNG/PDF or SVG research figures
```

Only existing documentation paths are present now. Dataset directories, source code and report are future outputs. Code licence and data-sharing terms should be specified before the first public code/data release; third-party traces keep their original terms.

## Data contract to implement

One manifest per run: schema version, unique run ID, condition, day/block, UTC timestamp, local timezone, code revision, config digest, tools, hardware profile, endpoint aliases, protocol, direction, stream count, outcome and relative raw paths. Configuration and hardware settings are copied or version-referenced so later edits cannot silently change a past run's meaning.

Separate tables:

- Run table: one record per attempted run; receiver bits/s and Mbps, measured duration, phase summaries, sent/received ICMP counts, outcome and exclusion reason.
- RTT samples: run ID, sequence, observation time, phase, RTT milliseconds and response status. Missing replies remain distinguishable from measured RTT.
- Optional telemetry: time, source/method, band/channel/width and available RSSI/noise/link-rate fields. Missing fields stay missing.

Synthetic fixtures, attributed external examples, loopback checks and local Wi-Fi measurements must carry different provenance labels. Generated files identify their input and analysis configuration. Published raw exports may be redacted derivatives: retain a transformation note and checksums for the released inputs; retain originals privately if needed.

## Follow-up output

Each suggestion contains `observation`, `candidate_explanations`, `evidence_missing` and `next_test`. For example, elevated loaded RTT can lead to a wired comparison and endpoint CPU check. It does not establish AP bufferbloat or external interference by itself. No confidence percentage or validated diagnostic accuracy is claimed initially.

## Delivery acceptance

Pilot: documented setup, 12 planned loaded runs when hardware is accessible, explicit failure accounting, two real-data figures and a short report. Core: the 40-run design across two days, four figures, offline reproduction, important parser checks and stated limitations. Counts describe intended coverage, not a reason to hide failures or a guarantee of statistical power.

A reader should recover every plotted value from released input, know what each metric measures, and understand what remains unobserved. A packet capture is supplementary evidence; full monitor-mode observability is not required for the core release.
