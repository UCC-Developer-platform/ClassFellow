"""
ClassFellow Web - Student Views
Student registry browsing, multi-field search, and student admission workflows.
"""

from decimal import Decimal
import datetime
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.core.models import AcademicSession
from apps.students.models import ClassGroup, Gender, Student
from apps.students.services import StudentWebService


@login_required
def student_list_view(request: HttpRequest) -> HttpResponse:
    """Renders student directory with real-time multi-field search and class filtering."""
    query = request.GET.get("q", "").strip()
    class_id = request.GET.get("class_id", "").strip()
    session_id = request.GET.get("session_id", "").strip()

    class_filter = int(class_id) if class_id.isdigit() else None
    session_filter = int(session_id) if session_id.isdigit() else None

    if query or class_filter or session_filter:
        students = StudentWebService.search_students(
            query=query,
            class_group_id=class_filter,
            session_id=session_filter,
        )
    else:
        students = (
            Student.objects.filter(is_active=True)
            .prefetch_related("enrollments__class_group", "enrollments__session")
            .order_by("-id")[:100]
        )

    classes = ClassGroup.objects.all().order_by("name", "section_or_batch")
    sessions = AcademicSession.objects.all().order_by("-is_active", "-start_date")
    active_session = AcademicSession.objects.filter(is_active=True).first()

    context = {
        "students": students,
        "classes": classes,
        "sessions": sessions,
        "active_session": active_session,
        "query": query,
        "selected_class_id": class_filter,
        "selected_session_id": session_filter,
        "gender_choices": Gender.choices,
    }
    return render(request, "students/student_list.html", context)


@login_required
@require_http_methods(["POST"])
def student_create_view(request: HttpRequest) -> HttpResponse:
    """Processes new student admission submission with validation and atomic enrollment."""
    try:
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        urdu_name = request.POST.get("urdu_name", "").strip()
        gender = request.POST.get("gender", Gender.MALE)
        guardian_name = request.POST.get("guardian_name", "").strip()
        guardian_phone = request.POST.get("guardian_phone", "").strip()
        guardian_relation = request.POST.get("guardian_relation", "Father").strip()

        session_id_val = request.POST.get("session_id")
        class_group_id_val = request.POST.get("class_group_id")

        if not session_id_val or not class_group_id_val:
            raise ValueError("Both Academic Session and Class Group are required for admission.")

        session_id = int(session_id_val)
        class_group_id = int(class_group_id_val)

        roll_number = request.POST.get("roll_number", "").strip()
        discount_val = request.POST.get("custom_discount_amount", "0.00").strip()
        discount = Decimal(discount_val) if discount_val else Decimal("0.00")

        dob_str = request.POST.get("date_of_birth", "").strip()
        date_of_birth = datetime.date.fromisoformat(dob_str) if dob_str else None

        student, enrollment = StudentWebService.register_student(
            first_name=first_name,
            guardian_name=guardian_name,
            guardian_phone=guardian_phone,
            gender=gender,
            session_id=session_id,
            class_group_id=class_group_id,
            last_name=last_name,
            urdu_name=urdu_name,
            guardian_relation=guardian_relation,
            date_of_birth=date_of_birth,
            roll_number=roll_number,
            custom_discount_amount=discount,
        )

        messages.success(
            request,
            f"Student {student.first_name} {student.last_name} admitted successfully! "
            f"Assigned Admission #: {student.admission_number}",
        )
    except Exception as e:
        messages.error(request, f"Admission failed: {str(e)}")

    return redirect("/students/")
