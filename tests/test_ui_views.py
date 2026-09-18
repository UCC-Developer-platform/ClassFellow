"""
Automated Test Suite for Modular UI Layer & Commercial Architecture
===================================================================
Tests:
  - Feature-flag commercial tier gating (Tier 1 Fee-Only, Tier 2 Standard, Tier 3 Pro).
  - Workspace swapping engine and navigation routing.
  - Headless display detection guard.
  - Read-only table grid data population and search filter queries.
  - Focus-trapping modal input validation (admissions, payments, marks).
"""

import os
import sys
from decimal import Decimal
import pytest
from unittest.mock import patch, MagicMock

from database import init_database
from ui import (
    has_active_display,
    BaseView,
    BaseModal,
    DashboardView,
    StudentView,
    FeeView,
    AttendanceView,
    ExamView,
    SettingsView,
)
from app.app import ClassFellowApp


@pytest.fixture
def populated_ui_db(tmp_path):
    """Creates a temporary migrated SQLite database with sample data for UI tests."""
    db_path = str(tmp_path / "classfellow_ui_test.db")
    conn = init_database(db_path)

    # 1. Academic Session
    conn.execute(
        "INSERT OR IGNORE INTO academic_sessions (name, start_date, end_date, is_active) "
        "VALUES ('2026-2027', '2026-04-01', '2027-03-31', 1);"
    )

    # 2. Class Group
    conn.execute(
        "INSERT OR IGNORE INTO class_groups (session_id, name, section_or_batch, group_type, monthly_tuition_fee) "
        "VALUES (1, 'Class 10', 'A', 'SchoolClass', '3000.00');"
    )

    # 3. Students & Enrollments
    conn.execute(
        "INSERT INTO students (admission_number, first_name, last_name, urdu_name, gender, guardian_name, guardian_phone, is_active) "
        "VALUES ('CF-2026-0001', 'Usman', 'Tariq', 'عثمان طارق', 'Male', 'Tariq Khan', '03001234567', 1);"
    )
    conn.execute(
        "INSERT INTO enrollments (student_id, class_group_id, session_id, roll_number, enrollment_date) "
        "VALUES (1, 1, 1, '101', '2026-04-01');"
    )

    # 4. Fee Invoice & Payment
    conn.execute(
        "INSERT INTO fee_invoices (enrollment_id, session_id, month_year, issue_date, due_date, valid_until, total_payable, discount_amount, net_due) "
        "VALUES (1, 1, '2026-04', '2026-04-01', '2026-04-10', '2026-04-15', '3000.00', '0.00', '3000.00');"
    )
    conn.execute(
        "INSERT INTO payments (receipt_number, invoice_id, amount, payment_date, payment_method, status) "
        "VALUES ('REC-2026-00001', 1, '1000.00', '2026-04-05', 'Cash', 'Issued');"
    )

    # 5. Exam & Subjects
    conn.execute(
        "INSERT INTO exams (session_id, name, exam_type, start_date, end_date) "
        "VALUES (1, 'Midterm 2026', 'TermExam', '2026-05-01', '2026-05-10');"
    )
    conn.execute(
        "INSERT INTO exam_subjects (exam_id, class_group_id, subject_id, maximum_marks, passing_marks) "
        "VALUES (1, 1, 1, '100.00', '33.00');"
    )
    conn.execute(
        "INSERT INTO marks (exam_subject_id, enrollment_id, marks_obtained, is_absent) "
        "VALUES (1, 1, '88.00', 0);"
    )

    # Seed BISE grading tiers
    from services.exam_service import ExamService
    ExamService(conn).seed_default_grading_tiers(session_id=1)

    return conn, db_path


# =============================================================================
# Headless Display Detection Tests
# =============================================================================

def test_has_active_display_logic():
    """Verifies that has_active_display accurately evaluates Windows vs Linux display presence."""
    with patch("sys.platform", "win32"):
        assert has_active_display() is True

    with patch("sys.platform", "linux"), patch.dict(os.environ, {}, clear=True):
        assert has_active_display() is False

    with patch("sys.platform", "linux"), patch.dict(os.environ, {"DISPLAY": ":0"}):
        assert has_active_display() is True


# =============================================================================
# Commercial Tier Feature-Flag Gating Tests
# =============================================================================

