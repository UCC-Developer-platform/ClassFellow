"""
ClassFellow Web - Teacher Mobile REST API Views
Endpoints for teacher class allocations, attendance rosters, bulk attendance upserts,
and examination marks entry with strict bounds validation.
"""

import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.attendance.services import AttendanceWebService
from apps.examinations.models import ExamSubject
from apps.examinations.services import ExamWebService
from apps.staff.models import StaffSubjectAllocation
from apps.students.models import ClassGroup


def _is_staff_or_admin(user) -> bool:
    """Helper checking if user has staff/teacher permissions."""
    if user.is_superuser or user.role in [Role.ADMIN, Role.PRINCIPAL]:
        return True
    return user.role == Role.TEACHER or (hasattr(user, "staff_profile") and user.staff_profile is not None)


class TeacherAssignedClassesView(APIView):
    """
    GET /api/v1/teacher/classes/
    Returns classes and subjects allocated to the authenticated teacher.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        user = request.user
        if not _is_staff_or_admin(user):
            return Response(
                {"error": "Access denied. Teacher or administrative role required."},
                status=status.HTTP_403_FORBIDDEN,
            )

        allocations_qs = StaffSubjectAllocation.objects.select_related(
            "class_group__campus", "subject", "academic_session"
        )

        if user.is_superuser or user.role in [Role.ADMIN, Role.PRINCIPAL]:
            staff_id_param = request.query_params.get("staff_id")
            if staff_id_param and staff_id_param.isdigit():
                allocations_qs = allocations_qs.filter(staff_id=int(staff_id_param))
        else:
            staff_profile = getattr(user, "staff_profile", None)
            if not staff_profile:
                return Response(
                    {"error": "No linked staff profile found for this user."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            allocations_qs = allocations_qs.filter(staff=staff_profile)

        results: List[Dict[str, Any]] = []
        for alloc in allocations_qs.order_by("class_group__name", "subject__name"):
            cg = alloc.class_group
            sub = alloc.subject
            sess = alloc.academic_session
            results.append(
                {
                    "allocation_id": alloc.id,
                    "class_group": {
                        "id": cg.id,
                        "name": cg.name,
                        "section": cg.section_or_batch,
                        "campus_id": cg.campus_id,
                        "campus_name": cg.campus.name if cg.campus else None,
                    },
                    "subject": {
                        "id": sub.id,
                        "name": sub.name,
                        "code": sub.code,
                    },
                    "academic_session": {
                        "id": sess.id,
                        "name": sess.name,
                        "is_active": sess.is_active,
                    },
                }
            )

        return Response(results, status=status.HTTP_200_OK)


class TeacherRosterView(APIView):
    """
    GET /api/v1/teacher/roster/?class_group_id=<id>&date=<YYYY-MM-DD>
    Loads the student attendance roster for a class on a specified date.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        user = request.user
        if not _is_staff_or_admin(user):
            return Response(
                {"error": "Access denied. Teacher or administrative role required."},
                status=status.HTTP_403_FORBIDDEN,
            )

        class_group_id_str = request.query_params.get("class_group_id", "").strip()
        if not class_group_id_str or not class_group_id_str.isdigit():
            return Response(
                {"error": "Query parameter 'class_group_id' (integer) is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        class_group_id = int(class_group_id_str)
        if not ClassGroup.objects.filter(id=class_group_id).exists():
            return Response(
                {"error": f"Class group id={class_group_id} does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Scoping check for teachers
        if not (user.is_superuser or user.role in [Role.ADMIN, Role.PRINCIPAL]):
            staff_profile = getattr(user, "staff_profile", None)
            if not staff_profile or not StaffSubjectAllocation.objects.filter(
                staff=staff_profile, class_group_id=class_group_id
            ).exists():
                return Response(
                    {"error": "You are not assigned to this class group."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        date_str = request.query_params.get("date", "").strip()
        if date_str:
            try:
                attendance_date = datetime.date.fromisoformat(date_str)
            except ValueError:
                return Response(
                    {"error": "Invalid date format. Expected YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            attendance_date = timezone.localdate()

        roster = AttendanceWebService.load_class_roster(
            class_group_id=class_group_id,
            attendance_date=attendance_date,
        )

        return Response(
            {
                "class_group_id": class_group_id,
                "attendance_date": attendance_date.isoformat(),
                "total_students": len(roster),
                "roster": roster,
            },
            status=status.HTTP_200_OK,
        )


class TeacherAttendanceSaveView(APIView):
    """
    POST /api/v1/teacher/attendance/save/
    Bulk upserts student attendance records with user audit attribution.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        user = request.user
        if not _is_staff_or_admin(user):
            return Response(
                {"error": "Access denied. Teacher or administrative role required."},
                status=status.HTTP_403_FORBIDDEN,
            )

        data = request.data
        class_group_id = data.get("class_group_id")
        date_str = data.get("attendance_date")
        entries = data.get("attendance_entries", [])
        batch_session_id = data.get("batch_session_id")

        if not class_group_id or not date_str:
            return Response(
                {"error": "'class_group_id' and 'attendance_date' are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            class_group_id = int(class_group_id)
            attendance_date = datetime.date.fromisoformat(str(date_str))
        except (ValueError, TypeError):
            return Response(
                {"error": "Invalid 'class_group_id' or 'attendance_date' (YYYY-MM-DD)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(entries, list) or len(entries) == 0:
            return Response(
                {"error": "'attendance_entries' must be a non-empty list."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Scoping check for teachers
        if not (user.is_superuser or user.role in [Role.ADMIN, Role.PRINCIPAL]):
            staff_profile = getattr(user, "staff_profile", None)
            if not staff_profile or not StaffSubjectAllocation.objects.filter(
                staff=staff_profile, class_group_id=class_group_id
            ).exists():
                return Response(
                    {"error": "You are not assigned to record attendance for this class."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        try:
            saved_count = AttendanceWebService.save_bulk_attendance(
                class_group_id=class_group_id,
                attendance_date=attendance_date,
                attendance_entries=entries,
                recorded_by_user_id=user.id,
                batch_session_id=batch_session_id,
            )
        except ValueError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "status": "success",
                "saved_count": saved_count,
                "message": f"Successfully saved attendance for {saved_count} students.",
            },
            status=status.HTTP_200_OK,
        )


class TeacherMarksSaveView(APIView):
    """
    POST /api/v1/teacher/marks/save/
    Submits student exam marks with bounds validation (0 <= marks <= maximum_marks).
    Accepts either a single mark payload or a batch {"marks": [...]}.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        user = request.user
        if not _is_staff_or_admin(user):
            return Response(
                {"error": "Access denied. Teacher or administrative role required."},
                status=status.HTTP_403_FORBIDDEN,
            )

        data = request.data
        if "marks" in data and isinstance(data["marks"], list):
            items_to_save = data["marks"]
        else:
            items_to_save = [data]

        if not items_to_save:
            return Response(
                {"error": "No marks data provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Pre-validate exam subjects and teacher scoping
        staff_profile = getattr(user, "staff_profile", None)
        is_admin = user.is_superuser or user.role in [Role.ADMIN, Role.PRINCIPAL]

        recorded_marks = []
        try:
            for item in items_to_save:
                exam_subject_id = item.get("exam_subject_id")
                enrollment_id = item.get("enrollment_id")
                marks_val = item.get("marks_obtained")
                is_absent = bool(item.get("is_absent", False))
                remarks = str(item.get("remarks", "")).strip()

                if exam_subject_id is None or enrollment_id is None:
                    return Response(
                        {"error": "'exam_subject_id' and 'enrollment_id' are required."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                exam_sub = ExamSubject.objects.filter(id=exam_subject_id).first()
                if not exam_sub:
                    return Response(
                        {"error": f"ExamSubject id={exam_subject_id} not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                if not is_admin:
                    if not staff_profile or not StaffSubjectAllocation.objects.filter(
                        staff=staff_profile,
                        class_group=exam_sub.class_group,
                        subject=exam_sub.subject,
                    ).exists():
                        return Response(
                            {"error": f"You are not assigned to record marks for {exam_sub.subject.name}."},
                            status=status.HTTP_403_FORBIDDEN,
                        )

                if is_absent:
                    decimal_marks = Decimal("0.00")
                else:
                    if marks_val is None:
                        return Response(
                            {"error": "Marks obtained is required when student is present."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    try:
                        decimal_marks = Decimal(str(marks_val))
                    except (InvalidOperation, TypeError):
                        return Response(
                            {"error": f"Invalid marks value: {marks_val}"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                mark_record = ExamWebService.record_student_marks(
                    exam_subject_id=exam_subject_id,
                    enrollment_id=enrollment_id,
                    marks_obtained=decimal_marks,
                    is_absent=is_absent,
                    remarks=remarks,
                    recorded_by_user_id=user.id,
                )
                recorded_marks.append(
                    {
                        "mark_id": mark_record.id,
                        "enrollment_id": mark_record.enrollment_id,
                        "exam_subject_id": mark_record.exam_subject_id,
                        "marks_obtained": str(mark_record.marks_obtained),
                        "is_absent": mark_record.is_absent,
                    }
                )
        except ValueError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "status": "success",
                "recorded_count": len(recorded_marks),
                "recorded_marks": recorded_marks,
                "message": f"Successfully recorded marks for {len(recorded_marks)} student(s).",
            },
            status=status.HTTP_200_OK,
        )
