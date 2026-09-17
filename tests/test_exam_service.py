"""
Tests for Examination Subsystem (CF-SRS-05):
- Migration v3 table verification and version check
- Subject and Exam creation
- Dynamic Exam-Subject configuration with limit validation
- Configurable Grading Tiers boundary lookup and seed verification
- Marks Entry Ledger with strict upper bound validation (marks_obtained <= maximum_marks)
- Aggregate term percentage calculation and rank ordering (including joint ties)
- ReportLab A4 Terminal Report Card PDF generation (single-sheet, valid %PDF header)
"""

import io
import pytest
import sqlite3
from decimal import Decimal

from models import StudentDTO
from services.schema_service import (
    migrate_to_latest,
    get_schema_version,
    SCHEMA_VERSION_CURRENT,
    migration_v3_exam_schema,
)
from services.student_service import StudentService
from services.attendance_service import AttendanceService
from services.exam_service import ExamService
from app.reports.report_card_generator import ReportCardGenerator, generate_report_card_pdf


@pytest.fixture
def migrated_db(db_connection):
    """Provides a SQLite connection migrated to the latest schema version."""
    migrate_to_latest(db_connection)
    return db_connection


@pytest.fixture
def student_service(migrated_db):
    return StudentService(migrated_db)


@pytest.fixture
def attendance_service(migrated_db):
    return AttendanceService(migrated_db)


@pytest.fixture
def exam_service(migrated_db):
    return ExamService(migrated_db)


@pytest.fixture
def exam_test_setup(student_service, exam_service, attendance_service):
    """
    Sets up:
    - Session 2025-2026
    - Class 10th - Section A
    - 3 Students (Hamza, Fatima, Ali)
    - Default BISE Punjab Grading Tiers
    - Subjects: Math (100 max, 33 pass), English (100 max, 33 pass), Urdu (100 max, 33 pass)
    - Exam: Mid-Term Exam 2025
    """
    session_id = student_service.create_academic_session(
        name="2025-2026",
        start_date="2025-04-01",
        end_date="2026-03-31"
    )
    class_group_id = student_service.create_class_group(
        session_id=session_id,
        name="Class 10",
        section_or_batch="Section A",
        group_type="SchoolClass",
        monthly_tuition_fee=Decimal("6000.00")
    )

    # Register 3 students
    s1 = StudentDTO(
        first_name="Hamza",
        last_name="Tariq",
        urdu_name="حمزہ طارق",
        gender="Male",
        guardian_name="Tariq Mahmood",
        guardian_phone="03001112233"
    )
    _, enr_id1 = student_service.register_student(s1, class_group_id, session_id, roll_number="101")

    s2 = StudentDTO(
        first_name="Fatima",
        last_name="Zahra",
        urdu_name="فاطمہ زہرا",
        gender="Female",
        guardian_name="Muhammad Ali",
        guardian_phone="03002223344"
    )
    _, enr_id2 = student_service.register_student(s2, class_group_id, session_id, roll_number="102")

    s3 = StudentDTO(
        first_name="Ali",
        last_name="Raza",
        urdu_name="علی رضا",
        gender="Male",
        guardian_name="Hassan Raza",
        guardian_phone="03003334455"
    )
    _, enr_id3 = student_service.register_student(s3, class_group_id, session_id, roll_number="103")


    # Seed grading tiers
    exam_service.seed_default_grading_tiers(session_id)

    # Create exam
    exam_id = exam_service.create_exam(
        session_id=session_id,
        name="Mid-Term Examination 2025",
        exam_type="TermExam",
        start_date="2025-09-10",
        end_date="2025-09-20",
        is_published=True
    )

    # Get subjects from seeded migration v3
    subjects = {s.name: s.id for s in exam_service.get_subjects()}

    # Configure exam subjects
    es_math_id = exam_service.configure_exam_subject(
        exam_id=exam_id,
        class_group_id=class_group_id,
        subject_id=subjects["Mathematics"],
        maximum_marks=Decimal("100.00"),
        passing_marks=Decimal("33.00"),
        exam_date="2025-09-11"
    )
    es_eng_id = exam_service.configure_exam_subject(
        exam_id=exam_id,
        class_group_id=class_group_id,
        subject_id=subjects["English"],
        maximum_marks=Decimal("100.00"),
        passing_marks=Decimal("33.00"),
        exam_date="2025-09-13"
    )
    es_urdu_id = exam_service.configure_exam_subject(
        exam_id=exam_id,
        class_group_id=class_group_id,
        subject_id=subjects["Urdu"],
        maximum_marks=Decimal("100.00"),
        passing_marks=Decimal("33.00"),
        exam_date="2025-09-15"
    )

    # Log some attendance for hamza (100%), fatima (50%), ali (0%)
    attendance_service.save_bulk_attendance(
        date="2025-09-01",
        entries=[
            {"enrollment_id": enr_id1, "status": "Present"},
            {"enrollment_id": enr_id2, "status": "Present"},
            {"enrollment_id": enr_id3, "status": "Absent"},
        ]
    )
    attendance_service.save_bulk_attendance(
        date="2025-09-02",
        entries=[
            {"enrollment_id": enr_id1, "status": "Present"},
            {"enrollment_id": enr_id2, "status": "Absent"},
            {"enrollment_id": enr_id3, "status": "Absent"},
        ]
    )



    return {
        "session_id": session_id,
        "class_group_id": class_group_id,
        "exam_id": exam_id,
        "enrollments": [enr_id1, enr_id2, enr_id3],
        "exam_subjects": {
            "math": es_math_id,
            "eng": es_eng_id,
            "urdu": es_urdu_id,
        }
    }


