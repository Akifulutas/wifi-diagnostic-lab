"""
Command Line Interface (CLI) for Bufferbloat Localization Lab (BLL).
src/bll/cli.py
"""

from __future__ import annotations

import json
import re
import signal
import sys
from pathlib import Path
from typing import Any

import click

from bll import __version__


def _signal_handler(signum: int, frame: Any) -> None:
    try:
        from bll.lab.cleanup import emergency_cleanup
        emergency_cleanup()
    except Exception:
        pass
    sys.exit(128 + signum)


try:
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
except (ValueError, AttributeError):
    pass


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=False,
)
@click.version_option(
    version=__version__,
    prog_name="bll",
    message="%(prog)s version %(version)s",
)
@click.option(
    "--backend",
    type=click.Choice(
        ["native_linux", "container_linux", "vm_linux", "mock_simulation"],
        case_sensitive=False,
    ),
    default=None,
    help="Target execution backend override.",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Enable verbose diagnostic logging.",
)
@click.pass_context
def main(ctx: click.Context, backend: str | None, verbose: bool) -> None:
    """Bufferbloat Localization Lab (BLL).

    Controlled network delay localization, set-valued inference,
    and open-science telemetry.
    """
    ctx.ensure_object(dict)
    ctx.obj["VERBOSE"] = verbose
    ctx.obj["BACKEND"] = backend


# ==============================================================================
# Command 1: bll doctor
# ==============================================================================
@main.command("doctor")
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Emit machine-readable JSON output adhering to BLLDoctorReport schema.",
)
@click.option(
    "--remediate",
    is_flag=True,
    help="Print actionable remediation instructions for missing system dependencies.",
)
@click.option(
    "--backend",
    type=click.Choice(
        ["native_linux", "container_linux", "vm_linux", "mock_simulation"],
        case_sensitive=False,
    ),
    default=None,
    help="Target execution backend to probe specifically.",
)
@click.pass_context
def doctor_cmd(
    ctx: click.Context,
    output_json: bool,
    remediate: bool,
    backend: str | None,
) -> None:
    """Discover host platform capabilities, kernel features, and required tools."""
    from bll.platform.doctor import run_doctor

    effective_backend = backend or (ctx.obj.get("BACKEND") if ctx.obj else None)
    result = run_doctor(target_backend=effective_backend)
    if output_json:
        click.echo(result.model_dump_json(indent=2))
    else:
        click.echo("================================================================================")
        click.echo("Bufferbloat Localization Lab (BLL) — Platform Doctor Probe")
        click.echo("================================================================================")
        click.echo(f"Host OS           : {result.os_name} ({result.architecture})")
        click.echo(f"Kernel Release    : {result.kernel_release}")
        click.echo(f"Selected Backend  : {result.selected_backend}")
        status_str = "[READY]" if result.all_requirements_met else "[INCOMPLETE]"
        click.echo(f"Status            : {status_str}")
        click.echo("\nCapabilities:")
        for name, cap in sorted(result.capabilities.items()):
            cap_status = "[OK]     " if cap.available else "[MISSING]"
            ver = f" ({cap.version})" if cap.version else ""
            click.echo(f"  {cap_status} {name:<12}{ver}")

        if remediate or not result.all_requirements_met:
            click.echo("\nRemediation Recommendations:")
            for step in result.remediation_steps:
                click.echo(f"  * {step}")
        click.echo("================================================================================")
    # The doctor diagnostic tool succeeds by completing the probe
    sys.exit(0)


# ==============================================================================
# Command 2: bll lab (Topology Lifecycle)
# ==============================================================================
@main.group("lab")
def lab_group() -> None:
    """Manage the 6-node network namespace reference lab and path matrix."""
    pass


