"""
ClassFellow Web - Student Domain Web Service (StudentWebService)
Implements business logic for student identities, phone validation,
auto-incrementing admission numbers, profile search, and enrollment status transitions.
"""

import datetime
import re
from decimal import Decimal
from typing import Optional, Tuple

from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.core.models import AcademicSession
from apps.students.models import ClassGroup, Enrollment, EnrollmentStatus, Gender, Student


def normalize_pakistan_phone(phone: str) -> str:
    """
    Normalizes and validates a Pakistani mobile number.
    Accepts: '03001234567', '+923001234567', '00923001234567', '0300-1234567', '0300 1234567'.

    Returns:
        Standard 11-digit string matching regex: ^03[0-9]{9}$
    Raises:
        ValueError: If phone number does not conform to Pakistani mobile standard.
    """
    if not phone or not str(phone).strip():
        raise ValueError("Phone number cannot be empty.")

    cleaned = str(phone).strip()
    cleaned = re.sub(r"[\s\-\(\)\.]", "", cleaned)

    if cleaned.startswith("0092"):
        cleaned = "0" + cleaned[4:]
    elif cleaned.startswith("+92"):
        cleaned = "0" + cleaned[3:]
    elif cleaned.startswith("92") and len(cleaned) == 12:
        cleaned = "0" + cleaned[2:]

    if not re.match(r"^03\d{9}$", cleaned):
        raise ValueError(
            f"Invalid Pakistani phone number: '{phone}'. Must be 11 digits starting with '03' (e.g., 03001234567)."
        )

    return cleaned


