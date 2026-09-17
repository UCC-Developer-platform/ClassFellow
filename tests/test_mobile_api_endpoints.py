"""
tests/test_mobile_api_endpoints.py
==================================
Automated verification test suite for Category 15:
- Mobile API Gateway & Headless REST Services:
  1. Token authentication (/api/v1/auth/login/) and gating (401 Unauthorized).
  2. Teacher mobile REST API: class/subject allocations, rosters, bulk attendance upserts,
     and marks entry with bounds validation (0 <= marks <= max_marks).
  3. Parent portal REST API: student discovery across campuses by phone, fee invoice/payment history,
     monthly attendance log/metrics, and examination scorecards with class ranking.
  4. Strict IDOR parent-child ownership verification (403 Forbidden on guardian phone mismatch).
"""

import datetime
from decimal import Decimal
import os
import pytest

os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
os.environ["DJANGO_DB_ENGINE"] = "sqlite"

import django  # noqa: E402
django.setup()

from django.core.management import call_command  # noqa: E402
from rest_framework.authtoken.models import Token  # noqa: E402
from rest_framework.test import APIClient  # noqa: E402

from apps.accounts.models import Role, User  # noqa: E402
from apps.attendance.models import AttendanceRecord, AttendanceStatus  # noqa: E402
from apps.core.models import AcademicSession, Campus  # noqa: E402
from apps.examinations.models import Exam, ExamSubject, ExamType, GradingTier, Mark, Subject  # noqa: E402
from apps.fees.models import FeeHead, FeeInvoice, FeeInvoiceItem, Payment, PaymentMethod, PaymentStatus  # noqa: E402
from apps.staff.models import Staff, StaffSubjectAllocation  # noqa: E402
from apps.students.models import ClassGroup, Enrollment, EnrollmentStatus, Gender, GroupType, Student  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def setup_api_database():
    """Migrates the test database to ensure all tables exist."""
    call_command("migrate", interactive=False)


@pytest.fixture(autouse=True)
def clean_database():
    """Isolate tests from stale records."""
    Mark.objects.all().delete()
    ExamSubject.objects.all().delete()
    GradingTier.objects.all().delete()
    Exam.objects.all().delete()
    AttendanceRecord.objects.all().delete()
    Payment.objects.all().delete()
    FeeInvoiceItem.objects.all().delete()
    FeeInvoice.objects.all().delete()
    FeeHead.objects.all().delete()
    Enrollment.objects.all().delete()
    StaffSubjectAllocation.objects.all().delete()
    Staff.objects.all().delete()
    Student.objects.all().delete()
    ClassGroup.objects.all().delete()
    Subject.objects.all().delete()
    Campus.objects.filter(code__startswith="CAMPUS-").delete()
    User.objects.filter(username__startswith="api_").delete()
    Token.objects.all().delete()
    yield


@pytest.fixture
def campus_fixture():
    campus, _ = Campus.objects.get_or_create(
        code="CAMPUS-API",
        defaults={
            "name": "API Model Campus",
            "address": "Campus Boulevard, Lahore",
            "phone": "04231122334",
            "is_active": True,
        },
    )
    return campus


@pytest.fixture
def session_fixture():
    session, _ = AcademicSession.objects.get_or_create(
        name="2026-2027 API Session",
        defaults={
            "start_date": datetime.date(2026, 4, 1),
            "end_date": datetime.date(2027, 3, 31),
            "is_active": True,
        },
    )
    return session


@pytest.fixture
def class_fixture(campus_fixture, session_fixture):
    cg, _ = ClassGroup.objects.get_or_create(
        name="Class 9",
        section_or_batch="Section A",
        session=session_fixture,
        defaults={
            "campus": campus_fixture,
            "group_type": GroupType.SCHOOL_CLASS,
            "monthly_tuition_fee": Decimal("5000.00"),
        },
    )
    return cg


@pytest.fixture
def subject_fixture():
    sub, _ = Subject.objects.get_or_create(
        code="CS-9",
        defaults={"name": "Computer Science"},
    )
    return sub


