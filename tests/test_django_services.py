"""
ClassFellow - Django Web Domain Services Integration Test Suite
Verifies business logic, transactional atomicity, phone normalization,
sequential numbering, bulk upserts, and rankings across all 4 web services.
"""

import datetime
from decimal import Decimal
import os
import sys
from pathlib import Path
import pytest

# Ensure classfellow_web is on sys.path
WEB_DIR = Path(__file__).resolve().parent.parent / "classfellow_web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ["DJANGO_DB_ENGINE"] = "sqlite"

import django
django.setup()

from django.core.management import call_command

from apps.accounts.models import User, Role
from apps.attendance.models import AttendanceStatus
from apps.attendance.services import AttendanceWebService
from apps.core.models import AcademicSession
from apps.examinations.models import ExamType, Subject, GradingTier
from apps.examinations.services import ExamWebService
from apps.fees.models import FeeHead, PaymentMethod, PaymentStatus
from apps.fees.services import FeeWebService
from apps.students.models import ClassGroup, Enrollment, EnrollmentStatus, GroupType, Student
from apps.students.services import StudentWebService, normalize_pakistan_phone


@pytest.fixture(scope="module", autouse=True)
def setup_test_database():
    """Migrates and flushes the test database to ensure complete isolation."""
    call_command("migrate", interactive=False)
    call_command("flush", interactive=False)



# =============================================================================
# 1. StudentWebService Tests
# =============================================================================

def test_phone_normalization_logic():
    """Tests Pakistani phone number formatting and prefix standardization."""
    assert normalize_pakistan_phone("03001234567") == "03001234567"
    assert normalize_pakistan_phone("+923001234567") == "03001234567"
    assert normalize_pakistan_phone("00923001234567") == "03001234567"
    assert normalize_pakistan_phone("923001234567") == "03001234567"
    assert normalize_pakistan_phone("0300-1234567") == "03001234567"
    assert normalize_pakistan_phone("0300 1234567") == "03001234567"

    with pytest.raises(ValueError, match="Invalid Pakistani phone"):
        normalize_pakistan_phone("0421234567")
    with pytest.raises(ValueError, match="Invalid Pakistani phone"):
        normalize_pakistan_phone("12345678901")
    with pytest.raises(ValueError, match="cannot be empty"):
        normalize_pakistan_phone("")


def test_student_registration_and_admission_number_sequence():
    """Tests atomic student registration, sequential admission numbering, and enrollment creation."""
    session, _ = AcademicSession.objects.get_or_create(
        name="2026-2027 Test",
        defaults={
            "start_date": datetime.date(2026, 4, 1),
            "end_date": datetime.date(2027, 3, 31),
            "is_active": True,
        },
    )
    class_group, _ = ClassGroup.objects.get_or_create(
        session=session,
        name="Class 10",
        section_or_batch="Section Blue",
        defaults={
            "group_type": GroupType.SCHOOL_CLASS,
            "monthly_tuition_fee": Decimal("4500.00"),
        },
    )

    # First student auto-number
    student1, enr1 = StudentWebService.register_student(
        first_name="Ahmed",
        last_name="Khan",
        urdu_name="احمد خان",
        guardian_name="Tariq Khan",
        guardian_phone="+92-300-1112233",
        gender="Male",
        session_id=session.id,
        class_group_id=class_group.id,
        roll_number="101",
        custom_discount_amount=Decimal("500.00"),
    )

    assert student1.admission_number == "CF-2026-0001"
    assert student1.guardian_phone == "03001112233"
    assert enr1.student == student1
    assert enr1.class_group == class_group
    assert enr1.status == EnrollmentStatus.ACTIVE
    assert enr1.custom_discount_amount == Decimal("500.00")

    # Second student auto-number
    student2, enr2 = StudentWebService.register_student(
        first_name="Fatima",
        last_name="Ali",
        guardian_name="Ali Raza",
        guardian_phone="0300-9998877",
        gender="Female",
        session_id=session.id,
        class_group_id=class_group.id,
        roll_number="102",
    )

    assert student2.admission_number == "CF-2026-0002"
    assert student2.guardian_phone == "03009998877"


