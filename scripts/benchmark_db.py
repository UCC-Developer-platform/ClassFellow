"""
ClassFellow - Database Performance Profiling & Query Benchmarking Tool
======================================================================
Populates a synthetic load dataset into a target SQLite database and benchmarks
core relational queries against SLA thresholds (< 100ms):
  1. Defaulter Ledger Query (overdue balances scanning after valid_until)
  2. Student Multi-Field Search (name, admission number, guardian phone)
  3. Attendance Class Roster Loading (joined with recorded statuses)
  4. Monthly Fee Invoice Batch Generation (bulk creation for class group)

Also validates SQLite PRAGMA integrity_check and WAL passive checkpointing.
"""

import os
import sys
import time
import re
import argparse
import sqlite3
from decimal import Decimal
from typing import Dict, Any, List, Tuple, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from database import get_connection, transaction
from services.schema_service import migrate_to_latest
from services.student_service import StudentService
from services.fee_service import FeeService
from services.attendance_service import AttendanceService

DEFAULT_BENCHMARK_DB = os.path.join(PROJECT_ROOT, "data", "benchmark_test.db")
MAX_SLA_LATENCY_MS = 100.0


# =============================================================================
# 1. Synthetic Load Generation
# =============================================================================

def generate_synthetic_data(
    conn: sqlite3.Connection,
    student_count: int = 5000,
    class_count: int = 20,
    invoices_count: int = 50000,
    attendance_count: int = 100000,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Populates the database with large synthetic volume using chunked executemany
    batches inside dedicated transactions.

    Args:
        conn: SQLite connection with migrations already applied.
        student_count: Number of students to create (default: 5,000).
        class_count: Number of class groups (default: 20).
        invoices_count: Number of fee invoices to generate (default: 50,000).
        attendance_count: Number of attendance records (default: 100,000).
        verbose: If True, prints progress milestones.

    Returns:
        Dict containing generated session_id and list of class_group_ids.
    """
    t0 = time.perf_counter()
    cursor = conn.cursor()

    if verbose:
        print(f"[*] Initializing synthetic data generation...")

    # 1. Academic Session
    cursor.execute("SELECT id FROM academic_sessions WHERE name = '2026-2027';")
    row = cursor.fetchone()
    if row:
        session_id = row[0]
    else:
        cursor.execute(
            "INSERT INTO academic_sessions (name, start_date, end_date, is_active) VALUES ('2026-2027', '2026-04-01', '2027-03-31', 1);"
        )
        session_id = cursor.lastrowid

    # 2. Class Groups
    class_group_ids = []
    cursor.execute("SELECT id FROM class_groups WHERE session_id = ?;", (session_id,))
    existing_classes = cursor.fetchall()
    if len(existing_classes) >= class_count:
        class_group_ids = [r[0] for r in existing_classes[:class_count]]
    else:
        sections = ["Section A", "Section B", "Section C", "Section D"]
        classes_data = []
        for i in range(class_count):
            cls_num = (i // 2) + 1
            sec = sections[i % len(sections)]
            fee = Decimal("4000.00") + Decimal(str((cls_num * 150)))
            classes_data.append((session_id, f"Class {cls_num}", sec, "SchoolClass", str(fee)))

        with transaction(conn):
            cursor.executemany(
                """
                INSERT OR IGNORE INTO class_groups (session_id, name, section_or_batch, group_type, monthly_tuition_fee)
                VALUES (?, ?, ?, ?, ?);
                """,
                classes_data
            )
        cursor.execute("SELECT id FROM class_groups WHERE session_id = ? ORDER BY id ASC;", (session_id,))
        class_group_ids = [r[0] for r in cursor.fetchall()][:class_count]

    # 3. Students & Enrollments
    cursor.execute("SELECT COUNT(*) FROM students;")
    current_student_count = cursor.fetchone()[0]
    needed_students = student_count - current_student_count

    first_names = ["Usman", "Ayesha", "Ali", "Fatima", "Zaid", "Hamza", "Bilal", "Sara", "Zainab", "Omar", "Hassan", "Khadija"]
    last_names = ["Khan", "Tariq", "Malik", "Raza", "Ahmed", "Sheikh", "Bibi", "Siddiqui", "Abbasi", "Mehmood"]
    urdu_names = ["محمد عثمان", "عائشہ بی بی", "علی حسن", "فاطمہ زہرا", "زید خان", "حمزہ عباسی", "بلال احمد", "سارہ ملک"]

    if needed_students > 0:
        if verbose:
            print(f"[*] Inserting {needed_students} student identities and active enrollments...")
        student_records = []
        enrollment_records = []

        start_idx = current_student_count + 1
        for i in range(needed_students):
            num = start_idx + i
            adm_no = f"CF-2026-{num:05d}"
            fn = first_names[i % len(first_names)]
            ln = last_names[(i // len(first_names)) % len(last_names)]
            un = urdu_names[i % len(urdu_names)]
            gender = "Male" if (i % 2 == 0) else "Female"
            dob = f"{2010 + (i % 6):04d}-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}"
            gn = f"{ln} Guardian"
            phone = f"03{num % 1000000000:09d}"

            student_records.append((
                adm_no, fn, ln, un, gender, dob, gn, phone, f"House {num}, Street {(num % 20) + 1}, Lahore", 1
            ))

        with transaction(conn):
            cursor.executemany(
                """
                INSERT OR IGNORE INTO students (
                    admission_number, first_name, last_name, urdu_name, gender,
                    date_of_birth, guardian_name, guardian_phone, residential_address, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                student_records
            )

        # Retrieve student IDs to link enrollments
        cursor.execute("SELECT id FROM students WHERE admission_number >= ? ORDER BY id ASC;", (f"CF-2026-{start_idx:05d}",))
        new_student_ids = [r[0] for r in cursor.fetchall()]

        for idx, sid in enumerate(new_student_ids):
            cg_id = class_group_ids[idx % len(class_group_ids)]
            roll = str((idx % 250) + 1)
            disc = "200.00" if (idx % 10 == 0) else "0.00"
            enrollment_records.append((sid, cg_id, session_id, roll, "2026-04-01", "Active", disc))

        with transaction(conn):
            cursor.executemany(
                """
                INSERT OR IGNORE INTO enrollments (
                    student_id, class_group_id, session_id, roll_number,
                    enrollment_date, status, custom_discount_amount
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                enrollment_records
            )

    # 4. Fee Invoices & Payments Generation
    cursor.execute("SELECT COUNT(*) FROM fee_invoices WHERE session_id = ?;", (session_id,))
    current_invoice_count = cursor.fetchone()[0]
    needed_invoices = invoices_count - current_invoice_count

    if needed_invoices > 0:
        if verbose:
            print(f"[*] Generating {needed_invoices} itemized fee invoices across billing cycles...")

        cursor.execute("SELECT id, custom_discount_amount FROM enrollments WHERE session_id = ? ORDER BY id ASC LIMIT ?;", (session_id, student_count))
        active_enrollments = cursor.fetchall()

        # Generate cycles like 2026-04, 2026-05, etc.
        months = [
            ("2026-04", "2026-04-01", "2026-04-10", "2026-04-20"),
            ("2026-05", "2026-05-01", "2026-05-10", "2026-05-20"),
            ("2026-06", "2026-06-01", "2026-06-10", "2026-06-20"),
            ("2026-07", "2026-07-01", "2026-07-10", "2026-07-20"),
            ("2026-08", "2026-08-01", "2026-08-10", "2026-08-20"),
            ("2026-09", "2026-09-01", "2026-09-10", "2026-09-20"),
            ("2026-10", "2026-10-01", "2026-10-10", "2026-10-20"),
            ("2026-11", "2026-11-01", "2026-11-10", "2026-11-20"),
            ("2026-12", "2026-12-01", "2026-12-10", "2026-12-20"),
            ("2027-01", "2027-01-01", "2027-01-10", "2027-01-20"),
        ]

        invoice_tuples = []
        invoices_per_cycle = max(1, needed_invoices // len(months))

        inv_counter = 0
        for m_idx, (m_yr, iss_d, due_d, val_d) in enumerate(months):
            for enr_row in active_enrollments:
                if inv_counter >= needed_invoices:
                    break
                enr_id = enr_row[0]
                disc = Decimal(str(enr_row[1]))
                tot = Decimal("4500.00")
                net = max(Decimal("0.00"), tot - disc)

                invoice_tuples.append((
                    enr_id, session_id, m_yr, iss_d, due_d, val_d,
                    "200.00", str(tot), str(disc), str(net)
                ))
                inv_counter += 1
            if inv_counter >= needed_invoices:
                break

        # Batch insert fee_invoices
        with transaction(conn):
            cursor.executemany(
                """
                INSERT OR IGNORE INTO fee_invoices (
                    enrollment_id, session_id, month_year, issue_date,
                    due_date, valid_until, late_fee_surcharge, total_payable,
                    discount_amount, net_due
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                invoice_tuples
            )

        # Retrieve created invoice IDs for items and payments
        cursor.execute("SELECT id, net_due FROM fee_invoices WHERE session_id = ? ORDER BY id ASC;", (session_id,))
        all_invoices = cursor.fetchall()

        # Fee Invoice Items (Tuition Fee head id=1)
        cursor.execute("SELECT id FROM fee_heads WHERE name = 'Tuition Fee' LIMIT 1;")
        fh_row = cursor.fetchone()
        tuition_head_id = fh_row[0] if fh_row else 1

        items_tuples = [(inv[0], tuition_head_id, "4500.00") for inv in all_invoices]
        with transaction(conn):
            cursor.executemany(
                "INSERT OR IGNORE INTO fee_invoice_items (invoice_id, fee_head_id, amount) VALUES (?, ?, ?);",
                items_tuples
            )

        # Payment Ledger Rows: 70% paid in full, 15% partial, 15% unpaid
        if verbose:
            print(f"[*] Populating payments ledger for realistic collection status...")
        payments_tuples = []
        pay_counter = 1
        for idx, (inv_id, net_due_str) in enumerate(all_invoices):
            net_due = Decimal(str(net_due_str))
            if idx % 10 < 7:
                # Fully paid
                pay_amt = net_due
            elif idx % 10 < 8:
                # Partially paid
                pay_amt = net_due / Decimal("2.00")
            else:
                # Unpaid defaulter
                continue

            rec_no = f"REC-2026-{pay_counter:07d}"
            payments_tuples.append((inv_id, str(pay_amt), "2026-04-12", rec_no, "Cash", "Issued"))
            pay_counter += 1

        with transaction(conn):
            cursor.executemany(
                """
                INSERT OR IGNORE INTO payments (
                    invoice_id, amount, payment_date, receipt_number, payment_method, status
                ) VALUES (?, ?, ?, ?, ?, ?);
                """,
                payments_tuples
            )

    # 5. Attendance Records Generation (100,000 records across 20 dates)
    cursor.execute("SELECT COUNT(*) FROM attendance_records;")
    current_attendance_count = cursor.fetchone()[0]
    needed_attendance = attendance_count - current_attendance_count

    if needed_attendance > 0:
        if verbose:
            print(f"[*] Generating {needed_attendance} daily attendance records across academic calendar...")

        cursor.execute("SELECT id FROM enrollments WHERE session_id = ? ORDER BY id ASC LIMIT ?;", (session_id, student_count))
        enr_ids = [r[0] for r in cursor.fetchall()]

        dates = [f"2026-04-{(d % 28) + 1:02d}" for d in range(20)]
        attendance_tuples = []
        att_counter = 0

        for d_str in dates:
            for e_idx, e_id in enumerate(enr_ids):
                if att_counter >= needed_attendance:
                    break
                # Status distribution: 90% Present, 5% Absent, 3% Late, 2% Leave
                mod = (e_idx + att_counter) % 100
                if mod < 90:
                    status = "Present"
                elif mod < 95:
                    status = "Absent"
                elif mod < 98:
                    status = "Late"
                else:
                    status = "Leave"

                attendance_tuples.append((e_id, d_str, status))
                att_counter += 1
            if att_counter >= needed_attendance:
                break

        with transaction(conn):
            cursor.executemany(
                """
                INSERT OR IGNORE INTO attendance_records (enrollment_id, attendance_date, status)
                VALUES (?, ?, ?);
                """,
                attendance_tuples
            )

    elapsed = time.perf_counter() - t0
    if verbose:
        print(f"[+] Synthetic dataset ready in {elapsed:.2f} seconds.")

    return {
        "session_id": session_id,
        "class_group_ids": class_group_ids,
        "elapsed_seconds": elapsed,
    }


# =============================================================================
# 2. Query Performance Benchmarking
# =============================================================================

def run_query_benchmarks(
    conn: sqlite3.Connection,
    session_id: int,
    class_group_id: int,
    iterations: int = 3
) -> List[Dict[str, Any]]:
    """
    Executes and times the 4 core relational queries multiple times,
    recording latency in milliseconds and comparing against SLA (< 100ms).

    Returns:
        List of benchmark metric dictionaries.
    """
    fee_service = FeeService(conn)
    student_service = StudentService(conn)
    attendance_service = AttendanceService(conn)

    results = []

    # -------------------------------------------------------------------------
    # Benchmark 1: Defaulter Ledger Query
    # -------------------------------------------------------------------------
    latencies = []
    defaulters_count = 0
    for _ in range(iterations):
        t_start = time.perf_counter()
        # Scan overdue balances where valid_until cutoff has passed
        res = fee_service.get_defaulters_list(
            session_id=session_id,
            overdue_as_of="2026-05-25"
        )
        t_end = time.perf_counter()
        latencies.append((t_end - t_start) * 1000.0)
        defaulters_count = len(res)

    mean_ms = sum(latencies) / len(latencies)
    results.append({
        "name": "Defaulter Ledger Scan (overdue balances)",
        "volume": f"{defaulters_count:,} defaulters identified",
        "mean_ms": round(mean_ms, 2),
        "min_ms": round(min(latencies), 2),
        "sla_ms": MAX_SLA_LATENCY_MS,
        "passed": mean_ms < MAX_SLA_LATENCY_MS
    })

    # -------------------------------------------------------------------------
    # Benchmark 2: Student Multi-Field Search
    # -------------------------------------------------------------------------
    search_queries = ["Ali", "0300", "CF-2026-0010"]
    latencies = []
    matches_count = 0
    for q in search_queries:
        for _ in range(iterations):
            t_start = time.perf_counter()
            res = student_service.search_students(query=q, session_id=session_id)
            t_end = time.perf_counter()
            latencies.append((t_end - t_start) * 1000.0)
            matches_count = len(res)

    mean_ms = sum(latencies) / len(latencies)
    results.append({
        "name": "Student Multi-Field Search (Name, Phone, Adm#)",
        "volume": f"{matches_count} matches per search",
        "mean_ms": round(mean_ms, 2),
        "min_ms": round(min(latencies), 2),
        "sla_ms": MAX_SLA_LATENCY_MS,
        "passed": mean_ms < MAX_SLA_LATENCY_MS
    })

    # -------------------------------------------------------------------------
    # Benchmark 3: Attendance Roster Loading
    # -------------------------------------------------------------------------
    latencies = []
    roster_count = 0
    for _ in range(iterations):
        t_start = time.perf_counter()
        roster = attendance_service.load_class_roster_for_attendance(
            class_group_id=class_group_id,
            date="2026-04-10"
        )
        t_end = time.perf_counter()
        latencies.append((t_end - t_start) * 1000.0)
        roster_count = len(roster)

    mean_ms = sum(latencies) / len(latencies)
    results.append({
        "name": "Class Attendance Roster Join & Status Check",
        "volume": f"{roster_count} student roster entries",
        "mean_ms": round(mean_ms, 2),
        "min_ms": round(min(latencies), 2),
        "sla_ms": MAX_SLA_LATENCY_MS,
        "passed": mean_ms < MAX_SLA_LATENCY_MS
    })

    # -------------------------------------------------------------------------
    # Benchmark 4: Monthly Fee Invoice Generation (Class Group Batch)
    # -------------------------------------------------------------------------
    latencies = []
    created_count = 0
    cursor = conn.cursor()
    for iter_idx in range(iterations):
        cycle_month = f"2028-{iter_idx + 1:02d}"
        cursor.execute("DELETE FROM fee_invoices WHERE month_year = ? AND session_id = ?;", (cycle_month, session_id))
        conn.commit()

        t_start = time.perf_counter()
        count = fee_service.generate_monthly_invoices(
            session_id=session_id,
            month_year=cycle_month,
            issue_date="2028-01-01",
            due_date="2028-01-10",
            valid_until="2028-01-20",
            class_group_id=class_group_id
        )
        t_end = time.perf_counter()
        latencies.append((t_end - t_start) * 1000.0)
        created_count = count

    mean_ms = sum(latencies) / len(latencies)
    results.append({
        "name": "Batch Fee Invoice Creation (Target Class)",
        "volume": f"{created_count} vouchers generated",
        "mean_ms": round(mean_ms, 2),
        "min_ms": round(min(latencies), 2),
        "sla_ms": MAX_SLA_LATENCY_MS,
        "passed": mean_ms < MAX_SLA_LATENCY_MS
    })

    return results


# =============================================================================
# 3. WAL Mode & Database Integrity Verification
# =============================================================================

def verify_database_integrity(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Executes PRAGMA integrity_check and PRAGMA wal_checkpoint(PASSIVE),
    validating engine health.
    """
    cursor = conn.cursor()

    # 1. Integrity Check
    cursor.execute("PRAGMA integrity_check;")
    integrity_rows = [r[0] for r in cursor.fetchall()]
    integrity_ok = integrity_rows == ["ok"]

    # 2. WAL Checkpoint (PASSIVE: checkpoints without blocking concurrent connections)
    cursor.execute("PRAGMA wal_checkpoint(PASSIVE);")
    checkpoint_res = cursor.fetchone()
    # checkpoint_res returns (busy, log_pages, checkpointed_pages)
    checkpoint_ok = checkpoint_res is not None and checkpoint_res[0] == 0

    return {
        "integrity_ok": integrity_ok,
        "integrity_message": integrity_rows[0] if integrity_rows else "Unknown",
        "checkpoint_ok": checkpoint_ok,
        "checkpoint_stats": tuple(checkpoint_res) if checkpoint_res else (),
    }


# =============================================================================
# 4. ASCII Report Presentation
# =============================================================================

def print_benchmark_report(
    db_path: str,
    counts: Dict[str, int],
    results: List[Dict[str, Any]],
    integrity: Dict[str, Any]
) -> None:
    """Renders a polished, professional ASCII report to standard output."""
    db_size_mb = os.path.getsize(db_path) / (1024 * 1024) if os.path.exists(db_path) else 0.0

    print("\n" + "=" * 80)
    print("      ClassFellow - Enterprise Relational Query Benchmark (Task PLT-03)")
    print("=" * 80)
    print(f" Database Target : {db_path} ({db_size_mb:.2f} MB)")
    print(f" Record Volumes  : {counts.get('students', 0):,} Students | {counts.get('invoices', 0):,} Invoices | {counts.get('attendance', 0):,} Attendance")
    print(f" Engine Pragmas  : WAL Mode | Synchronous=NORMAL | Foreign Keys=ON")
    print("-" * 80)
    print(f" {'Query Benchmark Operation':<42} | {'Volume':<15} | {'Latency':<9} | {'SLA':<7} | {'Status'}")
    print("-" * 80)

    all_passed = True
    for r in results:
        status = "PASSED" if r["passed"] else "FAILED"
        if not r["passed"]:
            all_passed = False
        print(f" {r['name']:<42} | {r['volume']:<15} | {r['mean_ms']:>6.2f} ms | <{int(r['sla_ms'])}ms  | [ {status} ]")

    print("-" * 80)
    integ_str = "OK (Clean)" if integrity["integrity_ok"] else f"FAIL ({integrity['integrity_message']})"
    chk_str = f"Clean (Busy={integrity['checkpoint_stats'][0]}, Pages={integrity['checkpoint_stats'][2]})" if integrity["checkpoint_ok"] else "FAIL"
    print(f" Engine Integrity Check : {integ_str}")
    print(f" WAL Passive Checkpoint : {chk_str}")
    print("=" * 80)

    if all_passed and integrity["integrity_ok"]:
        print("  [+] BENCHMARK RESULT: 100% SLA COMPLIANCE (All queries < 100ms)")
    else:
        print("  [!] BENCHMARK RESULT: PERFORMANCE SLA BREACHED")
    print("=" * 80 + "\n")


# =============================================================================
# 5. CLI Entrypoint
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="ClassFellow Relational Database Performance Benchmarking Tool")
    parser.add_argument("--db-path", default=DEFAULT_BENCHMARK_DB, help="Target database path")
    parser.add_argument("--students", type=int, default=5000, help="Number of students to populate")
    parser.add_argument("--classes", type=int, default=20, help="Number of class groups")
    parser.add_argument("--invoices", type=int, default=50000, help="Number of fee invoices")
    parser.add_argument("--attendance", type=int, default=100000, help="Number of attendance records")
    parser.add_argument("--cleanup", action="store_true", help="Remove test database after execution")
    args = parser.parse_args()

    conn = get_connection(args.db_path)
    try:
        migrate_to_latest(conn)

        meta = generate_synthetic_data(
            conn,
            student_count=args.students,
            class_count=args.classes,
            invoices_count=args.invoices,
            attendance_count=args.attendance,
            verbose=True
        )

        results = run_query_benchmarks(
            conn,
            session_id=meta["session_id"],
            class_group_id=meta["class_group_ids"][0],
            iterations=3
        )

        integrity = verify_database_integrity(conn)

        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM students;")
        n_stu = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM fee_invoices;")
        n_inv = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM attendance_records;")
        n_att = cur.fetchone()[0]

        counts = {"students": n_stu, "invoices": n_inv, "attendance": n_att}
        print_benchmark_report(args.db_path, counts, results, integrity)

    finally:
        conn.close()
        if args.cleanup:
            for ext in ("", "-wal", "-shm"):
                p = args.db_path + ext
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass
            print(f"[*] Cleaned up benchmark test database at: {args.db_path}")


if __name__ == "__main__":
    main()
