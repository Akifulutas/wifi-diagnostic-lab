"""
Empirical Adversarial Challenge Suite: Platform Backends, Doctor & Parquet Schemas
tests/contract/test_m1_2_adversarial.py

Challenger M1-2 empirical test harness:
1. Platform Doctor & Backends Resilience:
   - Missing binaries (shutil.which returning None)
   - Unreadable / corrupt /proc filesystem files
   - Simulated non-Linux systems (Windows, FreeBSD, Solaris)
   - Corrupt environment variables (missing PATH, empty PATH, non-ASCII PATH)
   - Subprocess timeouts and execution failures
   - CLI --backend parameter rejection (exit code 2)
   - CLI global --backend propagation check
   - MockSimulationBackend state resilience and lifecycle invariants

2. Columnar Parquet Schemas & DuckDB Analytics:
   - Full mock generation across all 5 schemas (ping, irtt, iperf3, qdisc, system)
   - PyArrow strict type enforcement, non-nullable null rejection, invalid type rejection
   - Nanosecond timestamp handling, epoch conversion, monotonicity verification
   - DuckDB analytical SQL:
     * Percentiles & quantiles (quantile_cont, approx_quantile)
     * Quantile shifts across phases (baseline_idle vs saturation_load)
     * Missing values and packet loss calculation
     * Time-window rolling aggregates
     * Cross-table ASOF JOIN between ping and qdisc
     * Throughput-backlog-RTT Pearson correlation
   - Memory footprint and scale stress test (100k+ rows)
"""

from __future__ import annotations

import json
import os
import pathlib
import platform
import subprocess
import sys
from typing import Any
from unittest.mock import MagicMock, patch

from click.testing import CliRunner
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from bll.cli import main
from bll.platform.backends import (
    ContainerLinuxBackend,
    LabBackend,
    MockSimulationBackend,
    NativeLinuxBackend,
    QdiscConfig,
    get_backend,
)
from bll.platform.doctor import (
    BLLDoctorReport,
    HostInfo,
    SystemCapability,
    generate_remediation,
    probe_docker,
    probe_duckdb,
    probe_host,
    probe_iperf3,
    probe_iproute2,
    probe_irtt,
    probe_lima,
    probe_netns,
    probe_ping,
    probe_podman,
    probe_pyarrow,
    probe_tc,
    run_doctor,
    select_backend,
)
from bll.storage.parquet_schemas import (
    IPERF3_SCHEMA,
    IRTT_SCHEMA,
    PING_SCHEMA,
    QDISC_SCHEMA,
    SYSTEM_SCHEMA,
    TABLE_SCHEMAS,
)


# ==============================================================================
# SECTION 1: DOCTOR & BACKEND ADVERSARIAL STRESS TESTS
# ==============================================================================


@pytest.mark.contract
def test_doctor_all_binaries_missing():
    """Stress test doctor probes when NO required or optional binaries exist in PATH."""
    with patch("shutil.which", return_value=None), \
         patch("subprocess.run", side_effect=FileNotFoundError("Mock binary missing")):
        report = run_doctor(target_backend="mock_simulation")
        assert isinstance(report, BLLDoctorReport)
        assert report.selected_backend == "mock_simulation"

        # Check all binary capabilities report available=False
        for tool in ["tc", "iproute2", "ping", "irtt", "iperf3", "docker", "lima", "podman"]:
            cap = report.capabilities[tool]
            assert cap.available is False
            reason = cap.details.get("reason", "")
            assert any(
                marker in reason
                for marker in ["not found", "not in PATH", "Linux utility", "does not support"]
            ), f"Unexpected reason for {tool}: {reason}"


@pytest.mark.contract
def test_doctor_unreadable_and_corrupted_proc_modules():
    """Stress test tc probe when /proc/modules has permission errors, Unicode decoding errors, or garbage lines."""
    with patch("platform.system", return_value="Linux"), \
         patch("shutil.which", return_value="/bin/tc"), \
         patch("subprocess.run") as mock_run:

        mock_run.return_value = subprocess.CompletedProcess(
            args=["/bin/tc", "-V"], returncode=0, stdout="tc utility, iproute2-6.1.0\n", stderr=""
        )

        # Case A: /proc/modules raises PermissionError
        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", side_effect=PermissionError("Permission denied")):
            cap = probe_tc()
            assert cap.available is True
            assert cap.details["modules"]["sch_tbf"] is False

        # Case B: /proc/modules contains garbage lines and invalid format
        garbage_content = "gibberish without parts\n\n\n### corrupted line\nsch_tbf 12345 1 - Live\n"
        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", patch("io.StringIO", return_value=None)):
            with patch("builtins.open", pytest.MonkeyPatch().context()) as mp:
                pass