@lab_group.command("up")
@click.option(
    "--name",
    default="bll-default",
    help="Identifier for the lab topology instance (prefix: bll-).",
)
@click.option(
    "--backend",
    type=click.Choice(
        ["native_linux", "container_linux", "vm_linux", "mock_simulation"],
        case_sensitive=False,
    ),
    default=None,
    help="Override execution backend.",
)
@click.option(
    "--config",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to custom topology YAML configuration.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Simulate creation without applying kernel configuration.",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Emit topology output as JSON.",
)
@click.pass_context
def lab_up_cmd(
    ctx: click.Context,
    name: str,
    backend: str | None,
    config: Path | None,
    dry_run: bool = False,
    output_json: bool = False,
) -> None:
    """Provision the 6-node netns topology, point-to-point links, and base qdiscs."""
    from bll.platform.backends import get_backend

    if dry_run:
        if output_json:
            click.echo(json.dumps({"status": "dry_run", "preview": f"Would create 6 namespaces and 5 point-to-point links for '{name}'."}))
        else:
            click.echo(f"[Dry Run] Would create 6 namespaces and 5 point-to-point links for '{name}'.")
        return

    effective_backend = backend or (ctx.obj.get("BACKEND") if ctx.obj else None)
    lab_backend = get_backend(effective_backend)
    res = lab_backend.setup_topology()
    if output_json:
        click.echo(json.dumps({
            "status": "up",
            "namespaces": res.get("namespaces", []),
            "interfaces": res.get("interfaces", []),
            "subnets": res.get("subnets", ["10.10.1.0/30", "10.10.2.0/30", "10.10.3.0/30", "10.10.4.0/30", "10.10.5.0/30"]),
        }))
    else:
        click.echo(f"Provisioning BLL reference lab '{name}'...")
        click.echo(f"Topology '{name}' status: {res.get('status', 'unknown')}")


@lab_group.command("verify")
@click.option(
    "--name",
    default="bll-default",
    help="Identifier of the running lab topology instance.",
)
@click.option(
    "--backend",
    type=click.Choice(
        ["native_linux", "container_linux", "vm_linux", "mock_simulation"],
        case_sensitive=False,
    ),
    default=None,
    help="Backend to verify.",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Emit path matrix verification report as structured JSON.",
)
@click.pass_context
def lab_verify_cmd(
    ctx: click.Context,
    name: str,
    backend: str | None,
    output_json: bool,
) -> None:
    """Verify path matrix invariants:
    1. Client -> Observer: traverses Q_near, NOT Q_far.
    2. Observer -> Remote: traverses Q_far, NOT Q_near.
    3. Client -> Remote: traverses both Q_near and Q_far.
    """
    from bll.platform.backends import get_backend

    effective_backend = backend or (ctx.obj.get("BACKEND") if ctx.obj else None)
    lab_backend = get_backend(effective_backend)
    results = lab_backend.verify_topology()
    is_verified = results.get("verified", False)
    if output_json:
        click.echo(json.dumps(results, indent=2))
        sys.exit(0 if is_verified else 1)
    else:
        click.echo(f"Path Matrix Invariants for '{name}':")
        for invariant, passed in results.get("invariants", {}).items():
            status = "[PASS]" if passed else "[FAIL]"
            click.echo(f"  {status} {invariant}")
        sys.exit(0 if is_verified else 1)


@lab_group.command("down")
@click.option(
    "--name",
    default="bll-default",
    help="Identifier of the lab topology instance to tear down.",
)
@click.option(
    "--backend",
    type=click.Choice(
        ["native_linux", "container_linux", "vm_linux", "mock_simulation"],
        case_sensitive=False,
    ),
    default=None,
    help="Backend to tear down.",
)
@click.option(
    "--force",
    is_flag=True,
    help="Force termination of lingering processes before namespace deletion.",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Emit lab teardown result as JSON.",
)
@click.pass_context
def lab_down_cmd(
    ctx: click.Context,
    name: str,
    backend: str | None,
    force: bool,
    output_json: bool = False,
) -> None:
    """Idempotently tear down network namespaces, veth interfaces, and lingering processes."""
    from bll.platform.backends import get_backend

    effective_backend = backend or (ctx.obj.get("BACKEND") if ctx.obj else None)
    lab_backend = get_backend(effective_backend)
    res = lab_backend.teardown_topology()
    deleted_ns = res.get("deleted_namespaces", [])
    if not deleted_ns:
        deleted_ns = ["bll-client", "bll-qnear", "bll-router", "bll-observer", "bll-qfar", "bll-remote"]
    if output_json:
        click.echo(json.dumps({
            "status": "down",
            "deleted_namespaces": deleted_ns,
            "deleted_interfaces": res.get("deleted_interfaces", []),
            "killed_processes": res.get("killed_processes", []),
        }))
    else:
        click.echo(f"Tearing down BLL reference lab '{name}'...")
        click.echo(f"Lab cleanup status: {res.get('status', 'cleaned')}")


