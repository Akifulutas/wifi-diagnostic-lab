"""Environment diagnostics and readiness checker for Wi-Fi Diagnostic Lab."""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CheckResult:
    name: str
    status: str  # "OK", "WARN", "FAIL"
    message: str
    details: Optional[str] = None


@dataclass
class WifiInterfaceInfo:
    interface: str = "en0"
    card_type: str = "Unknown"
    firmware: str = "Unknown"
    supported_phy: list[str] = field(default_factory=list)
    current_ssid: Optional[str] = None
    current_phy_mode: Optional[str] = None
    current_channel: Optional[str] = None
    current_band: Optional[str] = None
    channel_width: Optional[str] = None
    country_code: Optional[str] = None


def check_python_version() -> CheckResult:
    major, minor, micro = sys.version_info[:3]
    v_str = f"{major}.{minor}.{micro}"
    if sys.version_info >= (3, 11):
        return CheckResult(
            name="Python Runtime",
            status="OK",
            message=f"Python {v_str} (>= 3.11 required)",
            details=f"Executable: {sys.executable}",
        )
    return CheckResult(
        name="Python Runtime",
        status="FAIL",
        message=f"Python {v_str} is unsupported (< 3.11). Please use Python 3.11 or newer.",
    )


def check_os_platform() -> CheckResult:
    system = platform.system()
    release = platform.release()
    machine = platform.machine()
    if system == "Darwin":
        mac_ver = platform.mac_ver()[0]
        return CheckResult(
            name="Operating System",
            status="OK",
            message=f"macOS {mac_ver} ({machine}, Darwin {release})",
            details="Native macOS network telemetry and ping supported",
        )
    return CheckResult(
        name="Operating System",
        status="WARN",
        message=f"{system} ({machine})",
        details="Primary platform is macOS (Darwin); some Wi-Fi telemetry tools may differ.",
    )


def check_ping_tool() -> CheckResult:
    ping_path = shutil.which("ping")
    if not ping_path:
        return CheckResult(
            name="ICMP Ping Utility",
            status="FAIL",
            message="ping binary not found in PATH",
        )
    return CheckResult(
        name="ICMP Ping Utility",
        status="OK",
        message=f"Found at {ping_path}",
    )


def check_iperf3_tool() -> CheckResult:
    iperf3_path = shutil.which("iperf3")
    if not iperf3_path:
        # Check standard Homebrew locations
        for brew_path in ("/opt/homebrew/bin/iperf3", "/usr/local/bin/iperf3"):
            if os.path.isfile(brew_path) and os.access(brew_path, os.X_OK):
                iperf3_path = brew_path
                break

    if not iperf3_path:
        return CheckResult(
            name="iperf3 Network Benchmarking",
            status="WARN",
            message="iperf3 not found in PATH",
            details="Install via 'brew install iperf3' before live hardware runs. (Mock/replay mode works offline)",
        )

    try:
        proc = subprocess.run([iperf3_path, "--version"], capture_output=True, text=True, timeout=5)
        first_line = proc.stdout.splitlines()[0] if proc.stdout else "iperf3 available"
        return CheckResult(
            name="iperf3 Network Benchmarking",
            status="OK",
            message=f"{first_line} ({iperf3_path})",
        )
    except Exception as e:
        return CheckResult(
            name="iperf3 Network Benchmarking",
            status="WARN",
            message=f"Found at {iperf3_path} but error querying version: {e}",
        )


