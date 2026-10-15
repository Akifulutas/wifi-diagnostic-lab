# Implementation backlog

Planning document, 14 October 2026. None of these implementation tasks is marked complete. IDs can become GitHub issues later; no remote issues have been created. Estimates include small checks and documentation but vary with familiarity and hardware access.

## Ordered work packages

| ID | Priority / estimate | Task and dependency | Acceptance evidence |
|---|---|---|---|
| P01 | Essential / 3–4 h | Record installed tools, observed hardware settings and one attributed JSON example; read tool output semantics | Example provenance; protocol/direction/receiver fields manually explained; environment recorded |
| P02 | Essential / 4–6 h | Normalize one supported TCP iperf JSON shape; depends on P01 | One run row, explicit units/field provenance; invalid or failed output gives a visible error |
| P03 | Essential / 3–4 h | Produce first throughput figure from labelled examples; depends on P02 | Plot recreated from input with unit/condition; fixtures are visibly labelled rather than presented as measurements |
| P04 | Essential / 3–4 h | Implement config validation, run IDs and immutable per-run manifests | Invalid settings rejected before collection; source version/config/raw paths traceable |
| P05 | Essential / 4–6 h | Add sequential TCP runner; depends on P04 and server access for integration | Normal/reverse directions, raw stdout/stderr, timeout, exit status and cancellation cleanup |
| P06 | Essential / 5–7 h | Parse installed macOS ping and align phase events; depends on metric definition | Replies, missing/duplicate/late responses handled; unsupported format fails clearly; actual phase boundaries inspected |
| P07 | Essential / 5–7 h | Execute and inspect pilot; depends on P02–P06 and server | 12 planned conditions/repeats with attempts/failures accounted for; two figures and concise method/result note |
| P08 | Essential / 4–6 h | Offline analysis command and data dictionary | Run-level summaries and phase-labelled figures generated from a frozen input sample; no personal absolute paths |
| P09 | Essential / 5–7 h | Main study and day comparison; depends on pilot review | Planned 40-run coverage; blocked order, day labels, controls and deviations documented |
| P10 | Secondary / 3–4 h | Add evidence-linked follow-up suggestions; depends on real observations | Four-part output; unknown/missing-evidence path; no unsupported root-cause or accuracy claim |
| P11 | Secondary / 4–6 h | One extra experiment, chosen after core results | New question/protocol, controlled configuration and original figure |
| P12 | Essential / 5–7 h | Reproduction, report and release preparation | Fresh offline rerun; README matches implemented status; report and five-minute English demo |

These packages total roughly 48–68 implementation/analysis hours. The 120-hour schedule also reserves time for networking/literature learning, protocol labs, integration problems, report revisions and presentation. They are planning ranges, not delivery guarantees. Implement the smallest end-to-end path before adding branches.

## Important correctness checks

Use real, attributed outputs for supported-format examples, or explicitly synthetic minimal fixtures for software checks. The important cases are:

- Decimal bits/s → Mbps conversion and preservation of raw units.
- Receiver selection under normal and reverse directions; no aggregate/stream double counting.
- A TCP parser must not silently reinterpret UDP output as TCP.
- Nonzero tool exit, truncated JSON, timeout and missing required receiver fields.
- Ping timeout/loss, duplicate/late replies and phase-boundary ambiguity; no missing RTT replaced by zero.
- Optional telemetry can be absent without pretending the corresponding metric is zero.
- One failed attempt persists in the dataset and is included in failure denominators.
- Run-level aggregation retains condition/day identity instead of counting every packet as a replicate.

Use a small meaningful suite as the relevant components are built. A fixed test count or coverage badge is not a project target. CI checks parser/analysis correctness on stored inputs; it cannot validate the radio environment.

## Design constraints

Invoke subprocesses with argument lists and finite timeouts; preserve original output before parsing. Keep sampling/collection timing separate from offline plotting. Use a shared client monotonic time base for event alignment plus UTC for provenance. Do not assume remote host clocks are synchronized for one-way delay.

Keep experiment configuration distinct from device credentials and local identifiers. Published samples require a provenance/redaction note. Record actual selected association conditions rather than deriving them from a router model name.

## Suggestions to evaluate after data exists

| Observation | Candidate explanations | Discriminating follow-up |
|---|---|---|
| High loaded RTT | Queueing, airtime contention, host/AP scheduling | Same traffic on wired path, CPU observation, compare upload/download |
| Near-position rate plateaus | Ethernet ceiling, endpoint CPU, wireless limit | Wired reference and server/interface checks |
| Far-position throughput changes | Propagation/orientation, rate adaptation, changing background use | Controlled position return and repeated balanced blocks |
| Good local test but poor internet test | WAN/path/remote endpoint or a different workload | Matched wired internet comparison and explicit endpoint/method documentation |

Rule output is an investigation aid. Rules tested on their own constructed scenarios do not provide independent diagnostic-accuracy evidence.

## Future testbed branch

After the core release, choose based on access: multi-client scheduled traffic; mesh with wired versus wireless backhaul and fixed node placement; verified native MLO mode with per-link observations; or a verified 6 GHz/VLP device study. Each is a new experimental protocol. Native MLO requires appropriate client and AP support; a single current AP cannot provide it.

Defer a large classifier, driver development, full ns-3 study and public dashboard until a concrete research question and valid core dataset justify them.
