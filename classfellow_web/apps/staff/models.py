"""
ClassFellow Web - Staff Models
Defines Staff records and teacher-to-subject class allocations.
"""

from decimal import Decimal
from django.conf import settings
from django.db import models


class Staff(models.Model):
    """Represents an employee, teacher, or administrator at the institution."""

    employee_id = models.CharField(
        max_length=50,
        unique=True,
        help_text="Institutional employee code (e.g., EMP-1001).",
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True, default="")
    urdu_name = models.CharField(
        max_length=150,
        blank=True,
        default="",
        help_text="Urdu Nastaliq staff name.",
    )
    designation = models.CharField(
        max_length=100,
        help_text="e.g. Senior Teacher, Accountant, Lab Assistant, Principal.",
    )
    department = models.CharField(
        max_length=100,
        blank=True,
        default="Administration",
        help_text="e.g. Science, Arts, Administration.",
    )
    campus = models.ForeignKey(
        "core.Campus",
        on_delete=models.RESTRICT,
        related_name="staff_members",
        help_text="Campus or branch assignment.",
    )
    phone = models.CharField(
        max_length=20,
        help_text="Normalized primary contact (03XXXXXXXXX).",
    )
    email = models.EmailField(blank=True, default="")
    national_id_cnic = models.CharField(
        max_length=30,
        blank=True,
        default="",
        help_text="NADRA CNIC number.",
    )
    basic_salary = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Monthly base remuneration in PKR.",
    )
    joining_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="staff_profile",
        help_text="Optional linked application login account.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "staff_members"
        verbose_name = "Staff Member"
        verbose_name_plural = "Staff Members"
        ordering = ["employee_id"]
        indexes = [
            models.Index(fields=["employee_id"], name="idx_staff_emp_id"),
            models.Index(fields=["first_name", "last_name"], name="idx_staff_names"),
            models.Index(fields=["phone"], name="idx_staff_phone"),
        ]

    def __str__(self):
        full = f"{self.first_name} {self.last_name}".strip()
        return f"{self.employee_id} - {full} ({self.designation})"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class StaffSubjectAllocation(models.Model):
    """Maps a teacher to a specific subject, class group, and academic session."""

    staff = models.ForeignKey(
        Staff,
        on_delete=models.CASCADE,
        related_name="allocations",
    )
    class_group = models.ForeignKey(
        "students.ClassGroup",
        on_delete=models.CASCADE,
        related_name="staff_allocations",
    )
    subject = models.ForeignKey(
        "examinations.Subject",
        on_delete=models.CASCADE,
        related_name="staff_allocations",
    )
    academic_session = models.ForeignKey(
        "core.AcademicSession",
        on_delete=models.CASCADE,
        related_name="staff_allocations",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "staff_allocations"
        verbose_name = "Staff Subject Allocation"
        verbose_name_plural = "Staff Subject Allocations"
        constraints = [
            models.UniqueConstraint(
                fields=["staff", "class_group", "subject", "academic_session"],
                name="unique_staff_class_subject_session",
            )
        ]

    def __str__(self):
        return f"{self.staff.full_name} -> {self.subject.name} ({self.class_group.name} - {self.academic_session.name})"
