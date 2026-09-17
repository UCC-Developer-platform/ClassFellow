"""
ClassFellow Web - Core Application Views
Institutional executive dashboard with real-time operational KPI metrics.
"""

from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone

from apps.attendance.models import AttendanceRecord, AttendanceStatus
from apps.core.models import AcademicSession, InstitutionProfile
from apps.fees.models import FeeInvoice, Payment, PaymentStatus
from apps.students.models import ClassGroup, Enrollment, EnrollmentStatus, Student


@login_required
def dashboard_view(request: HttpRequest) -> HttpResponse:
    """Renders the executive dashboard with real-time KPIs and recent operational activity."""
    today = timezone.now().date()
    current_month = today.strftime("%Y-%m")

    active_session = AcademicSession.objects.filter(is_active=True).first()
    institution = InstitutionProfile.objects.first()

    # Student KPIs
    total_students = Student.objects.filter(is_active=True).count()
    total_classes = ClassGroup.objects.count()
    active_enrollments = Enrollment.objects.filter(status=EnrollmentStatus.ACTIVE).count()

    # Attendance KPIs
    today_records = AttendanceRecord.objects.filter(attendance_date=today)
    total_attendance_marked = today_records.count()
    present_today = today_records.filter(status=AttendanceStatus.PRESENT).count()
    absent_today = today_records.filter(status=AttendanceStatus.ABSENT).count()
    late_today = today_records.filter(status=AttendanceStatus.LATE).count()
    leave_today = today_records.filter(status=AttendanceStatus.LEAVE).count()

    attendance_pct = (
        round((present_today / total_attendance_marked) * 100, 1)
        if total_attendance_marked > 0
        else 0.0
    )

    # Financial KPIs
    monthly_invoices = FeeInvoice.objects.filter(month_year=current_month)
    total_invoiced = monthly_invoices.aggregate(val=Coalesce(Sum("net_due"), Decimal("0.00")))["val"]

    monthly_payments = Payment.objects.filter(
        payment_date__year=today.year,
        payment_date__month=today.month,
        status=PaymentStatus.ISSUED,
    )
    total_collected = monthly_payments.aggregate(val=Coalesce(Sum("amount"), Decimal("0.00")))["val"]
    outstanding_balance = max(Decimal("0.00"), total_invoiced - total_collected)

    recent_payments = (
        Payment.objects.filter(status=PaymentStatus.ISSUED)
        .select_related("invoice__enrollment__student", "invoice__enrollment__class_group")
        .order_by("-id")[:8]
    )

    context = {
        "active_session": active_session,
        "institution": institution,
        "total_students": total_students,
        "total_classes": total_classes,
        "active_enrollments": active_enrollments,
        "total_attendance_marked": total_attendance_marked,
        "present_today": present_today,
        "absent_today": absent_today,
        "late_today": late_today,
        "leave_today": leave_today,
        "attendance_pct": attendance_pct,
        "current_month": current_month,
        "total_invoiced": total_invoiced,
        "total_collected": total_collected,
        "outstanding_balance": outstanding_balance,
        "recent_payments": recent_payments,
        "today_date": today,
    }
    return render(request, "core/dashboard.html", context)