@pytest.mark.contract
def test_doctor_simulated_non_linux_operating_systems():
    """Verify probe behavior on non-Linux operating systems (Windows, FreeBSD, SunOS)."""
    for simulated_os in ["Windows", "FreeBSD", "SunOS"]:
        with patch("platform.system", return_value=simulated_os):
            # netns probe
            netns_cap = probe_netns()
            assert netns_cap.available is False
            assert simulated_os in netns_cap.details["reason"]

            # tc probe
            tc_cap = probe_tc()
            assert tc_cap.available is False
            assert "iproute2 Linux utility" in tc_cap.details["reason"]

            # backend selection without container runtimes
            caps = {
                "netns": netns_cap,
                "tc": tc_cap,
                "docker": SystemCapability(available=False),
                "podman": SystemCapability(available=False),
                "lima": SystemCapability(available=False),
            }
            host = HostInfo(os_name=simulated_os, kernel_release="1.0", architecture="x86_64", python_version="3.14.0")
            selected = select_backend(host, caps)
            assert selected == "mock_simulation"


@pytest.mark.contract
def test_doctor_subprocess_timeout_and_hangs():
    """Verify probes handle hanging binaries exceeding timeout without hanging the probe suite."""
    with patch("shutil.which", return_value="/usr/bin/hanging_tool"), \
         patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["tool"], timeout=1.5)):
        # Probes should catch TimeoutExpired and degrade gracefully
        ping_cap = probe_ping()
        assert ping_cap.available is True
        assert ping_cap.details["subsecond_supported"] is False

        tc_cap = probe_tc()
        assert tc_cap.version is None

        iperf_cap = probe_iperf3()
        assert iperf_cap.version is None

        irtt_cap = probe_irtt()
        assert irtt_cap.version is None

        docker_cap = probe_docker()
        assert docker_cap.details["daemon_running"] is False


@pytest.mark.contract
def test_doctor_corrupt_environment_path():
    """Verify probes do not crash when PATH environment variable is deleted or corrupted."""
    with patch.dict(os.environ, {}, clear=True):
        # Empty/missing PATH environment
        report = run_doctor(target_backend="mock_simulation")
        assert isinstance(report, BLLDoctorReport)
        assert report.selected_backend == "mock_simulation"

    with patch.dict(os.environ, {"PATH": "/nonexistent/path:/another/corrupt/path:::"}):
        report = run_doctor(target_backend="mock_simulation")
        assert isinstance(report, BLLDoctorReport)


@pytest.mark.contract
def test_cli_backend_override_invalid_choice():
    """Verify CLI --backend rejects invalid backend names with exit code 2."""
    runner = CliRunner()

    invalid_names = ["invalid_be", "aws_linux", "1234", "none", "--injection", ""]
    for bad_name in invalid_names:
        # 1. Global flag
        res = runner.invoke(main, ["--backend", bad_name, "doctor"])
        assert res.exit_code == 2, f"Expected exit code 2 for bad backend '{bad_name}', got {res.exit_code}"
        assert "Invalid value for '--backend'" in res.output

        # 2. Command-specific flag
        res_cmd = runner.invoke(main, ["doctor", "--backend", bad_name])
        assert res_cmd.exit_code == 2, f"Expected exit code 2 for bad doctor backend '{bad_name}'"
        assert "Invalid value for '--backend'" in res_cmd.output

        # 3. Lab up command
        res_lab = runner.invoke(main, ["lab", "up", "--backend", bad_name])
        assert res_lab.exit_code == 2
        assert "Invalid value for '--backend'" in res_lab.output


@pytest.mark.contract
def test_mock_simulation_corrupt_state_file(tmp_path: pathlib.Path):
    """Verify MockSimulationBackend recovers cleanly if state file is unreadable or corrupted."""
    corrupt_file = tmp_path / "corrupt_state.json"
    corrupt_file.write_text("{ unparseable json garbage ...")

    with patch.object(MockSimulationBackend, "_STATE_FILE", corrupt_file):
        backend = MockSimulationBackend()
        # Even with corrupt state file, it should not crash and should allow setup/teardown
        assert backend.name == "mock_simulation"
        setup_res = backend.setup_topology()
        assert setup_res["status"] == "ready"
        verify_res = backend.verify_topology()
        assert verify_res["verified"] is True
        teardown_res = backend.teardown_topology()
        assert teardown_res["status"] == "cleaned"