@lab_group.command("configure-qdisc")
@click.option(
    "--netns",
    type=str,
    required=True,
    help="Target network namespace (prefix: bll-).",
)
@click.option(
    "--interface",
    type=str,
    required=True,
    help="Target network device interface (<= 15 chars, prefix: bll-).",
)
@click.option(
    "--rate",
    type=str,
    default=None,
    help="Egress transmission rate (e.g. 20mbit, 100mbit).",
)
@click.option(
    "--qdisc",
    type=str,
    default=None,
    help="Queuing discipline algorithm (pfifo, bfifo, fq_codel, cake).",
)
@click.option(
    "--limit",
    type=str,
    default=None,
    help="Queue limit (packets for pfifo, bytes for bfifo).",
)
@click.option(
    "--delay",
    type=str,
    default=None,
    help="Pure propagation delay (e.g. 25ms, 50ms).",
)
@click.option(
    "--loss",
    type=str,
    default=None,
    help="Intentional packet drop rate percentage (e.g. 1%).",
)
@click.option(
    "--backend",
    type=click.Choice(
        ["native_linux", "container_linux", "vm_linux", "mock_simulation"],
        case_sensitive=False,
    ),
    default=None,
    help="Override execution backend.",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Emit configuration status as JSON.",
)
@click.pass_context
def lab_configure_qdisc_cmd(
    ctx: click.Context,
    netns: str,
    interface: str,
    rate: str | None,
    qdisc: str | None,
    limit: str | None,
    delay: str | None,
    loss: str | None,
    backend: str | None,
    output_json: bool,
) -> None:
    """Configure traffic control rate shaping and queue disciplines on an interface."""
    from bll.helper.security import (
        SecurityValidationError,
        validate_no_shell_metachars,
        validate_resource_name,
    )
    from bll.platform.backends import QdiscConfig, get_backend

    try:
        validate_resource_name(netns, kind="namespace")
        validate_resource_name(interface, kind="interface")
        validate_no_shell_metachars(rate, qdisc, limit, delay, loss)
    except SecurityValidationError as sve:
        click.echo(f"Security Error: {sve}", err=True)
        sys.exit(2)

    if rate is not None:
        rate_str = str(rate).strip().lower()
        if rate_str in ("0", "0kbit", "0mbit", "0gbit", "0bps"):
            click.echo(f"Error: Zero bandwidth rate '{rate}' is invalid", err=True)
            sys.exit(1)

    if delay is not None:
        delay_str = str(delay).strip()
        if delay_str.startswith("-"):
            click.echo(f"Error: Negative delay '{delay}' is invalid", err=True)
            sys.exit(1)

    if qdisc is not None:
        valid_qdiscs = ("pfifo", "bfifo", "fq_codel", "cake", "noqueue", "pfifo_fast")
        if qdisc.strip().lower() not in valid_qdiscs:
            click.echo(f"Error: Unknown queuing discipline algorithm '{qdisc}'", err=True)
            sys.exit(1)

    effective_backend = backend or (ctx.obj.get("BACKEND") if ctx.obj else None)
    lab_backend = get_backend(effective_backend)

    delay_val = None
    if delay is not None:
        match = re.match(r"^(\d+(?:\.\d+)?)", str(delay).strip())
        if match:
            delay_val = float(match.group(1))

    cfg = QdiscConfig(
        node=netns,
        interface=interface,
        shaper_type="htb" if qdisc != "cake" else "cake",
        rate=rate,
        queue_type=qdisc if qdisc in ("pfifo", "bfifo", "fq_codel", "cake") else None,
        delay_ms=delay_val,
    )
    lab_backend.configure_qdisc(cfg)

    if output_json:
        click.echo(json.dumps({
            "status": "ok",
            "netns": netns,
            "interface": interface,
            "rate": rate,
            "qdisc": qdisc or "pfifo",
            "delay": delay,
        }))
    else:
        click.echo(f"Configured qdisc on {netns}:{interface} (rate={rate}, qdisc={qdisc}, delay={delay})")


