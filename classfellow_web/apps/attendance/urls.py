"""
ClassFellow Web - Attendance App URL Configuration
"""

from django.urls import path
from apps.attendance import views

app_name = "attendance"

urlpatterns = [
    path("", views.attendance_roster_view, name="roster"),
    path("save/", views.save_attendance_view, name="save"),
]
