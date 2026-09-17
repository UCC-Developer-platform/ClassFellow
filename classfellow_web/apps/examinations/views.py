"""
ClassFellow Web - Examinations Application Views & PDF Streaming
Marks ledger management, class rank scorecards, and in-memory ReportLab terminal report card streaming.
"""

from decimal import Decimal, ROUND_HALF_UP
import io
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from app.reports.report_card_generator import generate_report_card_pdf
from apps.attendance.models import AttendanceRecord, AttendanceStatus
from apps.core.models import InstitutionProfile
from apps.examinations.models import Exam, ExamSubject, GradingTier, Mark
from apps.examinations.services import ExamWebService
from apps.students.models import ClassGroup, Enrollment, EnrollmentStatus
from models import StudentReportCardDTO, SubjectResultDTO


@login_required
def exam_workspace_view(request: HttpRequest) -> HttpResponse:
    """Renders examination workspace with tabs for Marks Entry Sheet and Class Rankings."""
    exams = Exam.objects.all().order_by("-start_date")
    classes = ClassGroup.objects.all().order_by("name", "section_or_batch")

    exam_id_val = request.GET.get("exam_id", "").strip()
    selected_exam_id = int(exam_id_val) if exam_id_val.isdigit() else None
    if not selected_exam_id and exams.exists():
        selected_exam_id = exams.first().id

    class_id_val = request.GET.get("class_id", "").strip()
    selected_class_id = int(class_id_val) if class_id_val.isdigit() else None
    if not selected_class_id and classes.exists():
        selected_class_id = classes.first().id

    exam_subjects = []
    selected_subject_id = None
    student_marks_entries = []
    results = []

    if selected_exam_id and selected_class_id:
        exam_subjects = list(
            ExamSubject.objects.filter(
                exam_id=selected_exam_id,
                class_group_id=selected_class_id,
            ).select_related("subject")
        )

        subj_id_val = request.GET.get("subject_id", "").strip()
        if subj_id_val.isdigit():
            selected_subject_id = int(subj_id_val)
        elif exam_subjects:
            selected_subject_id = exam_subjects[0].id

        # Calculate class rankings
        results = ExamWebService.calculate_class_results(
            exam_id=selected_exam_id,
            class_group_id=selected_class_id,
        )

        # If an exam subject is selected, load student marks entry roster
        if selected_subject_id:
            target_exam_subject = next((es for es in exam_subjects if es.id == selected_subject_id), None)
            if target_exam_subject:
                enrollments = (
                    Enrollment.objects.filter(
                        class_group_id=selected_class_id,
                        status=EnrollmentStatus.ACTIVE,
                    )
                    .select_related("student")
                    .order_by("roll_number", "student__first_name")
                )

                existing_marks = {
                    m.enrollment_id: m
                    for m in Mark.objects.filter(exam_subject_id=selected_subject_id)
                }

                for enr in enrollments:
                    m = existing_marks.get(enr.id)
                    student_marks_entries.append({
                        "enrollment_id": enr.id,
                        "roll_number": enr.roll_number,
                        "student_name": f"{enr.student.first_name} {enr.student.last_name}".strip(),
                        "urdu_name": enr.student.urdu_name,
                        "admission_number": enr.student.admission_number,
                        "marks_obtained": m.marks_obtained if m else "",
                        "is_absent": m.is_absent if m else False,
                        "remarks": m.remarks if m else "",
                    })

    context = {
        "exams": exams,
        "classes": classes,
        "selected_exam_id": selected_exam_id,
        "selected_class_id": selected_class_id,
        "exam_subjects": exam_subjects,
        "selected_subject_id": selected_subject_id,
        "student_marks_entries": student_marks_entries,
        "results": results,
    }
    return render(request, "examinations/exam_view.html", context)


@login_required
@require_http_methods(["POST"])
def save_marks_view(request: HttpRequest) -> HttpResponse:
    """Processes bulk student marks entry for an exam subject with validation."""
    try:
        exam_subject_id = int(request.POST["exam_subject_id"])
        get_object_or_404(ExamSubject, id=exam_subject_id)

        enrollment_ids = request.POST.getlist("enrollment_ids")
        saved_count = 0

        for enr_id_str in enrollment_ids:
            enr_id = int(enr_id_str)
            is_absent = request.POST.get(f"absent_{enr_id}") == "1"
            marks_str = request.POST.get(f"marks_{enr_id}", "").strip()
            remarks = request.POST.get(f"remarks_{enr_id}", "").strip()

            if is_absent:
                marks_val = Decimal("0.00")
            elif marks_str:
                marks_val = Decimal(marks_str)
            else:
                continue

            ExamWebService.record_student_marks(
                exam_subject_id=exam_subject_id,
                enrollment_id=enr_id,
                marks_obtained=marks_val,
                is_absent=is_absent,
                remarks=remarks,
                recorded_by_user_id=request.user.id,
            )
            saved_count += 1

        messages.success(request, f"Successfully recorded marks for {saved_count} students!")
    except Exception as e:
        messages.error(request, f"Failed to record marks: {str(e)}")

    redirect_url = (
        f"/examinations/?exam_id={request.POST.get('exam_id')}"
        f"&class_id={request.POST.get('class_id')}"
        f"&subject_id={request.POST.get('exam_subject_id')}"
    )
    return redirect(redirect_url)


