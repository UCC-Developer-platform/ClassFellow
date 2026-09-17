from django.conf import settings
from django.db import models


class AttendanceStatus(models.TextChoices):
    PRESENT = "Present", "Present"
    ABSENT = "Absent", "Absent"
    LATE = "Late", "Late"
    LEAVE = "Leave", "Leave"


class BatchSession(models.Model):
    class_group = models.ForeignKey(
        "students.ClassGroup",
        on_delete=models.RESTRICT,
        related_name="batch_sessions",
    )
    session_date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    topic_covered = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "batch_sessions"
        verbose_name = "Batch Lecture Session"
        verbose_name_plural = "Batch Lecture Sessions"

    def __str__(self):
        return f"{self.class_group.name} - {self.session_date}"


class AttendanceRecord(models.Model):
    enrollment = models.ForeignKey(
        "students.Enrollment",
        on_delete=models.RESTRICT,
        related_name="attendance_records",
    )
    attendance_date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=AttendanceStatus.choices,
        default=AttendanceStatus.PRESENT,
    )
    batch_session = models.ForeignKey(
        BatchSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_logs",
    )
    reason_note = models.TextField(blank=True, default="")
    recorded_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_attendances",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "attendance_records"
        verbose_name = "Attendance Record"
        verbose_name_plural = "Attendance Records"
        constraints = [
            models.UniqueConstraint(
                fields=["enrollment", "attendance_date"],
                name="uq_attendance_enrollment_date",
            ),
        ]
        indexes = [
            models.Index(fields=["enrollment", "attendance_date"], name="idx_attendance_enrollment_date"),
            models.Index(fields=["attendance_date", "status"], name="idx_attendance_date_status"),
            models.Index(fields=["batch_session"], name="idx_attendance_batch"),
        ]

    def __str__(self):
        return f"{self.enrollment.student.admission_number} - {self.attendance_date}: {self.status}"