def test_student_search_and_status_update():
    """Tests multi-field Q searching and status transitions."""
    session = AcademicSession.objects.filter(name="2026-2027 Test").first()
    class_group = ClassGroup.objects.filter(session=session, name="Class 10").first()

    student, enr = StudentWebService.register_student(
        first_name="Zainab",
        last_name="Bibi",
        urdu_name="زینب بی بی",
        guardian_name="Muhammad Asif",
        guardian_phone="0312-3456789",
        gender="Female",
        session_id=session.id,
        class_group_id=class_group.id,
        roll_number="103",
    )

    # Search by Urdu script
    results = StudentWebService.search_students("زینب")
    assert any(s.id == student.id for s in results)

    # Search by phone
    results_phone = StudentWebService.search_students("03123456789")
    assert any(s.id == student.id for s in results_phone)

    # Update status to Withdrawn
    updated_enr = StudentWebService.update_student_status(enr.id, EnrollmentStatus.WITHDRAWN)
    assert updated_enr.status == EnrollmentStatus.WITHDRAWN
    student.refresh_from_db()
    assert student.is_active is False

    # Restore to Active
    restored_enr = StudentWebService.update_student_status(enr.id, EnrollmentStatus.ACTIVE)
    assert restored_enr.status == EnrollmentStatus.ACTIVE
    student.refresh_from_db()
    assert student.is_active is True


# =============================================================================
# 2. FeeWebService Tests
# =============================================================================

def test_fee_monthly_invoicing_and_balance_calculation():
    """Tests monthly batch invoice generation and fact-derived invoice balances."""
    session = AcademicSession.objects.filter(name="2026-2027 Test").first()
    class_group = ClassGroup.objects.filter(session=session, name="Class 10").first()

    # Generate invoices for 2026-05
    issue_date = datetime.date(2026, 5, 1)
    due_date = datetime.date(2026, 5, 10)
    valid_until = datetime.date(2026, 5, 20)

    count = FeeWebService.generate_monthly_invoices(
        session_id=session.id,
        month_year="2026-05",
        issue_date=issue_date,
        due_date=due_date,
        valid_until=valid_until,
        class_group_id=class_group.id,
    )
    assert count >= 2, f"Expected at least 2 invoices generated, got {count}"

    # Running again for the same month skips existing invoices (idempotent)
    repeat_count = FeeWebService.generate_monthly_invoices(
        session_id=session.id,
        month_year="2026-05",
        issue_date=issue_date,
        due_date=due_date,
        valid_until=valid_until,
        class_group_id=class_group.id,
    )
    assert repeat_count == 0


def test_payment_recording_and_receipt_sequence():
    """Tests concurrency-safe payment collection and sequential REC numbering."""
    session = AcademicSession.objects.filter(name="2026-2027 Test").first()
    student = Student.objects.filter(admission_number="CF-2026-0001").first()
    enr = student.enrollments.first()
    invoice = enr.invoices.filter(month_year="2026-05").first()

    # Initial balance check
    bal_initial = FeeWebService.calculate_invoice_balance(invoice)
    assert bal_initial["status"] == "Unpaid"
    assert bal_initial["net_due"] == Decimal("4000.00")  # 4500 tuition - 500 discount
    assert bal_initial["current_balance"] == Decimal("4000.00")

    # Partial payment
    payment1 = FeeWebService.record_payment(
        invoice_id=invoice.id,
        amount=Decimal("1500.00"),
        payment_method=PaymentMethod.CASH,
    )
    assert payment1.receipt_number == "REC-2026-00001"
    assert payment1.status == PaymentStatus.ISSUED

    bal_part = FeeWebService.calculate_invoice_balance(invoice)
    assert bal_part["status"] == "Partially Paid"
    assert bal_part["total_paid"] == Decimal("1500.00")
    assert bal_part["current_balance"] == Decimal("2500.00")

    # Second payment completing invoice
    payment2 = FeeWebService.record_payment(
        invoice_id=invoice.id,
        amount=Decimal("2500.00"),
        payment_method=PaymentMethod.BANK_TRANSFER,
    )
    assert payment2.receipt_number == "REC-2026-00002"

    bal_paid = FeeWebService.calculate_invoice_balance(invoice)
    assert bal_paid["status"] == "Paid"
    assert bal_paid["current_balance"] == Decimal("0.00")