@pytest.fixture
def teacher_user(campus_fixture):
    user = User.objects.create_user(
        username="api_teacher_khan",
        password="TeacherPass123!",
        role=Role.TEACHER,
        first_name="Zubair",
        last_name="Khan",
        phone="03007654321",
    )
    staff = Staff.objects.create(
        user=user,
        employee_id="EMP-API-01",
        first_name="Zubair",
        last_name="Khan",
        urdu_name="زبیر خان",
        designation="Senior Science Teacher",
        department="Computer Science",
        campus=campus_fixture,
        phone="03007654321",
        basic_salary=Decimal("60000.00"),
    )
    token = Token.objects.create(user=user)
    return user, staff, token


@pytest.fixture
def parent_user():
    user = User.objects.create_user(
        username="api_parent_tariq",
        password="ParentPass123!",
        role=Role.PARENT,
        first_name="Tariq",
        last_name="Mehmood",
        phone="03001234567",
    )
    token = Token.objects.create(user=user)
    return user, token


@pytest.fixture
def student_and_enrollment(class_fixture, session_fixture):
    student = Student.objects.create(
        admission_number="CF-API-101",
        first_name="Hamza",
        last_name="Tariq",
        urdu_name="حمزہ طارق",
        gender=Gender.MALE,
        guardian_name="Tariq Mehmood",
        guardian_phone="03001234567",
    )
    enrollment = Enrollment.objects.create(
        student=student,
        class_group=class_fixture,
        session=session_fixture,
        roll_number="01",
        status=EnrollmentStatus.ACTIVE,
    )
    return student, enrollment


# =============================================================================
# 1. Authentication & Token Gating Tests (Task API-01)
# =============================================================================

def test_unauthenticated_requests_return_401():
    """Verifies that endpoints gated by IsAuthenticated reject unauthenticated calls."""
    client = APIClient()
    protected_endpoints = [
        ("get", "/api/v1/teacher/classes/"),
        ("get", "/api/v1/teacher/roster/?class_group_id=1"),
        ("post", "/api/v1/teacher/attendance/save/"),
        ("post", "/api/v1/teacher/marks/save/"),
        ("get", "/api/v1/parent/children/"),
        ("get", "/api/v1/parent/fees/?enrollment_id=1"),
        ("get", "/api/v1/parent/attendance/?enrollment_id=1"),
        ("get", "/api/v1/parent/report-card/?enrollment_id=1"),
    ]
    for method, path in protected_endpoints:
        if method == "get":
            resp = client.get(path)
        else:
            resp = client.post(path, {}, format="json")
        assert resp.status_code == 401, f"Expected 401 on {path}, got {resp.status_code}"


def test_auth_login_validation_and_token_issuance(teacher_user):
    """Verifies login endpoint credentials validation, token retrieval, and role profile."""
    client = APIClient()

    # Empty payload
    resp_empty = client.post("/api/v1/auth/login/", {}, format="json")
    assert resp_empty.status_code == 400
    assert "required" in resp_empty.data["error"]

    # Invalid credentials
    resp_bad = client.post(
        "/api/v1/auth/login/",
        {"username": "api_teacher_khan", "password": "WrongPassword!"},
        format="json",
    )
    assert resp_bad.status_code == 401
    assert "Invalid username or password" in resp_bad.data["error"]

    # Valid credentials
    resp_ok = client.post(
        "/api/v1/auth/login/",
        {"username": "api_teacher_khan", "password": "TeacherPass123!"},
        format="json",
    )
    assert resp_ok.status_code == 200
    data = resp_ok.data
    assert "token" in data
    assert data["username"] == "api_teacher_khan"
    assert data["role"] == Role.TEACHER
    assert data["full_name"] == "Zubair Khan"


def test_auth_login_inactive_user_rejection():
    """Verifies that deactivated users receive 403 Forbidden on login."""
    client = APIClient()
    User.objects.create_user(
        username="api_inactive_staff",
        password="SecretPassword123!",
        is_active=False,
    )
    resp = client.post(
        "/api/v1/auth/login/",
        {"username": "api_inactive_staff", "password": "SecretPassword123!"},
        format="json",
    )
    assert resp.status_code == 403
    assert "inactive" in resp.data["error"]


# =============================================================================
# 2. Teacher Mobile REST Services Tests (Task API-02)
# =============================================================================

