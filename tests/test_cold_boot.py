"""
ClassFellow - Cold-Start Database Bootstrap & UI Navigation Regression Test
===========================================================================
Verifies that when ClassFellow launches against a brand-new, empty, or unmigrated
database file (such as on a fresh USB launch on Windows 11), init_database()
automatically executes schema migrations, creates all 15 relational tables,
and allows seamless navigation across Students, Attendance, Exams, Fees,
Settings, and Dashboard workspaces without crashing or freezing.
"""

import os
from decimal import Decimal
import pytest

from database import init_database, get_schema_version
from app.app import ClassFellowApp, SidebarNavButton
from ui import has_active_display


def test_init_database_on_empty_file(tmp_path):
    """Verifies that init_database on a clean 0-byte file builds the full v5 schema."""
    cold_db = str(tmp_path / "cold_start.db")
    assert not os.path.exists(cold_db)

    from services.school_service import is_school_profile_configured, setup_initial_school

    # Bootstrapping on brand-new file
    conn = init_database(cold_db)
    try:
        assert os.path.exists(cold_db)
        assert get_schema_version(conn) == 5

        # Verify all essential tables exist
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cur.fetchall()}

        expected_tables = {
            "school_profiles",
            "academic_sessions",
            "students",
            "class_groups",
            "enrollments",
            "fee_heads",
            "fee_invoices",
            "fee_invoice_items",
            "payments",
            "attendance_records",
            "exams",
            "exam_subjects",
            "marks",
            "subjects",
            "grading_tiers",
        }
        for t in expected_tables:
            assert t in tables, f"Expected table '{t}' was not created during cold bootstrap!"

        # Zero-state database must have fee heads catalog but no synthetic mock classes/sessions
        assert is_school_profile_configured(conn) is False

        # Configure school via Mother Form setup service
        p_id, s_id = setup_initial_school(
            conn,
            profile_data={"school_name": "Allied Model School", "contact_number": "03001234567"},
            session_data={"name": "2026-2027 Academic Session", "start_date": "2026-04-01", "end_date": "2027-03-31"},
            classes_data=[{"name": "Class 1", "section_or_batch": "Section A", "monthly_tuition_fee": Decimal("3500.00")}]
        )
        assert p_id is not None
        assert s_id is not None
        assert is_school_profile_configured(conn) is True

        cur.execute("SELECT COUNT(*) FROM academic_sessions WHERE is_active = 1;")
        assert cur.fetchone()[0] >= 1

        cur.execute("SELECT COUNT(*) FROM class_groups;")
        assert cur.fetchone()[0] >= 1
    finally:
        conn.close()


