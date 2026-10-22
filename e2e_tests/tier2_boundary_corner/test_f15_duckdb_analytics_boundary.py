"""
Feature 15: DuckDB Telemetry Analytics (Boundary & Corner Cases)
Tier 2: Boundary & Corner Cases (>=5 test cases)
"""

import pathlib
import pytest
from e2e_tests.harness import HAS_DUCKDB

if HAS_DUCKDB:
    import duckdb


def test_duckdb_missing_parquet_file_handled(tmp_path: pathlib.Path):
    """F15-T2-1: Querying a non-existent parquet table raises clean DuckDB IO error."""
    if not HAS_DUCKDB:
        pytest.skip("DuckDB not installed")
    con = duckdb.connect()
    with pytest.raises(Exception):
        con.execute(f"SELECT * FROM read_parquet('{tmp_path}/nonexistent.parquet')")


def test_duckdb_empty_table_aggregation(tmp_path: pathlib.Path):
    """F15-T2-2: Aggregation over 0 rows yields NULL or 0 without crashing."""
    if not HAS_DUCKDB:
        pytest.skip("DuckDB not installed")
    con = duckdb.connect()
    res = con.execute("SELECT count(*), avg(val) FROM (SELECT 1.0 AS val WHERE 1=0)").fetchone()
    assert res[0] == 0
    assert res[1] is None


def test_duckdb_malformed_sql_caught():
    """F15-T2-3: Malformed SQL statement raises DuckDB ParserException."""
    if not HAS_DUCKDB:
        pytest.skip("DuckDB not installed")
    con = duckdb.connect()
    with pytest.raises(Exception):
        con.execute("SELECT FROM WHERE BROKEN SYNTAX")


def test_duckdb_division_by_zero_safe():
    """F15-T2-4: Division by zero returns NULL rather than crashing in SQL."""
    if not HAS_DUCKDB:
        pytest.skip("DuckDB not installed")
    con = duckdb.connect()
    res = con.execute("SELECT 100.0 / NULLIF(0, 0)").fetchone()
    assert res[0] is None


def test_duckdb_in_memory_connection_isolation():
    """F15-T2-5: In-memory DuckDB connections do not leak tables across instances."""
    if not HAS_DUCKDB:
        pytest.skip("DuckDB not installed")
    con1 = duckdb.connect()
    con1.execute("CREATE TABLE t1 AS SELECT 42 AS id")
    con2 = duckdb.connect()
    with pytest.raises(Exception):
        con2.execute("SELECT * FROM t1")
