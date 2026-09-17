"""
tests/test_analytics_and_notices.py
====================================
Automated verification test suite for Category 14:
- ExecutiveAnalyticsService: class-level & overall fee recovery, top defaulting classes,
  and multi-dimensional student academic risk roster detection (attendance < 75% & failing marks).
- InstitutionNotice model, campus/class scoping, and WhatsApp bulletin generation.
- RBAC protection on /analytics/, notice creation on /notices/, and in-memory multi-page
  ReportLab monthly audit packet PDF streaming.
"""

import datetime
from decimal import Decimal
import os
import pytest

os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
os.environ["DJANGO_DB_ENGINE"] = "sqlite"

import django  # noqa: E402
django.setup()

from django.test import Client  # noqa: E402

from apps.accounts.models import Role, User  # noqa: E402
from apps.attendance.models import AttendanceRecord, AttendanceStatus  # noqa: E402
from apps.core.analytics import ExecutiveAnalyticsService  # noqa: E402
from apps.core.models import (  # noqa: E402
    AcademicSession,
    Campus,
    InstitutionNotice,
    InstitutionProfile,
    NoticeType,
)
from apps.examinations.models import Exam, ExamSubject, ExamType, Mark, Subject  # noqa: E402
from apps.fees.models import FeeInvoice, FeeInvoiceItem, Payment, PaymentMethod, PaymentStatus  # noqa: E402
from apps.students.models import ClassGroup, Enrollment, Gender, GroupType, Student  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database():
    """Ensures test isolation."""
    InstitutionNotice.objects.all().delete()
    Payment.objects.all().delete()
    FeeInvoiceItem.objects.all().delete()
    FeeInvoice.objects.all().delete()
    Mark.objects.all().delete()
    ExamSubject.objects.all().delete()
    Exam.objects.all().delete()
    AttendanceRecord.objects.all().delete()
    Enrollment.objects.all().delete()
    Student.objects.all().delete()
    User.objects.filter(username__startswith="anl_").delete()
    yield


@pytest.fixture
def institution_fixture():
    inst, _ = InstitutionProfile.objects.get_or_create(
        id=1,
        defaults={
            "name": "Quaid-e-Azam Model College",
            "campus_name": "Main Campus",
        },
    )
    return inst


@pytest.fixture
def campus_a():
    campus, _ = Campus.objects.get_or_create(
        code="CMP-A",
        defaults={"name": "Boys Campus Gulberg", "address": "Lahore"},
    )
    return campus


@pytest.fixture
def campus_b():
    campus, _ = Campus.objects.get_or_create(
        code="CMP-B",
        defaults={"name": "Junior Campus Model Town", "address": "Lahore"},
    )
    return campus


@pytest.fixture
def session_fixture():
    session, _ = AcademicSession.objects.get_or_create(
        name="2026-2027 Analytics Session",
        defaults={
            "start_date": datetime.date(2026, 4, 1),
            "end_date": datetime.date(2027, 3, 31),
            "is_active": True,
        },
    )
    return session


@pytest.fixture
def admin_user():
    return User.objects.create_user(
        username="anl_admin",
        password="Password123!",
        role=Role.ADMIN,
        first_name="Director",
        last_name="Executive",
    )


@pytest.fixture
def cashier_user():
    return User.objects.create_user(
        username="anl_cashier",
        password="Password123!",
        role=Role.CASHIER,
        first_name="Junior",
        last_name="Cashier",
    )


# =============================================================================
# 1. ExecutiveAnalyticsService Tests
# =============================================================================

