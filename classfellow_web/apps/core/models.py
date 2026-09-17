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
