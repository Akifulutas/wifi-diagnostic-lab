"""
Idempotent Lab Lifecycle and Fault-Tolerant Cleanup State Machine.
src/bll/lab/cleanup.py
"""

from __future__ import annotations

import logging
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Set

logger = logging.getLogger("bll.lab.cleanup")


class LabCleanupManager:
    """Manages leak-free teardown of network namespaces, interfaces, and child processes."""

    NS_PREFIX = "bll-"
    IFACE_PREFIX_REGEX = re.compile(r"^(bll-[a-z0-9_-]{1,11}|veth-bll-[a-z0-9_-]{1,7})$")

    @classmethod
    def discover_bll_namespaces(cls) -> List[str]:
        """Discovers all active network namespaces matching the 'bll-' prefix."""
        # Method 1: Check /var/run/netns directory
        netns_dir = Path("/var/run/netns")
        found = set()
        if netns_dir.exists():
            try:
                for entry in netns_dir.iterdir():
                    if entry.name.startswith(cls.NS_PREFIX):
                        found.add(entry.name)
            except Exception:
                pass

        # Method 2: Check ip netns list
        try:
            res = subprocess.run(["ip", "netns", "list"], capture_output=True, text=True, timeout=2.0)
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    name = line.split()[0] if line.split() else ""
                    if name.startswith(cls.NS_PREFIX):
                        found.add(name)
        except Exception:
            pass

        return sorted(list(found))

    @classmethod
    def find_pids_in_namespace(cls, netns_name: str) -> List[int]:
        """Discovers process IDs running inside the specified network namespace."""
        pids = set()

        # Method 1: ip netns pids <netns>
        try:
            res = subprocess.run(["ip", "netns", "pids", netns_name], capture_output=True, text=True, timeout=1.0)
            if res.returncode == 0:
                for p in res.stdout.split():
                    if p.strip().isdigit():
                        pids.add(int(p.strip()))
                if pids:
                    return sorted(list(pids))
        except Exception:
            pass

        # Method 2: Fallback scan /proc/*/ns/net
        ns_path = Path(f"/var/run/netns/{netns_name}")
        if ns_path.exists():
            try:
                target_stat = ns_path.stat()
                for proc_dir in Path("/proc").glob("[0-9]*"):
                    try:
                        net_link = proc_dir / "ns" / "net"
                        if net_link.exists() and net_link.stat().st_ino == target_stat.st_ino:
                            pids.add(int(proc_dir.name))
                    except (OSError, ValueError):
                        continue
            except Exception:
                pass

        return sorted(list(pids))

    @classmethod
    def terminate_processes(cls, pids: List[int], grace_seconds: float = 0.5) -> List[int]:
        """Sends SIGTERM, waits grace period, and escalates to SIGKILL if processes remain."""
        if not pids:
            return []

        killed = []
        survivors = []

        # Phase 1: SIGTERM
        for pid in pids:
            try:
                os.kill(pid, signal.SIGTERM)
                survivors.append(pid)
            except ProcessLookupError:
                killed.append(pid)
            except PermissionError as exc:
                logger.warning(f"Permission denied sending SIGTERM to PID {pid}: {exc}")

        # Grace period wait
        if survivors:
            time.sleep(grace_seconds)

        # Phase 2: SIGKILL for survivors
        for pid in survivors:
            try:
                os.kill(pid, signal.SIGKILL)
                killed.append(pid)
            except ProcessLookupError:
                killed.append(pid)
            except PermissionError as exc:
                logger.error(f"Permission denied sending SIGKILL to PID {pid}: {exc}")

        return killed

    @classmethod
    def delete_namespace(cls, netns_name: str) -> bool:
        """Deletes a network namespace via ip netns del."""
        try:
            res = subprocess.run(["ip", "netns", "del", netns_name], capture_output=True, text=True, timeout=2.0)
            return res.returncode == 0
        except Exception as exc:
            logger.error(f"Failed deleting netns {netns_name}: {exc}")
            return False

    @classmethod
    def sweep_residual_host_links(cls) -> List[str]:
        """Sweeps residual veth interfaces matching the bll- prefix from host namespace."""
        deleted_links = []
        try:
            res = subprocess.run(["ip", "-o", "link", "show"], capture_output=True, text=True, timeout=2.0)
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    parts = line.split(":")
                    if len(parts) >= 2:
                        iface = parts[1].strip().split("@")[0]
                        if cls.IFACE_PREFIX_REGEX.match(iface):
                            del_res = subprocess.run(["ip", "link", "del", iface], capture_output=True, timeout=1.0)
                            if del_res.returncode == 0:
                                deleted_links.append(iface)
        except Exception:
            pass
        return deleted_links

    @classmethod
    def cleanup(cls, force: bool = False) -> Dict[str, Any]:
        """Executes full 6-step idempotent teardown algorithm."""
        deleted_ns = []
        killed_pids = []

        # Step 1 & 2: Discover & terminate processes in bll-* namespaces
        namespaces = cls.discover_bll_namespaces()
        for ns in namespaces:
            pids = cls.find_pids_in_namespace(ns)
            if pids:
                killed = cls.terminate_processes(pids)
                killed_pids.extend(killed)

        # Step 3: Delete namespaces
        for ns in namespaces:
            if cls.delete_namespace(ns):
                deleted_ns.append(ns)

        # Step 4: Sweep residual host links
        deleted_links = cls.sweep_residual_host_links()

        # Step 5: Clean ephemeral locks and temporary state files
        for ephem in Path("/tmp").glob("bll*"):
            try:
                if ephem.is_file() or ephem.is_symlink():
                    ephem.unlink(missing_ok=True)
            except Exception:
                pass

        # Also purge backend state file if present
        mock_state = Path("/tmp/bll_mock_simulation_state.json")
        try:
            mock_state.unlink(missing_ok=True)
        except Exception:
            pass

        return {
            "status": "cleaned",
            "deleted_namespaces": deleted_ns,
            "deleted_interfaces": deleted_links,
            "killed_processes": killed_pids,
        }


def emergency_cleanup() -> None:
    """Safe emergency cleanup routine invoked by signal handlers and atexit."""
    try:
        from bll.platform.backends import get_backend
        backend = get_backend()
        backend.teardown_topology()
    except Exception as exc:
        sys.stderr.write(f"Emergency cleanup notice: {exc}\n")