def test_app_cold_start_and_workspace_navigation(tmp_path):
    """
    Verifies that ClassFellowApp initializes cleanly on cold DB, navigates to all workspaces,
    enforces RTL justification on Urdu fields, allows inline class creation via QuickAddClassModal,
    and reports live operational diagnostics in settings.
    """
    if not has_active_display():
        pytest.skip("Active GUI display not available in this environment.")

    from ui.student_view import StudentAdmissionModal, QuickAddClassModal

    cold_db = str(tmp_path / "app_cold_start.db")

    try:
        app = ClassFellowApp(db_path=cold_db)
    except Exception as exc:
        if "tk.tcl" in str(exc) or "TclError" in type(exc).__name__:
            pytest.skip(f"Tkinter GUI runtime unavailable on this runner: {exc}")
        raise

    try:
        # Schema must be auto-bootstrapped to version 5
        assert get_schema_version(app.db_conn) == 5

        # Verify Route Guard: is_school_profile_configured is initially False
        from services.school_service import is_school_profile_configured, setup_initial_school
        assert is_school_profile_configured(app.db_conn) is False

        # Execute Mother Form setup to transition school to configured state
        setup_initial_school(
            app.db_conn,
            profile_data={"school_name": "ClassFellow Grammar School", "contact_number": "03001234567"},
            session_data={"name": "2026-2027 Academic Session", "start_date": "2026-04-01", "end_date": "2027-03-31"},
            classes_data=[{"name": "Class 1", "section_or_batch": "Section A", "monthly_tuition_fee": Decimal("3500.00")}]
        )
        assert is_school_profile_configured(app.db_conn) is True

        # Sidebar navigation buttons must be 2-column aligned SidebarNavButton instances
        assert hasattr(app, "sidebar_buttons")
        for key, btn in app.sidebar_buttons.items():
            assert isinstance(btn, SidebarNavButton)
            assert btn.icon_label.cget("width") in (36, 40)

        # Navigation to all tabs must succeed without uncaught exceptions
        modules_to_test = ["dashboard", "students", "fees", "attendance", "examinations", "settings"]
        for mod in modules_to_test:
            nav_success = app.navigate_to(mod)
            assert nav_success is True, f"Navigation to '{mod}' failed on cold start!"
            assert app.current_view is not None

        # Verify Student Admission Modal and QuickAddClassModal on students workspace
        app.navigate_to("students")
        student_view = app.views.get("students")
        assert student_view is not None

        modal = StudentAdmissionModal(student_view)
        try:
            # 1. Verify Urdu inputs are Right-to-Left (justify="right")
            assert modal.urdu_name.cget("justify") == "right"
            assert modal.guardian_urdu_name.cget("justify") == "right"
            assert modal.first_name.cget("justify") == "left"

            # 2. Verify baseline class is present in dropdown
            assert len(modal.class_names) >= 1
            assert "Class 1 (Section A)" in modal.class_names

            # 3. Test inline QuickAddClassModal
            quick_modal = QuickAddClassModal(modal)
            try:
                quick_modal.name_entry.insert(0, "Class 9")
                quick_modal.sec_entry.insert(0, "Green")
                quick_modal.fee_entry.delete(0, "end")
                quick_modal.fee_entry.insert(0, "3500.00")
                quick_modal._save_class()
            finally:
                quick_modal.destroy()

            # Verify new class is added and automatically selected
            assert "Class 9 (Green)" in modal.class_names
            assert modal.class_var.get() == "Class 9 (Green)"

            # 4. Fill student admission data
            modal.first_name.insert(0, "Abdullah Mohsen")
            modal.last_name.insert(0, "Butt")
            modal.urdu_name.insert(0, "بٹ محسن عبداللہ")
            modal.guardian_name.insert(0, "Mohsen Farhan Butt")
            modal.guardian_urdu_name.insert(0, "بٹ فرحان محسن")
            modal.guardian_phone.insert(0, "03213000625")
            modal.guardian_email.insert(0, "mohsen@example.com")
            modal.discount_entry.insert(0, "500.00")

            # 5. Submit admission
            modal._submit_admission()

            # Verify student is admitted in SQLite
            cur = app.db_conn.cursor()
            cur.execute(
                "SELECT id, admission_number, first_name, urdu_name, guardian_urdu_name, guardian_email "
                "FROM students WHERE guardian_phone = '03213000625';"
            )
            row = cur.fetchone()
            assert row is not None
            assert row[2] == "Abdullah Mohsen"
            assert row[3] == "بٹ محسن عبداللہ"
            assert row[4] == "بٹ فرحان محسن"
            assert row[5] == "mohsen@example.com"

            # Verify enrollment in the new class
            cur.execute("SELECT class_group_id FROM enrollments WHERE student_id = ?;", (row[0],))
            enr_row = cur.fetchone()
            assert enr_row is not None
            assert enr_row[0] == modal.class_groups_map["Class 9 (Green)"]

        finally:
            modal.destroy()

        # Verify that Settings workspace probes report operational status
        settings_view = app.views.get("settings")
        assert settings_view is not None
        assert "Active & Verified" in settings_view.db_conn_status_label.cget("text")
        assert "Operational" in settings_view.probe_students_label.cget("text")
        assert "Operational" in settings_view.probe_fees_label.cget("text")
        assert "Operational" in settings_view.probe_attendance_label.cget("text")
        assert "Operational" in settings_view.probe_exams_label.cget("text")

        # Test the 1-click auto-repair utility in settings
        settings_view._run_db_repair()
        assert "verified & auto-repaired" in settings_view.repair_status_label.cget("text")

    finally:
        app.destroy()
