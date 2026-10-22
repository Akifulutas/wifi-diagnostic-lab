"""
Platform discovery, capability probe, and execution backends for BLL.
"""

from bll.platform.doctor import BLLDoctorReport, SystemCapability, run_doctor
from bll.platform.backends import (
    LabBackend,
    NativeLinuxBackend,
    ContainerLinuxBackend,
    MockSimulationBackend,
    QdiscConfig,
    get_backend,
)

__all__ = [
    "BLLDoctorReport",
    "SystemCapability",
    "run_doctor",
    "LabBackend",
    "NativeLinuxBackend",
    "ContainerLinuxBackend",
    "MockSimulationBackend",
    "QdiscConfig",
    "get_backend",
]