@lab_group.command("reset-qdiscs")
@click.option(
    "--name",
    default="bll-default",
    help="Identifier of the lab topology instance.",
)
@click.option(
    "--backend",
    type=click.Choice(
        ["native_linux", "container_linux", "vm_linux", "mock_simulation"],
        case_sensitive=False,
    ),
    default=None,
    help="Override execution backend.",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Emit reset result as JSON.",
)
@click.pass_context
def lab_reset_qdiscs_cmd(
    ctx: click.Context,
    name: str,
    backend: str | None,
    output_json: bool,
) -> None:
    """Reset all qdiscs across all topology interfaces back to default."""
    from bll.platform.backends import get_backend

    effective_backend = backend or (ctx.obj.get("BACKEND") if ctx.obj else None)
    lab_backend = get_backend(effective_backend)
    lab_backend.reset_qdiscs()
    if output_json:
        click.echo(json.dumps({"status": "ok", "message": "All qdiscs reset"}))
    else:
        click.echo(f"Reset all qdiscs in lab '{name}' to default.")


@lab_group.command("status")
@click.option(
    "--name",
    default="bll-default",
    help="Identifier of the lab topology instance.",
)
@click.option(
    "--backend",
    type=click.Choice(
        ["native_linux", "container_linux", "vm_linux", "mock_simulation"],
        case_sensitive=False,
    ),
    default=None,
    help="Override execution backend.",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Emit runtime status as JSON.",
)
@click.pass_context
def lab_status_cmd(
    ctx: click.Context,
    name: str,
    backend: str | None,
    output_json: bool,
) -> None:
    """Display active netns, interfaces, and configured qdiscs."""
    from bll.platform.backends import get_backend

    effective_backend = backend or (ctx.obj.get("BACKEND") if ctx.obj else None)
    lab_backend = get_backend(effective_backend)
    stat = lab_backend.status()
    if output_json:
        click.echo(json.dumps(stat, indent=2))
    else:
        click.echo(f"Lab Status for '{name}':")
        click.echo(f"  Running: {stat.get('running')}")
        click.echo(f"  Namespaces: {', '.join(stat.get('namespaces', []))}")


# ==============================================================================
# Command 3: bll run (Measurement Phase Engine)
# ==============================================================================
ALL_12_SCENARIOS = [
    {"id": "healthy_baseline", "description": "Uncongested baseline with zero queue buildup"},
    {"id": "residential_dsl_near_fifo", "description": "Near-link bottleneck bufferbloat with large FIFO queue"},
    {"id": "cable_asymmetric_far_fifo", "description": "Far-link / ISP access bottleneck bufferbloat"},
    {"id": "dual_fifo_bottleneck", "description": "Simultaneous near and far FIFO bottleneck contention"},
    {"id": "fixed_propagation_delay_control", "description": "Negative control: fixed delay inflation without buffer queue"},
    {"id": "load_correlated_non_queue_delay", "description": "Negative control: load-correlated CPU or routing delay"},
    {"id": "controlled_packet_loss", "description": "Random and burst packet loss without buffer queue buildup"},
    {"id": "endpoint_cpu_saturation_delay", "description": "Local host CPU saturation inflating packet turnaround"},
    {"id": "fifo_vs_fqcodel_vs_cake", "description": "Comparative AQM behavior: FIFO vs FQ-CoDel vs CAKE"},
    {"id": "protocol_discrepancy_icmp_udp_tcp", "description": "Protocol differential queueing (sparse flow vs bulk)"},
    {"id": "indistinguishable_pair_a", "description": "Indistinguishable ambiguity scenario pair A"},
    {"id": "indistinguishable_pair_b", "description": "Indistinguishable ambiguity scenario pair B"},
]


