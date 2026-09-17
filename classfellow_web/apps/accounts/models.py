from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    ADMIN = "Admin", "Administrator"
    PRINCIPAL = "Principal", "Principal"
    CASHIER = "Cashier", "Cashier"
    TEACHER = "Teacher", "Teacher"
    PARENT = "Parent", "Parent"


class User(AbstractUser):
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CASHIER,
        help_text="Operational institutional role.",
    )
    phone = models.CharField(max_length=20, blank=True, help_text="Direct mobile contact.")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "auth_users"
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