def test_financial_recovery_metrics_calculation(session_fixture, campus_a, campus_b):
    """Verifies class-by-class recovery percentages, outstanding totals, and top defaulter sorting."""
    # 1. Setup 2 Classes across 2 campuses
    class_9, _ = ClassGroup.objects.get_or_create(
        session=session_fixture,
        campus=campus_a,
        name="Class 9",
        section_or_batch="Section A",
        defaults={
            "group_type": GroupType.SCHOOL_CLASS,
            "monthly_tuition_fee": Decimal("10000.00"),
        },
    )
    class_10, _ = ClassGroup.objects.get_or_create(
        session=session_fixture,
        campus=campus_b,
        name="Class 10",
        section_or_batch="Section B",
        defaults={
            "group_type": GroupType.SCHOOL_CLASS,
            "monthly_tuition_fee": Decimal("20000.00"),
        },
    )

    # 2. Setup Students & Enrollments
    stu1 = Student.objects.create(
        admission_number="CF-2026-ANL-01",
        first_name="Ali",
        last_name="Raza",
        gender=Gender.MALE,
        guardian_name="Raza",
        guardian_phone="03001112233",
    )
    enr1 = Enrollment.objects.create(student=stu1, class_group=class_9, session=session_fixture)

    stu2 = Student.objects.create(
        admission_number="CF-2026-ANL-02",
        first_name="Bilal",
        last_name="Khan",
        gender=Gender.MALE,
        guardian_name="Khan",
        guardian_phone="03004445566",
    )
    enr2 = Enrollment.objects.create(student=stu2, class_group=class_10, session=session_fixture)

    # 3. Create Invoices for cycle 2026-06
    inv1 = FeeInvoice.objects.create(
        enrollment=enr1,
        session=session_fixture,
        month_year="2026-06",
        issue_date=datetime.date(2026, 6, 1),
        due_date=datetime.date(2026, 6, 10),
        valid_until=datetime.date(2026, 6, 20),
        total_payable=Decimal("10000.00"),
        net_due=Decimal("10000.00"),
    )
    inv2 = FeeInvoice.objects.create(
        enrollment=enr2,
        session=session_fixture,
        month_year="2026-06",
        issue_date=datetime.date(2026, 6, 1),
        due_date=datetime.date(2026, 6, 10),
        valid_until=datetime.date(2026, 6, 20),
        total_payable=Decimal("20000.00"),
        net_due=Decimal("20000.00"),
    )

    # 4. Record partial payment on inv1 (8,000 paid -> 80% recovery, 2,000 balance)
    Payment.objects.create(
        invoice=inv1,
        receipt_number="REC-ANL-001",
        amount=Decimal("8000.00"),
        payment_date=datetime.date(2026, 6, 5),
        payment_method=PaymentMethod.CASH,
        status=PaymentStatus.ISSUED,
    )
    # Record partial payment on inv2 (5,000 paid -> 25% recovery, 15,000 balance)
    Payment.objects.create(
        invoice=inv2,
        receipt_number="REC-ANL-002",
        amount=Decimal("5000.00"),
        payment_date=datetime.date(2026, 6, 7),
        payment_method=PaymentMethod.BANK_TRANSFER,
        status=PaymentStatus.ISSUED,
    )

    # 5. Compute recovery metrics institution-wide
    metrics = ExecutiveAnalyticsService.get_financial_recovery_metrics(
        session_id=session_fixture.id,
        month_year="2026-06",
    )

    assert metrics["total_invoiced"] == Decimal("30000.00")
    assert metrics["total_collected"] == Decimal("13000.00")
    assert metrics["total_outstanding"] == Decimal("17000.00")
    assert metrics["overall_recovery_pct"] == Decimal("43.33")

    # Verify class breakdown
    c9_data = next(c for c in metrics["class_recovery_list"] if "Class 9" in c["class_name"])
    assert c9_data["invoiced_amount"] == Decimal("10000.00")
    assert c9_data["collected_amount"] == Decimal("8000.00")
    assert c9_data["outstanding_amount"] == Decimal("2000.00")
    assert c9_data["recovery_percentage"] == Decimal("80.00")

    c10_data = next(c for c in metrics["class_recovery_list"] if "Class 10" in c["class_name"])
    assert c10_data["invoiced_amount"] == Decimal("20000.00")
    assert c10_data["collected_amount"] == Decimal("5000.00")
    assert c10_data["outstanding_amount"] == Decimal("15000.00")
    assert c10_data["recovery_percentage"] == Decimal("25.00")

    # Verify top defaulting classes is ordered by outstanding amount descending (Class 10 first)
    assert len(metrics["top_defaulting_classes"]) == 2
    assert "Class 10" in metrics["top_defaulting_classes"][0]["class_name"]
    assert metrics["top_defaulting_classes"][0]["outstanding_amount"] == Decimal("15000.00")

    # 6. Test Campus-scoped filtering
    metrics_campus_a = ExecutiveAnalyticsService.get_financial_recovery_metrics(
        session_id=session_fixture.id,
        month_year="2026-06",
        campus_id=campus_a.id,
    )
    assert metrics_campus_a["total_invoiced"] == Decimal("10000.00")
    assert metrics_campus_a["total_collected"] == Decimal("8000.00")
    assert metrics_campus_a["overall_recovery_pct"] == Decimal("80.00")
    invoiced_classes = [c for c in metrics_campus_a["class_recovery_list"] if c["invoiced_amount"] > Decimal("0.00")]
    assert len(invoiced_classes) == 1
    assert "Class 9" in invoiced_classes[0]["class_name"]