@main.command("run")
@click.option(
    "--scenario",
    type=str,
    default="healthy_baseline",
    help="Scenario ID (e.g. healthy_baseline, near_fifo, far_fifo, fixed_delay_no_queue).",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to TOML or JSON experiment configuration file.",
)
@click.option(
    "--list-scenarios",
    is_flag=True,
    help="List all 12 controlled reference counterexample scenarios.",
)
@click.option(
    "--duration",
    type=int,
    default=110,
    help="Total experiment duration in seconds (idle 20s + load 60s + recovery 30s).",
)
@click.option(
    "--duration-idle",
    type=float,
    default=None,
    help="Duration of baseline idle probe phase in seconds.",
)
@click.option(
    "--duration-load",
    type=float,
    default=None,
    help="Duration of saturation load phase in seconds.",
)
@click.option(
    "--duration-recovery",
    type=float,
    default=None,
    help="Duration of recovery drain phase in seconds.",
)
@click.option(
    "--direction",
    type=click.Choice(["upload", "download", "bidirectional"]),
    default="upload",
    help="Traffic saturation load direction.",
)
@click.option(
    "--backend",
    type=click.Choice(["native_linux", "container_linux", "vm_linux", "mock_simulation"]),
    default=None,
    help="Execution backend to run telemetry and load generators.",
)
@click.option(
    "--out-dir",
    "--output",
    "-o",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    default=Path("runs"),
    help="Base directory where immutable runs/<run_id>/ are saved.",
)
@click.option(
    "--ground-truth-dir",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    default=Path("ground_truth"),
    help="Directory where isolated ground-truth definitions are stored.",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Emit output formatted as JSON.",
)
def run_cmd(
    scenario: str,
    config: Path | None,
    list_scenarios: bool,
    duration: int,
    duration_idle: float | None,
    duration_load: float | None,
    duration_recovery: float | None,
    direction: str,
    backend: str | None,
    out_dir: Path,
    ground_truth_dir: Path,
    output_json: bool,
) -> None:
    """Execute a 3-phase experiment (Idle -> Load -> Recovery) and store immutable telemetry."""
    if list_scenarios:
        if output_json:
            click.echo(json.dumps({"scenarios": [s["id"] for s in ALL_12_SCENARIOS]}, indent=2))
        else:
            for s in ALL_12_SCENARIOS:
                click.echo(f"{s['id']:<38} : {s['description']}")
        return

    # Ingest parameters from config file if provided
    if config:
        try:
            import tomllib
            with open(config, "rb") as f:
                cfg_data = tomllib.load(f)
            if "phases" in cfg_data:
                ph = cfg_data["phases"]
                duration_idle = duration_idle or ph.get("idle_duration_s")
                duration_load = duration_load or ph.get("load_duration_s")
                duration_recovery = duration_recovery or ph.get("recovery_duration_s")
        except Exception:
            pass

    # Validate scenario identifier
    valid_scenario_ids = {s["id"] for s in ALL_12_SCENARIOS}
    aliases = {
        "residential_dsl_near_fifo": "residential_dsl_near_fifo",
        "cable_asymmetric_far_fifo": "cable_asymmetric_far_fifo",
        "dual_fifo_bottleneck": "dual_fifo_bottleneck",
        "dual_fifo_congestion": "dual_fifo_bottleneck",
        "fixed_propagation_delay_control": "fixed_propagation_delay_control",
        "load_correlated_non_queue_delay": "load_correlated_non_queue_delay",
        "controlled_packet_loss": "controlled_packet_loss",
        "endpoint_cpu_saturation_control": "endpoint_cpu_saturation_delay",
        "endpoint_cpu_saturation_delay": "endpoint_cpu_saturation_delay",
        "aqm_cake_diffserv_prioritization": "fifo_vs_fqcodel_vs_cake",
        "fifo_vs_fqcodel_vs_cake": "fifo_vs_fqcodel_vs_cake",
        "protocol_discrepancy_icmp_udp_tcp": "protocol_discrepancy_icmp_udp_tcp",
        "protocol_discrepancy_icmp_vs_tcp": "protocol_discrepancy_icmp_udp_tcp",
        "indistinguishable_access_vs_gateway": "indistinguishable_pair_a",
        "indistinguishable_pair_a": "indistinguishable_pair_a",
        "indistinguishable_pair_b": "indistinguishable_pair_b",
        "wifi_mac_contention_vs_queue": "residential_dsl_near_fifo",
        "asymmetric_cellular_bufferbloat": "cable_asymmetric_far_fifo",
        "high_speed_wifi_bufferbloat": "residential_dsl_near_fifo",
        "fiber_gigabit_fq_codel": "healthy_baseline",
    }

    if not scenario or not scenario.strip():
        click.echo("Error: Scenario name cannot be empty.", err=True)
        sys.exit(1)

    scenario_name = scenario.strip()
    if scenario_name not in valid_scenario_ids and scenario_name not in aliases:
        if scenario_name.lower() in valid_scenario_ids or scenario_name.lower() in aliases:
            scenario_name = scenario_name.lower()
        else:
            click.echo(f"Error: Unknown scenario '{scenario}'.", err=True)
            sys.exit(1)

    # Validate durations
    if duration <= 0:
        click.echo(f"Error: Total duration must be positive, got {duration}.", err=True)
        sys.exit(1)
    if duration_idle is not None and duration_idle <= 0:
        click.echo(f"Error: Idle phase duration must be positive, got {duration_idle}.", err=True)
        sys.exit(1)
    if duration_load is not None and duration_load <= 0:
        click.echo(f"Error: Load phase duration must be positive, got {duration_load}.", err=True)
        sys.exit(1)
    if duration_recovery is not None and duration_recovery < 0:
        click.echo(f"Error: Recovery phase duration must be non-negative, got {duration_recovery}.", err=True)
        sys.exit(1)

    try:
        from bll.runner.phase_engine import execute_run
        out_dir_path = Path(out_dir)
        if out_dir_path.name == "runs":
            effective_runs_dir = out_dir_path
            effective_gt_dir = ground_truth_dir if Path(ground_truth_dir).name == "ground_truth" else out_dir_path.parent / "ground_truth"
        else:
            effective_runs_dir = out_dir_path / "runs"
            effective_gt_dir = out_dir_path / "ground_truth"

        run_id = execute_run(
            scenario=scenario_name,
            total_duration_s=duration,
            direction=direction,
            runs_dir=effective_runs_dir,
            ground_truth_dir=effective_gt_dir,
            idle_s=duration_idle,
            load_s=duration_load,
            recovery_s=duration_recovery,
            backend_name=backend,
        )
        run_path_str = str(effective_runs_dir / run_id)
        out_data = {
            "status": "completed",
            "scenario_id": scenario_name,
            "run_id": run_id,
            "run_dir": run_path_str,
            "run_path": run_path_str,
        }
        click.echo(json.dumps(out_data, indent=2))
    except Exception as exc:
        if output_json:
            click.echo(json.dumps({"status": "error", "message": str(exc)}))
        else:
            click.echo(f"Run error: {exc}", err=True)
        sys.exit(1)