def test_teacher_assigned_classes_and_roster_view(
    teacher_user, parent_user, class_fixture, subject_fixture, session_fixture, student_and_enrollment
):
    """Verifies teacher class allocations listing and student attendance roster."""
    user, staff, token = teacher_user
    p_user, p_token = parent_user
    student, enrollment = student_and_enrollment

    # Create allocation
    StaffSubjectAllocation.objects.create(
        staff=staff,
        class_group=class_fixture,
        subject=subject_fixture,
        academic_session=session_fixture,
    )

    client = APIClient()

    # Non-staff parent receives 403
    client.credentials(HTTP_AUTHORIZATION=f"Token {p_token.key}")
    resp_forbidden = client.get("/api/v1/teacher/classes/")
    assert resp_forbidden.status_code == 403

    # Teacher receives assigned classes
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    resp_classes = client.get("/api/v1/teacher/classes/")
    assert resp_classes.status_code == 200
    classes_data = resp_classes.data
    assert len(classes_data) == 1
    assert classes_data[0]["class_group"]["name"] == "Class 9"
    assert classes_data[0]["subject"]["name"] == "Computer Science"

    # Teacher loads attendance roster
    resp_roster = client.get(
        f"/api/v1/teacher/roster/?class_group_id={class_fixture.id}&date=2026-09-17"
    )
    assert resp_roster.status_code == 200
    roster_data = resp_roster.data
    assert roster_data["total_students"] == 1
    assert roster_data["roster"][0]["admission_number"] == "CF-API-101"
    # Unrecorded status defaults to Present
    assert roster_data["roster"][0]["status"] == AttendanceStatus.PRESENT


def test_teacher_bulk_attendance_save(
    teacher_user, class_fixture, subject_fixture, session_fixture, student_and_enrollment
):
    """Verifies bulk attendance submission and database upsert."""
    user, staff, token = teacher_user
    student, enrollment = student_and_enrollment

    StaffSubjectAllocation.objects.create(
        staff=staff,
        class_group=class_fixture,
        subject=subject_fixture,
        academic_session=session_fixture,
    )

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    payload = {
        "class_group_id": class_fixture.id,
        "attendance_date": "2026-09-17",
        "attendance_entries": [
            {
                "enrollment_id": enrollment.id,
                "status": AttendanceStatus.ABSENT,
                "reason_note": "Medical Leave",
            }
        ],
    }
    resp = client.post("/api/v1/teacher/attendance/save/", payload, format="json")
    assert resp.status_code == 200
    assert resp.data["saved_count"] == 1

    # Verify database persistence and user attribution
    rec = AttendanceRecord.objects.get(
        enrollment=enrollment, attendance_date=datetime.date(2026, 9, 17)
    )
    assert rec.status == AttendanceStatus.ABSENT
    assert rec.reason_note == "Medical Leave"
    assert rec.recorded_by_user_id == user.id


def test_teacher_marks_save_and_bounds_validation(
    teacher_user, class_fixture, subject_fixture, session_fixture, student_and_enrollment
):
    """Verifies teacher marks entry and strict upper/lower bound enforcement (0 <= marks <= max)."""
    user, staff, token = teacher_user
    student, enrollment = student_and_enrollment

    StaffSubjectAllocation.objects.create(
        staff=staff,
        class_group=class_fixture,
        subject=subject_fixture,
        academic_session=session_fixture,
    )

    exam = Exam.objects.create(
        session=session_fixture,
        name="Midterm Exam 2026",
        exam_type=ExamType.TERM_EXAM,
        start_date=datetime.date(2026, 9, 1),
        end_date=datetime.date(2026, 9, 15),
    )
    exam_sub = ExamSubject.objects.create(
        exam=exam,
        class_group=class_fixture,
        subject=subject_fixture,
        maximum_marks=Decimal("75.00"),
        passing_marks=Decimal("25.00"),
    )

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    # Exceeding maximum marks: 80 / 75 -> 400 Bad Request
    payload_overflow = {
        "exam_subject_id": exam_sub.id,
        "enrollment_id": enrollment.id,
        "marks_obtained": "80.00",
        "is_absent": False,
    }
    resp_overflow = client.post("/api/v1/teacher/marks/save/", payload_overflow, format="json")
    assert resp_overflow.status_code == 400
    assert "exceeds maximum marks" in resp_overflow.data["error"]

    # Negative marks: -5.00 -> 400 Bad Request
    payload_negative = {
        "exam_subject_id": exam_sub.id,
        "enrollment_id": enrollment.id,
        "marks_obtained": "-5.00",
        "is_absent": False,
    }
    resp_negative = client.post("/api/v1/teacher/marks/save/", payload_negative, format="json")
    assert resp_negative.status_code == 400
    assert "cannot be negative" in resp_negative.data["error"]

    # Valid marks: 68.50 -> 200 OK
    payload_valid = {
        "exam_subject_id": exam_sub.id,
        "enrollment_id": enrollment.id,
        "marks_obtained": "68.50",
        "is_absent": False,
        "remarks": "Great performance",
    }
    resp_valid = client.post("/api/v1/teacher/marks/save/", payload_valid, format="json")
    assert resp_valid.status_code == 200
    assert resp_valid.data["recorded_count"] == 1

    # Verify mark saved in DB
    mark = Mark.objects.get(exam_subject=exam_sub, enrollment=enrollment)
    assert mark.marks_obtained == Decimal("68.50")
    assert mark.recorded_by_user_id == user.id


