"""
ClassFellow Web - Attendance Application Views
Class roster loading, default 'Present' marking, atomic bulk upsert, and WhatsApp absence alerts.
"""

import datetime
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.attendance.models import AttendanceStatus
from apps.attendance.services import AttendanceWebService
from apps.core.models import InstitutionProfile
from apps.students.models import ClassGroup


@login_required
def attendance_roster_view(request: HttpRequest) -> HttpResponse:
    """Renders class attendance roster with date selection and status toggles."""
    classes = ClassGroup.objects.all().order_by("name", "section_or_batch")

    date_str = request.GET.get("date", "").strip()
    if date_str:
        try:
            target_date = datetime.date.fromisoformat(date_str)
        except ValueError:
            target_date = timezone.now().date()
    else:
        target_date = timezone.now().date()

    class_id_val = request.GET.get("class_id", "").strip()
    selected_class_id = int(class_id_val) if class_id_val.isdigit() else None
    if not selected_class_id and classes.exists():
        selected_class_id = classes.first().id

    roster = []
    institution = InstitutionProfile.objects.first()
    inst_name = institution.name if institution else "ClassFellow School"

    if selected_class_id:
        roster = AttendanceWebService.load_class_roster(
            class_group_id=selected_class_id,
            attendance_date=target_date,
        )
        for r in roster:
            if r["guardian_phone"]:
                try:
                    payload = AttendanceWebService.generate_whatsapp_payload(
                        student_name=r["student_name"],
                        guardian_phone=r["guardian_phone"],
                        attendance_date=target_date,
                        institution_name=inst_name,
                        urdu_name=r.get("urdu_name"),
                    )
                    r["whatsapp_url"] = payload["whatsapp_url"]
                except Exception:
                    r["whatsapp_url"] = ""

    context = {
        "classes": classes,
        "selected_class_id": selected_class_id,
        "target_date": target_date,
        "target_date_str": target_date.isoformat(),
        "roster": roster,
        "statuses": AttendanceStatus.choices,
    }
    return render(request, "attendance/roster.html", context)


@login_required
@require_http_methods(["POST"])
def save_attendance_view(request: HttpRequest) -> HttpResponse:
    """Processes bulk attendance save/upsert for the chosen class and date."""
    try:
        class_group_id = int(request.POST["class_group_id"])
        attendance_date = datetime.date.fromisoformat(request.POST["attendance_date"])

        enrollment_ids = request.POST.getlist("enrollment_ids")
        entries = []
        for enr_id_str in enrollment_ids:
            enr_id = int(enr_id_str)
            status = request.POST.get(f"status_{enr_id}", AttendanceStatus.PRESENT)
            reason = request.POST.get(f"reason_{enr_id}", "").strip()
            entries.append({
                "enrollment_id": enr_id,
                "status": status,
                "reason_note": reason,
            })

        count = AttendanceWebService.save_bulk_attendance(
            class_group_id=class_group_id,
            attendance_date=attendance_date,
            attendance_entries=entries,
            recorded_by_user_id=request.user.id,
        )

        messages.success(
            request,
            f"Attendance recorded successfully for {count} students on {attendance_date}!",
        )
    except Exception as e:
        messages.error(request, f"Failed to save attendance: {str(e)}")

    target_class = request.POST.get("class_group_id", "")
    target_date = request.POST.get("attendance_date", "")
    redirect_url = f"/attendance/?class_id={target_class}&date={target_date}"
    return redirect(redirect_url)