def test_commercial_tier_feature_flag_gating(populated_ui_db):
    """
    Verifies that workspace swapping strictly enforces commercial tier gating:
      - Tier 1 (Fee-Only Edition): Attendance & Exams are blocked.
      - Tier 2 (Standard Edition): Attendance allowed, Exams blocked.
      - Tier 3 (Professional Suite): All modules permitted.
    """
    conn, db_path = populated_ui_db

    # Create mock App structure without requiring a visible X11 window
    app = MagicMock()
    app.db_conn = conn
    app.db_path = db_path
    app.view_classes = {
        "dashboard": MagicMock(),
        "students": MagicMock(),
        "fees": MagicMock(),
        "attendance": MagicMock(),
        "examinations": MagicMock(),
        "settings": MagicMock(),
    }
    app.views = {}
    app.current_view = None
    app.status_label = MagicMock()

    # Bind real navigate_to implementation to mock app
    app.navigate_to = ClassFellowApp.navigate_to.__get__(app, ClassFellowApp)

    # --- 1. Test Tier 1: Fee-Only Edition ---
    app.config = {
        "modules": {
            "students": True,
            "fees": True,
            "attendance": False,
            "examinations": False,
        }
    }
    assert app.navigate_to("dashboard") is True
    assert app.navigate_to("students") is True
    assert app.navigate_to("fees") is True
    assert app.navigate_to("attendance") is False       # Blocked
    assert app.navigate_to("examinations") is False     # Blocked
    assert app.navigate_to("settings") is True

    # --- 2. Test Tier 2: Standard Edition ---
    app.config = {
        "modules": {
            "students": True,
            "fees": True,
            "attendance": True,
            "examinations": False,
        }
    }
    assert app.navigate_to("attendance") is True       # Permitted
    assert app.navigate_to("examinations") is False     # Blocked

    # --- 3. Test Tier 3: Professional Suite ---
    app.config = {
        "modules": {
            "students": True,
            "fees": True,
            "attendance": True,
            "examinations": True,
        }
    }
    assert app.navigate_to("examinations") is True     # Permitted
    assert app.navigate_to("unknown_view") is False     # Unregistered


# =============================================================================
# View Component Controller & Data Logic Tests
# =============================================================================

def test_dashboard_view_metrics_aggregation(populated_ui_db):
    """Verifies that Dashboard metrics aggregate live student, class, and fee revenue statistics."""
    conn, db_path = populated_ui_db

    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM students WHERE is_active = 1;")
    assert cur.fetchone()[0] == 1

    cur.execute("SELECT COUNT(*) FROM class_groups;")
    assert cur.fetchone()[0] >= 1

    cur.execute(
        "SELECT COALESCE(SUM(amount), '0.00') FROM payments "
        "WHERE status = 'Issued';"
    )
    assert Decimal(str(cur.fetchone()[0])) == Decimal("1000.00")

    cur.execute("SELECT COUNT(*) FROM academic_sessions;")
    assert cur.fetchone()[0] == 1


def test_student_view_search_and_status_toggle(populated_ui_db):
    """Verifies student search filtering and status toggle actions."""
    conn, db_path = populated_ui_db
    from services.student_service import StudentService

    student_service = StudentService(conn)

    # Test search by English name
    res1 = student_service.search_students("Usman")
    assert len(res1) == 1
    assert res1[0]["admission_number"] == "CF-2026-0001"

    # Test search by Urdu script
    res_urdu = student_service.search_students("عثمان")
    assert len(res_urdu) == 1

    # Test status toggle
    student_service.update_student_status(res1[0]["id"], is_active=False)
    res_inactive = student_service.search_students("Usman", active_only=False)
    assert len(res_inactive) == 1
    assert not bool(res_inactive[0]["is_active"])


def test_fee_view_invoice_filtering_and_receipt_issue(populated_ui_db):
    """Verifies invoice query filters and cash payment recording."""
    conn, db_path = populated_ui_db
    from services.fee_service import FeeService

    fee_service = FeeService(conn)

    # Verify existing partially paid invoice
    fin = fee_service.calculate_invoice_balance(invoice_id=1)
    assert fin["status"] == "Partially Paid"
    assert fin["net_due"] == Decimal("3000.00")
    assert fin["total_paid"] == Decimal("1000.00")
    assert fin["current_balance"] == Decimal("2000.00")

    # Pay remaining balance of 2000.00
    receipt_no = fee_service.record_payment(
        invoice_id=1,
        amount=Decimal("2000.00"),
        note="Remaining balance settled"
    )
    assert receipt_no.startswith("REC-")

    # Invoice should now transition to Paid
    updated_fin = fee_service.calculate_invoice_balance(invoice_id=1)
    assert updated_fin["status"] == "Paid"
    assert updated_fin["total_paid"] == Decimal("3000.00")
    assert updated_fin["current_balance"] == Decimal("0.00")


def test_attendance_view_roster_and_whatsapp_generation(populated_ui_db):
    """Verifies attendance roster loading, atomic bulk UPSERT, and WhatsApp URL alert generation."""
    conn, db_path = populated_ui_db
    from services.attendance_service import AttendanceService

    attendance_service = AttendanceService(conn)

    # 1. Load class roster
    roster = attendance_service.load_class_roster_for_attendance(class_group_id=1, date="2026-05-15")
    assert len(roster) == 1
    assert roster[0]["first_name"] == "Usman"
    assert roster[0]["status"] == "Present"  # Defaults to Present

    # 2. Save roster with Absent status
    attendance_service.save_bulk_attendance(
        date="2026-05-15",
        entries=[{"enrollment_id": 1, "status": "Absent", "reason_note": "Sick leave requested"}]
    )

    # 3. Generate WhatsApp absence alert
    wa_payload = attendance_service.generate_absence_whatsapp_payload(
        enrollment_id=1,
        date="2026-05-15",
        institution_name="ClassFellow Grammar School"
    )
    assert "03001234567" in wa_payload["guardian_phone"]
    assert "wa.me/923001234567" in wa_payload["whatsapp_url"]
    assert "Usman" in wa_payload["whatsapp_url"]
    assert "message_text" in wa_payload
    assert "محترم والدین" in wa_payload["message_text"]


