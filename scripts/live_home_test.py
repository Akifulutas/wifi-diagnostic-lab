#!/usr/bin/env python3
"""Wi-Fi Diagnostic Lab — Live Home Network Bufferbloat & Latency Localization.

Performs a controlled 3-phase live experiment on macOS:
1. Idle Baseline: Dual ICMP probing (Gateway vs. Remote Target)
2. Saturation Load: Multi-stream HTTP load + continuous dual probing
3. Recovery Phase: Drain observation + continuous dual probing

Differential Path Algebra:
  Hop 1 (Wi-Fi Hop): Client -> Gateway (FRITZ!Box 192.168.178.1)
  Hop 2 (Access / WAN): Gateway -> Remote Target (1.1.1.1 / 8.8.8.8)
  Delta RTT_wifi = RTT(Gateway, Load) - RTT(Gateway, Idle)
  Delta RTT_total = RTT(Remote, Load) - RTT(Remote, Idle)
  Delta RTT_wan = max(0, Delta RTT_total - Delta RTT_wifi)
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class ProbeSample:
    timestamp_utc: str
    target_name: str
    target_ip: str
    phase: str
    seq: int
    rtt_ms: float


@dataclass
class PhaseSummary:
    count: int = 0
    min_ms: float = 0.0
    median_ms: float = 0.0
    p95_ms: float = 0.0
    max_ms: float = 0.0
    jitter_ms: float = 0.0


def detect_default_gateway() -> str:
    """Detect default IPv4 gateway via netstat."""
    try:
        out = subprocess.check_output(["netstat", "-nr"], text=True)
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0] == "default" and re.match(r"^\d+\.\d+\.\d+\.\d+$", parts[1]):
                return parts[1]
    except Exception:
        pass
    return "192.168.178.1"


def get_wifi_telemetry() -> dict:
    """Query macOS SPAirPortDataType for live Wi-Fi 6 link parameters."""
    telemetry = {
        "phy_mode": "Unknown",
        "channel": "Unknown",
        "signal_noise": "Unknown",
        "tx_rate_mbps": 0.0,
        "mcs_index": "Unknown",
    }
    try:
        out = subprocess.check_output(["system_profiler", "SPAirPortDataType"], text=True, timeout=10)
        phy = re.search(r"PHY Mode:\s*(.+)", out)
        chan = re.search(r"Channel:\s*(.+)", out)
        snr = re.search(r"Signal\s*/\s*Noise:\s*(.+)", out)
        tx = re.search(r"Transmit Rate:\s*(\d+)", out)
        mcs = re.search(r"MCS Index:\s*(\d+)", out)
        if phy:
            telemetry["phy_mode"] = phy.group(1).strip()
        if chan:
            telemetry["channel"] = chan.group(1).strip()
        if snr:
            telemetry["signal_noise"] = snr.group(1).strip()
        if tx:
            telemetry["tx_rate_mbps"] = float(tx.group(1))
        if mcs:
            telemetry["mcs_index"] = mcs.group(1).strip()
    except Exception as e:
        telemetry["error"] = str(e)
    return telemetry


class ContinuousPingWorker:
    """Continuously pings a target and tags samples with the current phase."""

    def __init__(self, target_name: str, target_ip: str, interval_s: float = 0.2):
        self.target_name = target_name
        self.target_ip = target_ip
        self.interval_s = interval_s
        self.current_phase = "idle"
        self.samples: List[ProbeSample] = []
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def set_phase(self, phase: str):
        self.current_phase = phase

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3.0)

    def _run(self):
        # Use macOS ping: ping -c 999999 -i interval target
        cmd = ["ping", "-c", "999999", "-i", str(self.interval_s), self.target_ip]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            for line in proc.stdout:
                if self._stop_event.is_set():
                    break
                # Match: 64 bytes from ... icmp_seq=0 ttl=64 time=2.845 ms
                m = re.search(r"icmp_seq=(\d+).*time=([\d\.]+)\s*ms", line)
                if m:
                    seq = int(m.group(1))
                    rtt = float(m.group(2))
                    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    self.samples.append(
                        ProbeSample(
                            timestamp_utc=ts,
                            target_name=self.target_name,
                            target_ip=self.target_ip,
                            phase=self.current_phase,
                            seq=seq,
                            rtt_ms=rtt,
                        )
                    )
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                proc.kill()


class MultiStreamLoadGenerator:
    """Generates saturating network load using concurrent streaming HTTP chunk readers."""

    def __init__(self, streams: int = 4, url: str = "https://speed.cloudflare.com/__down?bytes=50000000"):
        self.streams = streams
        self.url = url
        self._stop_event = threading.Event()
        self._threads: List[threading.Thread] = []
        self.bytes_transferred = 0
        self.duration_s = 0.0
        self._lock = threading.Lock()

    def start(self):
        self._start_time = time.time()
        for i in range(self.streams):
            t = threading.Thread(target=self._worker, daemon=True)
            self._threads.append(t)
            t.start()

    def stop(self):
        self._stop_event.set()
        for t in self._threads:
            t.join(timeout=2.0)
        self.duration_s = max(0.1, time.time() - self._start_time)

    def _worker(self):
        import ssl
        import urllib.request

        ctx = ssl._create_unverified_context()
        while not self._stop_event.is_set():
            try:
                req = urllib.request.Request(self.url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})
                with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
                    while not self._stop_event.is_set():
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        with self._lock:
                            self.bytes_transferred += len(chunk)
            except Exception:
                time.sleep(0.2)

    @property
    def throughput_mbps(self) -> float:
        if self.duration_s <= 0:
            return 0.0
        return (self.bytes_transferred * 8.0) / (self.duration_s * 1_000_000.0)


def calc_stats(samples: List[ProbeSample]) -> PhaseSummary:
    if not samples:
        return PhaseSummary()
    vals = [s.rtt_ms for s in samples]
    vals.sort()
    count = len(vals)
    min_v = vals[0]
    med_v = statistics.median(vals)
    p95_idx = int(math.ceil(0.95 * count)) - 1
    p95_v = vals[min(p95_idx, count - 1)]
    max_v = vals[-1]
    # RFC 3393 jitter: mean of absolute differences of successive samples
    jitters = [abs(vals[i] - vals[i - 1]) for i in range(1, count)] if count > 1 else [0.0]
    jitter_v = statistics.mean(jitters)
    return PhaseSummary(
        count=count,
        min_ms=round(min_v, 2),
        median_ms=round(med_v, 2),
        p95_ms=round(p95_v, 2),
        max_ms=round(max_v, 2),
        jitter_ms=round(jitter_v, 2),
    )


def grade_bufferbloat(delta_rtt_ms: float) -> str:
    if delta_rtt_ms <= 5.0:
        return "A+ (Outstanding / No Bloat)"
    elif delta_rtt_ms <= 15.0:
        return "A (Minimal Bloat)"
    elif delta_rtt_ms <= 30.0:
        return "B (Acceptable)"
    elif delta_rtt_ms <= 60.0:
        return "C (Noticeable Degradation)"
    elif delta_rtt_ms <= 120.0:
        return "D (Poor / High Latency Spikes)"
    else:
        return "F (Severe Bufferbloat / Packet Stalling)"


def run_live_home_test(
    idle_s: float = 8.0,
    load_s: float = 15.0,
    recovery_s: float = 7.0,
    gateway_ip: Optional[str] = None,
    remote_ip: str = "1.1.1.1",
    output_dir: Path = Path("data/raw/live_home_runs"),
    streams: int = 4,
    position: str = "L1",
) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    gateway = gateway_ip or detect_default_gateway()

    ts_now = datetime.datetime.now(datetime.timezone.utc)
    run_id = f"live_home_{position}_{ts_now.strftime('%Y%m%dT%H%M%SZ')}"
    run_folder = output_dir / run_id
    run_folder.mkdir(parents=True, exist_ok=True)

    print("\033[1;36m" + "=" * 76 + "\033[0m")
    print(f"\033[1;32m  Bufferbloat & Wi-Fi Diagnostic Lab — Live Home Network Test ({position})\033[0m")
    print(f"  Run ID: \033[1m{run_id}\033[0m")
    print(f"  Position: \033[1;35m{position}\033[0m")
    print(f"  Local Gateway (Wi-Fi Hop):  \033[1;33m{gateway}\033[0m (FRITZ!Box 7530 AX)")
    print(f"  Remote Target (WAN / ISP):  \033[1;34m{remote_ip}\033[0m (Cloudflare Anycast)")
    print("\033[1;36m" + "=" * 76 + "\033[0m")

    # Step 0: Wi-Fi Telemetry
    print("\n[+] Inspecting physical Wi-Fi 6 link parameters via macOS framework...")
    wifi_meta = get_wifi_telemetry()
    print(f"    • 802.11 PHY Mode:  \033[1m{wifi_meta['phy_mode']}\033[0m")
    print(f"    • Operating Channel: \033[1m{wifi_meta['channel']}\033[0m")
    print(f"    • Signal / Noise:    \033[1m{wifi_meta['signal_noise']}\033[0m")
    print(f"    • Physical Tx Rate:  \033[1m{wifi_meta['tx_rate_mbps']} Mbps\033[0m (MCS Index {wifi_meta['mcs_index']})")

    # Initialize workers
    gw_worker = ContinuousPingWorker(target_name="gateway_wifi", target_ip=gateway, interval_s=0.2)
    rm_worker = ContinuousPingWorker(target_name="remote_wan", target_ip=remote_ip, interval_s=0.2)

    gw_worker.start()
    rm_worker.start()

    try:
        # Phase 1: Idle
        print(f"\n\033[1;35m[Phase 1/3] IDLE BASELINE ({idle_s:.1f}s)\033[0m: Measuring unloaded round-trip time...")
        gw_worker.set_phase("idle")
        rm_worker.set_phase("idle")
        for elapsed in range(int(idle_s)):
            time.sleep(1.0)
            sys.stdout.write(f"\r    Observing baseline... {elapsed + 1}/{int(idle_s)}s")
            sys.stdout.flush()
        print(" [Done]")

        # Phase 2: Load
        print(f"\n\033[1;31m[Phase 2/3] SATURATION LOAD ({load_s:.1f}s)\033[0m: Launching {streams} concurrent TCP load streams...")
        gw_worker.set_phase("load")
        rm_worker.set_phase("load")
        loader = MultiStreamLoadGenerator(streams=streams)
        loader.start()
        for elapsed in range(int(load_s)):
            time.sleep(1.0)
            sys.stdout.write(f"\r    Saturating link... {elapsed + 1}/{int(load_s)}s (Transferred: {loader.bytes_transferred / 1e6:.1f} MB)")
            sys.stdout.flush()
        loader.stop()
        print(f" [Done — Average Load Throughput: \033[1;32m{loader.throughput_mbps:.1f} Mbps\033[0m]")

        # Phase 3: Recovery
        print(f"\n\033[1;34m[Phase 3/3] RECOVERY PHASE ({recovery_s:.1f}s)\033[0m: Halting load, tracking queue drain back to baseline...")
        gw_worker.set_phase("recovery")
        rm_worker.set_phase("recovery")
        for elapsed in range(int(recovery_s)):
            time.sleep(1.0)
            sys.stdout.write(f"\r    Monitoring queue drain... {elapsed + 1}/{int(recovery_s)}s")
            sys.stdout.flush()
        print(" [Done]")

    finally:
        gw_worker.stop()
        rm_worker.stop()

    # Consolidate samples
    all_samples = gw_worker.samples + rm_worker.samples

    # Compute statistics by target and phase
    gw_idle = calc_stats([s for s in gw_worker.samples if s.phase == "idle"])
    gw_load = calc_stats([s for s in gw_worker.samples if s.phase == "load"])
    gw_recv = calc_stats([s for s in gw_worker.samples if s.phase == "recovery"])

    rm_idle = calc_stats([s for s in rm_worker.samples if s.phase == "idle"])
    rm_load = calc_stats([s for s in rm_worker.samples if s.phase == "load"])
    rm_recv = calc_stats([s for s in rm_worker.samples if s.phase == "recovery"])

    # Differential Path Calculations
    delta_wifi_med = max(0.0, gw_load.median_ms - gw_idle.median_ms)
    delta_wifi_p95 = max(0.0, gw_load.p95_ms - gw_idle.p95_ms)

    delta_total_med = max(0.0, rm_load.median_ms - rm_idle.median_ms)
    delta_total_p95 = max(0.0, rm_load.p95_ms - rm_idle.p95_ms)

    delta_wan_med = max(0.0, delta_total_med - delta_wifi_med)
    delta_wan_p95 = max(0.0, delta_total_p95 - delta_wifi_p95)

    # Deterministic Localization Decision
    if delta_wifi_p95 < 6.0 and delta_wan_p95 < 10.0:
        verdict = "HEALTHY_MINIMAL_BLOAT"
        bottleneck_region = "None (Queueing delay well controlled by AQM or adequate capacity)"
        details = "Neither the Wi-Fi hop nor the WAN link experienced significant queue buildup."
    elif delta_wifi_p95 >= 15.0 and delta_wan_p95 < 12.0:
        verdict = "WIFI_HOP_BOTTLENECK"
        bottleneck_region = "Local Wi-Fi Link (Client <-> FRITZ!Box AP)"
        details = f"Loaded latency accumulated primarily across the 802.11 link (+{delta_wifi_p95:.1f}ms p95), while WAN delay remained flat."
    elif delta_wifi_p95 < 10.0 and delta_wan_p95 >= 15.0:
        verdict = "WAN_ACCESS_BOTTLENECK"
        bottleneck_region = "WAN Access Link / Modem (NetCologne DS-Lite / ISP Queue)"
        details = f"Wi-Fi link remained ultra-fast (+{delta_wifi_p95:.1f}ms), but total end-to-end latency surged (+{delta_total_p95:.1f}ms). Queueing is in the WAN/modem buffer."
    else:
        verdict = "COMPOUND_BOTTLENECK"
        bottleneck_region = "Both Wi-Fi & WAN Queues"
        details = f"Both hops showed latency buildup: Wi-Fi (+{delta_wifi_p95:.1f}ms) and WAN (+{delta_wan_p95:.1f}ms)."

    grade = grade_bufferbloat(delta_total_p95)

    # Print Summary Table
    print("\n\033[1;36m" + "=" * 76 + "\033[0m")
    print(f"\033[1;33m  MEASUREMENT RESULTS & DIFFERENTIAL PATH LOCALIZATION\033[0m")
    print("\033[1;36m" + "=" * 76 + "\033[0m")
    print(f"{'Vantage Point':<26} | {'Idle Med (p95)':<16} | {'Load Med (p95)':<16} | {'Delta Bloat (p95)':<14}")
    print("-" * 76)
    print(f"{'Wi-Fi Hop (Gateway)':<26} | {gw_idle.median_ms:5.1f} ({gw_idle.p95_ms:5.1f} ms)  | {gw_load.median_ms:5.1f} ({gw_load.p95_ms:5.1f} ms)  | \033[1;32m+{delta_wifi_p95:5.1f} ms\033[0m")
    print(f"{'End-to-End (Remote WAN)':<26} | {rm_idle.median_ms:5.1f} ({rm_idle.p95_ms:5.1f} ms)  | {rm_load.median_ms:5.1f} ({rm_load.p95_ms:5.1f} ms)  | \033[1;31m+{delta_total_p95:5.1f} ms\033[0m")
    print(f"{'Differential WAN Hop (Derived)':<26} | {'--':<16} | {'--':<16} | \033[1;33m+{delta_wan_p95:5.1f} ms\033[0m")
    print("-" * 76)
    print(f"  • Load Throughput:      \033[1m{loader.throughput_mbps:.1f} Mbps\033[0m")
    print(f"  • Bufferbloat Rating:   \033[1m{grade}\033[0m")
    print(f"  • Localization Verdict: \033[1;32m{verdict}\033[0m")
    print(f"  • Bottleneck Region:    \033[1m{bottleneck_region}\033[0m")
    print(f"  • Scientific Analysis:  {details}")
    print("\033[1;36m" + "=" * 76 + "\033[0m")

    # Persist data
    csv_file = run_folder / "probes.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp_utc", "target_name", "target_ip", "phase", "seq", "rtt_ms"])
        for s in all_samples:
            writer.writerow([s.timestamp_utc, s.target_name, s.target_ip, s.phase, s.seq, s.rtt_ms])

    manifest = {
        "run_id": run_id,
        "position": position,
        "timestamp_utc": ts_now.isoformat(),
        "wifi_telemetry": wifi_meta,
        "network": {
            "gateway_ip": gateway,
            "remote_ip": remote_ip,
            "streams": streams,
            "load_throughput_mbps": round(loader.throughput_mbps, 2),
        },
        "statistics": {
            "wifi_hop": {
                "idle": asdict(gw_idle),
                "load": asdict(gw_load),
                "recovery": asdict(gw_recv),
                "delta_median_ms": round(delta_wifi_med, 2),
                "delta_p95_ms": round(delta_wifi_p95, 2),
            },
            "end_to_end": {
                "idle": asdict(rm_idle),
                "load": asdict(rm_load),
                "recovery": asdict(rm_recv),
                "delta_median_ms": round(delta_total_med, 2),
                "delta_p95_ms": round(delta_total_p95, 2),
            },
            "differential_wan": {
                "delta_median_ms": round(delta_wan_med, 2),
                "delta_p95_ms": round(delta_wan_p95, 2),
            },
        },
        "verdict": {
            "label": verdict,
            "bottleneck_region": bottleneck_region,
            "bufferbloat_grade": grade,
            "explanation": details,
        },
    }

    manifest_file = run_folder / "manifest.json"
    manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\n[✓] Run artifacts successfully saved:")
    print(f"    • Manifest: {manifest_file}")
    print(f"    • Time Series CSV: {csv_file} ({len(all_samples)} probe samples)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Live Home Network Bufferbloat & Latency Localization")
    parser.add_argument("--idle", type=float, default=8.0, help="Duration of idle baseline phase in seconds")
    parser.add_argument("--load", type=float, default=15.0, help="Duration of saturation load phase in seconds")
    parser.add_argument("--recovery", type=float, default=7.0, help="Duration of recovery phase in seconds")
    parser.add_argument("--gateway", type=str, default=None, help="Gateway IPv4 address (default: auto-detected)")
    parser.add_argument("--remote", type=str, default="1.1.1.1", help="Remote WAN IP target (default: 1.1.1.1)")
    parser.add_argument("--streams", type=int, default=4, help="Number of concurrent load streams (default: 4)")
    parser.add_argument("--position", type=str, default="L1", help="Measurement position label (e.g. L1, L2)")
    parser.add_argument("--output", type=Path, default=Path("data/raw/live_home_runs"), help="Output directory")

    args = parser.parse_args()
    return run_live_home_test(
        idle_s=args.idle,
        load_s=args.load,
        recovery_s=args.recovery,
        gateway_ip=args.gateway,
        remote_ip=args.remote,
        output_dir=args.output,
        streams=args.streams,
        position=args.position,
    )


if __name__ == "__main__":
    sys.exit(main())
