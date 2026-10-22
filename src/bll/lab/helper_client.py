"""
Helper Client library for BLL experiment controller.
src/bll/lab/helper_client.py
"""

from __future__ import annotations

import abc
import asyncio
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import uuid
from typing import Any, Dict, List, Optional, Tuple


class HelperRPCError(RuntimeError):
    """Raised when the privileged helper returns a JSON-RPC error."""

    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(f"Helper RPC Error [{code}]: {message}")
        self.code = code
        self.message = message
        self.data = data


class HelperTransport(abc.ABC):
    """Abstract communication transport for HelperClient."""

    @abc.abstractmethod
    def send_rpc(self, method: str, params: dict[str, Any], timeout: float = 30.0) -> dict[str, Any]:
        ...

    @abc.abstractmethod
    async def asend_rpc(self, method: str, params: dict[str, Any], timeout: float = 30.0) -> dict[str, Any]:
        ...

    @abc.abstractmethod
    def close(self) -> None:
        ...


class MockTransport(HelperTransport):
    """In-memory simulation transport for macOS and unprivileged environments."""

    def __init__(self):
        from bll.helper.server import HelperServer
        from bll.platform.backends import get_backend
        self._server = HelperServer(backend_runner=get_backend("mock_simulation"))

    def send_rpc(self, method: str, params: dict[str, Any], timeout: float = 30.0) -> dict[str, Any]:
        req = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": method,
            "params": params,
        }
        resp = self._server.dispatch(req)
        if "error" in resp:
            err = resp["error"]
            raise HelperRPCError(err["code"], err["message"], err.get("data"))
        return resp.get("result", {})

    async def asend_rpc(self, method: str, params: dict[str, Any], timeout: float = 30.0) -> dict[str, Any]:
        return self.send_rpc(method, params, timeout)

    def close(self) -> None:
        pass


class SubprocessTransport(HelperTransport):
    """Subprocess transport communicating with 'bll-lab-helper --stdio' via stdin/stdout pipe."""

    def __init__(self, helper_path: Optional[str] = None):
        bin_path = helper_path or shutil.which("bll-lab-helper")
        if bin_path:
            cmd = [bin_path, "--stdio"]
        else:
            cmd = [sys.executable, "-m", "bll.helper.server", "--stdio"]

        if os.getuid() != 0 and shutil.which("sudo"):
            self.helper_cmd = ["sudo", "-n"] + cmd
        else:
            self.helper_cmd = cmd
        self._proc: Optional[subprocess.Popen] = None

    def _ensure_proc(self) -> subprocess.Popen:
        if self._proc is None or self._proc.poll() is not None:
            self._proc = subprocess.Popen(
                self.helper_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        return self._proc

    def send_rpc(self, method: str, params: dict[str, Any], timeout: float = 30.0) -> dict[str, Any]:
        proc = self._ensure_proc()
        req_id = str(uuid.uuid4())
        req = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
        assert proc.stdin is not None
        assert proc.stdout is not None
        try:
            proc.stdin.write(json.dumps(req) + "\n")
            proc.stdin.flush()
            line = proc.stdout.readline()
        except Exception as exc:
            stderr = proc.stderr.read() if proc.stderr else ""
            raise RuntimeError(f"Helper process communication failed: {exc} ({stderr})") from exc

        if not line:
            stderr = proc.stderr.read() if proc.stderr else ""
            raise RuntimeError(f"Helper process terminated unexpectedly: {stderr}")

        resp = json.loads(line)
        if "error" in resp:
            err = resp["error"]
            raise HelperRPCError(err["code"], err["message"], err.get("data"))
        return resp.get("result", {})

    async def asend_rpc(self, method: str, params: dict[str, Any], timeout: float = 30.0) -> dict[str, Any]:
        return await asyncio.to_thread(self.send_rpc, method, params, timeout)

    def close(self) -> None:
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=1.0)
            except Exception:
                self._proc.kill()
        self._proc = None


class UnixSocketTransport(HelperTransport):
    """UNIX Domain Socket transport communicating with 'bll-lab-helper --socket PATH'."""

    def __init__(self, socket_path: str = "/var/run/bll-helper.sock"):
        self.socket_path = socket_path

    def send_rpc(self, method: str, params: dict[str, Any], timeout: float = 30.0) -> dict[str, Any]:
        req_id = str(uuid.uuid4())
        req = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            sock.connect(self.socket_path)
            sock.sendall((json.dumps(req) + "\n").encode("utf-8"))
            data = b""
            while b"\n" not in data:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk
            if not data:
                raise RuntimeError("Helper daemon closed connection without response")
            resp = json.loads(data.decode("utf-8").strip())
            if "error" in resp:
                err = resp["error"]
                raise HelperRPCError(err["code"], err["message"], err.get("data"))
            return resp.get("result", {})
        finally:
            sock.close()

    async def asend_rpc(self, method: str, params: dict[str, Any], timeout: float = 30.0) -> dict[str, Any]:
        return await asyncio.to_thread(self.send_rpc, method, params, timeout)

    def close(self) -> None:
        pass