class StudentWebService:
    """Encapsulates student registration, search, and enrollment workflows using Django ORM."""

    @staticmethod
    def generate_next_admission_number(year: Optional[int] = None) -> str:
        """
        Generates the next sequential admission number for the given calendar year.
        Format: 'CF-YYYY-XXXX' (e.g., 'CF-2026-0001').
        """
        if year is None:
            active_session = AcademicSession.objects.filter(is_active=True).first()
            if active_session and active_session.start_date:
                year = active_session.start_date.year
            else:
                year = datetime.date.today().year

        prefix = f"CF-{year}-"
        last_student = (
            Student.objects.filter(admission_number__startswith=prefix)
            .order_by("-id")
            .first()
        )
        if not last_student:
            return f"{prefix}0001"

        try:
            parts = last_student.admission_number.split("-")
            seq = int(parts[-1])
            return f"{prefix}{seq + 1:04d}"
        except (ValueError, IndexError):
            return f"{prefix}0001"

    @classmethod
    @transaction.atomic
    def register_student(
        cls,
        first_name: str,
        guardian_name: str,
        guardian_phone: str,
        gender: str,
        session_id: int,
        class_group_id: int,
        last_name: str = "",
        urdu_name: str = "",
        guardian_urdu_name: str = "",
        guardian_relation: str = "Father",
        guardian_whatsapp: str = "",
        guardian_cnic: str = "",
        date_of_birth: Optional[datetime.date] = None,
        b_form_number: str = "",
        residential_address: str = "",
        emergency_contact: str = "",
        admission_number: Optional[str] = None,
        roll_number: str = "",
        enrollment_date: Optional[datetime.date] = None,
        custom_discount_amount: Decimal = Decimal("0.00"),
    ) -> Tuple[Student, Enrollment]:
        """
        Registers a student and creates their initial class enrollment atomically.
        """
        if not first_name or not first_name.strip():
            raise ValueError("Student first name cannot be empty.")
        if not guardian_name or not guardian_name.strip():
            raise ValueError("Guardian name cannot be empty.")

        norm_phone = normalize_pakistan_phone(guardian_phone)
        norm_whatsapp = (
            normalize_pakistan_phone(guardian_whatsapp) if guardian_whatsapp and guardian_whatsapp.strip() else ""
        )

        valid_genders = [g.value for g in Gender]
        if gender not in valid_genders:
            raise ValueError(f"Invalid gender '{gender}'. Must be one of {valid_genders}.")

        session = AcademicSession.objects.filter(id=session_id).first()
        if not session:
            raise ValueError(f"AcademicSession id={session_id} does not exist.")

        class_group = ClassGroup.objects.filter(id=class_group_id, session=session).first()
        if not class_group:
            raise ValueError(f"ClassGroup id={class_group_id} does not exist in session {session.name}.")

        if not admission_number or not str(admission_number).strip():
            year = session.start_date.year if session.start_date else datetime.date.today().year
            admission_number = cls.generate_next_admission_number(year)
        else:
            admission_number = admission_number.strip()
            if Student.objects.filter(admission_number=admission_number).exists():
                raise ValueError(f"Admission number '{admission_number}' already exists.")

        student = Student.objects.create(
            admission_number=admission_number,
            first_name=first_name.strip(),
            last_name=last_name.strip() if last_name else "",
            urdu_name=urdu_name.strip() if urdu_name else "",
            gender=gender,
            date_of_birth=date_of_birth,
            b_form_number=b_form_number.strip() if b_form_number else "",
            guardian_name=guardian_name.strip(),
            guardian_urdu_name=guardian_urdu_name.strip() if guardian_urdu_name else "",
            guardian_relation=guardian_relation.strip() if guardian_relation else "Father",
            guardian_phone=norm_phone,
            guardian_whatsapp=norm_whatsapp,
            guardian_cnic=guardian_cnic.strip() if guardian_cnic else "",
            residential_address=residential_address.strip() if residential_address else "",
            emergency_contact=emergency_contact.strip() if emergency_contact else "",
            is_active=True,
        )

        enrollment = Enrollment.objects.create(
            student=student,
            class_group=class_group,
            session=session,
            roll_number=roll_number.strip() if roll_number else "",
            enrollment_date=enrollment_date or timezone.now().date(),
            status=EnrollmentStatus.ACTIVE,
            custom_discount_amount=custom_discount_amount,
        )

        return student, enrollment

    @staticmethod
    def search_students(
        query: str = "",
        session_id: Optional[int] = None,
        class_group_id: Optional[int] = None,
        status: Optional[str] = None,
    ) -> QuerySet[Student]:
        """
        Performs high-speed multi-field filtering across student and enrollment records.
        """
        qs = Student.objects.prefetch_related("enrollments", "enrollments__class_group")

        if query and query.strip():
            term = query.strip()
            qs = qs.filter(
                Q(admission_number__icontains=term)
                | Q(first_name__icontains=term)
                | Q(last_name__icontains=term)
                | Q(urdu_name__icontains=term)
                | Q(guardian_name__icontains=term)
                | Q(guardian_phone__icontains=term)
                | Q(enrollments__roll_number__icontains=term)
            ).distinct()

        if session_id is not None:
            qs = qs.filter(enrollments__session_id=session_id)

        if class_group_id is not None:
            qs = qs.filter(enrollments__class_group_id=class_group_id)

        if status:
            qs = qs.filter(enrollments__status=status)

        return qs.order_by("admission_number")

    @classmethod
    @transaction.atomic
    def update_student_status(cls, enrollment_id: int, new_status: str) -> Enrollment:
        """
        Updates an enrollment status (Active, Withdrawn, Transferred, Graduated).
        If status is Withdrawn and no other active enrollments exist, sets student.is_active = False.
        """
        valid_statuses = [s.value for s in EnrollmentStatus]
        if new_status not in valid_statuses:
            raise ValueError(f"Invalid status '{new_status}'. Must be one of {valid_statuses}.")

        enrollment = Enrollment.objects.select_for_update().filter(id=enrollment_id).first()
        if not enrollment:
            raise ValueError(f"Enrollment id={enrollment_id} does not exist.")

        enrollment.status = new_status
        enrollment.save(update_fields=["status"])

        if new_status == EnrollmentStatus.WITHDRAWN:
            other_active = Enrollment.objects.filter(
                student=enrollment.student,
                status=EnrollmentStatus.ACTIVE,
            ).exclude(id=enrollment.id).exists()
            if not other_active:
                enrollment.student.is_active = False
                enrollment.student.save(update_fields=["is_active", "updated_at"])
        elif new_status == EnrollmentStatus.ACTIVE:
            if not enrollment.student.is_active:
                enrollment.student.is_active = True
                enrollment.student.save(update_fields=["is_active", "updated_at"])

        return enrollment
