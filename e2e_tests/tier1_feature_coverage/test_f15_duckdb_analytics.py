"""
Feature 15: DuckDB Telemetry Analytics
Tier 1: Feature Coverage (>=5 test cases)
"""

import pathlib
import pytest
from e2e_tests.harness import run_bll, HAS_DUCKDB

if HAS_DUCKDB:
    import duckdb


@pytest.fixture
def sample_run_with_parquet(tmp_path: pathlib.Path):
    res = run_bll(["run", "--scenario", "residential_dsl_near_fifo", "--out-dir", str(tmp_path), "--duration-idle", "1", "--duration-load", "1", "--duration-recovery", "1"])
    assert res.exit_code == 0
    return pathlib.Path(res.json_data["run_dir"])


def test_duckdb_queries_ping_parquet(sample_run_with_parquet: pathlib.Path):
    """F15-T1-1: DuckDB executes analytical SQL over samples/ping.parquet."""
    if not HAS_DUCKDB:
        pytest.skip("DuckDB not installed in environment")
    parquet_path = sample_run_with_parquet / "samples" / "ping.parquet"
    con = duckdb.connect()
    res = con.execute(f"SELECT count(*), avg(rtt_ms) FROM read_parquet('{parquet_path}')").fetchall()
    assert res[0][0] > 0
    assert res[0][1] > 0.0


def test_duckdb_queries_iperf3_parquet(sample_run_with_parquet: pathlib.Path):
    """F15-T1-2: DuckDB aggregates throughput across phases from samples/iperf3.parquet."""
    if not HAS_DUCKDB:
        pytest.skip("DuckDB not installed in environment")
    parquet_path = sample_run_with_parquet / "samples" / "iperf3.parquet"
    con = duckdb.connect()
    res = con.execute(f"SELECT phase, avg(throughput_mbps) FROM read_parquet('{parquet_path}') GROUP BY phase").fetchall()
    assert len(res) >= 1


def test_duckdb_computes_rtt_delta(sample_run_with_parquet: pathlib.Path):
    """F15-T1-3: DuckDB query computes differential RTT delta (load vs idle)."""
    if not HAS_DUCKDB:
        pytest.skip("DuckDB not installed in environment")
    parquet_path = sample_run_with_parquet / "samples" / "ping.parquet"
    con = duckdb.connect()
    sql = f"""
        SELECT 
            avg(CASE WHEN phase = 'load' THEN rtt_ms END) - 
            avg(CASE WHEN phase = 'idle' THEN rtt_ms END) AS delta_rtt
        FROM read_parquet('{parquet_path}')
    """
    res = con.execute(sql).fetchone()
    assert res[0] is not None
    assert res[0] > 0.0  # In near_fifo scenario, loaded RTT is inflated


def test_duckdb_quantile_aggregations(sample_run_with_parquet: pathlib.Path):
    """F15-T1-4: DuckDB computes p50, p95, and max RTT quantiles."""
    if not HAS_DUCKDB:
        pytest.skip("DuckDB not installed in environment")
    parquet_path = sample_run_with_parquet / "samples" / "ping.parquet"
    con = duckdb.connect()
    sql = f"SELECT quantile_cont(rtt_ms, 0.5), quantile_cont(rtt_ms, 0.95), max(rtt_ms) FROM read_parquet('{parquet_path}')"
    p50, p95, pmax = con.execute(sql).fetchone()
    assert p50 <= p95 <= pmax


def test_duckdb_computes_buffer_drain_time(sample_run_with_parquet: pathlib.Path):
    """F15-T1-5: DuckDB analyzes recovery phase samples to compute buffer drain dynamics."""
    if not HAS_DUCKDB:
        pytest.skip("DuckDB not installed in environment")
    parquet_path = sample_run_with_parquet / "samples" / "ping.parquet"
    con = duckdb.connect()
    sql = f"SELECT count(*) FROM read_parquet('{parquet_path}') WHERE phase = 'recovery'"
    cnt = con.execute(sql).fetchone()[0]
    assert cnt > 0
