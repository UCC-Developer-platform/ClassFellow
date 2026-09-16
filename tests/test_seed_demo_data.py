"""
Automated Test Suite for Demo Pilot Seeder (tests/test_seed_demo_data.py)
========================================================================
Verifies that scripts/seed_demo_data.py creates a consistent, realistic,
and fully populated Punjab school dataset across all domain layers:
  - 1 Academic session & 3 Class groups (School & Academy models).
  - 15 Bilingual students with normalized mobile numbers.
  - 15 Fee invoices with paid, partially paid, and unpaid defaulters.
  - 5 Days of class attendance roll calls with exception flags.
  - 1 Examination cycle with subjects, BISE grading tiers, and ranks.
"""

import os
import sqlite3
from decimal import Decimal
import pytest

from scripts.seed_demo_data import seed_demo_database
from database import get_connection
from services.student_service import StudentService
from services.fee_service import FeeService
from services.attendance_service import AttendanceService
from services.exam_service import ExamService


def test_seed_demo_database_completeness_and_consistency(tmp_path):
    """
    Executes demo seeder on an isolated SQLite database and validates
    referential integrity, counts, and fact-derived business metrics.
    """
    db_path = str(tmp_path / "classfellow_demo_test.db")

    # 1. Execute seeder
    summary = seed_demo_database(db_path=db_path, verbose=False)

    assert summary["students_registered"] == 15
    assert summary["class_groups_created"] == 3
    assert summary["invoices_generated"] == 15
    assert summary["paid_invoices"] == 5
    assert summary["partial_invoices"] == 5
    assert summary["defaulter_invoices"] == 5
    assert summary["attendance_records_logged"] == 75
    assert summary["marks_records_entered"] == 35

    # 2. Inspect Database Records directly
    conn = get_connection(db_path)
    cur = conn.cursor()

    # Academic Session
    cur.execute("SELECT id, name, is_active FROM academic_sessions WHERE name = '2026-2027';")
    sess_row = cur.fetchone()
    assert sess_row is not None
    assert sess_row[2] == 1
    session_id = sess_row[0]

    # Class Groups (2 SchoolClass, 1 AcademyBatch)
    cur.execute("SELECT name, group_type, monthly_tuition_fee FROM class_groups ORDER BY id ASC;")
    classes = cur.fetchall()
    assert len(classes) == 3
    assert classes[0][0] == "Class 9"
    assert classes[0][1] == "SchoolClass"
    assert classes[1][0] == "Class 10"
    assert classes[1][1] == "SchoolClass"
    assert classes[2][0] == "Tuition Batch"
    assert classes[2][1] == "AcademyBatch"

    # Students & Enrollments
    cur.execute("SELECT id, admission_number, first_name, urdu_name, guardian_phone, is_active FROM students;")
    students = cur.fetchall()
    assert len(students) == 15
    for s in students:
        assert s[1].startswith("CF-2026-")  # Admission sequence
        assert s[3] is not None             # Urdu name populated
        assert s[4].startswith("03")        # Normalized Pakistani mobile number
        assert len(s[4]) == 11
        assert s[5] == 1                    # Active status

    cur.execute("SELECT COUNT(*) FROM enrollments WHERE status = 'Active';")
    assert cur.fetchone()[0] == 15

    # Invoices & Payments Ledger
    fee_svc = FeeService(conn)
    cur.execute("SELECT id FROM fee_invoices WHERE month_year = '2026-04' ORDER BY id ASC;")
    inv_rows = cur.fetchall()
    assert len(inv_rows) == 15

    # Invoices 0..4 Paid, 5..9 Partially Paid, 10..14 Defaulters
    for idx, (inv_id,) in enumerate(inv_rows):
        fin = fee_svc.calculate_invoice_balance(inv_id)
        if idx < 5:
            assert fin["status"] == "Paid"
            assert fin["current_balance"] == Decimal("0.00")
            assert fin["total_paid"] > Decimal("0.00")
        elif idx < 10:
            assert fin["status"] == "Partially Paid"
            assert fin["current_balance"] > Decimal("0.00")
            assert fin["total_paid"] > Decimal("0.00")
        else:
            assert fin["status"] == "Unpaid"
            assert fin["total_paid"] == Decimal("0.00")
            assert fin["current_balance"] == fin["net_due"]

    # Defaulters list query
    defaulters = fee_svc.get_defaulters_list(session_id=session_id, month_year="2026-04")
    # 5 partially paid + 5 unpaid = 10 defaulters with outstanding balance
    assert len(defaulters) == 10

    # Attendance Roll Call
    cur.execute("SELECT status, COUNT(*) FROM attendance_records GROUP BY status;")
    att_stats = dict(cur.fetchall())
    assert sum(att_stats.values()) == 75
    assert att_stats.get("Present", 0) >= 65
    assert att_stats.get("Absent", 0) >= 2
    assert att_stats.get("Late", 0) >= 1
    assert att_stats.get("Leave", 0) >= 1

    # Examination & BISE Punjab Ranks
    exam_svc = ExamService(conn)
    cur.execute("SELECT id FROM exams WHERE name = 'First Term Examination 2026';")
    exam_id = cur.fetchone()[0]

    # Calculate results for Class 9 (Class ID 1)
    class_9_results = exam_svc.calculate_class_results(exam_id=exam_id, class_group_id=1)
    assert len(class_9_results) == 5
    # Class 9 results should be ranked 1 to 5
    ranks = [r.rank_in_class for r in class_9_results]
    assert ranks == [1, 2, 3, 4, 5]
    # First ranked student has highest percentage
    assert class_9_results[0].total_obtained >= class_9_results[1].total_obtained
    assert class_9_results[0].percentage >= Decimal("85.00")

    conn.close()
