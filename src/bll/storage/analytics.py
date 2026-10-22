"""
DuckDB Telemetry Analytics over Columnar Parquet Runs.
src/bll/storage/analytics.py
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import duckdb

logger = logging.getLogger("bll.storage.analytics")


class DuckDBAnalytics:
    """High-performance SQL analytics engine querying runs/<run_id>/samples/*.parquet."""

    def __init__(self, run_dir: Path | str) -> None:
        self.run_dir = Path(run_dir)
        self.samples_dir = self.run_dir / "samples"
        self.conn = duckdb.connect(":memory:")

    def get_rtt_summary_by_phase(self) -> Dict[str, Dict[str, Any]]:
        """Calculates RTT distribution and packet loss rate per phase from ping.parquet."""
        ping_parquet = self.samples_dir / "ping.parquet"
        if not ping_parquet.exists():
            return {}

        query = f"""
        SELECT
            phase,
            count(*) as total_probes,
            sum(case when lost then 1 else 0 end) as dropped_probes,
            round(100.0 * sum(case when lost then 1 else 0 end) / count(*), 2) as loss_pct,
            min(rtt_ms) as min_rtt_ms,
            round(avg(rtt_ms), 3) as mean_rtt_ms,
            round(median(rtt_ms), 3) as median_rtt_ms,
            round(quantile_cont(rtt_ms, 0.95), 3) as p95_rtt_ms,
            round(max(rtt_ms), 3) as max_rtt_ms
        FROM read_parquet('{ping_parquet.as_posix()}')
        GROUP BY phase
        """
        rows = self.conn.execute(query).fetchall()
        summary = {}
        for row in rows:
            phase = row[0]
            stats = {
                "total_probes": row[1],
                "dropped_probes": row[2],
                "loss_pct": row[3],
                "min_rtt_ms": row[4],
                "mean_rtt_ms": row[5],
                "median_rtt_ms": row[6],
                "p95_rtt_ms": row[7],
                "max_rtt_ms": row[8],
            }
            summary[phase] = stats
            if phase == "idle":
                summary["baseline_idle"] = stats
            elif phase == "baseline_idle":
                summary["idle"] = stats
            elif phase == "load":
                summary["saturation_load"] = stats
            elif phase == "saturation_load":
                summary["load"] = stats
        return summary

    def get_bufferbloat_delta(self) -> float:
        """Calculates latency inflation: Delta RTT = p95_load - median_idle."""
        summary = self.get_rtt_summary_by_phase()
        idle = summary.get("baseline_idle") or summary.get("idle", {})
        load = summary.get("saturation_load") or summary.get("load", {})

        idle_median = idle.get("median_rtt_ms") or 25.0
        load_p95 = load.get("p95_rtt_ms") or idle_median

        return max(0.0, float(load_p95 - idle_median))

    def get_throughput_summary(self) -> Dict[str, Any]:
        """Calculates average throughput and retransmissions during saturation load."""
        iperf_parquet = self.samples_dir / "iperf3.parquet"
        if not iperf_parquet.exists():
            return {"mean_mbps": 0.0, "max_mbps": 0.0, "total_retransmits": 0}

        query = f"""
        SELECT
            round(avg(throughput_bps) / 1e6, 2) as mean_mbps,
            round(max(throughput_bps) / 1e6, 2) as max_mbps,
            sum(coalesce(retransmits, 0)) as total_retransmits
        FROM read_parquet('{iperf_parquet.as_posix()}')
        WHERE phase in ('saturation_load', 'load')
        """
        row = self.conn.execute(query).fetchone()
        if not row or row[0] is None:
            return {"mean_mbps": 0.0, "max_mbps": 0.0, "total_retransmits": 0}

        return {
            "mean_mbps": float(row[0]),
            "max_mbps": float(row[1]),
            "total_retransmits": int(row[2]),
        }