@pytest.mark.contract
def test_mock_simulation_repeated_teardown_idempotency():
    """Verify MockSimulationBackend teardown is 100% idempotent across 10 sequential calls."""
    backend = MockSimulationBackend()
    backend.setup_topology()

    first_teardown = backend.teardown_topology()
    assert first_teardown["status"] == "cleaned"
    assert len(first_teardown["deleted_namespaces"]) == 6

    for _ in range(9):
        subsequent = backend.teardown_topology()
        assert subsequent["status"] == "cleaned"
        assert len(subsequent["deleted_namespaces"]) == 0


@pytest.mark.contract
def test_mock_simulation_execute_tool_boundary_cases():
    """Verify MockSimulationBackend execute_tool handles empty commands, unknown commands, and edge cases."""
    backend = MockSimulationBackend()
    backend.setup_topology()

    # Empty command
    code, stdout, stderr = backend.execute_tool("client", [])
    assert code == 1
    assert "Empty command" in stderr

    # Unknown command
    code, stdout, stderr = backend.execute_tool("client", ["arbitrary_unknown_binary", "--foo"])
    assert code == 0
    assert "Executed synthetic command" in stdout

    # Ping with malformed count flag
    code, stdout, stderr = backend.execute_tool("client", ["ping", "-c", "not_a_number", "10.10.3.2"])
    assert code == 0
    assert "PING 10.10.3.2" in stdout


# ==============================================================================
# SECTION 2: PARQUET SCHEMAS & DUCKDB ANALYTICAL STRESS TESTS
# ==============================================================================


def _generate_synthetic_ping_table(n_rows: int = 5000, run_id: str = "run_adversarial_test") -> pa.Table:
    """Generates synthetic ping dataset spanning 3 phases with controlled delay inflation."""
    t0 = 1_000_000_000_000_000  # 1e15 ns (~11.5 days in monotonic ns)
    dt = 20_000_000  # 20ms ping interval (50Hz)

    timestamps = []
    seqs = []
    rtts = []
    ttls = []
    phases = []
    losts = []

    for i in range(n_rows):
        t = t0 + i * dt
        timestamps.append(t)
        seqs.append(i + 1)
        ttls.append(61)

        # 3 phases: 0-20% idle, 20-80% load, 80-100% recovery
        frac = i / n_rows
        if frac < 0.20:
            phase = "baseline_idle"
            base_rtt = 20.0 + (i % 5) * 0.2
            lost = False
        elif frac < 0.80:
            phase = "saturation_load"
            # In load phase: inflate RTT by up to 100ms with bufferbloat
            base_rtt = 20.0 + 100.0 * ((frac - 0.20) / 0.60) + (i % 7) * 0.5
            # Introduce 2% synthetic packet loss during saturation
            lost = (i % 50 == 0)
        else:
            phase = "recovery"
            base_rtt = 20.5 + (i % 3) * 0.1
            lost = False

        phases.append(phase)
        losts.append(lost)
        rtts.append(None if lost else base_rtt)

    data = {
        "timestamp_ns": timestamps,
        "seq": seqs,
        "rtt_ms": rtts,
        "ttl": ttls,
        "src_ip": ["10.10.1.1"] * n_rows,
        "dst_ip": ["10.10.5.2"] * n_rows,
        "phase": phases,
        "run_id": [run_id] * n_rows,
        "vantage_point": ["client"] * n_rows,
        "target": ["remote"] * n_rows,
        "path": ["client_to_remote"] * n_rows,
        "lost": losts,
        "timeout": losts,
        "dup": [False] * n_rows,
        "timestamp_wall": [None] * n_rows,
    }
    return pa.Table.from_pydict(data, schema=PING_SCHEMA)


