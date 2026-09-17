from django.db import models
from django.utils import timezone


class Gender(models.TextChoices):
    MALE = "Male", "Male"
    FEMALE = "Female", "Female"
    OTHER = "Other", "Other"


class GroupType(models.TextChoices):
    SCHOOL_CLASS = "SchoolClass", "School Class"
    ACADEMY_BATCH = "AcademyBatch", "Academy Batch"


class EnrollmentStatus(models.TextChoices):
    ACTIVE = "Active", "Active"
    TRANSFERRED = "Transferred", "Transferred"
    WITHDRAWN = "Withdrawn", "Withdrawn"
    GRADUATED = "Graduated", "Graduated"


class Student(models.Model):
    admission_number = models.CharField(max_length=50, unique=True, help_text="Institutional registration number.")
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True, default="")
    urdu_name = models.CharField(max_length=150, blank=True, default="", help_text="Urdu Nastaliq student name.")
    gender = models.CharField(max_length=20, choices=Gender.choices)
    date_of_birth = models.DateField(null=True, blank=True)
    b_form_number = models.CharField(max_length=30, blank=True, default="", help_text="NADRA B-Form number.")
    guardian_name = models.CharField(max_length=100)
    guardian_urdu_name = models.CharField(max_length=150, blank=True, default="")
    guardian_relation = models.CharField(max_length=50, default="Father")
    guardian_phone = models.CharField(max_length=20, help_text="Normalized primary contact (03XXXXXXXXX).")
    guardian_whatsapp = models.CharField(max_length=20, blank=True, default="")
    guardian_cnic = models.CharField(max_length=30, blank=True, default="")
    residential_address = models.TextField(blank=True, default="")
    emergency_contact = models.CharField(max_length=20, blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "students"
        verbose_name = "Student"
        verbose_name_plural = "Students"
        indexes = [
            models.Index(fields=["admission_number"], name="idx_students_admission_no"),
            models.Index(fields=["first_name", "last_name"], name="idx_students_names"),
            models.Index(fields=["guardian_phone"], name="idx_students_guardian_phone"),
        ]

    def __str__(self):
        return f"{self.admission_number} - {self.first_name} {self.last_name}".strip()


class ClassGroup(models.Model):
    session = models.ForeignKey(
        "core.AcademicSession",
        on_delete=models.RESTRICT,
        related_name="class_groups",
    )
    name = models.CharField(max_length=100, help_text="e.g. Class 9, Class 10, Matric Physics.")
    section_or_batch = models.CharField(max_length=100, help_text="e.g. Section A, Evening Batch.")
    group_type = models.CharField(max_length=50, choices=GroupType.choices, default=GroupType.SCHOOL_CLASS)
    monthly_tuition_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "class_groups"
        verbose_name = "Class Group"
        verbose_name_plural = "Class Groups"
        constraints = [
            models.UniqueConstraint(
                fields=["session", "name", "section_or_batch"],
                name="uq_class_groups_session_name_section",
            ),
        ]

    def __str__(self):
        return f"{self.name} - {self.section_or_batch} ({self.session.name})"


class Enrollment(models.Model):
    student = models.ForeignKey(
        Student,
        on_delete=models.RESTRICT,
        related_name="enrollments",
    )
    class_group = models.ForeignKey(
        ClassGroup,
        on_delete=models.RESTRICT,
        related_name="enrollments",
    )
    session = models.ForeignKey(
        "core.AcademicSession",
        on_delete=models.RESTRICT,
        related_name="enrollments",
    )
    roll_number = models.CharField(max_length=30, blank=True, default="")
    enrollment_date = models.DateField(default=timezone.now)
    status = models.CharField(max_length=30, choices=EnrollmentStatus.choices, default=EnrollmentStatus.ACTIVE)
    custom_discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "enrollments"
        verbose_name = "Enrollment"
        verbose_name_plural = "Enrollments"
        constraints = [
            models.UniqueConstraint(
                fields=["student", "class_group", "session"],
                name="uq_enrollments_student_class_session",
            ),
        ]
        indexes = [
            models.Index(fields=["student"], name="idx_enrollments_student"),
            models.Index(fields=["class_group", "session"], name="idx_enrollments_class_session"),
            models.Index(fields=["status"], name="idx_enrollments_status"),
        ]

    def __str__(self):
        return f"{self.student.admission_number} in {self.class_group.name} ({self.status})"
