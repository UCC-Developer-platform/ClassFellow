"""
ClassFellow Web - Core Application Views
Institutional executive dashboard with real-time operational KPI metrics.
"""

import hashlib
import hmac
import logging
from decimal import Decimal
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from apps.attendance.models import AttendanceRecord, AttendanceStatus
from apps.core.models import AcademicSession, InstitutionBackupSnapshot, InstitutionProfile
from apps.fees.models import FeeInvoice, Payment, PaymentStatus
from apps.students.models import ClassGroup, Enrollment, EnrollmentStatus, Student

logger = logging.getLogger(__name__)


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


@csrf_exempt
def sync_backup_upload_view(request: HttpRequest) -> JsonResponse:
    """
    Endpoint for desktop-to-cloud automated backup snapshot uploads.
    Secured with institutional bearer token, chunked SHA-256 validation,
    and constant-time checksum comparison via hmac.compare_digest().
    """
    if request.method != "POST":
        return JsonResponse(
            {"status": "error", "message": "Method not allowed. Only POST is supported."},
            status=405,
        )

    # 1. Bearer Token Authentication
    auth_header = request.META.get("HTTP_AUTHORIZATION", "").strip()
    expected_token = getattr(settings, "INSTITUTION_SYNC_TOKEN", "")

    if not auth_header.startswith("Bearer "):
        return JsonResponse(
            {"status": "error", "message": "Unauthorized: Missing Bearer authorization header."},
            status=401,
        )

    provided_token = auth_header[7:].strip()
    if not expected_token or not hmac.compare_digest(provided_token, expected_token):
        return JsonResponse(
            {"status": "error", "message": "Unauthorized: Invalid institutional sync bearer token."},
            status=401,
        )

    # 2. Extract Uploaded Backup File
    uploaded_file = request.FILES.get("backup_file") or request.FILES.get("file")
    if not uploaded_file:
        return JsonResponse(
            {
                "status": "error",
                "message": "Bad request: No backup file uploaded in 'backup_file' multipart form field.",
            },
            status=400,
        )

    # 3. Chunked SHA-256 Calculation
    hasher = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        hasher.update(chunk)
    computed_sha256 = hasher.hexdigest().lower()

    # 4. SHA-256 Checksum Verification
    client_sha256 = (
        request.META.get("HTTP_X_BACKUP_SHA256")
        or request.META.get("HTTP_X_SHA256_CHECKSUM")
        or request.META.get("HTTP_X_SHA256")
        or request.POST.get("sha256_hash")
        or request.POST.get("sha256")
        or ""
    ).strip().lower()

    if client_sha256 and not hmac.compare_digest(computed_sha256, client_sha256):
        logger.warning(
            "Sync backup upload checksum mismatch: computed=%s, client=%s, filename=%s",
            computed_sha256,
            client_sha256,
            uploaded_file.name,
        )
        return JsonResponse(
            {
                "status": "error",
                "message": (
                    f"Corrupted upload: SHA-256 checksum mismatch "
                    f"(computed {computed_sha256}, expected {client_sha256})."
                ),
            },
            status=400,
        )

    # 5. Extract Client Metadata
    desktop_machine_id = (
        request.POST.get("desktop_machine_id")
        or request.META.get("HTTP_X_MACHINE_ID", "")
    ).strip()

    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        ip_address = forwarded_for.split(",")[0].strip()
    else:
        ip_address = request.META.get("REMOTE_ADDR")

    # 6. Save Snapshot Record & Binary Archive
    try:
        snapshot = InstitutionBackupSnapshot.objects.create(
            filename=uploaded_file.name,
            file_size_bytes=uploaded_file.size,
            sha256_hash=computed_sha256,
            desktop_machine_id=desktop_machine_id,
            ip_address=ip_address,
            backup_file=uploaded_file,
        )
        logger.info(
            "Institution backup snapshot successfully synced: id=%d, file=%s, size=%d bytes, machine_id=%s",
            snapshot.id,
            snapshot.filename,
            snapshot.file_size_bytes,
            desktop_machine_id,
        )
        return JsonResponse(
            {
                "status": "success",
                "snapshot_id": snapshot.id,
                "uploaded_at": snapshot.uploaded_at.isoformat(),
            },
            status=201,
        )
    except Exception as exc:
        logger.exception("Failed to persist institution backup snapshot: %s", exc)
        return JsonResponse(
            {"status": "error", "message": f"Server error persisting backup snapshot: {str(exc)}"},
            status=500,
        )