def get_default_transport(backend: Optional[str] = None) -> HelperTransport:
    """Factory determining the appropriate transport for current host environment."""
    if backend == "mock_simulation" or platform.system() == "Darwin":
        return MockTransport()

    socket_path = "/var/run/bll-helper.sock"
    if os.path.exists(socket_path) and os.access(socket_path, os.R_OK | os.W_OK):
        return UnixSocketTransport(socket_path)

    return SubprocessTransport()


class HelperClient:
    """Public high-level client for interacting with bll-lab-helper."""

    def __init__(self, transport: Optional[HelperTransport] = None, backend: Optional[str] = None):
        self._transport = transport or get_default_transport(backend=backend)

    def create_topology(self, subnets: Optional[dict[str, str]] = None, topology_name: str = "bll-default") -> dict[str, Any]:
        return self._transport.send_rpc("create_topology", {"subnets": subnets or {}, "topology_name": topology_name})

    async def acreate_topology(self, subnets: Optional[dict[str, str]] = None, topology_name: str = "bll-default") -> dict[str, Any]:
        return await self._transport.asend_rpc("create_topology", {"subnets": subnets or {}, "topology_name": topology_name})

    def destroy_topology(self, force: bool = True) -> dict[str, Any]:
        return self._transport.send_rpc("destroy_topology", {"force": force})

    async def adestroy_topology(self, force: bool = True) -> dict[str, Any]:
        return await self._transport.asend_rpc("destroy_topology", {"force": force})

    def configure_qdisc(
        self,
        netns: str,
        interface: str,
        rate: Optional[str] = None,
        qdisc: Optional[str] = None,
        limit: Optional[str | int] = None,
        delay: Optional[str] = None,
        loss: Optional[str] = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"netns": netns, "interface": interface}
        if rate is not None:
            params["rate"] = rate
        if qdisc is not None:
            params["qdisc"] = qdisc
        if limit is not None:
            params["limit"] = limit
        if delay is not None:
            params["delay"] = delay
        if loss is not None:
            params["loss"] = loss
        return self._transport.send_rpc("configure_qdisc", params)

    async def aconfigure_qdisc(
        self,
        netns: str,
        interface: str,
        rate: Optional[str] = None,
        qdisc: Optional[str] = None,
        limit: Optional[str | int] = None,
        delay: Optional[str] = None,
        loss: Optional[str] = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"netns": netns, "interface": interface}
        if rate is not None:
            params["rate"] = rate
        if qdisc is not None:
            params["qdisc"] = qdisc
        if limit is not None:
            params["limit"] = limit
        if delay is not None:
            params["delay"] = delay
        if loss is not None:
            params["loss"] = loss
        return await self._transport.asend_rpc("configure_qdisc", params)

    def reset_qdiscs(self) -> dict[str, Any]:
        return self._transport.send_rpc("reset_qdiscs", {})

    async def areset_qdiscs(self) -> dict[str, Any]:
        return await self._transport.asend_rpc("reset_qdiscs", {})

    def verify_topology(self) -> dict[str, Any]:
        return self._transport.send_rpc("verify_topology", {})

    async def averify_topology(self) -> dict[str, Any]:
        return await self._transport.asend_rpc("verify_topology", {})

    def exec_tool(self, netns: str, command: list[str], timeout: float = 30.0) -> tuple[int, str, str]:
        res = self._transport.send_rpc("exec_tool", {"netns": netns, "command": command, "timeout_seconds": timeout})
        return res["exit_code"], res["stdout"], res["stderr"]

    async def aexec_tool(self, netns: str, command: list[str], timeout: float = 30.0) -> tuple[int, str, str]:
        res = await self._transport.asend_rpc("exec_tool", {"netns": netns, "command": command, "timeout_seconds": timeout})
        return res["exit_code"], res["stdout"], res["stderr"]

    def status(self) -> dict[str, Any]:
        return self._transport.send_rpc("status", {})

    async def astatus(self) -> dict[str, Any]:
        return await self._transport.asend_rpc("status", {})

    def close(self) -> None:
        self._transport.close()
