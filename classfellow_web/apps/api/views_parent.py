"""
ClassFellow Web - Parent Portal REST API Views
Secure endpoints for guardians to discover their children across campuses,
view fee account balances/receipts, monthly attendance summaries, and examination scorecards.
Enforces strict IDOR prevention (403 Forbidden on guardian-student phone mismatch).
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from django.db.models import Q, Sum
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.attendance.models import AttendanceRecord, AttendanceStatus
from apps.examinations.models import Exam, ExamSubject, Mark
from apps.examinations.services import ExamWebService
from apps.fees.models import FeeInvoice, Payment, PaymentStatus
from apps.students.models import Enrollment, EnrollmentStatus, Student
from apps.students.services import normalize_pakistan_phone


def _extract_phone_suffix(p: str) -> str:
    """Extracts the 10-digit phone subscriber suffix for format-agnostic matching."""
    digits = "".join(c for c in str(p) if c.isdigit())
    return digits[-10:] if len(digits) >= 10 else digits


def _get_guardian_normalized_phones(user, override_phone: Optional[str] = None) -> List[str]:
    """Extracts and normalizes phone numbers for a guardian user."""
    phones: List[str] = []
    target = override_phone if override_phone else getattr(user, "phone", "")
    target = str(target).strip()
    if target:
        phones.append(target)
        try:
            norm = normalize_pakistan_phone(target)
            if norm not in phones:
                phones.append(norm)
        except ValueError:
            pass
    return phones


def _verify_parent_access(user, enrollment_id: int) -> Union[Enrollment, None, bool]:
    """
    Validates that the authenticated user is authorized to access the given enrollment.
    Returns:
        Enrollment object if authorized.
        None if enrollment does not exist (HTTP 404).
        False if IDOR check fails: authenticated guardian's phone does not match student's guardian_phone (HTTP 403).
    """
    enrollment = (
        Enrollment.objects.select_related("student", "class_group__campus", "session")
        .filter(id=enrollment_id)
        .first()
    )
    if not enrollment:
        return None

    if user.is_superuser or user.role in [Role.ADMIN, Role.PRINCIPAL]:
        return enrollment

    user_phones = _get_guardian_normalized_phones(user)
    if not user_phones:
        return False

    stu_phone = enrollment.student.guardian_phone.strip()
    stu_suffix = _extract_phone_suffix(stu_phone)

    for up in user_phones:
        if up == stu_phone:
            return enrollment
        up_suffix = _extract_phone_suffix(up)
        if up_suffix and up_suffix == stu_suffix:
            return enrollment

    return False


class ParentChildrenView(APIView):
    """
    GET /api/v1/parent/children/
    Identifies children enrolled across campuses matching the authenticated guardian's phone.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        user = request.user
        override_phone = None
        if (user.is_superuser or user.role in [Role.ADMIN, Role.PRINCIPAL]) and "phone" in request.query_params:
            override_phone = request.query_params.get("phone", "").strip()

        guardian_phones = _get_guardian_normalized_phones(user, override_phone=override_phone)
        if not guardian_phones:
            return Response([], status=status.HTTP_200_OK)

        norm_targets = set()
        for p in guardian_phones:
            try:
                norm_targets.add(normalize_pakistan_phone(p))
            except ValueError:
                norm_targets.add(p)

        # Candidate query in SQL
        q_filter = Q(guardian_phone__in=guardian_phones)
        for p in guardian_phones:
            clean_digits = "".join(c for c in p if c.isdigit())
            if len(clean_digits) >= 7:
                q_filter |= Q(guardian_phone__icontains=clean_digits[-7:])

        candidate_students = Student.objects.filter(q_filter)
        matched_student_ids = []
        for stu in candidate_students:
            try:
                stu_norm = normalize_pakistan_phone(stu.guardian_phone)
                if stu_norm in norm_targets:
                    matched_student_ids.append(stu.id)
                    continue
            except ValueError:
                pass
            if any(_extract_phone_suffix(stu.guardian_phone) == _extract_phone_suffix(t) for t in norm_targets):
                matched_student_ids.append(stu.id)

        enrollments = (
            Enrollment.objects.filter(
                student_id__in=matched_student_ids,
                status=EnrollmentStatus.ACTIVE,
            )
            .select_related("student", "class_group__campus", "session")
            .order_by("student__first_name", "student__last_name")
        )

        results: List[Dict[str, Any]] = []
        for enr in enrollments:
            stu = enr.student
            cg = enr.class_group
            results.append(
                {
                    "enrollment_id": enr.id,
                    "student_id": stu.id,
                    "admission_number": stu.admission_number,
                    "first_name": stu.first_name,
                    "last_name": stu.last_name,
                    "full_name": f"{stu.first_name} {stu.last_name}".strip(),
                    "urdu_name": stu.urdu_name,
                    "gender": stu.gender,
                    "roll_number": enr.roll_number,
                    "class_name": cg.name,
                    "section": cg.section_or_batch,
                    "campus_id": cg.campus_id if cg.campus else None,
                    "campus_name": cg.campus.name if cg.campus else "Main Campus",
                    "session_id": enr.session_id,
                    "session_name": enr.session.name,
                    "guardian_name": stu.guardian_name,
                    "guardian_phone": stu.guardian_phone,
                }
            )

        return Response(results, status=status.HTTP_200_OK)


