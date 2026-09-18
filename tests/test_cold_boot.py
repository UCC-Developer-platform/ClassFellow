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
import sqlite3
import pytest

from database import init_database, get_schema_version, get_connection
from app.app import ClassFellowApp, SidebarNavButton
from ui import has_active_display


def test_init_database_on_empty_file(tmp_path):
    """Verifies that init_database on a clean 0-byte file builds the full v3 schema."""
    cold_db = str(tmp_path / "cold_start.db")
    assert not os.path.exists(cold_db)

    # Bootstrapping on brand-new file
    conn = init_database(cold_db)
    try:
        assert os.path.exists(cold_db)
        assert get_schema_version(conn) == 3

        # Verify all essential tables exist
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cur.fetchall()}

        expected_tables = {
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
    finally:
        conn.close()


def test_app_cold_start_and_workspace_navigation(tmp_path):
    """Verifies that ClassFellowApp initializes cleanly and navigates to all workspaces on cold DB."""
    if not has_active_display():
        pytest.skip("Active GUI display not available in this environment.")

    cold_db = str(tmp_path / "app_cold_start.db")

    app = ClassFellowApp(db_path=cold_db)
    try:
        # Schema must be auto-bootstrapped to version 3
        assert get_schema_version(app.db_conn) == 3

        # Sidebar navigation buttons must be 2-column aligned SidebarNavButton instances
        assert hasattr(app, "sidebar_buttons")
        for key, btn in app.sidebar_buttons.items():
            assert isinstance(btn, SidebarNavButton)
            assert btn.icon_label.cget("width") == 36

        # Navigation to all tabs must succeed without uncaught exceptions
        modules_to_test = ["dashboard", "students", "fees", "attendance", "examinations", "settings"]
        for mod in modules_to_test:
            nav_success = app.navigate_to(mod)
            assert nav_success is True, f"Navigation to '{mod}' failed on cold start!"
            assert app.current_view is not None

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