# =============================================================================
# 3. Parent Portal REST Services Tests (Task API-03)
# =============================================================================

def test_parent_children_discovery_across_campuses(
    parent_user, campus_fixture, session_fixture, student_and_enrollment
):
    """Verifies that a parent discovers all enrolled children matching guardian phone across campuses."""
    p_user, p_token = parent_user
    student, enrollment = student_and_enrollment

    # Create second campus and second child for the same parent (phone: 03001234567)
    campus_b, _ = Campus.objects.get_or_create(
        code="CAMPUS-GIRLS",
        defaults={
            "name": "Junior Girls Branch",
            "phone": "04239988776",
            "is_active": True,
        },
    )
    class_b = ClassGroup.objects.create(
        name="Class 5",
        section_or_batch="Section B",
        session=session_fixture,
        campus=campus_b,
    )
    student_b = Student.objects.create(
        admission_number="CF-API-102",
        first_name="Fatima",
        last_name="Tariq",
        gender=Gender.FEMALE,
        guardian_name="Tariq Mehmood",
        # Test Pakistani phone format tolerance: +92-300-1234567
        guardian_phone="+92-300-1234567",
    )
    Enrollment.objects.create(
        student=student_b,
        class_group=class_b,
        session=session_fixture,
        roll_number="12",
        status=EnrollmentStatus.ACTIVE,
    )

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {p_token.key}")

    resp = client.get("/api/v1/parent/children/")
    assert resp.status_code == 200
    children = resp.data
    assert len(children) == 2
    adm_nos = [c["admission_number"] for c in children]
    assert "CF-API-101" in adm_nos
    assert "CF-API-102" in adm_nos

    campuses = {c["campus_name"] for c in children}
    assert "API Model Campus" in campuses
    assert "Junior Girls Branch" in campuses


def test_parent_fee_summary_and_idor_protection(
    parent_user, session_fixture, student_and_enrollment
):
    """Verifies parent fee invoice and receipt summaries, and strict IDOR access rejection."""
    p_user, p_token = parent_user
    student, enrollment = student_and_enrollment

    # Setup fee head, invoice, and payment
    fh, _ = FeeHead.objects.get_or_create(name="Tuition Fee API")
    invoice = FeeInvoice.objects.create(
        enrollment=enrollment,
        session=session_fixture,
        month_year="2026-09",
        issue_date=datetime.date(2026, 9, 1),
        due_date=datetime.date(2026, 9, 10),
        valid_until=datetime.date(2026, 9, 20),
        total_payable=Decimal("5000.00"),
        discount_amount=Decimal("500.00"),
        net_due=Decimal("4500.00"),
    )
    FeeInvoiceItem.objects.create(invoice=invoice, fee_head=fh, amount=Decimal("5000.00"))
    Payment.objects.create(
        invoice=invoice,
        amount=Decimal("4500.00"),
        receipt_number="REC-API-001",
        payment_method=PaymentMethod.CASH,
        status=PaymentStatus.ISSUED,
    )

    # Authorized parent access
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {p_token.key}")

    resp_auth = client.get(f"/api/v1/parent/fees/?enrollment_id={enrollment.id}")
    assert resp_auth.status_code == 200
    fee_data = resp_auth.data
    assert fee_data["total_billed"] == "4500.00"
    assert fee_data["total_paid"] == "4500.00"
    assert fee_data["total_outstanding"] == "0.00"
    assert len(fee_data["invoices"]) == 1
    assert fee_data["invoices"][0]["is_paid"] is True
    assert len(fee_data["payments"]) == 1
    assert fee_data["payments"][0]["receipt_number"] == "REC-API-001"

    # IDOR Security Check: Another guardian attempts to view this enrollment
    other_parent = User.objects.create_user(
        username="api_parent_other",
        password="OtherPass123!",
        role=Role.PARENT,
        phone="03009998877",  # Different phone
    )
    other_token = Token.objects.create(user=other_parent)

    client.credentials(HTTP_AUTHORIZATION=f"Token {other_token.key}")
    resp_idor = client.get(f"/api/v1/parent/fees/?enrollment_id={enrollment.id}")
    assert resp_idor.status_code == 403
    assert "Access denied" in resp_idor.data["error"]