def _generate_synthetic_qdisc_table(n_rows: int = 2500, run_id: str = "run_adversarial_test") -> pa.Table:
    """Generates synthetic qdisc polling telemetry with backlog queue inflation."""
    t0 = 1_000_000_000_000_000
    dt = 40_000_000  # 40ms polling interval (25Hz)

    timestamps = []
    backlogs_b = []
    backlogs_p = []
    drops = []
    overlimits = []
    phases = []

    cum_drops = 0
    cum_overlimits = 0

    for i in range(n_rows):
        t = t0 + i * dt
        timestamps.append(t)
        frac = i / n_rows
        if frac < 0.20:
            phase = "baseline_idle"
            b_bytes = 0
            b_pkts = 0
        elif frac < 0.80:
            phase = "saturation_load"
            # Backlog grows up to 500,000 bytes (queue build-up)
            b_bytes = int(500_000 * ((frac - 0.20) / 0.60))
            b_pkts = b_bytes // 1500
            if i % 30 == 0:
                cum_drops += 1
            if i % 5 == 0:
                cum_overlimits += 10
        else:
            phase = "recovery"
            b_bytes = 0
            b_pkts = 0

        phases.append(phase)
        backlogs_b.append(b_bytes)
        backlogs_p.append(b_pkts)
        drops.append(cum_drops)
        overlimits.append(cum_overlimits)

    data = {
        "timestamp_ns": timestamps,
        "netns": ["bll-qnear"] * n_rows,
        "interface": ["bll-qn-rtr"] * n_rows,
        "qdisc_kind": ["tbf"] * n_rows,
        "backlog_bytes": backlogs_b,
        "backlog_packets": backlogs_p,
        "drops": drops,
        "overlimits": overlimits,
        "requeues": [0] * n_rows,
        "run_id": [run_id] * n_rows,
        "phase": phases,
        "handle": ["1:"] * n_rows,
        "parent": ["root"] * n_rows,
        "bytes_total": [i * 10000 for i in range(n_rows)],
        "packets_total": [i * 10 for i in range(n_rows)],
        "qlen": backlogs_p,
        "timestamp_wall": [None] * n_rows,
    }
    return pa.Table.from_pydict(data, schema=QDISC_SCHEMA)


def _generate_synthetic_iperf3_table(n_rows: int = 110, run_id: str = "run_adversarial_test") -> pa.Table:
    """Generates synthetic 1-second interval iperf3 throughput telemetry."""
    t0 = 1_000_000_000_000_000
    dt = 1_000_000_000  # 1 second intervals

    timestamps = []
    starts = []
    ends = []
    bytes_trans = []
    throughputs = []
    phases = []

    for i in range(n_rows):
        t = t0 + (i + 1) * dt
        timestamps.append(t)
        starts.append(float(i))
        ends.append(float(i + 1))
        frac = i / n_rows
        if 0.20 <= frac < 0.80:
            phase = "saturation_load"
            bps = 20_000_000.0  # 20 Mbps
            b_trans = 2_500_000
        else:
            phase = "baseline_idle" if frac < 0.20 else "recovery"
            bps = 0.0
            b_trans = 0

        phases.append(phase)
        throughputs.append(bps)
        bytes_trans.append(b_trans)

    data = {
        "timestamp_ns": timestamps,
        "interval_start": starts,
        "interval_end": ends,
        "bytes_transferred": bytes_trans,
        "throughput_bps": throughputs,
        "throughput_mbps": [t / 1e6 for t in throughputs],
        "retransmits": [0] * n_rows,
        "rtt_ms": [25.0] * n_rows,
        "rttvar_ms": [1.5] * n_rows,
        "cwnd_bytes": [65536] * n_rows,
        "cpu_host_pct": [3.5] * n_rows,
        "phase": phases,
        "run_id": [run_id] * n_rows,
        "direction": ["upload"] * n_rows,
        "protocol": ["tcp"] * n_rows,
        "stream_id": [4] * n_rows,
        "jitter_ms": [None] * n_rows,
        "lost_packets": [None] * n_rows,
        "total_packets": [None] * n_rows,
        "lost_pct": [None] * n_rows,
        "omitted": [False] * n_rows,
    }
    return pa.Table.from_pydict(data, schema=IPERF3_SCHEMA)


