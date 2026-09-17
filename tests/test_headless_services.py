"""
ClassFellow - Headless Domain Service Decoupling Audit (tests/test_headless_services.py)
=======================================================================================
Task WEB-01: Verifies that StudentService, FeeService, AttendanceService, ExamService,
and StudentImporterService maintain ZERO dependencies on GUI modules (tkinter, customtkinter)
and operate in complete headless isolation.
"""

import os
import ast
import sys
import pytest
from decimal import Decimal
from unittest.mock import patch

from database import get_connection
from services.schema_service import migrate_to_latest
from models import StudentDTO


SERVICES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "services")


# =============================================================================
# 1. Static AST Import Inspection
# =============================================================================

def test_domain_services_have_zero_gui_imports():
    """
    Statically analyzes the AST of every module in services/ to guarantee
    neither 'tkinter' nor 'customtkinter' is imported anywhere in the service layer.
    """
    forbidden_modules = {"tkinter", "customtkinter", "tkinter.ttk", "tkinter.messagebox", "tkinter.filedialog"}

    service_files = [
        f for f in os.listdir(SERVICES_DIR)
        if f.endswith(".py") and f != "__pycache__"
    ]
    assert len(service_files) >= 5, f"Expected domain service files in {SERVICES_DIR}"

    violations = []

    for fname in service_files:
        fpath = os.path.join(SERVICES_DIR, fname)
        with open(fpath, "r", encoding="utf-8") as src:
            tree = ast.parse(src.read(), filename=fname)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in forbidden_modules or any(alias.name.startswith(fm + ".") for fm in forbidden_modules):
                        violations.append((fname, node.lineno, f"import {alias.name}"))
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if mod in forbidden_modules or any(mod.startswith(fm) for fm in forbidden_modules):
                    violations.append((fname, node.lineno, f"from {mod} import ..."))

    assert len(violations) == 0, f"GUI imports detected in domain service layer: {violations}"


# =============================================================================
# 2. Dynamic Headless Execution with Tkinter Blocked
# =============================================================================

def test_domain_services_operate_cleanly_when_tkinter_blocked(tmp_path):
    """
    Exercises all 5 core domain services in a sub-runtime where 'tkinter' and 'customtkinter'
    are explicitly blocked from importing in sys.modules, verifying zero runtime GUI coupling.
    """
    # Block tkinter and customtkinter
    blocked_modules = {
        "tkinter": None,
        "tkinter.ttk": None,
        "tkinter.messagebox": None,
        "tkinter.filedialog": None,
        "customtkinter": None,
    }

    with patch.dict(sys.modules, blocked_modules):
        # Verify attempt to import tkinter directly fails in this context
        with pytest.raises((ImportError, ModuleNotFoundError, TypeError)):
            import tkinter  # noqa

        # 1. Initialize headless database
        db_file = str(tmp_path / "headless_test.db")
        conn = get_connection(db_file)
        migrate_to_latest(conn)

        # 2. Test StudentService
        from services.student_service import StudentService
        student_svc = StudentService(conn)
        sess_id = student_svc.create_academic_session("2026-2027", "2026-04-01", "2027-03-31")
        cg_id = student_svc.create_class_group(sess_id, "Grade 10", "A", "SchoolClass", Decimal("4500.00"))

        student_dto = StudentDTO(
            admission_number="CF-2026-0001",
            first_name="Bilal",
            last_name="Tariq",
            urdu_name="بلال طارق",
            gender="Male",
            guardian_name="Tariq Mehmood",
            guardian_relation="Father",
            guardian_phone="03001234567",
            residential_address="Gulberg, Lahore",
            is_active=True
        )
        s_id, e_id = student_svc.register_student(student_dto, cg_id, sess_id, roll_number="1")
        assert s_id is not None
        assert e_id is not None

        search_res = student_svc.search_students("Bilal")
        assert len(search_res) == 1
        assert search_res[0]["admission_number"] == "CF-2026-0001"

        # 3. Test FeeService
        from services.fee_service import FeeService
        fee_svc = FeeService(conn)
        inv_count = fee_svc.generate_monthly_invoices(
            session_id=sess_id,
            month_year="2026-04",
            issue_date="2026-04-01",
            due_date="2026-04-10",
            valid_until="2026-04-20"
        )
        assert inv_count == 1

        defaulters = fee_svc.get_defaulters_list(sess_id, month_year="2026-04")
        assert len(defaulters) == 1
        inv_id = defaulters[0]["id"]

        rec_no = fee_svc.record_payment(inv_id, Decimal("4500.00"))
        assert rec_no.startswith("REC-")
        rem_defaulters = fee_svc.get_defaulters_list(sess_id, month_year="2026-04")
        assert len(rem_defaulters) == 0

        # 4. Test AttendanceService
        from services.attendance_service import AttendanceService
        att_svc = AttendanceService(conn)
        roster = att_svc.load_class_roster_for_attendance(cg_id, "2026-04-05")
        assert len(roster) == 1
        assert roster[0]["status"] == "Present"

        saved_count = att_svc.save_bulk_attendance(
            "2026-04-05",
            [{"enrollment_id": e_id, "status": "Absent", "reason_note": "Fever"}]
        )
        assert saved_count == 1

        summary = att_svc.get_monthly_attendance_summary(e_id, "2026-04-01", "2026-04-30")
        assert summary.total_days == 1
        assert summary.absent_days == 1

        wa_payload = att_svc.generate_absence_whatsapp_payload(e_id, "2026-04-05")
        assert wa_payload["student_name"] == "Bilal Tariq"
        assert "03001234567" in wa_payload["guardian_phone"]

        # 5. Test ExamService
        from services.exam_service import ExamService
        exam_svc = ExamService(conn)
        exam_svc.create_grading_tier(sess_id, "A", Decimal("80.00"), Decimal("100.00"), Decimal("4.0"), "Excellent")
        subj_id = exam_svc.create_subject("Physics", "طبیعیات", "PHY")
        exam_id = exam_svc.create_exam(sess_id, "Mid-Term Examination 2026", "TermExam", "2026-09-01", "2026-09-15")
        es_id = exam_svc.configure_exam_subject(exam_id, cg_id, subj_id, Decimal("100.00"), Decimal("33.00"))
        exam_svc.record_student_marks(es_id, [{"enrollment_id": e_id, "marks_obtained": Decimal("88.50")}])

        results = exam_svc.calculate_class_results(exam_id, cg_id)
        assert len(results) == 1
        assert results[0].percentage == Decimal("88.50")
        assert results[0].rank_in_class == 1
        assert results[0].final_grade == "A"

        # 6. Test StudentImporterService
        from services.importer_service import StudentImporterService
        importer_svc = StudentImporterService(conn)
        tmpl_path = str(tmp_path / "headless_template.xlsx")
        out_path = importer_svc.generate_excel_template(tmpl_path)
        assert os.path.exists(out_path)

        conn.close()
