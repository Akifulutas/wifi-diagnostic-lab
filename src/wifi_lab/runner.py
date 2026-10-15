"""Experiment runner executing multi-phase measurements or deterministic mock replays."""

from __future__ import annotations

import datetime
import os
import random
import shutil
import subprocess
import sys
import time
import tomllib
from pathlib import Path
from typing import Optional

from wifi_lab.mock_engine import generate_mock_run
from wifi_lab.models import ConditionConfig, Direction, HardwareProfile, Outcome, RunManifest


def load_config(config_path: Path) -> dict:
    if not config_path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    with open(config_path, "rb") as f:
        return tomllib.load(f)


def execute_collection(
    config_path: Path,
    output_dir: Path,
    mock: bool = False,
    runs_override: Optional[int] = None,
) -> int:
    """Executes a study collection workflow across positions, directions, and repetitions."""
    cfg = load_config(config_path)
    exp_cfg = cfg.get("experiment", {})
    phases_cfg = cfg.get("phases", {})
    net_cfg = cfg.get("network", {})
    rep_cfg = cfg.get("repetition", {})
    pos_defs = cfg.get("positions", {})

    study_name = exp_cfg.get("study_name", "pilot")
    day_label = exp_cfg.get("target_day", "day1")
    random_seed = exp_cfg.get("random_seed", 42)

    positions = rep_cfg.get("positions", ["L1", "L2"])
    directions = rep_cfg.get("directions", ["download", "upload"])
    repeats_count = rep_cfg.get("repeats_per_condition", 3)

    if runs_override is not None:
        repeats_count = max(1, runs_override)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Check live tools availability
    has_iperf3 = bool(shutil.which("iperf3"))
    has_ping = bool(shutil.which("ping"))

    if not mock and (not has_iperf3 or not has_ping):
        print("\033[93m[NOTICE] iperf3 or ping not fully configured for live testbed. Falling back to high-fidelity mock/replay engine.\033[0m")
        mock = True

    # Build run matrix
    run_tasks = []
    for rep in range(1, repeats_count + 1):
        for pos in positions:
            for d_str in directions:
                run_tasks.append((pos, d_str, rep))

    if exp_cfg.get("randomize_order", True):
        rng = random.Random(random_seed)
        rng.shuffle(run_tasks)

    print("=" * 72)
    print(f"  Wi-Fi Diagnostic Lab — Experiment Runner ({study_name.upper()})")
    print(f"  Mode: {'MOCK/REPLAY (Offline Wi-Fi 6 Simulation)' if mock else 'LIVE TESTBED'}")
    print(f"  Planned runs: {len(run_tasks)} | Output: {output_dir}")
    print("=" * 72)

    completed = 0
    failed = 0

    for idx, (pos_id, dir_str, rep_idx) in enumerate(run_tasks, 1):
        direction = Direction(dir_str.lower())
        pos_desc = pos_defs.get(pos_id, {}).get("description", f"Position {pos_id}")

        cond = ConditionConfig(
            position_id=pos_id,
            position_description=pos_desc,
            direction=direction,
            protocol=net_cfg.get("protocol", "TCP"),
            streams=net_cfg.get("streams", 1),
            band=net_cfg.get("band", "5 GHz"),
            channel=net_cfg.get("channel", 116),
            channel_width_mhz=net_cfg.get("channel_width_mhz", 80),
            idle_duration_s=float(phases_cfg.get("idle_duration_s", 30.0)),
            warmup_duration_s=float(phases_cfg.get("warmup_duration_s", 3.0)),
            load_duration_s=float(phases_cfg.get("load_duration_s", 60.0)),
            recovery_duration_s=float(phases_cfg.get("recovery_duration_s", 30.0)),
            ping_interval_s=float(phases_cfg.get("ping_interval_s", 0.2)),
        )

        if mock:
            ts_str = "20261015T120000Z"
        else:
            ts_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_id = f"{pos_id}_{direction.value}_rep{rep_idx}_{ts_str}"
        run_folder = output_dir / run_id
        run_folder.mkdir(parents=True, exist_ok=True)

        print(f"[{idx:02d}/{len(run_tasks):02d}] Running {run_id} ({pos_id} {direction.value.upper()} rep {rep_idx})...", end="", flush=True)

        if mock:
            # Simulate one realistic transient failure on rep 3 of L2 upload to test failure accounting
            sim_failure = (pos_id == "L2" and direction == Direction.UPLOAD and rep_idx == 3)
            iperf_raw, ping_raw, manifest = generate_mock_run(
                run_id=run_id,
                condition=cond,
                repetition_index=rep_idx,
                day_label=day_label,
                seed=random_seed + idx,
                simulate_failure=sim_failure,
            )
            # Write files
            (run_folder / "manifest.json").write_text(manifest.to_json(), encoding="utf-8")
            (run_folder / "iperf_raw.json").write_text(iperf_raw, encoding="utf-8")
            (run_folder / "ping_raw.txt").write_text(ping_raw, encoding="utf-8")

            if manifest.outcome == Outcome.OK:
                print(" \033[92m[OK]\033[0m")
                completed += 1
            else:
                print(f" \033[91m[{manifest.outcome.value.upper()} - {manifest.failure_reason}]\033[0m")
                failed += 1
        else:
            # Live execution
            manifest = _run_live_measurement(
                run_id=run_id,
                run_folder=run_folder,
                cond=cond,
                rep_idx=rep_idx,
                day_label=day_label,
                server_host=net_cfg.get("server_host", "192.168.178.50"),
                iperf_port=int(net_cfg.get("iperf_port", 5201)),
            )
            (run_folder / "manifest.json").write_text(manifest.to_json(), encoding="utf-8")
            if manifest.outcome == Outcome.OK:
                print(" \033[92m[OK]\033[0m")
                completed += 1
            else:
                print(f" \033[91m[{manifest.outcome.value.upper()}]\033[0m")
                failed += 1

    print("-" * 72)
    print(f"Collection complete: {completed} successful, {failed} failed (retained in failure accounting).")
    print(f"Raw run records saved to: {output_dir}")
    return 0


