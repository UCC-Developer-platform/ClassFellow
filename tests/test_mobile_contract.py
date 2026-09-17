"""
tests/test_mobile_contract.py
=============================
Cross-Platform Mobile Contract Verification Test Suite for Category 16.
Verifies that the backend REST API payload structures, field keys, and data types
strictly satisfy the Flutter Mobile Client (classfellow_mobile) model contracts:
- UserSession Contract
- TeacherAllocation & RosterResponse Contracts
- TeacherAttendanceSave & TeacherMarksSave Contracts
- ChildProfile Contract
- FeeSummaryResponse Contract
- AttendanceSummaryResponse Contract
- ReportCardResponse Contract
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
    call_command("migrate", interactive=False)


@pytest.fixture(autouse=True)
def clean_database():
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
    User.objects.filter(username__startswith="contract_").delete()
    Token.objects.all().delete()
    yield


@pytest.fixture
def campus_fixture():
    campus, _ = Campus.objects.get_or_create(
        code="CAMPUS-CONTRACT",
        defaults={
            "name": "Contract Model Campus",
            "address": "Sector G-10/4, Islamabad",
            "phone": "0512233445",
            "is_active": True,
        },
    )
    return campus


@pytest.fixture
def session_fixture():
    session, _ = AcademicSession.objects.get_or_create(
        name="2026-2027 Mobile Session",
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
        name="Class 10",
        section_or_batch="Section A",
        session=session_fixture,
        defaults={
            "campus": campus_fixture,
            "group_type": GroupType.SCHOOL_CLASS,
        },
    )
    return cg


@pytest.fixture
def subject_fixture():
    sub, _ = Subject.objects.get_or_create(
        name="Computer Science",
        defaults={"code": "CS-10"},
    )
    return sub


@pytest.fixture
def teacher_fixture(campus_fixture, class_fixture, subject_fixture, session_fixture):
    user = User.objects.create_user(
        username="contract_teacher_usman",
        password="ValidPassword123!",
        first_name="Usman",
        last_name="Tariq",
        role=Role.TEACHER,
    )
    staff = Staff.objects.create(
        employee_id="EMP-CONTRACT-01",
        first_name="Usman",
        last_name="Tariq",
        designation="Lecturer",
        department="Computer Science",
        campus=campus_fixture,
        basic_salary=Decimal("65000.00"),
        joining_date=datetime.date(2024, 1, 1),
        user=user,
    )
    StaffSubjectAllocation.objects.create(
        staff=staff,
        class_group=class_fixture,
        subject=subject_fixture,
        academic_session=session_fixture,
    )
    token, _ = Token.objects.get_or_create(user=user)
    return user, staff, token


@pytest.fixture
def parent_and_student_fixture(campus_fixture, class_fixture, session_fixture):
    user = User.objects.create_user(
        username="contract_parent_rashid",
        password="ValidPassword123!",
        first_name="Rashid",
        last_name="Minhas",
        phone="03001234567",
        role=Role.PARENT,
    )
    student = Student.objects.create(
        first_name="Hamza",
        last_name="Rashid",
        date_of_birth=datetime.date(2010, 8, 15),
        gender=Gender.MALE,
        admission_number="ADM-MOB-2026-01",
        guardian_name="Rashid Minhas",
        guardian_phone="03001234567",
    )
    enrollment = Enrollment.objects.create(
        student=student,
        class_group=class_fixture,
        session=session_fixture,
        roll_number="10-A-01",
        status=EnrollmentStatus.ACTIVE,
    )
    token, _ = Token.objects.get_or_create(user=user)
    return user, student, enrollment, token


def test_mobile_contract_auth_login(teacher_fixture):
    """
    Contract 1: Mobile Auth Response Contract
    Flutter UserSession expects:
    token: str, user_id: int, username: str, role: str, full_name: str
    """
    user, _, _ = teacher_fixture
    client = APIClient()

    resp = client.post(
        "/api/v1/auth/login/",
        {"username": user.username, "password": "ValidPassword123!"},
        format="json",
    )
    assert resp.status_code == 200
    data = resp.json()

    # Exact field contract check
    assert isinstance(data["token"], str) and len(data["token"]) > 0
    assert isinstance(data["user_id"], int)
    assert data["username"] == user.username
    assert data["role"] == Role.TEACHER
    assert data["full_name"] == "Usman Tariq"


def test_mobile_contract_teacher_assigned_classes(teacher_fixture):
    """
    Contract 2: Teacher Assigned Classes Contract
    Flutter TeacherAllocation model structure:
    - allocation_id: int
    - class_group: {id: int, name: str, section: str, campus_name: str}
    - subject: {id: int, name: str, code: str}
    - academic_session: {id: int, name: str}
    """
    _, _, token = teacher_fixture
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    resp = client.get("/api/v1/teacher/classes/")
    assert resp.status_code == 200
    allocations = resp.json()

    assert isinstance(allocations, list)
    assert len(allocations) >= 1
    alloc = allocations[0]

    # Verify keys matching TeacherAllocation.fromJson
    assert isinstance(alloc["allocation_id"], int)
    assert "class_group" in alloc
    assert isinstance(alloc["class_group"]["id"], int)
    assert isinstance(alloc["class_group"]["name"], str)
    assert isinstance(alloc["class_group"]["section"], str)
    assert alloc["class_group"]["campus_name"] == "Contract Model Campus"

    assert "subject" in alloc
    assert isinstance(alloc["subject"]["id"], int)
    assert alloc["subject"]["name"] == "Computer Science"
    assert alloc["subject"]["code"] == "CS-10"

    assert "academic_session" in alloc
    assert isinstance(alloc["academic_session"]["id"], int)
    assert alloc["academic_session"]["name"] == "2026-2027 Mobile Session"


def test_mobile_contract_teacher_roster(teacher_fixture, parent_and_student_fixture):
    """
    Contract 3: Teacher Roster Contract
    Flutter RosterResponse model structure:
    - class_group_id: int
    - attendance_date: str (YYYY-MM-DD)
    - total_students: int
    - roster: List[RosterStudent]
      - enrollment_id: int
      - student_id: int
      - student_name: str
      - roll_number: str
      - admission_number: str
      - status: str
    """
    _, _, token = teacher_fixture
    _, _, enrollment, _ = parent_and_student_fixture
    class_group = enrollment.class_group

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    resp = client.get(
        "/api/v1/teacher/roster/",
        {"class_group_id": class_group.id, "date": "2026-09-17"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["class_group_id"] == class_group.id
    assert data["attendance_date"] == "2026-09-17"
    assert data["total_students"] == 1
    assert isinstance(data["roster"], list)
    assert len(data["roster"]) == 1

    student_item = data["roster"][0]
    assert student_item["enrollment_id"] == enrollment.id
    assert student_item["student_id"] == enrollment.student.id
    assert student_item["student_name"] == "Hamza Rashid"
    assert student_item["roll_number"] == "10-A-01"
    assert student_item["admission_number"] == "ADM-MOB-2026-01"


def test_mobile_contract_teacher_attendance_save(teacher_fixture, parent_and_student_fixture):
    """
    Contract 4: Teacher Attendance Bulk Save Contract
    Payload format sent by Flutter AttendanceRosterScreen:
    {
      "class_group_id": int,
      "attendance_date": "YYYY-MM-DD",
      "attendance_entries": [
        {"enrollment_id": int, "status": "Present", "reason_note": ""}
      ]
    }
    """
    _, _, token = teacher_fixture
    _, _, enrollment, _ = parent_and_student_fixture

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    payload = {
        "class_group_id": enrollment.class_group.id,
        "attendance_date": "2026-09-17",
        "attendance_entries": [
            {
                "enrollment_id": enrollment.id,
                "status": "Present",
                "reason_note": "On time in lab",
            }
        ],
    }

    resp = client.post("/api/v1/teacher/attendance/save/", payload, format="json")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["saved_count"] == 1

    # Verify DB persistence
    record = AttendanceRecord.objects.get(
        enrollment=enrollment, attendance_date=datetime.date(2026, 9, 17)
    )
    assert record.status == AttendanceStatus.PRESENT


def test_mobile_contract_teacher_marks_save(
    teacher_fixture, parent_and_student_fixture, session_fixture, subject_fixture
):
    """
    Contract 5: Teacher Marks Save Batch Contract
    Accepts batch payload:
    {"marks": [{"exam_subject_id": int, "enrollment_id": int, "marks_obtained": str, "is_absent": bool, "remarks": str}]}
    Enforces bounds validation ($0 <= marks <= max_marks$).
    """
    _, _, token = teacher_fixture
    _, _, enrollment, _ = parent_and_student_fixture

    exam = Exam.objects.create(
        name="Contract Midterms 2026",
        session=session_fixture,
        exam_type=ExamType.TERM_EXAM,
        start_date=datetime.date(2026, 10, 1),
        end_date=datetime.date(2026, 10, 15),
    )
    exam_subject = ExamSubject.objects.create(
        exam=exam,
        class_group=enrollment.class_group,
        subject=subject_fixture,
        maximum_marks=Decimal("100.00"),
        passing_marks=Decimal("33.00"),
    )

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    # 1. Reject out-of-bounds marks (> 100)
    invalid_batch = {
        "marks": [
            {
                "exam_subject_id": exam_subject.id,
                "enrollment_id": enrollment.id,
                "marks_obtained": "125.00",
                "is_absent": False,
                "remarks": "Invalid high",
            }
        ]
    }
    fail_resp = client.post("/api/v1/teacher/marks/save/", invalid_batch, format="json")
    assert fail_resp.status_code == 400

    # 2. Accept valid batch marks
    valid_batch = {
        "marks": [
            {
                "exam_subject_id": exam_subject.id,
                "enrollment_id": enrollment.id,
                "marks_obtained": "92.50",
                "is_absent": False,
                "remarks": "Exceptional coding skills",
            }
        ]
    }
    success_resp = client.post("/api/v1/teacher/marks/save/", valid_batch, format="json")
    assert success_resp.status_code == 200
    data = success_resp.json()
    assert data["status"] == "success"
    assert data["recorded_count"] == 1


def test_mobile_contract_parent_children(parent_and_student_fixture):
    """
    Contract 6: Parent Children Discovery Contract
    Flutter ChildProfile model:
    - enrollment_id: int
    - student_id: int
    - full_name: str
    - admission_number: str
    - roll_number: str
    - class_name: str
    - section: str
    - campus_name: str
    """
    _, student, enrollment, token = parent_and_student_fixture

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    resp = client.get("/api/v1/parent/children/")
    assert resp.status_code == 200
    children = resp.json()

    assert isinstance(children, list)
    assert len(children) == 1
    child = children[0]

    assert child["enrollment_id"] == enrollment.id
    assert child["student_id"] == student.id
    assert child["full_name"] == "Hamza Rashid"
    assert child["admission_number"] == "ADM-MOB-2026-01"
    assert child["roll_number"] == "10-A-01"
    assert child["class_name"] == "Class 10"
    assert child["section"] == "Section A"
    assert child["campus_name"] == "Contract Model Campus"


def test_mobile_contract_parent_fee_summary(parent_and_student_fixture, session_fixture):
    """
    Contract 7: Parent Fee Summary Contract
    Flutter FeeSummaryResponse model:
    - total_billed: float/str
    - total_paid: float/str
    - total_outstanding: float/str
    - invoices: List[FeeInvoiceRecord]
    - payments: List[PaymentReceiptRecord]
    """
    _, _, enrollment, token = parent_and_student_fixture

    # Create test invoice and payment
    head, _ = FeeHead.objects.get_or_create(name="Tuition Fee")
    invoice = FeeInvoice.objects.create(
        enrollment=enrollment,
        session=session_fixture,
        month_year="2026-09",
        issue_date=datetime.date(2026, 9, 1),
        due_date=datetime.date(2026, 9, 10),
        valid_until=datetime.date(2026, 9, 20),
        total_payable=Decimal("12000.00"),
        net_due=Decimal("12000.00"),
    )
    FeeInvoiceItem.objects.create(
        invoice=invoice, fee_head=head, amount=Decimal("12000.00")
    )
    Payment.objects.create(
        invoice=invoice,
        amount=Decimal("8000.00"),
        receipt_number="REC-CONTRACT-001",
        payment_method=PaymentMethod.CASH,
        status=PaymentStatus.ISSUED,
    )

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    resp = client.get(
        "/api/v1/parent/fees/",
        {"enrollment_id": enrollment.id},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert Decimal(str(data["total_billed"])) == Decimal("12000.00")
    assert Decimal(str(data["total_paid"])) == Decimal("8000.00")
    assert Decimal(str(data["total_outstanding"])) == Decimal("4000.00")

    assert len(data["invoices"]) == 1
    inv = data["invoices"][0]
    assert inv["invoice_id"] == invoice.id
    assert inv["month_year"] == "2026-09"
    assert Decimal(str(inv["net_due"])) == Decimal("12000.00")
    assert inv["is_paid"] is False

    assert len(data["payments"]) == 1
    pmt = data["payments"][0]
    assert pmt["receipt_number"] == "REC-CONTRACT-001"
    assert Decimal(str(pmt["amount"])) == Decimal("8000.00")


def test_mobile_contract_parent_attendance_summary(parent_and_student_fixture):
    """
    Contract 8: Parent Attendance Contract
    Flutter AttendanceSummaryResponse:
    - month_year: str
    - total_days: int
    - present_days: int
    - absent_days: int
    - leave_days: int
    - late_days: int
    - attendance_percentage: float/str
    - records: List[AttendanceRecordItem]
    """
    _, _, enrollment, token = parent_and_student_fixture

    AttendanceRecord.objects.create(
        enrollment=enrollment,
        attendance_date=datetime.date(2026, 9, 1),
        status=AttendanceStatus.PRESENT,
    )
    AttendanceRecord.objects.create(
        enrollment=enrollment,
        attendance_date=datetime.date(2026, 9, 2),
        status=AttendanceStatus.ABSENT,
        reason_note="Medical leave pending",
    )

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    resp = client.get(
        "/api/v1/parent/attendance/",
        {"enrollment_id": enrollment.id, "month_year": "2026-09"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["month_year"] == "2026-09"
    assert data["total_days"] == 2
    assert data["present_days"] == 1
    assert data["absent_days"] == 1
    assert Decimal(str(data["attendance_percentage"])) == Decimal("50.0")

    assert len(data["records"]) == 2
    rec1 = data["records"][0]
    assert rec1["date"] == "2026-09-01"
    assert rec1["status"] == "Present"


def test_mobile_contract_parent_report_card(
    parent_and_student_fixture, session_fixture, subject_fixture
):
    """
    Contract 9: Parent Report Card Contract
    Flutter ReportCardResponse:
    - student: {full_name, class_name, section}
    - exam: {id, name, term}
    - summary: {total_obtained, total_maximum, percentage, letter_grade, class_rank}
    - subjects: List[SubjectScorecard]
    """
    _, _, enrollment, token = parent_and_student_fixture

    GradingTier.objects.create(
        session=session_fixture,
        grade_name="A+",
        min_percentage=Decimal("90.00"),
        max_percentage=Decimal("100.00"),
        gpa_point=Decimal("4.00"),
    )
    GradingTier.objects.create(
        session=session_fixture,
        grade_name="A",
        min_percentage=Decimal("80.00"),
        max_percentage=Decimal("89.99"),
        gpa_point=Decimal("3.50"),
    )

    exam = Exam.objects.create(
        name="Contract Annuals 2026",
        session=session_fixture,
        exam_type=ExamType.ANNUAL_EXAM,
        start_date=datetime.date(2026, 11, 1),
        end_date=datetime.date(2026, 11, 20),
    )
    exam_sub = ExamSubject.objects.create(
        exam=exam,
        class_group=enrollment.class_group,
        subject=subject_fixture,
        maximum_marks=Decimal("100.00"),
        passing_marks=Decimal("33.00"),
    )
    Mark.objects.create(
        exam_subject=exam_sub,
        enrollment=enrollment,
        marks_obtained=Decimal("94.00"),
        is_absent=False,
        remarks="Distinction",
    )

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    resp = client.get(
        "/api/v1/parent/report-card/",
        {"enrollment_id": enrollment.id, "exam_id": exam.id},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["student"]["full_name"] == "Hamza Rashid"

    assert data["exam"]["id"] == exam.id
    assert data["exam"]["name"] == "Contract Annuals 2026"

    summary = data["summary"]
    assert Decimal(str(summary["total_obtained"])) == Decimal("94.00")
    assert Decimal(str(summary["total_maximum"])) == Decimal("100.00")
    assert Decimal(str(summary["percentage"])) == Decimal("94.00")
    assert summary["letter_grade"] == "A+"
    assert "1" in str(summary["class_rank"])

    assert len(data["subjects"]) == 1
    sub = data["subjects"][0]
    assert sub["subject_name"] == "Computer Science"
    assert Decimal(str(sub["marks_obtained"])) == Decimal("94.00")
