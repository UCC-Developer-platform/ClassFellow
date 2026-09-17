"""
ClassFellow Web - Executive Analytics Service
============================================
Provides high-level institutional intelligence:
- Class-by-class and campus-level fee recovery percentages and top defaulter analysis.
- Multi-dimensional academic risk roster detecting low attendance (< 75%) and subject failure rates.
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.db.models import Sum
from django.db.models.functions import Coalesce

from apps.attendance.models import AttendanceRecord, AttendanceStatus
from apps.examinations.models import Mark
from apps.fees.models import FeeInvoice, Payment, PaymentStatus
from apps.students.models import ClassGroup, Enrollment, EnrollmentStatus


class ExecutiveAnalyticsService:
    """Encapsulates executive financial recovery metrics and academic at-risk screening."""

    @classmethod
    def get_financial_recovery_metrics(
        cls,
        session_id: int,
        month_year: str,
        campus_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Calculates class-by-class and aggregate fee recovery percentages for a given month.
        Returns:
            Dict containing:
            - 'total_invoiced': Decimal
            - 'total_collected': Decimal
            - 'total_outstanding': Decimal
            - 'overall_recovery_pct': Decimal
            - 'class_recovery_list': List[Dict]
            - 'top_defaulting_classes': List[Dict]
        """
        # Query active classes for the session
        classes_qs = ClassGroup.objects.filter(session_id=session_id).select_related("campus")
        if campus_id:
            classes_qs = classes_qs.filter(campus_id=campus_id)

        classes = list(classes_qs.order_by("name", "section_or_batch"))

        class_recovery_list: List[Dict[str, Any]] = []
        grand_total_invoiced = Decimal("0.00")
        grand_total_collected = Decimal("0.00")

        for cg in classes:
            # Query invoices for this class and billing month
            invoices = FeeInvoice.objects.filter(
                enrollment__class_group=cg,
                enrollment__session_id=session_id,
                month_year=month_year,
            )

            inv_agg = invoices.aggregate(total=Coalesce(Sum("net_due"), Decimal("0.00")))
            class_invoiced = inv_agg["total"]

            # Query collected payments on those invoices
            pay_agg = Payment.objects.filter(
                invoice__in=invoices,
                status=PaymentStatus.ISSUED,
            ).aggregate(total=Coalesce(Sum("amount"), Decimal("0.00")))
            class_collected = pay_agg["total"]

            class_outstanding = max(Decimal("0.00"), class_invoiced - class_collected)

            if class_invoiced > Decimal("0.00"):
                recovery_pct = round((class_collected / class_invoiced) * Decimal("100.00"), 2)
            else:
                recovery_pct = Decimal("100.00") if class_collected > Decimal("0.00") else Decimal("0.00")

            class_info = {
                "class_id": cg.id,
                "class_name": f"{cg.name} ({cg.section_or_batch})",
                "campus_name": cg.campus.name if cg.campus else "Main Campus",
                "invoiced_amount": class_invoiced,
                "collected_amount": class_collected,
                "outstanding_amount": class_outstanding,
                "recovery_percentage": recovery_pct,
                "invoices_count": invoices.count(),
            }
            class_recovery_list.append(class_info)
            grand_total_invoiced += class_invoiced
            grand_total_collected += class_collected

        grand_total_outstanding = max(Decimal("0.00"), grand_total_invoiced - grand_total_collected)
        if grand_total_invoiced > Decimal("0.00"):
            overall_recovery_pct = round((grand_total_collected / grand_total_invoiced) * Decimal("100.00"), 2)
        else:
            overall_recovery_pct = Decimal("100.00") if grand_total_collected > Decimal("0.00") else Decimal("0.00")

        # Sort top defaulting classes by outstanding debt descending
        top_defaulting = [c for c in class_recovery_list if c["outstanding_amount"] > Decimal("0.00")]
        top_defaulting.sort(key=lambda x: x["outstanding_amount"], reverse=True)

        return {
            "session_id": session_id,
            "month_year": month_year,
            "total_invoiced": grand_total_invoiced,
            "total_collected": grand_total_collected,
            "total_outstanding": grand_total_outstanding,
            "overall_recovery_pct": overall_recovery_pct,
            "class_recovery_list": class_recovery_list,
            "top_defaulting_classes": top_defaulting[:5],
        }

    @classmethod
    def get_academic_risk_roster(
        cls,
        session_id: int,
        exam_id: Optional[int] = None,
        threshold_pct: Decimal = Decimal("40.00"),
    ) -> List[Dict[str, Any]]:
        """
        Identifies students exhibiting attendance risk (< 75%) or examination failure across subjects.
        Returns a sorted roster of at-risk students with prioritized warning flags.
        """
        enrollments = (
            Enrollment.objects.filter(session_id=session_id, status=EnrollmentStatus.ACTIVE)
            .select_related("student", "class_group", "class_group__campus")
            .order_by("class_group__name", "student__admission_number")
        )

        risk_roster: List[Dict[str, Any]] = []

        for enrollment in enrollments:
            student = enrollment.student
            risk_factors: List[str] = []

            # 1. Attendance Risk Check (< 75% threshold)
            att_records = AttendanceRecord.objects.filter(enrollment=enrollment)
            total_days = att_records.count()
            att_pct: Optional[Decimal] = None

            if total_days > 0:
                present_days = att_records.filter(status=AttendanceStatus.PRESENT).count()
                att_pct = round((Decimal(present_days) / Decimal(total_days)) * Decimal("100.00"), 1)
                if att_pct < Decimal("75.0"):
                    risk_factors.append(f"Low Attendance: {att_pct}% ({present_days}/{total_days} days)")

            # 2. Academic / Exam Performance Check
            marks_qs = Mark.objects.filter(enrollment=enrollment).select_related(
                "exam_subject", "exam_subject__exam", "exam_subject__subject"
            )
            if exam_id:
                marks_qs = marks_qs.filter(exam_subject__exam_id=exam_id)
            else:
                marks_qs = marks_qs.filter(exam_subject__exam__session_id=session_id)

            failing_subjects_count = 0
            total_max = Decimal("0.00")
            total_obtained = Decimal("0.00")
            avg_exam_pct: Optional[Decimal] = None

            marks_list = list(marks_qs)
            if marks_list:
                for m in marks_list:
                    max_marks = m.exam_subject.maximum_marks
                    pass_marks = m.exam_subject.passing_marks
                    total_max += max_marks

                    if m.is_absent:
                        failing_subjects_count += 1
                    else:
                        total_obtained += m.marks_obtained
                        subj_pct = (
                            (m.marks_obtained / max_marks) * Decimal("100.00")
                            if max_marks > Decimal("0.00")
                            else Decimal("0.00")
                        )
                        if m.marks_obtained < pass_marks or subj_pct < threshold_pct:
                            failing_subjects_count += 1

                if total_max > Decimal("0.00"):
                    avg_exam_pct = round((total_obtained / total_max) * Decimal("100.00"), 1)

                if failing_subjects_count > 0:
                    risk_factors.append(f"Failed {failing_subjects_count} Subject(s)")
                elif avg_exam_pct is not None and avg_exam_pct < threshold_pct:
                    risk_factors.append(f"Low Exam Average: {avg_exam_pct}%")

            # If either attendance or exam risk detected, include in roster
            if risk_factors:
                student_full_name = f"{student.first_name} {student.last_name}".strip()
                risk_roster.append(
                    {
                        "enrollment_id": enrollment.id,
                        "student_id": student.id,
                        "admission_number": student.admission_number,
                        "student_name": student_full_name,
                        "urdu_name": student.urdu_name,
                        "class_name": f"{enrollment.class_group.name} ({enrollment.class_group.section_or_batch})",
                        "campus_name": (
                            enrollment.class_group.campus.name if enrollment.class_group.campus else "Main Campus"
                        ),
                        "guardian_name": student.guardian_name,
                        "guardian_phone": student.guardian_phone,
                        "attendance_percentage": att_pct,
                        "total_attendance_days": total_days,
                        "failing_subjects_count": failing_subjects_count,
                        "average_exam_percentage": avg_exam_pct,
                        "risk_factors": risk_factors,
                    }
                )

        # Sort priority: failing subjects count desc, then attendance asc
        risk_roster.sort(
            key=lambda x: (
                -x["failing_subjects_count"],
                x["attendance_percentage"] if x["attendance_percentage"] is not None else Decimal("100.0"),
            )
        )
        return risk_roster
