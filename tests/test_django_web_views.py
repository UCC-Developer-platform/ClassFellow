"""
ClassFellow - Category 11 Web Presentation Layer Automated Test Suite
Tests authentication redirects, role permissions, workspace GET endpoints (status 200),
POST action submissions, and in-memory ReportLab A4 PDF streaming.
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

import django  # noqa: E402
django.setup()

from django.core.management import call_command  # noqa: E402
from django.test import Client  # noqa: E402

from apps.accounts.decorators import role_required  # noqa: E402
from apps.accounts.models import Role, User  # noqa: E402
from apps.attendance.models import AttendanceRecord, AttendanceStatus  # noqa: E402
from apps.core.models import AcademicSession, InstitutionProfile  # noqa: E402
from apps.examinations.models import Exam, ExamSubject, ExamType, GradingTier, Mark, Subject  # noqa: E402
from apps.fees.models import FeeHead, FeeInvoice, FeeInvoiceItem, Payment, PaymentMethod  # noqa: E402
from apps.students.models import ClassGroup, Enrollment, EnrollmentStatus, Gender, GroupType, Student  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def setup_web_test_database():
    """Migrates and pre-seeds test database for the web presentation test suite."""
    call_command("migrate", interactive=False)
    call_command("flush", interactive=False)

    # 1. Academic Session & Institution
    session = AcademicSession.objects.create(
        name="2026-2027 Web Test",
        start_date=datetime.date(2026, 4, 1),
        end_date=datetime.date(2027, 3, 31),
        is_active=True,
    )
    InstitutionProfile.objects.create(
        name="Punjab Model School & College",
        campus_name="Main Campus",
    )

    # 2. Users (Admin, Principal, Cashier)
    User.objects.create_user(
        username="test_admin",
        password="Password123!",
        role=Role.ADMIN,
        first_name="Admin",
        last_name="User",
    )
    User.objects.create_user(
        username="test_principal",
        password="Password123!",
        role=Role.PRINCIPAL,
        first_name="Principal",
        last_name="User",
    )
    User.objects.create_user(
        username="test_cashier",
        password="Password123!",
        role=Role.CASHIER,
        first_name="Cashier",
        last_name="User",
    )

    # 3. Class Group & Student
    class_group = ClassGroup.objects.create(
        session=session,
        name="Class 10",
        section_or_batch="Section Gold",
        group_type=GroupType.SCHOOL_CLASS,
        monthly_tuition_fee=Decimal("5000.00"),
    )

    student = Student.objects.create(
        admission_number="CF-2026-0099",
        first_name="Bilal",
        last_name="Tariq",
        urdu_name="بلال طارق",
        gender=Gender.MALE,
        guardian_name="Tariq Mahmood",
        guardian_phone="03001234567",
        is_active=True,
    )

    enrollment = Enrollment.objects.create(
        student=student,
        class_group=class_group,
        session=session,
        roll_number="10",
        status=EnrollmentStatus.ACTIVE,
        custom_discount_amount=Decimal("500.00"),
    )

    # 4. Fee Structure & Invoice
    tuition_head = FeeHead.objects.create(
        name="Tuition Fee",
        urdu_name="ٹیوشن فیس",
        is_recurring=True,
    )

    invoice = FeeInvoice.objects.create(
        enrollment=enrollment,
        session=session,
        month_year="2026-06",
        issue_date=datetime.date(2026, 6, 1),
        due_date=datetime.date(2026, 6, 10),
        valid_until=datetime.date(2026, 6, 20),
        late_fee_surcharge=Decimal("200.00"),
        total_payable=Decimal("5000.00"),
        discount_amount=Decimal("500.00"),
        net_due=Decimal("4500.00"),
    )

    FeeInvoiceItem.objects.create(
        invoice=invoice,
        fee_head=tuition_head,
        amount=Decimal("5000.00"),
    )

    # 5. Examination & Subject
    math = Subject.objects.create(name="Mathematics", code="MTH-10", urdu_name="ریاضی")
    GradingTier.objects.create(
        session=session,
        grade_name="A+",
        min_percentage=Decimal("90.00"),
        max_percentage=Decimal("100.00"),
        gpa_point=Decimal("4.00"),
        is_passing=True,
    )
    GradingTier.objects.create(
        session=session,
        grade_name="F",
        min_percentage=Decimal("0.00"),
        max_percentage=Decimal("39.99"),
        gpa_point=Decimal("0.00"),
        is_passing=False,
    )

    exam = Exam.objects.create(
        session=session,
        name="Midterm Exam 2026",
        exam_type=ExamType.TERM_EXAM,
        start_date=datetime.date(2026, 6, 1),
        end_date=datetime.date(2026, 6, 10),
    )

    exam_subject = ExamSubject.objects.create(
        exam=exam,
        class_group=class_group,
        subject=math,
        maximum_marks=Decimal("100.00"),
        passing_marks=Decimal("40.00"),
    )

    Mark.objects.create(
        exam_subject=exam_subject,
        enrollment=enrollment,
        marks_obtained=Decimal("95.00"),
        is_absent=False,
    )


# =============================================================================
# 1. Authentication & Role Enforcement Tests (Task WEB-UI-01)
# =============================================================================

def test_unauthenticated_user_redirected_to_login():
    """Verifies unauthenticated GET requests are redirected to /accounts/login/."""
    client = Client()
    for endpoint in ["/", "/students/", "/fees/", "/attendance/", "/examinations/"]:
        resp = client.get(endpoint)
        assert resp.status_code == 302
        assert "/accounts/login/" in resp.url


def test_login_interface_renders_and_rejects_bad_credentials():
    """Verifies login form displays and rejects invalid credentials."""
    client = Client()
    resp = client.get("/accounts/login/")
    assert resp.status_code == 200
    assert b"ClassFellow" in resp.content
    assert b"Institutional Authentication Gateway" in resp.content

    # Bad credentials
    bad_resp = client.post("/accounts/login/", {"username": "baduser", "password": "wrong"})
    assert bad_resp.status_code == 200
    assert b"Invalid username or password" in bad_resp.content


def test_login_success_and_logout_flow():
    """Verifies successful credential authentication and logout cleanup."""
    client = Client()
    login_resp = client.post(
        "/accounts/login/",
        {"username": "test_admin", "password": "Password123!"},
        follow=True,
    )
    assert login_resp.status_code == 200
    assert b"Institutional Dashboard" in login_resp.content

    # Logout
    logout_resp = client.post("/accounts/logout/", follow=True)
    assert logout_resp.status_code == 200
    assert b"Institutional Authentication Gateway" in logout_resp.content


def test_role_required_decorator_enforcement():
    """Verifies role_required blocks users without permitted roles."""
    from django.http import HttpResponse

    @role_required([Role.ADMIN])
    def admin_only_view(request):
        return HttpResponse("Admin Granted")

    from django.test import RequestFactory
    rf = RequestFactory()

    cashier = User.objects.get(username="test_cashier")
    admin = User.objects.get(username="test_admin")

    # Cashier denied
    req1 = rf.get("/dummy/")
    req1.user = cashier
    resp1 = admin_only_view(req1)
    assert resp1.status_code == 403

    # Admin granted
    req2 = rf.get("/dummy/")
    req2.user = admin
    resp2 = admin_only_view(req2)
    assert resp2.status_code == 200
    assert resp2.content == b"Admin Granted"


# =============================================================================
# 2. Workspace GET Endpoints Status 200 (Task WEB-UI-02)
# =============================================================================

def test_all_workspace_views_return_200_when_authenticated():
    """Verifies status 200 across Dashboard, Students, Fees, Attendance, and Examinations."""
    client = Client()
    client.login(username="test_admin", password="Password123!")

    # 1. Dashboard
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Active Students" in resp.content

    # 2. Students
    resp_stu = client.get("/students/")
    assert resp_stu.status_code == 200
    assert b"Student Directory & Admissions" in resp_stu.content
    assert b"CF-2026-0099" in resp_stu.content

    # 3. Fees
    resp_fee = client.get("/fees/")
    assert resp_fee.status_code == 200
    assert b"Fees, Accounts & Defaulters Ledger" in resp_fee.content

    # 4. Attendance
    resp_att = client.get("/attendance/")
    assert resp_att.status_code == 200
    assert b"Daily Class Attendance" in resp_att.content

    # 5. Examinations
    resp_exam = client.get("/examinations/")
    assert resp_exam.status_code == 200
    assert b"Examinations, Marks & Report Cards" in resp_exam.content


# =============================================================================
# 3. Action Submissions POST Tests (Task WEB-UI-02)
# =============================================================================

def test_student_admission_post_submission():
    """Verifies admitting a new student via the web admission form."""
    client = Client()
    client.login(username="test_admin", password="Password123!")

    session = AcademicSession.objects.filter(is_active=True).first()
    class_group = ClassGroup.objects.first()

    payload = {
        "first_name": "Hamza",
        "last_name": "Rashid",
        "urdu_name": "حمزہ راشد",
        "gender": Gender.MALE,
        "session_id": session.id,
        "class_group_id": class_group.id,
        "guardian_name": "Rashid Ali",
        "guardian_phone": "+923005556677",
        "guardian_relation": "Father",
        "roll_number": "11",
        "custom_discount_amount": "200.00",
    }
    resp = client.post("/students/admit/", payload, follow=True)
    assert resp.status_code == 200
    assert b"admitted successfully" in resp.content

    new_stu = Student.objects.filter(first_name="Hamza", last_name="Rashid").first()
    assert new_stu is not None
    assert new_stu.guardian_phone == "03005556677"


def test_cashier_payment_post_submission():
    """Verifies cashier recording payment via the web interface."""
    client = Client()
    client.login(username="test_cashier", password="Password123!")

    invoice = FeeInvoice.objects.first()
    initial_payment_count = Payment.objects.filter(invoice=invoice).count()

    payload = {
        "invoice_id": invoice.id,
        "amount": "1500.00",
        "payment_method": PaymentMethod.CASH,
        "note": "Web cashier deposit",
    }
    resp = client.post("/fees/pay/", payload, follow=True)
    assert resp.status_code == 200
    assert b"Payment of Rs. 1,500.00 recorded successfully" in resp.content

    assert Payment.objects.filter(invoice=invoice).count() == initial_payment_count + 1
    new_payment = Payment.objects.filter(invoice=invoice).order_by("-id").first()
    assert new_payment.receipt_number.startswith("REC-")


def test_bulk_attendance_save_post_submission():
    """Verifies saving class roster attendance via POST."""
    client = Client()
    client.login(username="test_admin", password="Password123!")

    class_group = ClassGroup.objects.first()
    enrollment = Enrollment.objects.filter(class_group=class_group).first()
    today_str = datetime.date.today().isoformat()

    payload = {
        "class_group_id": class_group.id,
        "attendance_date": today_str,
        "enrollment_ids": [enrollment.id],
        f"status_{enrollment.id}": AttendanceStatus.ABSENT,
        f"reason_{enrollment.id}": "Family event",
    }
    resp = client.post("/attendance/save/", payload, follow=True)
    assert resp.status_code == 200
    assert b"Attendance recorded successfully" in resp.content

    record = AttendanceRecord.objects.filter(enrollment=enrollment, attendance_date=today_str).first()
    assert record is not None
    assert record.status == AttendanceStatus.ABSENT
    assert record.reason_note == "Family event"


def test_exam_marks_save_post_submission():
    """Verifies recording subject marks via POST."""
    client = Client()
    client.login(username="test_admin", password="Password123!")

    exam_subject = ExamSubject.objects.first()
    enrollment = Enrollment.objects.filter(class_group=exam_subject.class_group).first()

    payload = {
        "exam_id": exam_subject.exam.id,
        "class_id": exam_subject.class_group.id,
        "exam_subject_id": exam_subject.id,
        "enrollment_ids": [enrollment.id],
        f"marks_{enrollment.id}": "88.50",
        f"remarks_{enrollment.id}": "Great effort",
    }
    resp = client.post("/examinations/save-marks/", payload, follow=True)
    assert resp.status_code == 200
    assert b"Successfully recorded marks" in resp.content

    m = Mark.objects.get(exam_subject=exam_subject, enrollment=enrollment)
    assert m.marks_obtained == Decimal("88.50")
    assert m.remarks == "Great effort"


# =============================================================================
# 4. In-Memory A4 PDF Streaming Tests (Task WEB-UI-03)
# =============================================================================

def test_stream_fee_voucher_pdf_endpoint():
    """
    Verifies streaming 3-panel A4 fee voucher PDF directly in-memory via io.BytesIO.
    Confirms HTTP 200, Content-Type: application/pdf, and %PDF- header.
    """
    client = Client()
    client.login(username="test_admin", password="Password123!")

    invoice = FeeInvoice.objects.first()
    resp = client.get(f"/fees/vouchers/{invoice.id}/pdf/")

    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/pdf"
    assert "inline" in resp["Content-Disposition"]
    assert f"Fee_Voucher_{invoice.month_year}_{invoice.id}.pdf" in resp["Content-Disposition"]

    content = resp.content
    assert len(content) > 1000
    assert content.startswith(b"%PDF-")


def test_stream_report_card_pdf_endpoint():
    """
    Verifies streaming bilingual A4 terminal report card PDF directly in-memory.
    Confirms HTTP 200, Content-Type: application/pdf, and %PDF- header.
    """
    client = Client()
    client.login(username="test_admin", password="Password123!")

    exam = Exam.objects.first()
    enrollment = Enrollment.objects.filter(class_group__exam_subjects__exam=exam).first()

    resp = client.get(f"/examinations/report-card/{exam.id}/{enrollment.id}/pdf/")

    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/pdf"
    assert "inline" in resp["Content-Disposition"]
    assert "Report_Card_" in resp["Content-Disposition"]

    content = resp.content
    assert len(content) > 1000
    assert content.startswith(b"%PDF-")