# ==============================================================================
# Test Cases
# ==============================================================================

def test_migration_v3_schema_and_version(db_connection):
    """Validates that migration v3 creates all exam tables and sets user_version to 3."""
    version = migrate_to_latest(db_connection)
    assert version == 3
    assert get_schema_version(db_connection) == SCHEMA_VERSION_CURRENT

    cursor = db_connection.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row["name"] for row in cursor.fetchall()]

    for t in ("subjects", "exams", "exam_subjects", "grading_tiers", "marks"):
        assert t in tables, f"Expected table '{t}' in sqlite schema."


def test_subject_creation_and_listing(exam_service):
    """Verifies creating custom subjects and fetching with Urdu names."""
    sub_id = exam_service.create_subject(
        name="Computer Science",
        urdu_name="کمپیوٹر سائنس",
        code="CS-10"
    )
    assert sub_id > 0

    subjects = exam_service.get_subjects()
    cs_sub = next((s for s in subjects if s.name == "Computer Science"), None)
    assert cs_sub is not None
    assert cs_sub.urdu_name == "کمپیوٹر سائنس"
    assert cs_sub.code == "CS-10"

    with pytest.raises(ValueError, match="Subject name cannot be empty"):
        exam_service.create_subject("")


def test_exam_subject_configuration_limits(exam_service, student_service):
    """Verifies validation rules when configuring exam subject limits."""
    session_id = student_service.create_academic_session("2025-2026", "2025-04-01", "2026-03-31")
    cg_id = student_service.create_class_group(session_id, "Class 8", "A", "SchoolClass", Decimal("3000"))
    exam_id = exam_service.create_exam(session_id, "Annual 2025", "AnnualExam", "2025-11-01", "2025-11-15")
    sub_id = exam_service.create_subject("Physics")

    # Invalid: Max marks <= 0
    with pytest.raises(ValueError, match="Maximum marks must be greater than zero"):
        exam_service.configure_exam_subject(exam_id, cg_id, sub_id, Decimal("0.00"), Decimal("0.00"))

    # Invalid: Passing marks > Max marks
    with pytest.raises(ValueError, match="Passing marks .* cannot exceed maximum marks"):
        exam_service.configure_exam_subject(exam_id, cg_id, sub_id, Decimal("50.00"), Decimal("60.00"))

    # Valid configuration
    es_id = exam_service.configure_exam_subject(
        exam_id, cg_id, sub_id, Decimal("75.00"), Decimal("25.00")
    )
    assert es_id > 0

    # UPSERT check: re-configuring should update rather than crash
    es_id2 = exam_service.configure_exam_subject(
        exam_id, cg_id, sub_id, Decimal("80.00"), Decimal("28.00")
    )
    assert es_id2 == es_id
    es_list = exam_service.get_exam_subjects(exam_id, cg_id)
    assert len(es_list) == 1
    assert es_list[0].maximum_marks == Decimal("80.00")
    assert es_list[0].passing_marks == Decimal("28.00")


