"""
Platform discovery, capability probe, and doctor reporting for BLL.
src/bll/platform/doctor.py
"""

from __future__ import annotations

import datetime
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SystemCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    available: bool
    version: str | None = None
    path: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class BLLDoctorReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp_utc: str
    os_name: str  # "Darwin", "Linux", "Windows", etc.
    kernel_release: str
    architecture: str
    selected_backend: Literal["native_linux", "container_linux", "vm_linux", "mock_simulation"]
    capabilities: dict[str, SystemCapability]
    all_requirements_met: bool
    remediation_steps: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class HostInfo:
    os_name: str
    kernel_release: str
    architecture: str
    python_version: str


def probe_host() -> HostInfo:
    """Collects host operating system, kernel, and hardware architecture."""
    return HostInfo(
        os_name=platform.system(),
        kernel_release=platform.release(),
        architecture=platform.machine(),
        python_version=sys.version.split()[0],
    )


def probe_netns() -> SystemCapability:
    """Probes Linux network namespace isolation capability."""
    if platform.system() != "Linux":
        return SystemCapability(
            available=False,
            version=None,
            path=None,
            details={
                "supported_natively": False,
                "reason": f"{platform.system()} kernel does not support Linux CLONE_NEWNET namespaces",
            },
        )

    has_proc_netns = os.path.exists("/proc/self/ns/net") or os.path.exists("/proc/sys/net")
    ip_path = shutil.which("ip")
    is_root = os.geteuid() == 0 if hasattr(os, "geteuid") else False

    available = has_proc_netns and (ip_path is not None)
    return SystemCapability(
        available=available,
        path=ip_path,
        version=None,
        details={
            "supported_natively": True,
            "proc_netns_present": has_proc_netns,
            "privileged": is_root,
        },
    )