def _run_live_measurement(
    run_id: str,
    run_folder: Path,
    cond: ConditionConfig,
    rep_idx: int,
    day_label: str,
    server_host: str,
    iperf_port: int,
) -> RunManifest:
    """Live runner executing sequential idle -> warmup -> load -> recovery subprocesses."""
    manifest = RunManifest(
        schema_version="1.0.0",
        run_id=run_id,
        timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        repetition_index=rep_idx,
        day_label=day_label,
        condition=cond,
        hardware=HardwareProfile(),
        outcome=Outcome.OK,
        raw_files={"iperf": "iperf_raw.json", "ping": "ping_raw.txt"},
    )

    ping_file = run_folder / "ping_raw.txt"
    iperf_file = run_folder / "iperf_raw.json"

    # Start ping in background
    # Note: On macOS ping -i supports intervals; default to 0.2s
    total_duration_s = cond.idle_duration_s + cond.warmup_duration_s + cond.load_duration_s + cond.recovery_duration_s
    probe_count = int(total_duration_s / cond.ping_interval_s)

    ping_cmd = ["ping", "-c", str(probe_count), "-i", str(cond.ping_interval_s), server_host]
    with open(ping_file, "w") as pf:
        ping_proc = subprocess.Popen(ping_cmd, stdout=pf, stderr=subprocess.STDOUT)

    # Wait for Idle Phase
    time.sleep(cond.idle_duration_s)

    # Launch iperf3 load
    iperf_cmd = [
        "iperf3",
        "-c", server_host,
        "-p", str(iperf_port),
        "-t", str(int(cond.load_duration_s)),
        "-O", str(int(cond.warmup_duration_s)),
        "-J",  # JSON
    ]
    if cond.direction == Direction.DOWNLOAD:
        iperf_cmd.append("-R")

    try:
        iperf_res = subprocess.run(iperf_cmd, capture_output=True, text=True, timeout=cond.load_duration_s + 15.0)
        with open(iperf_file, "w") as ipf:
            ipf.write(iperf_res.stdout)
        if iperf_res.returncode != 0:
            manifest.outcome = Outcome.TOOL_ERROR
            manifest.failure_reason = f"iperf3 exited with code {iperf_res.returncode}: {iperf_res.stderr.strip()}"
    except subprocess.TimeoutExpired:
        manifest.outcome = Outcome.TIMEOUT
        manifest.failure_reason = "iperf3 timed out waiting for server response"

    # Wait for Recovery Phase and Ping to finish
    try:
        ping_proc.wait(timeout=cond.recovery_duration_s + 10.0)
    except subprocess.TimeoutExpired:
        ping_proc.kill()
        manifest.outcome = Outcome.TOOL_ERROR
        manifest.failure_reason = (manifest.failure_reason or "") + "; ping timed out"

    return manifest
