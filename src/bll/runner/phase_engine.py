"""
Runner Bridge for Phase Engine CLI Execution.
src/bll/runner/phase_engine.py
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from bll.measurements.engine import MeasurementEngine, PhaseDurations
from bll.platform.backends import get_backend


def execute_run(
    scenario: str = "healthy_baseline",
    total_duration_s: int = 110,
    direction: str = "upload",
    runs_dir: Path | str = "runs",
    ground_truth_dir: Path | str = "ground_truth",
    idle_s: Optional[float] = None,
    load_s: Optional[float] = None,
    recovery_s: Optional[float] = None,
    backend_name: Optional[str] = None,
) -> str:
    """Executes a 3-phase run and returns the run_id."""
    if idle_s is not None and load_s is not None and recovery_s is not None:
        durations = PhaseDurations(idle_s=idle_s, load_s=load_s, recovery_s=recovery_s)
    else:
        # Scale 110s proportionally if total_duration_s is provided
        scale = max(0.01, total_duration_s / 110.0)
        durations = PhaseDurations(
            idle_s=20.0 * scale,
            load_s=60.0 * scale,
            recovery_s=30.0 * scale,
        )

    backend = get_backend(backend_name)
    engine = MeasurementEngine(
        backend=backend,
        durations=durations,
        direction=direction,
        runs_dir=runs_dir,
        ground_truth_dir=ground_truth_dir,
    )
    run_id, _ = engine.run_experiment(scenario_name=scenario)
    return run_id