def test_parent_attendance_view_and_metrics(parent_user, student_and_enrollment):
    """Verifies parent monthly attendance calendar, day counts, and percentage calculation."""
    p_user, p_token = parent_user
    student, enrollment = student_and_enrollment

    # Create 4 days of attendance: 3 Present, 1 Absent (75.0% attendance)
    for day, st in [(1, AttendanceStatus.PRESENT), (2, AttendanceStatus.PRESENT),
                    (3, AttendanceStatus.PRESENT), (4, AttendanceStatus.ABSENT)]:
        AttendanceRecord.objects.create(
            enrollment=enrollment,
            attendance_date=datetime.date(2026, 9, day),
            status=st,
            reason_note="Fever" if st == AttendanceStatus.ABSENT else "",
        )

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {p_token.key}")

    resp = client.get(f"/api/v1/parent/attendance/?enrollment_id={enrollment.id}&month_year=2026-09")
    assert resp.status_code == 200
    att_data = resp.data
    assert att_data["total_days"] == 4
    assert att_data["present_days"] == 3
    assert att_data["absent_days"] == 1
    assert att_data["attendance_percentage"] == "75.0"
    assert len(att_data["records"]) == 4


def test_parent_report_card_view_and_rankings(
    parent_user, class_fixture, session_fixture, student_and_enrollment
):
    """Verifies parent report card examination scorecards, letter grades, and joint class rank."""
    p_user, p_token = parent_user
    student, enrollment = student_and_enrollment

    # Create Grading Tier
    GradingTier.objects.create(
        session=session_fixture,
        grade_name="A+",
        min_percentage=Decimal("80.00"),
        max_percentage=Decimal("100.00"),
        gpa_point=Decimal("4.00"),
    )

    exam = Exam.objects.create(
        session=session_fixture,
        name="Annual Final 2026",
        exam_type=ExamType.ANNUAL_EXAM,
        start_date=datetime.date(2026, 6, 1),
        end_date=datetime.date(2026, 6, 15),
    )
    sub_math = Subject.objects.create(code="MTH-9", name="Mathematics")
    es_math = ExamSubject.objects.create(
        exam=exam,
        class_group=class_fixture,
        subject=sub_math,
        maximum_marks=Decimal("100.00"),
        passing_marks=Decimal("33.00"),
    )
    Mark.objects.create(
        exam_subject=es_math,
        enrollment=enrollment,
        marks_obtained=Decimal("88.00"),
    )

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {p_token.key}")

    resp = client.get(f"/api/v1/parent/report-card/?enrollment_id={enrollment.id}&exam_id={exam.id}")
    assert resp.status_code == 200
    rc = resp.data
    assert rc["student"]["admission_number"] == "CF-API-101"
    assert rc["exam"]["name"] == "Annual Final 2026"
    assert rc["summary"]["total_obtained"] == "88.00"
    assert rc["summary"]["percentage"] == "88.00"
    assert rc["summary"]["letter_grade"] == "A+"
    assert rc["summary"]["class_rank"] == 1
    assert len(rc["subjects"]) == 1
    assert rc["subjects"][0]["is_passed"] is True
