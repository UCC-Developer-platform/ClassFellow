from django.conf import settings
from django.db import models


class ExamType(models.TextChoices):
    MONTHLY_TEST = "MonthlyTest", "Monthly Test"
    TERM_EXAM = "TermExam", "Term Examination"
    ANNUAL_EXAM = "AnnualExam", "Annual Examination"
    MOCK_TEST = "MockTest", "Mock Test"


class Subject(models.Model):
    name = models.CharField(max_length=100, unique=True)
    urdu_name = models.CharField(max_length=150, blank=True, default="")
    code = models.CharField(max_length=20, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "subjects"
        verbose_name = "Subject"
        verbose_name_plural = "Subjects"

    def __str__(self):
        return f"{self.name} ({self.code})" if self.code else self.name


class Exam(models.Model):
    session = models.ForeignKey(
        "core.AcademicSession",
        on_delete=models.RESTRICT,
        related_name="exams",
    )
    name = models.CharField(max_length=100)
    exam_type = models.CharField(max_length=50, choices=ExamType.choices, default=ExamType.TERM_EXAM)
    start_date = models.DateField()
    end_date = models.DateField()
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "exams"
        verbose_name = "Examination"
        verbose_name_plural = "Examinations"
        constraints = [
            models.UniqueConstraint(
                fields=["session", "name"],
                name="uq_exams_session_name",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.session.name})"


class ExamSubject(models.Model):
    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name="exam_subjects",
    )
    class_group = models.ForeignKey(
        "students.ClassGroup",
        on_delete=models.RESTRICT,
        related_name="exam_subjects",
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.RESTRICT,
        related_name="exam_subjects",
    )
    maximum_marks = models.DecimalField(max_digits=6, decimal_places=2, default=100.00)
    passing_marks = models.DecimalField(max_digits=6, decimal_places=2, default=33.00)
    weightage_percent = models.DecimalField(max_digits=5, decimal_places=2, default=100.00)
    exam_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "exam_subjects"
        verbose_name = "Exam Subject Configuration"
        verbose_name_plural = "Exam Subject Configurations"
        constraints = [
            models.UniqueConstraint(
                fields=["exam", "class_group", "subject"],
                name="uq_exam_class_subject",
            ),
        ]
        indexes = [
            models.Index(fields=["exam", "class_group"], name="idx_exam_subjects_lookup"),
        ]

    def __str__(self):
        return f"{self.exam.name} - {self.class_group.name} - {self.subject.name}"


class GradingTier(models.Model):
    session = models.ForeignKey(
        "core.AcademicSession",
        on_delete=models.RESTRICT,
        related_name="grading_tiers",
    )
    grade_name = models.CharField(max_length=20)
    min_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    max_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    gpa_point = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    remarks_en = models.CharField(max_length=100, blank=True, default="")
    remarks_ur = models.CharField(max_length=150, blank=True, default="")
    is_passing = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "grading_tiers"
        verbose_name = "Grading Tier"
        verbose_name_plural = "Grading Tiers"
        constraints = [
            models.UniqueConstraint(
                fields=["session", "grade_name"],
                name="uq_grading_tiers_session_grade",
            ),
        ]

    def __str__(self):
        return f"Grade {self.grade_name} ({self.min_percentage}% - {self.max_percentage}%)"


class Mark(models.Model):
    exam_subject = models.ForeignKey(
        ExamSubject,
        on_delete=models.CASCADE,
        related_name="marks",
    )
    enrollment = models.ForeignKey(
        "students.Enrollment",
        on_delete=models.RESTRICT,
        related_name="marks",
    )
    marks_obtained = models.DecimalField(max_digits=6, decimal_places=2)
    is_absent = models.BooleanField(default=False)
    remarks = models.TextField(blank=True, default="")
    recorded_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_marks",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "marks"
        verbose_name = "Mark Record"
        verbose_name_plural = "Mark Records"
        constraints = [
            models.UniqueConstraint(
                fields=["exam_subject", "enrollment"],
                name="uq_marks_exam_subject_enrollment",
            ),
        ]
        indexes = [
            models.Index(fields=["enrollment"], name="idx_marks_enrollment"),
            models.Index(fields=["exam_subject", "enrollment"], name="idx_marks_lookup"),
        ]

    def __str__(self):
        return f"{self.enrollment.student.admission_number}: {self.marks_obtained}/{self.exam_subject.maximum_marks}"