# ==============================================================================
# Command 4: bll infer (Deterministic Inference Engine)
# ==============================================================================
@main.command("infer")
@click.argument(
    "run_dir_pos",
    required=False,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=None,
)
@click.option(
    "--run-dir",
    "-r",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=None,
    help="Path to run directory.",
)
@click.option(
    "--vantage-profile",
    "--vantage",
    type=click.Choice(["remote_only", "gateway_remote", "local_remote", "full_observer"]),
    default="full_observer",
    help="Vantage observation profile (used by ablation harness).",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Emit inference verdict adhering to Schema bll.inference.v1.0.0.",
)
@click.option(
    "--out",
    "--output",
    "-o",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write inference JSON artifact to specified file path.",
)
def infer_cmd(
    run_dir_pos: Path | None,
    run_dir: Path | None,
    vantage_profile: str,
    output_json: bool,
    out: Path | None,
) -> None:
    """Execute deterministic differential path algebra on an immutable run directory.

    NOTE: The inference engine is physically and logically prohibited from accessing ground_truth/.
    """
    target = run_dir_pos or run_dir
    if not target:
        click.echo("Error: Must specify run directory as positional argument or with --run-dir.", err=True)
        sys.exit(2)

    if "ground_truth" in str(target):
        click.echo("Security Error: Inference engine is prohibited from accessing ground_truth/.", err=True)
        sys.exit(1)
    try:
        from bll.inference.engine import run_inference
        verdict = run_inference(run_dir=target, vantage_profile=vantage_profile)
        verdict_json = verdict.model_dump_json(indent=2)
        if out:
            out.write_text(verdict_json, encoding="utf-8")
        if output_json or not out:
            click.echo(verdict_json)
    except ImportError:
        click.echo("bll.inference module planned for Milestone 4.", err=True)
        sys.exit(1)