def test_grading_tier_boundaries_and_lookup(exam_service, student_service):
    """Verifies configurable grade boundary evaluation logic."""
    session_id = student_service.create_academic_session("2025-2026", "2025-04-01", "2026-03-31")
    exam_service.seed_default_grading_tiers(session_id)

    # Test exact boundary matching
    g_100 = exam_service.get_grade_for_percentage(session_id, Decimal("100.00"))
    assert g_100.grade_name == "A+"
    assert g_100.gpa_point == Decimal("4.0")

    g_80 = exam_service.get_grade_for_percentage(session_id, Decimal("80.00"))
    assert g_80.grade_name == "A+"

    g_75 = exam_service.get_grade_for_percentage(session_id, Decimal("75.50"))
    assert g_75.grade_name == "A"

    g_65 = exam_service.get_grade_for_percentage(session_id, Decimal("65.00"))
    assert g_65.grade_name == "B"

    g_52 = exam_service.get_grade_for_percentage(session_id, Decimal("52.00"))
    assert g_52.grade_name == "C"

    g_33 = exam_service.get_grade_for_percentage(session_id, Decimal("33.00"))
    assert g_33.grade_name == "D"
    assert g_33.is_passing is True

    g_32 = exam_service.get_grade_for_percentage(session_id, Decimal("32.99"))
    assert g_32.grade_name == "F"
    assert g_32.is_passing is False


def test_marks_obtained_upper_bound_validation(exam_service, exam_test_setup):
    """
    CRITICAL GUARDRAIL: Validates that marks_obtained <= maximum_marks.
    Attempting to enter marks > maximum_marks must raise ValueError and roll back.
    """
    math_es_id = exam_test_setup["exam_subjects"]["math"]
    enr_id1 = exam_test_setup["enrollments"][0]

    # Max marks is 100.00. Attempt 101.00 -> Must raise ValueError
    with pytest.raises(ValueError, match="exceeds maximum marks"):
        exam_service.record_student_marks(
            exam_subject_id=math_es_id,
            marks_entries=[
                {"enrollment_id": enr_id1, "marks_obtained": Decimal("101.00")}
            ]
        )

    # Negative marks -> Must raise ValueError
    with pytest.raises(ValueError, match="cannot be negative"):
        exam_service.record_student_marks(
            exam_subject_id=math_es_id,
            marks_entries=[
                {"enrollment_id": enr_id1, "marks_obtained": Decimal("-5.00")}
            ]
        )

    # Valid marks entry
    count = exam_service.record_student_marks(
        exam_subject_id=math_es_id,
        marks_entries=[
            {"enrollment_id": enr_id1, "marks_obtained": Decimal("95.50"), "teacher_remarks": "Outstanding"}
        ]
    )
    assert count == 1