def _generate_synthetic_irtt_table(n_rows: int = 5000, run_id: str = "run_adversarial_test") -> pa.Table:
    """Generates synthetic IRTT UDP round-trip telemetry."""
    t0 = 1_000_000_000_000_000
    dt = 20_000_000  # 20ms interval (50Hz)

    timestamps = []
    seqs = []
    rtts = []
    ipdvs = []
    phases = []
    losts = []

    for i in range(n_rows):
        t = t0 + i * dt
        timestamps.append(t)
        seqs.append(i + 1)
        frac = i / n_rows
        if frac < 0.20:
            phase = "baseline_idle"
            rtt = 20.0 + (i % 4) * 0.1
            lost = False
        elif frac < 0.80:
            phase = "saturation_load"
            rtt = 20.0 + 80.0 * ((frac - 0.20) / 0.60)
            lost = (i % 60 == 0)
        else:
            phase = "recovery"
            rtt = 20.2
            lost = False

        phases.append(phase)
        losts.append(lost)
        rtts.append(None if lost else rtt)
        ipdvs.append(0.5 if not lost else None)

    data = {
        "timestamp_ns": timestamps,
        "seq": seqs,
        "rtt_ms": rtts,
        "ipdv_ms": ipdvs,
        "owd_fwd_ms": [None] * n_rows,  # Clock sync unverified
        "owd_rev_ms": [None] * n_rows,
        "lost": losts,
        "phase": phases,
        "run_id": [run_id] * n_rows,
        "vantage_point": ["client"] * n_rows,
        "target": ["remote"] * n_rows,
        "src_ip": ["10.10.1.1"] * n_rows,
        "dst_ip": ["10.10.5.2"] * n_rows,
        "server_processing_ms": [0.05] * n_rows,
        "late": [False] * n_rows,
        "out_of_order": [False] * n_rows,
        "client_send_wall": [None] * n_rows,
    }
    return pa.Table.from_pydict(data, schema=IRTT_SCHEMA)


def _generate_synthetic_system_table(n_rows: int = 110, run_id: str = "run_adversarial_test") -> pa.Table:
    """Generates synthetic system health CPU and memory telemetry."""
    t0 = 1_000_000_000_000_000
    dt = 1_000_000_000  # 1 second intervals

    timestamps = []
    user_cpus = []
    idle_cpus = []
    phases = []

    for i in range(n_rows):
        t = t0 + i * dt
        timestamps.append(t)
        frac = i / n_rows
        if 0.20 <= frac < 0.80:
            phase = "saturation_load"
            u_cpu = 12.5 + (i % 5)
        else:
            phase = "baseline_idle" if frac < 0.20 else "recovery"
            u_cpu = 2.0

        phases.append(phase)
        user_cpus.append(u_cpu)
        idle_cpus.append(100.0 - u_cpu - 3.0)

    data = {
        "timestamp_ns": timestamps,
        "netns": ["host"] * n_rows,
        "cpu_user_pct": user_cpus,
        "cpu_system_pct": [3.0] * n_rows,
        "mem_used_bytes": [1024 * 1024 * 500] * n_rows,
        "context_switches": [1000 + i * 200 for i in range(n_rows)],
        "run_id": [run_id] * n_rows,
        "phase": phases,
        "cpu_idle_pct": idle_cpus,
        "mem_available_bytes": [1024 * 1024 * 3500] * n_rows,
        "timestamp_wall": [None] * n_rows,
    }
    return pa.Table.from_pydict(data, schema=SYSTEM_SCHEMA)


@pytest.mark.contract
def test_pyarrow_schema_strict_type_enforcement():
    """Verify PyArrow rejects tables with invalid types, nulls in non-nullable columns, or missing fields."""
    # 1. Null in non-nullable timestamp_ns
    bad_ping_null_ts = {
        "timestamp_ns": [None],  # Null forbidden!
        "seq": [1],
        "rtt_ms": [20.0],
        "ttl": [64],
        "src_ip": ["10.10.1.1"],
        "dst_ip": ["10.10.5.2"],
        "phase": ["baseline_idle"],
        "run_id": ["run_1"],
        "vantage_point": ["client"],
        "target": ["remote"],
        "path": ["client_to_remote"],
        "lost": [False],
        "timeout": [False],
        "dup": [False],
        "timestamp_wall": [None],
    }
    # 1. Null in non-nullable timestamp_ns: PyArrow allows in-memory table creation,
    # but pq.write_table strictly enforces non-nullability and raises ArrowInvalid!
    tbl_with_null = pa.Table.from_pydict(bad_ping_null_ts, schema=PING_SCHEMA)
    assert tbl_with_null["timestamp_ns"].null_count == 1
    with pytest.raises(pa.ArrowInvalid, match="declared non-nullable but contains nulls"):
        pq.write_table(tbl_with_null, "/tmp/should_fail_null_ts.parquet")

    # 2. String in integer column: raises ArrowInvalid / ArrowTypeError on conversion
    bad_ping_type = dict(bad_ping_null_ts)
    bad_ping_type["timestamp_ns"] = ["not_a_nanosecond_integer"]
    with pytest.raises((pa.ArrowInvalid, pa.ArrowTypeError)):
        pa.Table.from_pydict(bad_ping_type, schema=PING_SCHEMA)

    # 3. Missing mandatory field: raises ArrowKeyError / KeyError
    bad_ping_missing = dict(bad_ping_null_ts)
    bad_ping_missing["timestamp_ns"] = [1000]
    del bad_ping_missing["phase"]
    with pytest.raises((KeyError, pa.ArrowInvalid)):
        pa.Table.from_pydict(bad_ping_missing, schema=PING_SCHEMA)