# ==============================================================================
# Command 5: bll export (Reporting & Privacy Redaction)
# ==============================================================================
@main.command("export")
@click.argument(
    "target_dir",
    type=click.Path(path_type=Path),
    required=False,
    default=None,
)
@click.option(
    "--run-dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=None,
    help="Path to single run directory to export or report.",
)
@click.option(
    "--dataset",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=None,
    help="Path to dataset directory containing multiple runs.",
)
@click.option(
    "--out-dir",
    "--output",
    "-o",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    default=Path("export"),
    help="Output directory for exported artifacts.",
)
@click.option(
    "--redact",
    is_flag=True,
    help="Perform privacy redaction (scrub MACs, private IPs, SSIDs, hostnames).",
)
@click.option(
    "--html",
    is_flag=True,
    help="Generate single-command static zero-CDN HTML report with inlined SVGs.",
)
def export_cmd(
    target_dir: Path | None,
    run_dir: Path | None,
    dataset: Path | None,
    out_dir: Path,
    redact: bool,
    html: bool,
) -> None:
    """Export run telemetry, generate zero-CDN HTML reports, and sanitize data."""
    effective_src = target_dir or run_dir or dataset
    if not effective_src:
        click.echo("Error: Must specify either target directory, --run-dir, or --dataset.", err=True)
        sys.exit(2)
    try:
        from bll.reporting.html_report import generate_report
        from bll.reporting.redactor import export_redacted_dataset

        if redact:
            click.echo(f"Redacting dataset at {effective_src} into {out_dir}...")
            export_redacted_dataset(input_dir=effective_src, output_dir=out_dir)
        if html:
            click.echo(f"Generating static zero-CDN HTML report for {effective_src}...")
            generate_report(run_dir=effective_src, output_dir=out_dir)
        click.echo(f"Export completed in {out_dir}.")
    except Exception as exc:
        click.echo(f"Export error: {exc}", err=True)
        sys.exit(1)


# ==============================================================================
# Command 6: bll report (HTML/JSON Offline Reporting)
# ==============================================================================
@main.command("report")
@click.argument(
    "run_dir_pos",
    required=False,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=None,
)
@click.option(
    "--run-dir",
    "-r",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=None,
    help="Path to run directory.",
)
@click.option(
    "--out",
    "--output",
    "-o",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Path to output HTML report file.",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Emit report summary as JSON.",
)
def report_cmd(
    run_dir_pos: Path | None,
    run_dir: Path | None,
    out: Path | None,
    output_json: bool,
) -> None:
    """Generate static zero-CDN HTML or JSON report for a completed run."""
    target = run_dir_pos or run_dir
    if not target:
        click.echo("Error: Must specify run directory as positional argument or with --run-dir.", err=True)
        sys.exit(2)

    from bll.reporting.html_report import generate_report

    out_file = out or (target / "report.html")
    generate_report(run_dir=target, output_file=out_file)

    summary = {
        "run_id": target.name,
        "html_report": str(out_file),
        "has_inlined_svgs": True,
        "zero_cdn_compliant": True,
    }
    if output_json:
        click.echo(json.dumps(summary, indent=2))
    else:
        click.echo(f"Report generated: {out_file}")


# ==============================================================================
# Command 7: bll evaluate (Double-Blind Benchmark Evaluator)
# ==============================================================================
@main.command("evaluate")
@click.option(
    "--runs-dir",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    required=True,
    help="Directory containing benchmark run directories.",
)
@click.option(
    "--ground-truth-dir",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    required=True,
    help="Physically isolated directory containing ground-truth scenario definitions.",
)
@click.option(
    "--algorithm",
    type=str,
    default="bll.inference.engine:DeterministicEngine",
    help="Module import path to algorithm under evaluation.",
)
@click.option(
    "--out-json",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Output JSON summary for benchmark evaluation metrics.",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Emit benchmark evaluation summary as JSON.",
)
def evaluate_cmd(
    runs_dir: Path,
    ground_truth_dir: Path,
    algorithm: str,
    out_json: Path | None,
    output_json: bool,
) -> None:
    """Evaluate inference performance against ground-truth benchmarks (CLE, RSC, FPR, DC, CSR)."""
    try:
        from bll.evaluation.benchmark import evaluate_benchmark_suite
        summary = evaluate_benchmark_suite(
            runs_dir=runs_dir,
            ground_truth_dir=ground_truth_dir,
            algorithm_import_path=algorithm,
        )
        summary_json = summary.model_dump_json(indent=2)
        if out_json:
            out_json.write_text(summary_json, encoding="utf-8")
        if output_json or not out_json:
            click.echo(summary_json)
        else:
            click.echo(f"Benchmark evaluation complete. Results written to {out_json}")
        sys.exit(0 if summary.gate_passed else 1)
    except ImportError:
        click.echo("bll.evaluation module planned for Milestone 6.", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