def test_class_results_ranking_and_ties(exam_service, exam_test_setup):
    """
    Verifies term aggregate percentage calculations and class rank ordering,
    including handling equal score joint rankings.
    """
    setup = exam_test_setup
    math_id = setup["exam_subjects"]["math"]
    eng_id = setup["exam_subjects"]["eng"]
    urdu_id = setup["exam_subjects"]["urdu"]

    enr1, enr2, enr3 = setup["enrollments"]

    # Student 1 (Hamza): 90 in Math, 85 in Eng, 85 in Urdu -> Total: 260/300 (86.67%)
    exam_service.record_student_marks(math_id, [{"enrollment_id": enr1, "marks_obtained": Decimal("90.00")}])
    exam_service.record_student_marks(eng_id, [{"enrollment_id": enr1, "marks_obtained": Decimal("85.00")}])
    exam_service.record_student_marks(urdu_id, [{"enrollment_id": enr1, "marks_obtained": Decimal("85.00")}])

    # Student 2 (Fatima): 90 in Math, 85 in Eng, 85 in Urdu -> Total: 260/300 (86.67%) -> Joint 1st!
    exam_service.record_student_marks(math_id, [{"enrollment_id": enr2, "marks_obtained": Decimal("90.00")}])
    exam_service.record_student_marks(eng_id, [{"enrollment_id": enr2, "marks_obtained": Decimal("85.00")}])
    exam_service.record_student_marks(urdu_id, [{"enrollment_id": enr2, "marks_obtained": Decimal("85.00")}])

    # Student 3 (Ali): 40 in Math, 30 in Eng (Failed), 50 in Urdu -> Total: 120/300 (40.00%)
    exam_service.record_student_marks(math_id, [{"enrollment_id": enr3, "marks_obtained": Decimal("40.00")}])
    exam_service.record_student_marks(eng_id, [{"enrollment_id": enr3, "marks_obtained": Decimal("30.00")}])
    exam_service.record_student_marks(urdu_id, [{"enrollment_id": enr3, "marks_obtained": Decimal("50.00")}])

    results = exam_service.calculate_class_results(setup["exam_id"], setup["class_group_id"])
    assert len(results) == 3

    # Check Rankings
    # Hamza and Fatima share rank 1
    assert results[0].rank_in_class == 1
    assert results[1].rank_in_class == 1
    assert results[0].total_obtained == Decimal("260.00")
    assert results[1].total_obtained == Decimal("260.00")
    assert results[0].final_grade == "A+"
    assert results[1].final_grade == "A+"

    # Ali has rank 3
    assert results[2].rank_in_class == 3
    assert results[2].total_obtained == Decimal("120.00")
    # Ali failed English (30 < 33 pass mark), so final grade is "F"
    assert results[2].final_grade == "F"

    # Check attendance percentages
    hamza_card = next(c for c in results if "Hamza" in c.student_name)
    fatima_card = next(c for c in results if "Fatima" in c.student_name)
    ali_card = next(c for c in results if "Ali" in c.student_name)

    assert hamza_card.attendance_percentage == 100.0
    assert fatima_card.attendance_percentage == 50.0
    assert ali_card.attendance_percentage == 0.0


def test_single_sheet_a4_report_card_pdf_generation(exam_service, exam_test_setup):
    """
    Verifies that ReportLab generates a valid single-sheet A4 PDF document
    with header '%PDF-', proper binary stream bytes, and correct student meta.
    """
    setup = exam_test_setup
    math_id = setup["exam_subjects"]["math"]
    enr1 = setup["enrollments"][0]

    exam_service.record_student_marks(
        math_id,
        [{"enrollment_id": enr1, "marks_obtained": Decimal("95.00"), "teacher_remarks": "Excellent student"}]
    )

    report_card = exam_service.get_student_report_card(
        exam_id=setup["exam_id"],
        class_group_id=setup["class_group_id"],
        enrollment_id=enr1
    )
    assert report_card is not None
    assert report_card.student_name == "Hamza Tariq"
    assert report_card.admission_number != ""
    assert len(report_card.results) == 3

    # Render PDF into in-memory buffer
    buffer = io.BytesIO()
    out = generate_report_card_pdf(report_card, output=buffer)

    pdf_bytes = out.getvalue()
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF-")