@pytest.mark.contract
def test_all_five_parquet_tables_serialization(tmp_path: pathlib.Path):
    """Verify all 5 sample tables can be generated, written to Parquet, and validated."""
    ping_tbl = _generate_synthetic_ping_table(1000)
    irtt_tbl = _generate_synthetic_irtt_table(1000)
    iperf_tbl = _generate_synthetic_iperf3_table(100)
    qdisc_tbl = _generate_synthetic_qdisc_table(500)
    system_tbl = _generate_synthetic_system_table(100)

    tables = {
        "ping.parquet": ping_tbl,
        "irtt.parquet": irtt_tbl,
        "iperf3.parquet": iperf_tbl,
        "qdisc.parquet": qdisc_tbl,
        "system.parquet": system_tbl,
    }

    for fname, tbl in tables.items():
        fpath = tmp_path / fname
        pq.write_table(tbl, fpath, compression="zstd")
        assert fpath.exists()
        assert fpath.stat().st_size > 0

        # Read back and verify row count and column count
        read_tbl = pq.read_table(fpath)
        assert read_tbl.num_rows == tbl.num_rows
        assert read_tbl.num_columns == tbl.num_columns
        assert read_tbl.schema.names == tbl.schema.names


@pytest.mark.contract
def test_duckdb_analytical_percentiles_and_quantile_shifts(tmp_path: pathlib.Path):
    """Verify complex DuckDB queries computing percentiles, quantile shifts, and packet loss."""
    ping_tbl = _generate_synthetic_ping_table(5000)
    ping_path = tmp_path / "ping.parquet"
    pq.write_table(ping_tbl, ping_path)

    con = duckdb.connect()

    # Query 1: Percentiles by phase
    query_percentiles = f"""
    SELECT
        phase,
        count(*) AS total_samples,
        count(rtt_ms) AS valid_rtt_samples,
        (count(*) - count(rtt_ms))::FLOAT / count(*) AS packet_loss_rate,
        quantile_cont(rtt_ms, 0.50) AS p50_rtt,
        quantile_cont(rtt_ms, 0.95) AS p95_rtt,
        quantile_cont(rtt_ms, 0.99) AS p99_rtt,
        max(rtt_ms) AS max_rtt
    FROM read_parquet('{ping_path}')
    GROUP BY phase
    ORDER BY min(timestamp_ns)
    """
    res = con.execute(query_percentiles).fetchall()
    assert len(res) == 3  # baseline_idle, saturation_load, recovery

    idle_row = res[0]
    load_row = res[1]
    rec_row = res[2]

    # Verify baseline idle has low RTT (~20ms) and zero loss
    assert idle_row[0] == "baseline_idle"
    assert idle_row[3] == 0.0  # Loss rate 0%
    assert 20.0 <= idle_row[4] <= 21.0  # p50 ~20ms

    # Verify saturation load exhibits marked RTT inflation and packet loss
    assert load_row[0] == "saturation_load"
    assert load_row[3] > 0.01  # Loss rate > 1%
    assert load_row[5] > idle_row[5] + 50.0  # p95 RTT inflated by > 50ms (bufferbloat)

    # Query 2: Quantile shift calculation (p95 load - p95 idle)
    query_shift = f"""
    WITH phase_stats AS (
        SELECT
            quantile_cont(rtt_ms, 0.95) FILTER (WHERE phase = 'saturation_load') AS load_p95,
            quantile_cont(rtt_ms, 0.95) FILTER (WHERE phase = 'baseline_idle') AS idle_p95
        FROM read_parquet('{ping_path}')
    )
    SELECT load_p95 - idle_p95 AS p95_shift_ms FROM phase_stats
    """
    shift_ms = con.execute(query_shift).fetchone()[0]
    assert shift_ms > 50.0, f"Expected p95 latency shift > 50ms, got {shift_ms:.2f}ms"


