"""
ClassFellow Web - Attendance Domain Web Service (AttendanceWebService)
Implements business logic for class rosters with default 'Present' status,
atomic bulk upsert on attendance records, and bilingual WhatsApp absence notifications.
"""

import datetime
import urllib.parse
from typing import Any, Dict, List, Optional

from django.db import transaction
from django.utils import timezone

from apps.attendance.models import AttendanceRecord, AttendanceStatus, BatchSession
from apps.students.models import Enrollment, EnrollmentStatus
from apps.students.services import normalize_pakistan_phone


class AttendanceWebService:
    """Encapsulates attendance logging, bulk roster entry, and absence alerts."""

    @staticmethod
    def load_class_roster(
        class_group_id: int,
        attendance_date: datetime.date,
    ) -> List[Dict[str, Any]]:
        """
        Loads the active student roster for a class group on a specific date.
        If attendance has already been recorded, existing statuses are populated;
        otherwise, all students default to 'Present'.
        """
        enrollments = (
            Enrollment.objects.filter(
                class_group_id=class_group_id,
                status=EnrollmentStatus.ACTIVE,
            )
            .select_related("student", "class_group")
            .order_by("roll_number", "student__first_name")
        )

        existing_records = {
            rec.enrollment_id: rec
            for rec in AttendanceRecord.objects.filter(
                enrollment__class_group_id=class_group_id,
                attendance_date=attendance_date,
            )
        }

        roster = []
        for enr in enrollments:
            rec = existing_records.get(enr.id)
            roster.append(
                {
                    "enrollment_id": enr.id,
                    "student_id": enr.student.id,
                    "roll_number": enr.roll_number,
                    "admission_number": enr.student.admission_number,
                    "student_name": f"{enr.student.first_name} {enr.student.last_name}".strip(),
                    "urdu_name": enr.student.urdu_name,
                    "guardian_name": enr.student.guardian_name,
                    "guardian_phone": enr.student.guardian_phone,
                    "status": rec.status if rec else AttendanceStatus.PRESENT,
                    "reason_note": rec.reason_note if rec else "",
                }
            )

        return roster

    @classmethod
    @transaction.atomic
    def save_bulk_attendance(
        cls,
        class_group_id: int,
        attendance_date: datetime.date,
        attendance_entries: List[Dict[str, Any]],
        recorded_by_user_id: Optional[int] = None,
        batch_session_id: Optional[int] = None,
    ) -> int:
        """
        Saves or updates daily attendance for multiple enrollments atomically.
        Uses bulk_create with update_conflicts for high-performance upserts.
        """
        valid_statuses = [s.value for s in AttendanceStatus]
        records_to_upsert = []

        for entry in attendance_entries:
            enrollment_id = entry["enrollment_id"]
            status = entry.get("status", AttendanceStatus.PRESENT)
            if status not in valid_statuses:
                raise ValueError(f"Invalid attendance status '{status}'. Must be one of {valid_statuses}.")

            reason_note = entry.get("reason_note", "")

            records_to_upsert.append(
                AttendanceRecord(
                    enrollment_id=enrollment_id,
                    attendance_date=attendance_date,
                    status=status,
                    reason_note=reason_note or "",
                    batch_session_id=batch_session_id,
                    recorded_by_user_id=recorded_by_user_id,
                )
            )

        if not records_to_upsert:
            return 0

        created_objs = AttendanceRecord.objects.bulk_create(
            records_to_upsert,
            update_conflicts=True,
            unique_fields=["enrollment", "attendance_date"],
            update_fields=["status", "reason_note", "batch_session", "recorded_by_user", "updated_at"],
        )

        return len(created_objs)

    @staticmethod
    def generate_whatsapp_payload(
        student_name: str,
        guardian_phone: str,
        attendance_date: datetime.date,
        institution_name: str = "ClassFellow School",
        urdu_name: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Generates a bilingual absence notification message and direct wa.me link.
        """
        norm_phone = normalize_pakistan_phone(guardian_phone)

        # Build wa.me international recipient (e.g. 03001234567 -> 923001234567)
        int_phone = "92" + norm_phone[1:]

        display_name = f"{student_name} ({urdu_name})" if urdu_name else student_name
        date_str = attendance_date.strftime("%Y-%m-%d")

        message_lines = [
            f"موقر والد صاحب / محترم سرپرست،",
            f"اطلاع دی جاتی ہے کہ آپ کا بچہ/بچی {display_name} آج مورخہ {date_str} کو بغیر پیشگی اطلاع غیر حاضر رہا/رہی ہے۔",
            f"Dear Guardian, this is to inform you that your child {student_name} was absent on {date_str}.",
            f"ادارہ: {institution_name}",
        ]
        message_text = "\n".join(message_lines)
        encoded_text = urllib.parse.quote(message_text)
        whatsapp_url = f"https://wa.me/{int_phone}?text={encoded_text}"

        return {
            "phone": norm_phone,
            "message_text": message_text,
            "whatsapp_url": whatsapp_url,
        }