def test_defaulters_list_query():
    """Tests overdue invoice filtering for defaulters past valid_until."""
    session = AcademicSession.objects.filter(name="2026-2027 Test").first()
    student2 = Student.objects.filter(admission_number="CF-2026-0002").first()
    enr2 = student2.enrollments.first()
    invoice2 = enr2.invoices.filter(month_year="2026-05").first()

    # Invoice 2 is completely unpaid with valid_until = 2026-05-20
    as_of = datetime.date(2026, 5, 25)
    defaulters = FeeWebService.get_defaulters_list(
        session_id=session.id,
        as_of_date=as_of,
    )
    assert any(d["invoice_id"] == invoice2.id for d in defaulters)
    # Student 1 paid in full, so not in defaulters
    assert not any(d["admission_number"] == "CF-2026-0001" for d in defaulters)


# =============================================================================
# 3. AttendanceWebService Tests
# =============================================================================

def test_attendance_roster_loading_and_bulk_upsert():
    """Tests loading roster with default Present and atomic bulk upsert."""
    session = AcademicSession.objects.filter(name="2026-2027 Test").first()
    class_group = ClassGroup.objects.filter(session=session, name="Class 10").first()

    target_date = datetime.date(2026, 5, 12)

    # Initial roster: defaults to Present
    roster_before = AttendanceWebService.load_class_roster(class_group.id, target_date)
    assert len(roster_before) >= 2
    assert all(r["status"] == AttendanceStatus.PRESENT for r in roster_before)

    # Mark first student Absent, second student Late
    entries = [
        {"enrollment_id": roster_before[0]["enrollment_id"], "status": AttendanceStatus.ABSENT, "reason_note": "Fever"},
        {"enrollment_id": roster_before[1]["enrollment_id"], "status": AttendanceStatus.LATE, "reason_note": "Bus delay"},
    ]
    count = AttendanceWebService.save_bulk_attendance(class_group.id, target_date, entries)
    assert count == 2

    # Verify reload reflects saved status
    roster_after = AttendanceWebService.load_class_roster(class_group.id, target_date)
    status_map = {r["enrollment_id"]: (r["status"], r["reason_note"]) for r in roster_after}

    enr_0 = roster_before[0]["enrollment_id"]
    enr_1 = roster_before[1]["enrollment_id"]
    assert status_map[enr_0] == (AttendanceStatus.ABSENT, "Fever")
    assert status_map[enr_1] == (AttendanceStatus.LATE, "Bus delay")

    # Upsert again on same date changing Absent to Leave (no duplicate key error)
    entries_update = [
        {"enrollment_id": enr_0, "status": AttendanceStatus.LEAVE, "reason_note": "Approved Leave"},
    ]
    AttendanceWebService.save_bulk_attendance(class_group.id, target_date, entries_update)
    roster_updated = AttendanceWebService.load_class_roster(class_group.id, target_date)
    updated_map = {r["enrollment_id"]: r["status"] for r in roster_updated}
    assert updated_map[enr_0] == AttendanceStatus.LEAVE


def test_whatsapp_absence_payload_generation():
    """Tests bilingual absence notification message assembly and wa.me URL encoding."""
    payload = AttendanceWebService.generate_whatsapp_payload(
        student_name="Ahmed Khan",
        guardian_phone="0300-1112233",
        attendance_date=datetime.date(2026, 5, 12),
        institution_name="Punjab Public School",
        urdu_name="احمد خان",
    )
    assert payload["phone"] == "03001112233"
    assert "https://wa.me/923001112233" in payload["whatsapp_url"]
    assert "Punjab Public School" in payload["message_text"]
    assert "احمد خان" in payload["message_text"]


# =============================================================================
# 4. ExamWebService Tests
# =============================================================================