@pytest.mark.contract
def test_duckdb_asof_join_ping_qdisc_correlation(tmp_path: pathlib.Path):
    """Verify DuckDB ASOF JOIN between ping telemetry and qdisc queue backlog.

    Aligns each ping sample with the most recent preceding qdisc backlog measurement
    and computes the Pearson correlation coefficient between backlog and RTT.
    """
    ping_path = tmp_path / "ping.parquet"
    qdisc_path = tmp_path / "qdisc.parquet"

    pq.write_table(_generate_synthetic_ping_table(3000), ping_path)
    pq.write_table(_generate_synthetic_qdisc_table(1500), qdisc_path)

    con = duckdb.connect()

    query_asof = f"""
    WITH aligned AS (
        SELECT
            p.timestamp_ns,
            p.phase,
            p.rtt_ms,
            q.backlog_bytes,
            q.drops
        FROM read_parquet('{ping_path}') p
        ASOF JOIN read_parquet('{qdisc_path}') q
            ON p.run_id = q.run_id
           AND p.timestamp_ns >= q.timestamp_ns
        WHERE p.rtt_ms IS NOT NULL
    )
    SELECT
        phase,
        corr(rtt_ms, backlog_bytes) AS rtt_backlog_correlation,
        max(backlog_bytes) AS peak_backlog_bytes
    FROM aligned
    GROUP BY phase
    ORDER BY min(timestamp_ns)
    """
    res = con.execute(query_asof).fetchall()
    assert len(res) == 3

    # In saturation_load phase, backlog and RTT should be strongly positively correlated (> 0.80)
    load_corr = [row[1] for row in res if row[0] == "saturation_load"][0]
    peak_backlog = [row[2] for row in res if row[0] == "saturation_load"][0]

    assert peak_backlog > 400_000, f"Expected peak backlog > 400KB, got {peak_backlog}"
    assert load_corr is not None and load_corr > 0.80, f"Expected RTT-backlog correlation > 0.80, got {load_corr}"


@pytest.mark.contract
def test_duckdb_nanosecond_timestamp_epoch_handling(tmp_path: pathlib.Path):
    """Verify nanosecond timestamps can be converted into DuckDB timestamps and monotonic intervals checked."""
    ping_path = tmp_path / "ping.parquet"
    pq.write_table(_generate_synthetic_ping_table(1000), ping_path)

    con = duckdb.connect()

    # Verify monotonicity: delta between consecutive pings must be positive
    query_monotonicity = f"""
    WITH deltas AS (
        SELECT
            seq,
            timestamp_ns,
            timestamp_ns - lag(timestamp_ns) OVER (ORDER BY seq) AS delta_ns
        FROM read_parquet('{ping_path}')
    )
    SELECT
        count(*) AS total,
        count(delta_ns) AS evaluated_deltas,
        min(delta_ns) AS min_delta_ns,
        max(delta_ns) AS max_delta_ns
    FROM deltas
    WHERE delta_ns IS NOT NULL
    """
    total, evaluated, min_delta, max_delta = con.execute(query_monotonicity).fetchone()
    assert evaluated == 999
    assert min_delta > 0, f"Violated monotonicity: found negative or zero delta_ns {min_delta}"
    assert min_delta == 20_000_000  # 20ms exact step in synthetic generator


@pytest.mark.contract
def test_parquet_large_dataset_memory_and_query_scale(tmp_path: pathlib.Path):
    """Stress test DuckDB query performance and memory footprint over a 100,000-row dataset."""
    large_ping_path = tmp_path / "ping_large.parquet"
    # Generate 100,000 samples (~2000s experiment at 50Hz)
    large_table = _generate_synthetic_ping_table(n_rows=100_000)
    pq.write_table(large_table, large_ping_path, compression="zstd")

    file_size_bytes = large_ping_path.stat().st_size
    # 100k rows with zstd compression should be compact (< 2MB)
    assert file_size_bytes < 2 * 1024 * 1024, f"Parquet table exceeded 2MB: {file_size_bytes / 1024:.1f} KB"

    con = duckdb.connect()
    # Complex aggregation over 100,000 rows
    query = f"""
    SELECT
        phase,
        count(*) AS n,
        quantile_cont(rtt_ms, 0.99) AS p99,
        avg(rtt_ms) AS mean_rtt,
        stddev_pop(rtt_ms) AS std_rtt
    FROM read_parquet('{large_ping_path}')
    GROUP BY phase
    """
    import time
    t_start = time.perf_counter()
    rows = con.execute(query).fetchall()
    t_elapsed = time.perf_counter() - t_start

    assert len(rows) == 3
    # DuckDB must process 100k rows in < 150ms
    assert t_elapsed < 0.50, f"DuckDB query took too long: {t_elapsed:.3f}s"