class ParentFeeSummaryView(APIView):
    """
    GET /api/v1/parent/fees/?enrollment_id=<id>
    Returns fee invoice breakdown, outstanding balance, and payment receipts.
    Enforces strict IDOR parent-child ownership verification.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        enrollment_id_str = request.query_params.get("enrollment_id", "").strip()
        if not enrollment_id_str or not enrollment_id_str.isdigit():
            return Response(
                {"error": "Query parameter 'enrollment_id' (integer) is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        access_check = _verify_parent_access(request.user, int(enrollment_id_str))
        if access_check is None:
            return Response({"error": "Enrollment not found."}, status=status.HTTP_404_NOT_FOUND)
        if access_check is False:
            return Response(
                {"error": "Access denied. You are not authorized to view fee records for this student."},
                status=status.HTTP_403_FORBIDDEN,
            )

        enrollment = access_check
        invoices = (
            FeeInvoice.objects.filter(enrollment=enrollment)
            .prefetch_related("items__fee_head")
            .order_by("-issue_date")
        )

        invoice_data = []
        total_billed = Decimal("0.00")
        total_paid = Decimal("0.00")

        for inv in invoices:
            total_billed += inv.net_due
            inv_paid = (
                Payment.objects.filter(invoice=inv, status=PaymentStatus.ISSUED).aggregate(
                    total=Sum("amount")
                )["total"]
                or Decimal("0.00")
            )
            total_paid += inv_paid
            inv_balance = max(Decimal("0.00"), inv.net_due - inv_paid)

            items_list = [
                {"head": item.fee_head.name, "amount": str(item.amount)}
                for item in inv.items.all()
            ]

            invoice_data.append(
                {
                    "invoice_id": inv.id,
                    "month_year": inv.month_year,
                    "issue_date": inv.issue_date.isoformat(),
                    "due_date": inv.due_date.isoformat(),
                    "valid_until": inv.valid_until.isoformat(),
                    "total_payable": str(inv.total_payable),
                    "discount_amount": str(inv.discount_amount),
                    "net_due": str(inv.net_due),
                    "paid_amount": str(inv_paid),
                    "balance": str(inv_balance),
                    "is_paid": inv_balance <= Decimal("0.00"),
                    "items": items_list,
                }
            )

        total_outstanding = max(Decimal("0.00"), total_billed - total_paid)

        payments = Payment.objects.filter(
            invoice__enrollment=enrollment, status=PaymentStatus.ISSUED
        ).order_by("-payment_date", "-id")

        payment_data = [
            {
                "receipt_number": p.receipt_number,
                "amount": str(p.amount),
                "payment_date": p.payment_date.isoformat(),
                "payment_method": p.payment_method,
                "invoice_id": p.invoice_id,
                "month_year": p.invoice.month_year,
            }
            for p in payments
        ]

        stu = enrollment.student
        return Response(
            {
                "student": {
                    "admission_number": stu.admission_number,
                    "full_name": f"{stu.first_name} {stu.last_name}".strip(),
                    "class_name": enrollment.class_group.name,
                    "section": enrollment.class_group.section_or_batch,
                },
                "total_billed": str(total_billed),
                "total_paid": str(total_paid),
                "total_outstanding": str(total_outstanding),
                "invoices": invoice_data,
                "payments": payment_data,
            },
            status=status.HTTP_200_OK,
        )


class ParentAttendanceView(APIView):
    """
    GET /api/v1/parent/attendance/?enrollment_id=<id>&month_year=<YYYY-MM>
    Returns monthly attendance calendar, counts, and attendance percentage.
    Enforces strict IDOR parent-child ownership verification.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        enrollment_id_str = request.query_params.get("enrollment_id", "").strip()
        if not enrollment_id_str or not enrollment_id_str.isdigit():
            return Response(
                {"error": "Query parameter 'enrollment_id' (integer) is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        access_check = _verify_parent_access(request.user, int(enrollment_id_str))
        if access_check is None:
            return Response({"error": "Enrollment not found."}, status=status.HTTP_404_NOT_FOUND)
        if access_check is False:
            return Response(
                {"error": "Access denied. You are not authorized to view attendance records for this student."},
                status=status.HTTP_403_FORBIDDEN,
            )

        enrollment = access_check
        records_qs = AttendanceRecord.objects.filter(enrollment=enrollment)

        month_year = request.query_params.get("month_year", "").strip()
        if month_year:
            parts = month_year.split("-")
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                records_qs = records_qs.filter(
                    attendance_date__year=int(parts[0]),
                    attendance_date__month=int(parts[1]),
                )

        records_qs = records_qs.order_by("attendance_date")

        total_days = records_qs.count()
        present_days = records_qs.filter(status=AttendanceStatus.PRESENT).count()
        absent_days = records_qs.filter(status=AttendanceStatus.ABSENT).count()
        leave_days = records_qs.filter(status=AttendanceStatus.LEAVE).count()
        late_days = records_qs.filter(status=AttendanceStatus.LATE).count()

        if total_days > 0:
            att_pct = (Decimal(present_days) / Decimal(total_days) * Decimal("100.00")).quantize(
                Decimal("0.1")
            )
        else:
            att_pct = Decimal("0.0")

        daily_log = [
            {
                "date": rec.attendance_date.isoformat(),
                "status": rec.status,
                "reason_note": rec.reason_note,
            }
            for rec in records_qs
        ]

        stu = enrollment.student
        return Response(
            {
                "student": {
                    "admission_number": stu.admission_number,
                    "full_name": f"{stu.first_name} {stu.last_name}".strip(),
                    "class_name": enrollment.class_group.name,
                },
                "month_year": month_year or "All",
                "total_days": total_days,
                "present_days": present_days,
                "absent_days": absent_days,
                "leave_days": leave_days,
                "late_days": late_days,
                "attendance_percentage": str(att_pct),
                "records": daily_log,
            },
            status=status.HTTP_200_OK,
        )


class ParentReportCardView(APIView):
    """
    GET /api/v1/parent/report-card/?enrollment_id=<id>&exam_id=<id>
    Returns examination scorecard, subject marks, overall percentage, letter grade, and class rank.
    Enforces strict IDOR parent-child ownership verification.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        enrollment_id_str = request.query_params.get("enrollment_id", "").strip()
        if not enrollment_id_str or not enrollment_id_str.isdigit():
            return Response(
                {"error": "Query parameter 'enrollment_id' (integer) is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        access_check = _verify_parent_access(request.user, int(enrollment_id_str))
        if access_check is None:
            return Response({"error": "Enrollment not found."}, status=status.HTTP_404_NOT_FOUND)
        if access_check is False:
            return Response(
                {"error": "Access denied. You are not authorized to view examination records for this student."},
                status=status.HTTP_403_FORBIDDEN,
            )

        enrollment = access_check

        exam_id_str = request.query_params.get("exam_id", "").strip()
        if exam_id_str and exam_id_str.isdigit():
            exam = Exam.objects.filter(id=int(exam_id_str)).select_related("session").first()
        else:
            exam = (
                Exam.objects.filter(session=enrollment.session)
                .select_related("session")
                .order_by("-start_date")
                .first()
            )

        if not exam:
            return Response(
                {"error": "No examination found for this enrollment session."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Calculate class results for rank and aggregates
        class_results = ExamWebService.calculate_class_results(
            exam_id=exam.id,
            class_group_id=enrollment.class_group_id,
        )
        student_result = next(
            (r for r in class_results if r["enrollment_id"] == enrollment.id),
            None,
        )

        exam_subjects = (
            ExamSubject.objects.filter(exam=exam, class_group=enrollment.class_group)
            .select_related("subject")
            .order_by("subject__name")
        )

        marks_records = {
            m.exam_subject_id: m
            for m in Mark.objects.filter(
                exam_subject__in=exam_subjects,
                enrollment=enrollment,
            )
        }

        subject_scorecards = []
        for es in exam_subjects:
            mark_entry = marks_records.get(es.id)
            if mark_entry:
                marks_obt = mark_entry.marks_obtained
                is_abs = mark_entry.is_absent
                rem = mark_entry.remarks
                is_pass = (not is_abs) and (marks_obt >= es.passing_marks)
            else:
                marks_obt = Decimal("0.00")
                is_abs = False
                rem = "Pending"
                is_pass = False

            subject_scorecards.append(
                {
                    "subject_name": es.subject.name,
                    "subject_code": es.subject.code,
                    "maximum_marks": str(es.maximum_marks),
                    "passing_marks": str(es.passing_marks),
                    "marks_obtained": str(marks_obt),
                    "is_absent": is_abs,
                    "is_passed": is_pass,
                    "remarks": rem,
                }
            )

        stu = enrollment.student
        return Response(
            {
                "student": {
                    "admission_number": stu.admission_number,
                    "full_name": f"{stu.first_name} {stu.last_name}".strip(),
                    "class_name": enrollment.class_group.name,
                    "section": enrollment.class_group.section_or_batch,
                },
                "exam": {
                    "id": exam.id,
                    "name": exam.name,
                    "term": exam.get_exam_type_display(),
                    "session_name": exam.session.name,
                },
                "summary": {
                    "total_obtained": str(
                        student_result.get("total_obtained", Decimal("0.00"))
                        if student_result
                        else Decimal("0.00")
                    ),
                    "total_maximum": str(
                        student_result.get("total_max_marks", Decimal("0.00"))
                        if student_result
                        else Decimal("0.00")
                    ),
                    "percentage": str(
                        student_result.get("percentage", Decimal("0.00"))
                        if student_result
                        else Decimal("0.00")
                    ),
                    "letter_grade": (
                        student_result.get("grade", "N/A")
                        if student_result
                        else "N/A"
                    ),
                    "class_rank": (
                        student_result.get("rank", "N/A")
                        if student_result
                        else "N/A"
                    ),
                },
                "subjects": subject_scorecards,
            },
            status=status.HTTP_200_OK,
        )
