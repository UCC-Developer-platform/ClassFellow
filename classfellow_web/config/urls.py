"""
ClassFellow Web - Root URL Configuration
"""

from django.contrib import admin
from django.urls import include, path
from apps.core import views as core_views

urlpatterns = [
    path("health/", core_views.health_check_view, name="health_check"),
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("students/", include("apps.students.urls")),
    path("staff/", include("apps.staff.urls")),
    path("fees/", include("apps.fees.urls")),
    path("attendance/", include("apps.attendance.urls")),
    path("examinations/", include("apps.examinations.urls")),
    path("api/v1/", include("apps.api.urls")),
    path("", include("apps.core.urls")),
]