def test_exam_marks_recording_bounds_and_ranking():
    """Tests marks recording, bounds validation, and joint competition ranking."""
    session = AcademicSession.objects.filter(name="2026-2027 Test").first()
    class_group = ClassGroup.objects.filter(session=session, name="Class 10").first()

    # Create Grading Tiers
    GradingTier.objects.get_or_create(session=session, grade_name="A+", defaults={"min_percentage": Decimal("90.00"), "max_percentage": Decimal("100.00"), "gpa_point": Decimal("4.00"), "is_passing": True})
    GradingTier.objects.get_or_create(session=session, grade_name="A", defaults={"min_percentage": Decimal("80.00"), "max_percentage": Decimal("89.99"), "gpa_point": Decimal("3.70"), "is_passing": True})
    GradingTier.objects.get_or_create(session=session, grade_name="B", defaults={"min_percentage": Decimal("70.00"), "max_percentage": Decimal("79.99"), "gpa_point": Decimal("3.00"), "is_passing": True})
    GradingTier.objects.get_or_create(session=session, grade_name="F", defaults={"min_percentage": Decimal("0.00"), "max_percentage": Decimal("32.99"), "gpa_point": Decimal("0.00"), "is_passing": False})

    math, _ = Subject.objects.get_or_create(name="Mathematics", defaults={"code": "MTH-10"})
    eng, _ = Subject.objects.get_or_create(name="English", defaults={"code": "ENG-10"})

    from apps.examinations.models import Exam, ExamSubject
    exam, _ = Exam.objects.get_or_create(
        session=session,
        name="First Term 2026",
        defaults={
            "exam_type": ExamType.TERM_EXAM,
            "start_date": datetime.date(2026, 6, 1),
            "end_date": datetime.date(2026, 6, 15),
        },
    )

    es_math, _ = ExamSubject.objects.get_or_create(
        exam=exam,
        class_group=class_group,
        subject=math,
        defaults={"maximum_marks": Decimal("100.00"), "passing_marks": Decimal("33.00")},
    )
    es_eng, _ = ExamSubject.objects.get_or_create(
        exam=exam,
        class_group=class_group,
        subject=eng,
        defaults={"maximum_marks": Decimal("50.00"), "passing_marks": Decimal("17.00")},
    )

    student1 = Student.objects.filter(admission_number="CF-2026-0001").first()
    student2 = Student.objects.filter(admission_number="CF-2026-0002").first()
    enr1 = student1.enrollments.first()
    enr2 = student2.enrollments.first()

    # Valid marks
    ExamWebService.record_student_marks(exam_subject_id=es_math.id, enrollment_id=enr1.id, marks_obtained=Decimal("95.00"))
    ExamWebService.record_student_marks(exam_subject_id=es_eng.id, enrollment_id=enr1.id, marks_obtained=Decimal("45.00"))

    # Student 2 marks (exact tie on math, different on eng)
    ExamWebService.record_student_marks(exam_subject_id=es_math.id, enrollment_id=enr2.id, marks_obtained=Decimal("80.00"))
    ExamWebService.record_student_marks(exam_subject_id=es_eng.id, enrollment_id=enr2.id, marks_obtained=Decimal("40.00"))

    # Upper bound violation test
    with pytest.raises(ValueError, match="exceeds maximum marks"):
        ExamWebService.record_student_marks(exam_subject_id=es_eng.id, enrollment_id=enr1.id, marks_obtained=Decimal("55.00"))

    # Calculate class rankings
    results = ExamWebService.calculate_class_results(exam_id=exam.id, class_group_id=class_group.id)
    assert len(results) >= 2

    # Student 1: 95 + 45 = 140 / 150 = 93.33% -> Rank 1, Grade A+
    top_student = results[0]
    assert top_student["admission_number"] == "CF-2026-0001"
    assert top_student["total_obtained"] == Decimal("140.00")
    assert top_student["percentage"] == Decimal("93.33")
    assert top_student["grade"] == "A+"
    assert top_student["rank"] == 1

    # Student 2: 80 + 40 = 120 / 150 = 80.00% -> Rank 2, Grade A
    second_student = results[1]
    assert second_student["admission_number"] == "CF-2026-0002"
    assert second_student["total_obtained"] == Decimal("120.00")
    assert second_student["percentage"] == Decimal("80.00")
    assert second_student["grade"] == "A"
    assert second_student["rank"] == 2
