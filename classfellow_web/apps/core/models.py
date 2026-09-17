from django.db import models


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
