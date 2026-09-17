"""
ClassFellow Web - Examination Domain Web Service (ExamWebService)
Implements business logic for marks ledger recording, bounds validation,
grading tier evaluation, and joint class rank calculations.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.examinations.models import Exam, ExamSubject, GradingTier, Mark
from apps.students.models import Enrollment, EnrollmentStatus


class ExamWebService:
    """Encapsulates examination marks entry, grade boundaries, and class rankings."""

    @classmethod
    @transaction.atomic
    def record_student_marks(
        cls,
        exam_subject_id: int,
        enrollment_id: int,
        marks_obtained: Decimal,
        is_absent: bool = False,
        remarks: str = "",
        recorded_by_user_id: Optional[int] = None,
    ) -> Mark:
        """
        Records or updates student marks with strict upper and lower bound verification.
        Validates: 0.00 <= marks_obtained <= exam_subject.maximum_marks.
        """
        exam_subject = ExamSubject.objects.filter(id=exam_subject_id).first()
        if not exam_subject:
            raise ValueError(f"ExamSubject id={exam_subject_id} does not exist.")

        enrollment = Enrollment.objects.filter(id=enrollment_id).first()
        if not enrollment:
            raise ValueError(f"Enrollment id={enrollment_id} does not exist.")

        if is_absent:
            marks_obtained = Decimal("0.00")
        else:
            if marks_obtained < Decimal("0.00"):
                raise ValueError(f"Marks obtained cannot be negative: {marks_obtained}")
            if marks_obtained > exam_subject.maximum_marks:
                raise ValueError(
                    f"Marks obtained ({marks_obtained}) exceeds maximum marks ({exam_subject.maximum_marks})."
                )

        mark, _ = Mark.objects.update_or_create(
            exam_subject=exam_subject,
            enrollment=enrollment,
            defaults={
                "marks_obtained": marks_obtained,
                "is_absent": is_absent,
                "remarks": remarks.strip() if remarks else "",
                "recorded_by_user_id": recorded_by_user_id,
            },
        )

        return mark

    @staticmethod
    def calculate_class_results(
        exam_id: int,
        class_group_id: int,
    ) -> List[Dict[str, Any]]:
        """
        Calculates student scorecards, percentage aggregates, letter grades,
        and standard competition ranks (1, 2, 2, 4...) for a class group.
        """
        exam = Exam.objects.select_related("session").filter(id=exam_id).first()
        if not exam:
            raise ValueError(f"Exam id={exam_id} does not exist.")

        exam_subjects = list(
            ExamSubject.objects.filter(
                exam_id=exam_id,
                class_group_id=class_group_id,
            ).select_related("subject")
        )
        if not exam_subjects:
            return []

        total_max_marks = sum(es.maximum_marks for es in exam_subjects)
        if total_max_marks <= Decimal("0.00"):
            return []

        grading_tiers = list(
            GradingTier.objects.filter(session=exam.session).order_by("-min_percentage")
        )

        enrollments = (
            Enrollment.objects.filter(
                class_group_id=class_group_id,
                session=exam.session,
                status=EnrollmentStatus.ACTIVE,
            )
            .select_related("student")
            .order_by("roll_number", "student__first_name")
        )

        marks_by_enrollment: Dict[int, List[Mark]] = {}
        marks_qs = Mark.objects.filter(
            exam_subject__in=exam_subjects,
            enrollment__in=enrollments,
        ).select_related("exam_subject")

        for m in marks_qs:
            marks_by_enrollment.setdefault(m.enrollment_id, []).append(m)

        raw_results = []
        for enr in enrollments:
            student_marks = marks_by_enrollment.get(enr.id, [])
            total_obtained = sum((m.marks_obtained for m in student_marks), Decimal("0.00"))

            percentage = ((total_obtained / total_max_marks) * Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

            # Match grading tier
            matched_grade = "F"
            gpa = Decimal("0.00")
            is_passing = False
            for tier in grading_tiers:
                if tier.min_percentage <= percentage <= tier.max_percentage:
                    matched_grade = tier.grade_name
                    gpa = tier.gpa_point
                    is_passing = tier.is_passing
                    break

            raw_results.append(
                {
                    "enrollment_id": enr.id,
                    "student_id": enr.student.id,
                    "roll_number": enr.roll_number,
                    "admission_number": enr.student.admission_number,
                    "student_name": f"{enr.student.first_name} {enr.student.last_name}".strip(),
                    "urdu_name": enr.student.urdu_name,
                    "total_max_marks": total_max_marks,
                    "total_obtained": total_obtained,
                    "percentage": percentage,
                    "grade": matched_grade,
                    "gpa": gpa,
                    "is_passing": is_passing,
                }
            )

        # Sort descending by total obtained
        raw_results.sort(key=lambda r: r["total_obtained"], reverse=True)

        # Assign standard competition rank: 1, 2, 2, 4...
        ranked_results = []
        current_rank = 1
        for i, item in enumerate(raw_results):
            if i > 0 and item["total_obtained"] == raw_results[i - 1]["total_obtained"]:
                item["rank"] = ranked_results[i - 1]["rank"]
            else:
                item["rank"] = current_rank
            current_rank += 1
            ranked_results.append(item)

        return ranked_results