def test_academic_risk_roster_detection(session_fixture, campus_a):
    """Verifies students with attendance < 75% or failing marks are flagged in academic risk roster."""
    class_grp, _ = ClassGroup.objects.get_or_create(
        session=session_fixture,
        campus=campus_a,
        name="Class 8",
        section_or_batch="Section A",
        defaults={
            "group_type": GroupType.SCHOOL_CLASS,
            "monthly_tuition_fee": Decimal("4000.00"),
        },
    )

    # Student 1: Poor Attendance (4 present out of 10 days = 40%)
    stu_att_risk = Student.objects.create(
        admission_number="CF-RISK-01",
        first_name="Hamza",
        last_name="Tariq",
        gender=Gender.MALE,
        guardian_name="Tariq",
        guardian_phone="03001230001",
    )
    enr_att_risk = Enrollment.objects.create(student=stu_att_risk, class_group=class_grp, session=session_fixture)

    for i in range(10):
        AttendanceRecord.objects.create(
            enrollment=enr_att_risk,
            attendance_date=datetime.date(2026, 5, 1) + datetime.timedelta(days=i),
            status=AttendanceStatus.PRESENT if i < 4 else AttendanceStatus.ABSENT,
        )

    # Student 2: Good attendance (10/10 = 100%), but fails Exam Subjects
    stu_exam_risk = Student.objects.create(
        admission_number="CF-RISK-02",
        first_name="Zain",
        last_name="Abbas",
        gender=Gender.MALE,
        guardian_name="Abbas",
        guardian_phone="03001230002",
    )
    enr_exam_risk = Enrollment.objects.create(student=stu_exam_risk, class_group=class_grp, session=session_fixture)

    for i in range(10):
        AttendanceRecord.objects.create(
            enrollment=enr_exam_risk,
            attendance_date=datetime.date(2026, 5, 1) + datetime.timedelta(days=i),
            status=AttendanceStatus.PRESENT,
        )

    exam = Exam.objects.create(
        session=session_fixture,
        name="Midterm Exam 2026",
        exam_type=ExamType.TERM_EXAM,
        start_date=datetime.date(2026, 5, 15),
        end_date=datetime.date(2026, 5, 20),
    )
    sub_math, _ = Subject.objects.get_or_create(name="Mathematics", defaults={"code": "MATH-8"})
    sub_sci, _ = Subject.objects.get_or_create(name="Science", defaults={"code": "SCI-8"})

    es_math = ExamSubject.objects.create(
        exam=exam,
        class_group=class_grp,
        subject=sub_math,
        maximum_marks=Decimal("100.00"),
        passing_marks=Decimal("33.00"),
    )
    es_sci = ExamSubject.objects.create(
        exam=exam,
        class_group=class_grp,
        subject=sub_sci,
        maximum_marks=Decimal("100.00"),
        passing_marks=Decimal("33.00"),
    )

    # Fails both Math (22/100) and Science (15/100)
    Mark.objects.create(exam_subject=es_math, enrollment=enr_exam_risk, marks_obtained=Decimal("22.00"))
    Mark.objects.create(exam_subject=es_sci, enrollment=enr_exam_risk, marks_obtained=Decimal("15.00"))

    # Student 3: Honor student, 100% attendance, passes all subjects (85/100 & 90/100)
    stu_good = Student.objects.create(
        admission_number="CF-RISK-03",
        first_name="Ayesha",
        last_name="Siddiqua",
        gender=Gender.FEMALE,
        guardian_name="Siddique",
        guardian_phone="03001230003",
    )
    enr_good = Enrollment.objects.create(student=stu_good, class_group=class_grp, session=session_fixture)
    for i in range(10):
        AttendanceRecord.objects.create(
            enrollment=enr_good,
            attendance_date=datetime.date(2026, 5, 1) + datetime.timedelta(days=i),
            status=AttendanceStatus.PRESENT,
        )
    Mark.objects.create(exam_subject=es_math, enrollment=enr_good, marks_obtained=Decimal("85.00"))
    Mark.objects.create(exam_subject=es_sci, enrollment=enr_good, marks_obtained=Decimal("90.00"))

    # Execute risk screening
    roster = ExecutiveAnalyticsService.get_academic_risk_roster(session_id=session_fixture.id)

    # Verify flagged students
    adm_nos = [r["admission_number"] for r in roster]
    assert "CF-RISK-01" in adm_nos  # Flagged for attendance
    assert "CF-RISK-02" in adm_nos  # Flagged for failing marks
    assert "CF-RISK-03" not in adm_nos  # Good student NOT in risk roster

    # Verify risk factors
    r1 = next(r for r in roster if r["admission_number"] == "CF-RISK-01")
    assert r1["attendance_percentage"] == Decimal("40.0")
    assert any("Low Attendance" in f for f in r1["risk_factors"])

    r2 = next(r for r in roster if r["admission_number"] == "CF-RISK-02")
    assert r2["failing_subjects_count"] == 2
    assert any("Failed 2 Subject(s)" in f for f in r2["risk_factors"])