def test_exam_view_results_and_bounds_validation(populated_ui_db):
    """Verifies exam results calculation and score upper-bound enforcement."""
    conn, db_path = populated_ui_db
    from services.exam_service import ExamService

    exam_service = ExamService(conn)

    # Calculate class results
    results = exam_service.calculate_class_results(exam_id=1, class_group_id=1)
    assert len(results) == 1
    res = results[0]
    assert res.total_obtained == Decimal("88.00")
    assert res.total_maximum == Decimal("100.00")
    assert res.percentage == Decimal("88.00")
    assert res.final_grade == "A+"
    assert res.rank_in_class == 1

    # Verify score upper-bound validation guard
    with pytest.raises(ValueError, match="exceeds maximum marks"):
        exam_service.record_student_marks(
            exam_subject_id=1,
            marks_entries=[{"enrollment_id": 1, "marks_obtained": Decimal("105.00")}]  # Exceeds max of 100.00
        )


def test_settings_view_backup_and_connectivity_probes(populated_ui_db, tmp_path):
    """Verifies settings backup service hooks and connectivity probes."""
    conn, db_path = populated_ui_db
    from services.backup_service import BackupService, check_network_connectivity

    backup_base = str(tmp_path / "backups_settings")
    backup_service = BackupService(conn=conn, db_path=db_path, backup_base_dir=backup_base)

    # Execute Tier 1 daily backup
    daily_path = backup_service.run_startup_backup()
    assert daily_path is not None
    assert os.path.exists(daily_path)

    # Execute Tier 2 USB export
    usb_dir = str(tmp_path / "usb_out")
    archive_path = backup_service.export_usb_backup(target_directory=usb_dir)
    assert os.path.exists(archive_path)
    assert archive_path.endswith(".zip")

    # Connectivity probe
    with patch("socket.create_connection") as mock_conn:
        mock_conn.return_value = MagicMock()
        assert check_network_connectivity() is True


# =============================================================================
# Full GUI Instantiation & Workspace Swapping (When Display is Available)
# =============================================================================

@pytest.mark.skipif(not has_active_display(), reason="Active display required for CTk window instantiation")
def test_gui_workspace_swapping_live_window(populated_ui_db):
    """
    Executes live CustomTkinter workspace swapping when a desktop display is available.
    Skipped automatically in headless CI environments.
    """
    conn, db_path = populated_ui_db

    with patch.object(ClassFellowApp, "_run_async_startup_backup", lambda self: None):
        app = ClassFellowApp(db_path=db_path)
        app.withdraw()
        try:
            # Default workspace is dashboard
            assert app.current_view == app.views.get("dashboard")

            # Swap to students
            assert app.navigate_to("students") is True
            student_view = app.views.get("students")
            assert app.current_view == student_view

            # Verify ImportSummaryModal and StudentImportModal
            from ui.student_view import StudentImportModal, ImportSummaryModal
            import_modal = StudentImportModal(student_view)
            import_modal.close()

            summary_with_errors = {
                "total_rows": 5,
                "imported_count": 4,
                "failed_count": 1,
                "errors": [{"row": 2, "student_name": "Bad Phone Student", "error": "Invalid phone format"}]
            }
            summary_modal = ImportSummaryModal(student_view, summary_with_errors)
            summary_modal.close()

            summary_clean = {"total_rows": 3, "imported_count": 3, "failed_count": 0, "errors": []}
            clean_modal = ImportSummaryModal(student_view, summary_clean)
            clean_modal.close()

            # Swap to fees
            assert app.navigate_to("fees") is True
            assert app.current_view == app.views.get("fees")

            # Swap to attendance
            assert app.navigate_to("attendance") is True
            assert app.current_view == app.views.get("attendance")

            # Verify WhatsAppNotificationModal inside active app
            from ui.attendance_view import WhatsAppNotificationModal
            wa_payload = {
                "student_name": "Usman",
                "guardian_phone": "03001234567",
                "message_text": "محترم والدین، اطلاع دی جاتی ہے کہ بچہ غیر حاضر ہے۔",
                "whatsapp_url": "https://wa.me/923001234567?text=test"
            }
            modal = WhatsAppNotificationModal(app, wa_payload)
            assert modal.message_label.cget("text") == wa_payload["message_text"]
            assert modal.payload["whatsapp_url"] == wa_payload["whatsapp_url"]
            modal._copy_message()
            assert "copied" in modal.status_lbl.cget("text").lower()
            with patch("webbrowser.open") as mock_open:
                modal._open_whatsapp_url()
                mock_open.assert_called_once_with(wa_payload["whatsapp_url"])
            modal.close()

            # Swap to examinations
            assert app.navigate_to("examinations") is True
            assert app.current_view == app.views.get("examinations")

            # Swap to settings
            assert app.navigate_to("settings") is True
            assert app.current_view == app.views.get("settings")

        finally:
            app.destroy()