def query_macos_wifi_telemetry() -> WifiInterfaceInfo:
    info = WifiInterfaceInfo()
    try:
        proc = subprocess.run(
            ["system_profiler", "SPAirPortDataType"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode != 0 or not proc.stdout:
            return info

        stdout = proc.stdout
        card_match = re.search(r"Card Type:\s*(.+)", stdout)
        if card_match:
            info.card_type = card_match.group(1).strip()

        fw_match = re.search(r"Firmware Version:\s*(.+)", stdout)
        if fw_match:
            info.firmware = fw_match.group(1).strip()

        phy_match = re.search(r"Supported PHY Modes:\s*(.+)", stdout)
        if phy_match:
            info.supported_phy = [p.strip() for p in phy_match.group(1).split()]

        # Look for Current Network Information
        if "Current Network Information:" in stdout:
            curr_section = stdout.split("Current Network Information:", 1)[1]
            lines = curr_section.splitlines()
            for line in lines[:25]:
                stripped = line.strip()
                if stripped.startswith("PHY Mode:"):
                    info.current_phy_mode = stripped.split(":", 1)[1].strip()
                elif stripped.startswith("Channel:"):
                    chan_val = stripped.split(":", 1)[1].strip()
                    info.current_channel = chan_val
                    if "5GHz" in chan_val:
                        info.current_band = "5 GHz"
                    elif "2GHz" in chan_val or "2.4GHz" in chan_val:
                        info.current_band = "2.4 GHz"
                    elif "6GHz" in chan_val:
                        info.current_band = "6 GHz"

                    width_match = re.search(r"(\d+MHz)", chan_val)
                    if width_match:
                        info.channel_width = width_match.group(1)
                elif stripped.startswith("Country Code:"):
                    info.country_code = stripped.split(":", 1)[1].strip()
                elif line.startswith("            ") and line.rstrip().endswith(":"):
                    # Potential SSID header
                    candidate = line.strip().rstrip(":")
                    if candidate and not info.current_ssid and candidate != "<redacted>":
                        info.current_ssid = candidate
    except Exception:
        pass
    return info


def check_wifi_environment() -> CheckResult:
    if platform.system() != "Darwin":
        return CheckResult(
            name="Wi-Fi 6 Hardware & Telemetry",
            status="WARN",
            message="Non-macOS environment, skipping SPAirPortDataType query",
        )

    info = query_macos_wifi_telemetry()
    has_ax = any("ax" in p.lower() for p in info.supported_phy) or (
        info.current_phy_mode and "ax" in info.current_phy_mode.lower()
    )

    details = []
    if info.card_type != "Unknown":
        details.append(f"Card: {info.card_type}")
    if info.supported_phy:
        details.append(f"Supported PHY: {' '.join(info.supported_phy)}")
    if info.current_phy_mode:
        details.append(f"Active Link: {info.current_phy_mode}")
    if info.current_channel:
        details.append(f"Channel/Band: {info.current_channel}")

    detail_str = "; ".join(details) if details else None

    if has_ax:
        return CheckResult(
            name="Wi-Fi 6 Hardware & Telemetry",
            status="OK",
            message="Wi-Fi 6 (802.11ax) hardware confirmed active",
            details=detail_str,
        )
    return CheckResult(
        name="Wi-Fi 6 Hardware & Telemetry",
        status="WARN",
        message="Wi-Fi card detected, but 802.11ax capability not yet verified",
        details=detail_str,
    )


def run_doctor(verbose: bool = False) -> int:
    """Runs all readiness checks and prints a formatted diagnostic report."""
    checks = [
        check_python_version(),
        check_os_platform(),
        check_ping_tool(),
        check_iperf3_tool(),
        check_wifi_environment(),
    ]

    print("=" * 68)
    print("  Wi-Fi Diagnostic Lab — Pre-flight Environment Doctor")
    print("=" * 68)

    status_symbols = {
        "OK": "\033[92m[  OK  ]\033[0m",
        "WARN": "\033[93m[ WARN ]\033[0m",
        "FAIL": "\033[91m[ FAIL ]\033[0m",
    }

    fail_count = 0
    warn_count = 0

    for c in checks:
        sym = status_symbols.get(c.status, f"[{c.status}]")
        print(f"{sym} {c.name:<32} {c.message}")
        if c.details:
            print(f"         ↳ {c.details}")
        if c.status == "FAIL":
            fail_count += 1
        elif c.status == "WARN":
            warn_count += 1

    print("-" * 68)
    if fail_count > 0:
        print(f"\033[91mDoctor summary: {fail_count} critical failure(s). Fix missing requirements before proceeding.\033[0m")
        return 1
    elif warn_count > 0:
        print(f"\033[93mDoctor summary: System ready with {warn_count} warning(s).\033[0m")
        print("Tip: Mock/replay mode and offline statistical analyses are fully available.")
        return 0
    else:
        print("\033[92mDoctor summary: All pre-flight checks passed! System fully prepared for live runs.\033[0m")
        return 0


if __name__ == "__main__":
    sys.exit(run_doctor())
