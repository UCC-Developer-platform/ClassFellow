"""
ClassFellow Web - Root URL Configuration
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("students/", include("apps.students.urls")),
    path("fees/", include("apps.fees.urls")),
    path("attendance/", include("apps.attendance.urls")),
    path("examinations/", include("apps.examinations.urls")),
    path("", include("apps.core.urls")),
]