# =============================================================================
# 2. InstitutionNotice & WhatsApp Bulletin Tests
# =============================================================================

def test_institution_notice_model_and_whatsapp_bulletin(campus_a):
    """Verifies InstitutionNotice creation, campus scoping, and WhatsApp string formatting."""
    notice = InstitutionNotice.objects.create(
        title="Fee Submission Deadline Extension",
        urdu_title="فیس جمع کروانے کی تاریخ میں توسیع",
        content=(
            "The last date for fee deposit for the month of June 2026 has been "
            "extended to 25th June without surcharge."
        ),
        urdu_content="جون 2026 کی فیس بغیر جرمانے کے 25 جون تک جمع کروائی جا سکتی ہے۔",
        notice_type=NoticeType.FEE_REMINDER,
        target_campus=campus_a,
        issued_date=datetime.date(2026, 6, 12),
        is_published=True,
    )

    assert notice.id is not None
    assert "Fee Reminder" in str(notice)
    assert "Deadline Extension" in str(notice)

    bulletin = notice.generate_whatsapp_bulletin(institution_name="Lahore Model Academy")

    # Verify structured WhatsApp bulletin formatting
    assert "LAHORE MODEL ACADEMY" in bulletin
    assert "FEE REMINDER" in bulletin
    assert "Fee Submission Deadline Extension" in bulletin
    assert "Boys Campus Gulberg" in bulletin
    assert "25th June without surcharge" in bulletin
    assert "فیس جمع کروانے کی تاریخ میں توسیع" in bulletin
    assert "School Administration Office" in bulletin


# =============================================================================
# 3. Web Views, RBAC & PDF Streaming Tests
# =============================================================================

