from typing import Optional
from django.db import models
from django.utils import timezone


class AcademicSession(models.Model):
    name = models.CharField(max_length=50, unique=True, help_text="Session name (e.g. 2026-2027).")
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "academic_sessions"
        verbose_name = "Academic Session"
        verbose_name_plural = "Academic Sessions"
        ordering = ["-start_date"]

    def __str__(self):
        return self.name


class InstitutionProfile(models.Model):
    name = models.CharField(max_length=200, help_text="Institutional official name.")
    campus_name = models.CharField(max_length=100, blank=True, help_text="Sub-campus or branch.")
    tagline = models.CharField(max_length=255, blank=True)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    logo_path = models.CharField(max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "institution_profiles"
        verbose_name = "Institution Profile"
        verbose_name_plural = "Institution Profiles"

    def __str__(self):
        return self.name


class Campus(models.Model):
    name = models.CharField(max_length=150, help_text="e.g. Main Boys Campus, Junior Wing.")
    code = models.CharField(max_length=20, unique=True, null=True, blank=True, help_text="Short campus identifier.")
    address = models.TextField(blank=True, default="")
    phone = models.CharField(max_length=50, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "campuses"
        verbose_name = "Campus"
        verbose_name_plural = "Campuses"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})" if self.code else self.name


class InstitutionBackupSnapshot(models.Model):
    """Stores metadata and payload for desktop-to-cloud automated backup snapshots."""
    filename = models.CharField(max_length=255, help_text="Original snapshot filename.")
    file_size_bytes = models.BigIntegerField(help_text="File size in bytes.")
    sha256_hash = models.CharField(max_length=64, help_text="Cryptographic SHA-256 hex checksum.")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    desktop_machine_id = models.CharField(
        max_length=100, blank=True, default="", help_text="Client machine hardware ID."
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True, help_text="Originating IP address.")
    backup_file = models.FileField(upload_to="uploads/backups/", help_text="Snapshot archive file.")

    class Meta:
        db_table = "institution_backups"
        verbose_name = "Institution Backup Snapshot"
        verbose_name_plural = "Institution Backup Snapshots"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.filename} ({self.file_size_bytes} bytes) - {self.uploaded_at.strftime('%Y-%m-%d %H:%M')}"


class NoticeType(models.TextChoices):
    FEE_REMINDER = "FeeReminder", "Fee Reminder"
    EXAM_SCHEDULE = "ExamSchedule", "Exam Schedule"
    HOLIDAY = "Holiday", "Holiday Announcement"
    GENERAL = "General", "General Notice"


class InstitutionNotice(models.Model):
    """Represents an official announcement or circular posted for parents and students."""
    title = models.CharField(max_length=200, help_text="Circular heading or subject.")
    urdu_title = models.CharField(max_length=250, blank=True, default="", help_text="Urdu Nastaliq notice title.")
    content = models.TextField(help_text="Detailed circular announcement body.")
    urdu_content = models.TextField(blank=True, default="", help_text="Urdu Nastaliq announcement body.")
    notice_type = models.CharField(
        max_length=50,
        choices=NoticeType.choices,
        default=NoticeType.GENERAL,
        help_text="Category of circular.",
    )
    target_campus = models.ForeignKey(
        Campus,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notices",
        help_text="Specific campus scope (null applies to all campuses).",
    )
    target_class = models.ForeignKey(
        "students.ClassGroup",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notices",
        help_text="Specific class group scope (null applies to all classes).",
    )
    issued_date = models.DateField(default=timezone.now, help_text="Official publication date.")
    is_published = models.BooleanField(default=True, help_text="Visibility toggle.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "institution_notices"
        verbose_name = "Institution Notice"
        verbose_name_plural = "Institution Notices"
        ordering = ["-issued_date", "-created_at"]

    def __str__(self):
        return f"[{self.get_notice_type_display()}] {self.title} ({self.issued_date})"

    def generate_whatsapp_bulletin(self, institution_name: Optional[str] = None) -> str:
        """
        Formats a structured bilingual WhatsApp broadcast bulletin text
        suitable for one-click sharing to parent broadcast lists.
        """
        school = institution_name or "CLASSFELLOW HIGH SCHOOL & ACADEMY"
        campus_line = f"🏢 *Campus:* {self.target_campus.name}" if self.target_campus else ""
        class_line = (
            f"👥 *Target:* {self.target_class.name} ({self.target_class.section_or_batch})"
            if self.target_class
            else ""
        )

        bulletin_lines = [
            f"📢 *{school.upper()}*",
            f"📌 *{self.get_notice_type_display().upper()}:* {self.title}",
            f"🗓 *Date:* {self.issued_date.strftime('%d %B %Y')}",
        ]
        if campus_line:
            bulletin_lines.append(campus_line)
        if class_line:
            bulletin_lines.append(class_line)

        bulletin_lines.append("")
        bulletin_lines.append(self.content.strip())

        if self.urdu_title or self.urdu_content:
            bulletin_lines.append("")
            if self.urdu_title:
                bulletin_lines.append(f"*{self.urdu_title.strip()}*")
            if self.urdu_content:
                bulletin_lines.append(self.urdu_content.strip())

        bulletin_lines.append("")
        bulletin_lines.append("— *School Administration Office*")
        return "\n".join(bulletin_lines)