@login_required
def stream_report_card_pdf(
    request: HttpRequest,
    exam_id: int,
    enrollment_id: int,
) -> HttpResponse:
    """
    Renders and streams a single-sheet A4 bilingual terminal report card PDF
    in-memory via ReportLab and io.BytesIO.
    """
    exam = Exam.objects.select_related("session").filter(id=exam_id).first()
    if not exam:
        raise Http404("Examination not found.")

    enrollment = (
        Enrollment.objects.select_related("student", "class_group")
        .filter(id=enrollment_id)
        .first()
    )
    if not enrollment:
        raise Http404("Student enrollment not found.")

    institution = InstitutionProfile.objects.first()
    inst_name = institution.name if institution else "CLASSFELLOW HIGH SCHOOL & ACADEMY"

    # Load all subjects configured for this exam and class
    exam_subjects = list(
        ExamSubject.objects.filter(
            exam=exam,
            class_group=enrollment.class_group,
        ).select_related("subject")
    )

    if not exam_subjects:
        raise Http404("No subjects configured for this examination and class.")

    # Load marks for this enrollment
    marks_map = {
        m.exam_subject_id: m
        for m in Mark.objects.filter(
            exam_subject__in=exam_subjects,
            enrollment=enrollment,
        )
    }

    # Grading Tiers
    grading_tiers = list(
        GradingTier.objects.filter(session=exam.session).order_by("-min_percentage")
    )

    subject_results = []
    total_max = Decimal("0.00")
    total_obtained = Decimal("0.00")

    for es in exam_subjects:
        m = marks_map.get(es.id)
        obt = m.marks_obtained if (m and not m.is_absent) else Decimal("0.00")
        is_absent = m.is_absent if m else False
        is_passed = (obt >= es.passing_marks) and not is_absent

        pct = (
            ((obt / es.maximum_marks) * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if es.maximum_marks > 0
            else Decimal("0.00")
        )

        sub_grade = "F"
        for tier in grading_tiers:
            if tier.min_percentage <= pct <= tier.max_percentage:
                sub_grade = tier.grade_name
                break

        subject_results.append(
            SubjectResultDTO(
                subject_name=es.subject.name,
                subject_urdu_name=es.subject.urdu_name or None,
                maximum_marks=es.maximum_marks,
                passing_marks=es.passing_marks,
                marks_obtained=obt,
                is_absent=is_absent,
                is_passed=is_passed,
                grade=sub_grade,
            )
        )
        total_max += es.maximum_marks
        total_obtained += obt

    # Overall percentage and final grade
    overall_pct = (
        ((total_obtained / total_max) * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if total_max > 0
        else Decimal("0.00")
    )

    final_grade = "F"
    gpa_point = Decimal("0.00")
    for tier in grading_tiers:
        if tier.min_percentage <= overall_pct <= tier.max_percentage:
            final_grade = tier.grade_name
            gpa_point = tier.gpa_point
            break

    # Calculate class rank
    class_results = ExamWebService.calculate_class_results(exam.id, enrollment.class_group.id)
    rank = 1
    for r in class_results:
        if r["enrollment_id"] == enrollment.id:
            rank = r["rank"]
            break

    # Attendance calculation for student
    att_records = AttendanceRecord.objects.filter(enrollment=enrollment)
    total_att = att_records.count()
    present_att = att_records.filter(status=AttendanceStatus.PRESENT).count()
    att_pct = round((present_att / total_att * 100), 1) if total_att > 0 else 95.0

    report_dto = StudentReportCardDTO(
        student_name=f"{enrollment.student.first_name} {enrollment.student.last_name}".strip(),
        urdu_name=enrollment.student.urdu_name or None,
        roll_number=enrollment.roll_number or None,
        class_name=f"{enrollment.class_group.name} - {enrollment.class_group.section_or_batch}",
        admission_number=enrollment.student.admission_number,
        exam_name=exam.name,
        session_name=exam.session.name,
        results=subject_results,
        total_maximum=total_max,
        total_obtained=total_obtained,
        percentage=overall_pct,
        final_grade=final_grade,
        gpa_point=gpa_point,
        rank_in_class=rank,
        total_students_in_class=len(class_results) or 1,
        attendance_percentage=att_pct,
        teacher_remarks="Satisfactory performance. Maintain consistent dedication.",
        teacher_urdu_remarks="شاندار کارکردگی۔ محنت جاری رکھیں۔",
        enrollment_id=enrollment.id,
    )

    pdf_buffer = io.BytesIO()
    generate_report_card_pdf(
        report_data=report_dto,
        output=pdf_buffer,
        institution_name=inst_name,
    )

    pdf_bytes = pdf_buffer.getvalue()
    pdf_buffer.close()

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    filename = f"Report_Card_{enrollment.student.admission_number}_{exam.name}.pdf".replace(" ", "_")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response