def probe_tc() -> SystemCapability:
    """Probes Linux Traffic Control (tc) binary and kernel scheduler modules."""
    if platform.system() != "Linux":
        return SystemCapability(
            available=False,
            version=None,
            path=None,
            details={"modules": {}, "reason": "tc is an iproute2 Linux utility"},
        )

    tc_path = shutil.which("tc")
    if not tc_path:
        return SystemCapability(
            available=False,
            version=None,
            path=None,
            details={"modules": {}, "reason": "tc binary not found in PATH"},
        )

    version_str = None
    try:
        proc = subprocess.run([tc_path, "-V"], capture_output=True, text=True, timeout=1.5)
        if proc.returncode == 0:
            version_str = proc.stdout.strip().split("\n")[0]
    except Exception:
        pass

    modules_checked = ["sch_netem", "sch_tbf", "sch_cake", "sch_htb", "sch_fq_codel"]
    modules_status: dict[str, bool] = {}

    loaded_modules = set()
    if os.path.exists("/proc/modules"):
        try:
            with open("/proc/modules", "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.split()
                    if parts:
                        loaded_modules.add(parts[0])
        except Exception:
            pass

    for mod in modules_checked:
        modules_status[mod] = mod in loaded_modules

    return SystemCapability(
        available=True,
        version=version_str,
        path=tc_path,
        details={"modules": modules_status},
    )


def probe_iproute2() -> SystemCapability:
    """Probes iproute2 `ip` CLI utility."""
    ip_path = shutil.which("ip")
    if not ip_path:
        return SystemCapability(
            available=False,
            version=None,
            path=None,
            details={"reason": "ip utility not found in PATH"},
        )

    version_str = None
    try:
        proc = subprocess.run([ip_path, "-V"], capture_output=True, text=True, timeout=1.5)
        if proc.returncode == 0:
            version_str = proc.stdout.strip().split("\n")[0]
    except Exception:
        pass

    return SystemCapability(
        available=True,
        version=version_str,
        path=ip_path,
        details={},
    )


def probe_ping() -> SystemCapability:
    """Probes ping utility, identifying iputils vs BSD ping and subsecond capability."""
    path = shutil.which("ping")
    if not path:
        return SystemCapability(available=False, details={"reason": "ping not found in PATH"})

    flavor = "unknown"
    version = None
    subsecond_supported = False

    try:
        proc = subprocess.run([path, "-V"], capture_output=True, text=True, timeout=1.5)
        if proc.returncode == 0 and "iputils" in proc.stdout:
            flavor = "iputils"
            version = proc.stdout.strip().split("\n")[0]
            subsecond_supported = True
    except Exception:
        pass

    if flavor == "unknown" and platform.system() == "Darwin":
        flavor = "bsd"
        version = "macOS BSD ping"
        try:
            proc = subprocess.run(
                [path, "-c", "1", "-i", "0.2", "127.0.0.1"],
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            subsecond_supported = (proc.returncode == 0)
        except Exception:
            subsecond_supported = False

    return SystemCapability(
        available=True,
        path=path,
        version=version,
        details={"flavor": flavor, "subsecond_supported": subsecond_supported},
    )


def probe_iperf3() -> SystemCapability:
    """Probes iperf3 load generator binary."""
    path = shutil.which("iperf3")
    if not path:
        return SystemCapability(available=False, details={"reason": "iperf3 not found in PATH"})

    version = None
    try:
        proc = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=1.5)
        if proc.returncode == 0:
            version = proc.stdout.strip().split("\n")[0]
    except Exception:
        pass

    return SystemCapability(
        available=True,
        path=path,
        version=version,
        details={"supports_json": True},
    )


def probe_irtt() -> SystemCapability:
    """Probes irtt isochronous round-trip tester binary."""
    path = shutil.which("irtt")
    if not path:
        return SystemCapability(available=False, details={"reason": "irtt not found in PATH"})

    version = None
    try:
        proc = subprocess.run([path, "version"], capture_output=True, text=True, timeout=1.5)
        if proc.returncode == 0:
            version = proc.stdout.strip().split("\n")[0]
    except Exception:
        pass

    return SystemCapability(
        available=True,
        path=path,
        version=version,
        details={"supports_json": True},
    )


def probe_duckdb() -> SystemCapability:
    """Probes DuckDB Python module and optional CLI."""
    has_module = False
    version = None
    try:
        import duckdb
        has_module = True
        version = duckdb.__version__
    except ImportError:
        pass

    cli_path = shutil.which("duckdb")
    return SystemCapability(
        available=has_module,
        version=version,
        path=cli_path,
        details={"python_module": has_module, "cli_binary": bool(cli_path)},
    )


def probe_pyarrow() -> SystemCapability:
    """Probes PyArrow Python library."""
    has_module = False
    version = None
    try:
        import pyarrow
        has_module = True
        version = pyarrow.__version__
    except ImportError:
        pass

    return SystemCapability(
        available=has_module,
        version=version,
        path=None,
        details={"python_module": has_module},
    )


def probe_docker() -> SystemCapability:
    """Probes Docker CLI and verifies if daemon is active."""
    path = shutil.which("docker")
    if not path:
        return SystemCapability(available=False, details={"reason": "docker CLI not in PATH"})

    daemon_running = False
    server_version = None
    try:
        proc = subprocess.run(
            [path, "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=1.5,
        )
        if proc.returncode == 0:
            daemon_running = True
            server_version = proc.stdout.strip()
    except Exception:
        pass

    return SystemCapability(
        available=True,
        path=path,
        version=server_version,
        details={"daemon_running": daemon_running},
    )


def probe_colima() -> SystemCapability:
    """Probes Colima container runtime."""
    path = shutil.which("colima")
    if not path:
        return SystemCapability(available=False, details={"reason": "colima not in PATH"})

    running = False
    try:
        proc = subprocess.run([path, "status"], capture_output=True, text=True, timeout=1.5)
        running = (proc.returncode == 0 and "running" in proc.stdout.lower())
    except Exception:
        pass

    return SystemCapability(
        available=True,
        path=path,
        details={"running": running},
    )


def probe_lima() -> SystemCapability:
    """Probes Lima VM manager (`limactl`)."""
    path = shutil.which("limactl")
    if not path:
        return SystemCapability(available=False, details={"reason": "limactl not in PATH"})

    instances_running = False
    try:
        proc = subprocess.run([path, "list"], capture_output=True, text=True, timeout=1.5)
        instances_running = (proc.returncode == 0 and "Running" in proc.stdout)
    except Exception:
        pass

    return SystemCapability(
        available=True,
        path=path,
        details={"instances_running": instances_running},
    )


def probe_podman() -> SystemCapability:
    """Probes Podman container runtime."""
    path = shutil.which("podman")
    if not path:
        return SystemCapability(available=False, details={"reason": "podman not in PATH"})

    daemon_running = False
    try:
        proc = subprocess.run([path, "info"], capture_output=True, text=True, timeout=1.5)
        daemon_running = (proc.returncode == 0)
    except Exception:
        pass

    return SystemCapability(
        available=True,
        path=path,
        details={"daemon_running": daemon_running},
    )


def select_backend(
    host: HostInfo,
    capabilities: dict[str, SystemCapability],
    explicit_override: str | None = None,
) -> Literal["native_linux", "container_linux", "vm_linux", "mock_simulation"]:
    """Selects the best available execution backend for the current host environment."""
    valid_backends = ("native_linux", "container_linux", "vm_linux", "mock_simulation")
    if explicit_override:
        if explicit_override not in valid_backends:
            raise ValueError(f"Unknown backend '{explicit_override}'. Must be one of {valid_backends}")
        return explicit_override  # type: ignore

    # 1. Native Linux
    if host.os_name == "Linux":
        netns_cap = capabilities.get("netns")
        tc_cap = capabilities.get("tc")
        if netns_cap and netns_cap.available and tc_cap and tc_cap.available:
            return "native_linux"

    # 2. Container Linux (macOS or non-netns Linux)
    docker_cap = capabilities.get("docker")
    if docker_cap and docker_cap.available and docker_cap.details.get("daemon_running", False):
        return "container_linux"

    podman_cap = capabilities.get("podman")
    if podman_cap and podman_cap.available and podman_cap.details.get("daemon_running", False):
        return "container_linux"

    # 3. Lima VM
    lima_cap = capabilities.get("lima")
    if lima_cap and lima_cap.available and lima_cap.details.get("instances_running", False):
        return "vm_linux"

    # 4. Fallback to mock simulation
    return "mock_simulation"


def generate_remediation(
    backend: Literal["native_linux", "container_linux", "vm_linux", "mock_simulation"],
    host: HostInfo,
    capabilities: dict[str, SystemCapability],
) -> tuple[bool, list[str]]:
    """Evaluates whether all requirements for the selected backend are met and produces remediation steps."""
    remediation: list[str] = []
    requirements_met = True

    # Common Python analytical requirements
    if not capabilities["duckdb"].available:
        requirements_met = False
        remediation.append("Install DuckDB Python library: pip install 'duckdb>=1.0.0'")
    if not capabilities["pyarrow"].available:
        requirements_met = False
        remediation.append("Install PyArrow Python library: pip install 'pyarrow>=15.0.0'")

    if backend == "native_linux":
        if not capabilities["netns"].available:
            requirements_met = False
            remediation.append("Ensure Linux kernel supports network namespaces (CONFIG_NET_NS=y)")
        if not capabilities["tc"].available:
            requirements_met = False
            remediation.append("Install iproute2: sudo apt-get update && sudo apt-get install -y iproute2")
        if not capabilities["iperf3"].available:
            requirements_met = False
            remediation.append("Install iperf3: sudo apt-get install -y iperf3")
        if not capabilities["irtt"].available:
            remediation.append(
                "Optional: Install irtt for UDP round-trip jitter measurements (https://github.com/peteheist/irtt)"
            )

    elif backend == "container_linux":
        docker_cap = capabilities.get("docker")
        podman_cap = capabilities.get("podman")
        has_running_container = (
            (docker_cap and docker_cap.available and docker_cap.details.get("daemon_running", False))
            or (podman_cap and podman_cap.available and podman_cap.details.get("daemon_running", False))
        )
        if not has_running_container:
            requirements_met = False
            if host.os_name == "Darwin":
                remediation.append("Start Docker Desktop (open -a Docker) or start Colima (colima start)")
            else:
                remediation.append("Start Docker daemon: sudo systemctl start docker")

    elif backend == "vm_linux":
        lima_cap = capabilities.get("lima")
        if not (lima_cap and lima_cap.available and lima_cap.details.get("instances_running", False)):
            requirements_met = False
            remediation.append("Start Lima VM instance: limactl start")

    elif backend == "mock_simulation":
        # Mock simulation is self-contained in Python
        if host.os_name == "Darwin":
            remediation.append(
                "Notice: Running in Mock Simulation mode. For physical Linux netns emulation on macOS, start Docker or Colima."
            )
        else:
            remediation.append(
                "Notice: Running in Mock Simulation mode. For physical Linux netns emulation, run on Linux with CAP_NET_ADMIN."
            )

    return requirements_met, remediation


def run_doctor(target_backend: str | None = None) -> BLLDoctorReport:
    """Executes full platform capability discovery and returns BLLDoctorReport."""
    host = probe_host()

    # Required 8 tools from contract + container probes
    capabilities: dict[str, SystemCapability] = {
        "netns": probe_netns(),
        "tc": probe_tc(),
        "iproute2": probe_iproute2(),
        "ping": probe_ping(),
        "irtt": probe_irtt(),
        "iperf3": probe_iperf3(),
        "duckdb": probe_duckdb(),
        "pyarrow": probe_pyarrow(),
        "docker": probe_docker(),
        "colima": probe_colima(),
        "lima": probe_lima(),
        "podman": probe_podman(),
    }

    backend = select_backend(host, capabilities, explicit_override=target_backend)
    all_requirements_met, remediation = generate_remediation(backend, host, capabilities)

    now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return BLLDoctorReport(
        timestamp_utc=now_utc,
        os_name=host.os_name,
        kernel_release=host.kernel_release,
        architecture=host.architecture,
        selected_backend=backend,
        capabilities=capabilities,
        all_requirements_met=all_requirements_met,
        remediation_steps=remediation,
    )