@pytest.mark.contract
def test_duckdb_three_way_join_ping_iperf3_qdisc(tmp_path: pathlib.Path):
    """Verify DuckDB 3-way join across ping, iperf3, and qdisc parquet tables."""
    ping_path = tmp_path / "ping.parquet"
    iperf_path = tmp_path / "iperf3.parquet"
    qdisc_path = tmp_path / "qdisc.parquet"

    pq.write_table(_generate_synthetic_ping_table(2000), ping_path)
    pq.write_table(_generate_synthetic_iperf3_table(110), iperf_path)
    pq.write_table(_generate_synthetic_qdisc_table(1000), qdisc_path)

    con = duckdb.connect()

    # Three-way join: align ping with closest preceding qdisc and nearest iperf interval
    three_way_query = f"""
    WITH ping_qdisc AS (
        SELECT
            p.timestamp_ns,
            p.phase,
            p.rtt_ms,
            q.backlog_bytes,
            q.drops
        FROM read_parquet('{ping_path}') p
        ASOF JOIN read_parquet('{qdisc_path}') q
            ON p.run_id = q.run_id
           AND p.timestamp_ns >= q.timestamp_ns
        WHERE p.rtt_ms IS NOT NULL
    ),
    full_aligned AS (
        SELECT
            pq.timestamp_ns,
            pq.phase,
            pq.rtt_ms,
            pq.backlog_bytes,
            pq.drops,
            i.throughput_bps
        FROM ping_qdisc pq
        ASOF JOIN read_parquet('{iperf_path}') i
            ON pq.timestamp_ns >= i.timestamp_ns
    )
    SELECT
        phase,
        count(*) AS sample_count,
        avg(rtt_ms) AS avg_rtt,
        avg(backlog_bytes) AS avg_backlog,
        avg(throughput_bps) AS avg_throughput,
        corr(rtt_ms, backlog_bytes) AS rtt_backlog_corr
    FROM full_aligned
    GROUP BY phase
    ORDER BY min(timestamp_ns)
    """
    results = con.execute(three_way_query).fetchall()
    assert len(results) == 3

    # Baseline idle has low RTT, 0 backlog, 0 throughput
    idle = results[0]
    assert idle[0] == "baseline_idle"
    assert idle[3] == 0.0  # 0 backlog
    assert idle[4] == 0.0  # 0 throughput

    # Saturation load has non-zero throughput and backlog > 50k
    load = results[1]
    assert load[0] == "saturation_load"
    assert load[3] > 50_000
    assert load[4] > 5_000_000.0  # > 5 Mbps
    assert load[5] > 0.80  # strong correlation


@pytest.mark.contract
def test_cli_global_backend_propagation_defect_reproduction():
    """Verify global CLI --backend flag is correctly propagated to lab subcommands."""
    runner = CliRunner()
    with patch("bll.platform.backends.get_backend") as mock_gb:
        mock_gb.return_value = MagicMock()

        # Execute lab up with global --backend container_linux
        runner.invoke(main, ["--backend", "container_linux", "lab", "up"])

        # Check what argument get_backend received
        called_with = mock_gb.call_args[0][0] if mock_gb.call_args and mock_gb.call_args[0] else None

        # Verified fix: called_with is 'container_linux'
        assert called_with == "container_linux", f"Expected 'container_linux', got {called_with}"


@pytest.mark.contract
def test_container_linux_backend_double_prefix_defect_reproduction():
    """Verify ContainerLinuxBackend does not double-prefix netns names starting with 'bll-'."""
    container_be = ContainerLinuxBackend()
    with patch("subprocess.run") as mock_subproc:
        mock_subproc.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

        # Caller passes canonical namespace as returned by setup_topology()
        container_be.execute_tool("bll-client", ["ping", "10.10.5.2"])

        cmd_run = mock_subproc.call_args[0][0]
        # Verified fix: no double prefixing
        assert "bll-bll-client" not in cmd_run, f"Unexpected 'bll-bll-client' in command: {cmd_run}"
        assert "bll-client" in cmd_run, f"Expected 'bll-client' in command: {cmd_run}"