def test_analytics_web_view_rbac_and_rendering(admin_user, cashier_user, session_fixture):
    """Verifies RBAC enforcement and HTTP 200 response on GET /analytics/."""
    client = Client()

    # Cashier is forbidden (403)
    client.login(username="anl_cashier", password="Password123!")
    resp_cashier = client.get("/analytics/")
    assert resp_cashier.status_code == 403

    # Admin is authorized (200)
    client.login(username="anl_admin", password="Password123!")
    resp_admin = client.get(f"/analytics/?session_id={session_fixture.id}&month_year=2026-06")
    assert resp_admin.status_code == 200
    assert b"Executive Analytics & Risk Intelligence" in resp_admin.content
    assert b"Class-by-Class Fee Recovery Breakdown" in resp_admin.content
    assert b"Academic Risk Intelligence Roster" in resp_admin.content
    assert b"Download Monthly Audit Packet (PDF)" in resp_admin.content


def test_notices_web_view_rendering_and_creation(admin_user, campus_a):
    """Verifies listing notices on GET /notices/ and publishing new notice via POST."""
    client = Client()
    client.login(username="anl_admin", password="Password123!")

    # 1. GET noticeboard
    resp_get = client.get("/notices/")
    assert resp_get.status_code == 200
    assert b"Parent Noticeboard & WhatsApp Bulletin Hub" in resp_get.content

    # 2. POST create notice
    post_data = {
        "title": "Summer Vacations Announcement",
        "urdu_title": "تعطیلات گرما کا اعلان",
        "content": "The school will remain closed for summer vacation from June 15 to August 14.",
        "urdu_content": "سکول 15 جون سے 14 اگست تک تعطیلات گرما کے لیے بند رہے گا۔",
        "notice_type": NoticeType.HOLIDAY,
        "target_campus_id": str(campus_a.id),
    }
    resp_post = client.post("/notices/", data=post_data)
    assert resp_post.status_code == 302
    assert resp_post.url == "/notices/"

    # Verify created in DB
    notice = InstitutionNotice.objects.get(title="Summer Vacations Announcement")
    assert notice.notice_type == NoticeType.HOLIDAY
    assert notice.target_campus == campus_a
    assert notice.urdu_title == "تعطیلات گرما کا اعلان"


def test_stream_monthly_audit_packet_pdf(admin_user, session_fixture, campus_a):
    """Verifies in-memory ReportLab multi-page monthly audit packet PDF streaming endpoint."""
    client = Client()
    client.login(username="anl_admin", password="Password123!")

    # Generate a sample invoice so PDF has data
    class_pdf, _ = ClassGroup.objects.get_or_create(
        session=session_fixture,
        campus=campus_a,
        name="Class 9 PDF",
        section_or_batch="Section A",
        defaults={
            "group_type": GroupType.SCHOOL_CLASS,
            "monthly_tuition_fee": Decimal("6000.00"),
        },
    )
    stu = Student.objects.create(
        admission_number="CF-PDF-001",
        first_name="Usman",
        last_name="Ghani",
        gender=Gender.MALE,
        guardian_name="Ghani",
        guardian_phone="03009998877",
    )
    enr = Enrollment.objects.create(student=stu, class_group=class_pdf, session=session_fixture)
    FeeInvoice.objects.create(
        enrollment=enr,
        session=session_fixture,
        month_year="2026-06",
        issue_date=datetime.date(2026, 6, 1),
        due_date=datetime.date(2026, 6, 10),
        valid_until=datetime.date(2026, 6, 20),
        total_payable=Decimal("6000.00"),
        net_due=Decimal("6000.00"),
    )

    url = f"/reports/monthly-audit-packet/{session_fixture.id}/2026-06/pdf/"
    resp = client.get(url)

    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/pdf"
    assert "Monthly_Audit_Packet_2026-06.pdf" in resp["Content-Disposition"]
    assert resp.content.startswith(b"%PDF-")
    assert len(resp.content) > 1000  # Valid substantial binary PDF
