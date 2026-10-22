"""
Security validation, resource gating, and privilege dropping for bll-lab-helper.
src/bll/helper/security.py
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any, Iterable

# Linux kernel IFNAMSIZ is 16 bytes (15 chars + null byte)
MAX_IFACE_LEN = 15
MAX_NETNS_LEN = 20

NETNS_REGEX = re.compile(r"^bll-[a-z0-9_-]{1,16}$")
IFACE_REGEX = re.compile(r"^bll-[a-z0-9_-]{1,11}$")

FORBIDDEN_SHELL_CHARS = set(";`&|$()<>\n\r\0*?[]{}~!#\"'\\")

TRUSTED_BINARY_DIRS = {
    "/bin",
    "/sbin",
    "/usr/bin",
    "/usr/sbin",
    "/usr/local/bin",
    "/opt/homebrew/bin",
}

WHITELISTED_TOOL_NAMES = {
    "ping": ["/bin/ping", "/sbin/ping", "/usr/bin/ping"],
    "iperf3": ["/usr/bin/iperf3", "/usr/local/bin/iperf3", "/bin/iperf3", "/opt/homebrew/bin/iperf3"],
    "irtt": ["/usr/bin/irtt", "/usr/local/bin/irtt", "/bin/irtt", "/opt/homebrew/bin/irtt"],
    "tc": ["/sbin/tc", "/usr/sbin/tc", "/bin/tc", "/usr/bin/tc"],
    "ip": ["/sbin/ip", "/usr/sbin/ip", "/bin/ip", "/usr/bin/ip"],
    "tcpdump": ["/usr/sbin/tcpdump", "/usr/bin/tcpdump"],
}


class SecurityValidationError(ValueError):
    """Raised when an RPC parameter or CLI input violates security policy."""
    pass


def validate_no_shell_metachars(*values: Any) -> None:
    """Ensures none of the passed values contain shell injection or control metacharacters."""
    for val in values:
        if val is None:
            continue
        val_str = str(val)
        for ch in val_str:
            if ch in FORBIDDEN_SHELL_CHARS:
                raise SecurityValidationError(
                    f"Security Policy: Shell metacharacter '{ch}' rejected in parameter '{val_str}'"
                )


def validate_resource_name(name: str, kind: str = "namespace") -> str:
    """Validates that a resource name strictly starts with 'bll-', contains no traversal,

    has no shell metacharacters, and adheres to length limits (IFNAMSIZ for interfaces).
    """
    if not isinstance(name, str):
        raise SecurityValidationError(f"Invalid {kind} name: must be string, got {type(name).__name__}")

    name = name.strip()
    if not name:
        raise SecurityValidationError(f"Invalid {kind} name: cannot be empty")

    if "/" in name or "\\" in name or ".." in name:
        raise SecurityValidationError(f"Security Policy: Path traversal characters forbidden in {kind} name: '{name}'")

    validate_no_shell_metachars(name)

    if not name.startswith("bll-"):
        raise SecurityValidationError(f"Security Policy: Resource '{name}' must start with 'bll-' prefix")

    if kind == "interface":
        if len(name) > MAX_IFACE_LEN:
            raise SecurityValidationError(
                f"Interface name '{name}' ({len(name)} chars) exceeds Linux IFNAMSIZ limit of {MAX_IFACE_LEN}"
            )
        if not IFACE_REGEX.match(name):
            raise SecurityValidationError(f"Invalid interface name '{name}': does not match {IFACE_REGEX.pattern}")
    else:
        if len(name) > MAX_NETNS_LEN:
            raise SecurityValidationError(
                f"Namespace name '{name}' ({len(name)} chars) exceeds limit of {MAX_NETNS_LEN}"
            )
        if not NETNS_REGEX.match(name):
            raise SecurityValidationError(f"Invalid namespace name '{name}': does not match {NETNS_REGEX.pattern}")

    return name


def validate_tool_command(command: list[str]) -> list[str]:
    """Validates that the requested binary is in the strict tool whitelist and arguments are safe."""
    if not command or not isinstance(command, list):
        raise SecurityValidationError("Command must be a non-empty list of strings")

    validate_no_shell_metachars(*command)

    binary = command[0]
    if not isinstance(binary, str) or not binary.strip():
        raise SecurityValidationError("Binary command name must be a non-empty string")

    # Reject path traversal
    if ".." in binary:
        raise SecurityValidationError(f"Security Policy: Path traversal forbidden in binary '{binary}'")

    bin_name = Path(binary).name
    if bin_name not in WHITELISTED_TOOL_NAMES:
        raise SecurityValidationError(
            f"Security Policy: Executable '{bin_name}' is not in approved tool whitelist: "
            f"{sorted(list(WHITELISTED_TOOL_NAMES.keys()))}"
        )

    # If binary path contains directory separators, enforce strict absolute system directory validation
    if "/" in binary or "\\" in binary:
        if not binary.startswith("/"):
            raise SecurityValidationError(
                f"Security Policy: Relative binary path '{binary}' forbidden. Use bare tool name or canonical absolute path."
            )
        bin_dir = str(Path(binary).parent)
        if bin_dir.startswith("/tmp") or bin_dir.startswith("/var/tmp") or bin_dir not in TRUSTED_BINARY_DIRS:
            raise SecurityValidationError(
                f"Security Policy: Binary path '{binary}' outside trusted system binary directories: {sorted(list(TRUSTED_BINARY_DIRS))}"
            )
        resolved = binary
    else:
        # Bare binary name: resolve via system PATH ensuring it stays within trusted dirs
        resolved = shutil.which(binary)
        if resolved:
            resolved_dir = str(Path(resolved).parent)
            if resolved_dir not in TRUSTED_BINARY_DIRS:
                resolved = None

        if not resolved:
            # Fallback to candidate list
            for candidate in WHITELISTED_TOOL_NAMES.get(bin_name, []):
                if os.path.exists(candidate) and os.access(candidate, os.X_OK):
                    resolved = candidate
                    break

        if not resolved:
            resolved = WHITELISTED_TOOL_NAMES[bin_name][0]

    return [resolved] + list(command[1:])


def get_target_credentials() -> tuple[int, int]:
    """Resolves target unprivileged UID and GID for measurement tool execution."""
    sudo_uid = os.environ.get("SUDO_UID")
    sudo_gid = os.environ.get("SUDO_GID")
    if sudo_uid is not None and sudo_gid is not None:
        try:
            return int(sudo_uid), int(sudo_gid)
        except ValueError:
            pass

    uid = os.getuid()
    gid = os.getgid()
    if uid != 0:
        return uid, gid

    # If running as root without sudo, drop to nobody
    try:
        import pwd
        nobody = pwd.getpwnam("nobody")
        return nobody.pw_uid, nobody.pw_gid
    except (KeyError, ImportError):
        return 65534, 65534


def drop_privileges(target_uid: int, target_gid: int) -> None:
    """Drops elevated root privileges to target unprivileged user and group."""
    if os.getuid() != 0:
        return

    try:
        os.setgroups([])
        os.setgid(target_gid)
        os.setuid(target_uid)
        if os.geteuid() != target_uid or os.getegid() != target_gid:
            raise PermissionError("Privilege drop verification failed: effective UID/GID do not match target")
    except Exception as exc:
        raise PermissionError(f"Failed to drop privileges: {exc}") from exc
