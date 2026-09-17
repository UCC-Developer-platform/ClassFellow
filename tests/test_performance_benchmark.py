"""
ClassFellow - Performance Profiling & Query Benchmarking Tests
==============================================================
Validates that synthetic load generation, WAL mode checkpointing, database
integrity checks, and core query latencies remain strictly within SLA thresholds
(< 100ms) under automated CI/CD runs to prevent query regressions.
"""

import os
import sqlite3
import pytest
from decimal import Decimal

from database import get_connection
from services.schema_service import migrate_to_latest
from scripts.benchmark_db import (
    generate_synthetic_data,
    run_query_benchmarks,
    verify_database_integrity,
    print_benchmark_report,
    MAX_SLA_LATENCY_MS,
)


@pytest.fixture
def perf_db(tmp_path):
    """Provides a temporary, isolated SQLite database file with latest migrations applied."""
    db_file = str(tmp_path / "ci_perf_benchmark.db")
    conn = get_connection(db_file)
    migrate_to_latest(conn)
    yield conn, db_file
    conn.close()


def test_ci_scoped_synthetic_data_and_benchmarks(perf_db):
    """
    Executes a fast, scoped load test (500 students, 5,000 invoices, 10,000 attendance records)
    and verifies that all core query latencies remain under 100ms.
    """
    conn, db_path = perf_db

    # 1. Populate scoped dataset
    meta = generate_synthetic_data(
        conn=conn,
        student_count=500,
        class_count=10,
        invoices_count=5000,
        attendance_count=10000,
        verbose=False
    )
    assert meta["session_id"] is not None
    assert len(meta["class_group_ids"]) == 10

    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM students;")
    assert cursor.fetchone()[0] == 500

    cursor.execute("SELECT COUNT(*) FROM fee_invoices;")
    assert cursor.fetchone()[0] == 5000

    cursor.execute("SELECT COUNT(*) FROM attendance_records;")
    assert cursor.fetchone()[0] == 10000

    # 2. Run query benchmarks
    results = run_query_benchmarks(
        conn=conn,
        session_id=meta["session_id"],
        class_group_id=meta["class_group_ids"][0],
        iterations=2
    )
    assert len(results) == 4

    for r in results:
        # Assert each operation passed and latency is below 100ms SLA
        assert r["passed"] is True, f"Benchmark failed: {r['name']} took {r['mean_ms']}ms (SLA: {r['sla_ms']}ms)"
        assert r["mean_ms"] < MAX_SLA_LATENCY_MS
        assert r["min_ms"] < MAX_SLA_LATENCY_MS


def test_wal_checkpoint_and_integrity_verification(perf_db):
    """Verifies that PRAGMA integrity_check and PRAGMA wal_checkpoint operate cleanly."""
    conn, db_path = perf_db

    # Insert a minimal session
    conn.execute("INSERT INTO academic_sessions (name, start_date, end_date) VALUES ('2026-2027', '2026-04-01', '2027-03-31');")
    conn.commit()

    integrity = verify_database_integrity(conn)
    assert integrity["integrity_ok"] is True
    assert integrity["integrity_message"] == "ok"
    assert integrity["checkpoint_ok"] is True
    assert len(integrity["checkpoint_stats"]) == 3
    assert integrity["checkpoint_stats"][0] == 0  # Not busy


def test_benchmark_report_formatter(capsys, perf_db):
    """Verifies that ASCII report generator executes and outputs formatted table."""
    conn, db_path = perf_db

    dummy_counts = {"students": 500, "invoices": 5000, "attendance": 10000}
    dummy_results = [
        {
            "name": "Defaulter Ledger Scan",
            "volume": "300 defaulters",
            "mean_ms": 15.2,
            "min_ms": 14.1,
            "sla_ms": 100.0,
            "passed": True
        }
    ]
    dummy_integrity = {
        "integrity_ok": True,
        "integrity_message": "ok",
        "checkpoint_ok": True,
        "checkpoint_stats": (0, 10, 10)
    }

    print_benchmark_report(db_path, dummy_counts, dummy_results, dummy_integrity)
    captured = capsys.readouterr()

    assert "ClassFellow - Enterprise Relational Query Benchmark" in captured.out
    assert "Defaulter Ledger Scan" in captured.out
    assert "100% SLA COMPLIANCE" in captured.out
