"""
ClassFellow Web - API URL Configuration
Registers mobile API endpoints for authentication, teacher portal, and parent portal.
"""

from django.urls import path

from apps.api.views_auth import LoginView
from apps.api.views_parent import (
    ParentAttendanceView,
    ParentChildrenView,
    ParentFeeSummaryView,
    ParentReportCardView,
)
from apps.api.views_teacher import (
    TeacherAssignedClassesView,
    TeacherAttendanceSaveView,
    TeacherMarksSaveView,
    TeacherRosterView,
)
from apps.core import views as core_views

app_name = "api"

urlpatterns = [
    # Auth
    path("auth/login/", LoginView.as_view(), name="auth_login"),
    # Teacher Mobile API
    path("teacher/classes/", TeacherAssignedClassesView.as_view(), name="teacher_classes"),
    path("teacher/roster/", TeacherRosterView.as_view(), name="teacher_roster"),
    path("teacher/attendance/save/", TeacherAttendanceSaveView.as_view(), name="teacher_attendance_save"),
    path("teacher/marks/save/", TeacherMarksSaveView.as_view(), name="teacher_marks_save"),
    # Parent Portal API
    path("parent/children/", ParentChildrenView.as_view(), name="parent_children"),
    path("parent/fees/", ParentFeeSummaryView.as_view(), name="parent_fees"),
    path("parent/attendance/", ParentAttendanceView.as_view(), name="parent_attendance"),
    path("parent/report-card/", ParentReportCardView.as_view(), name="parent_report_card"),
    # Cloud Sync Gateway
    path("sync/upload/", core_views.sync_backup_upload_view, name="sync_backup_upload"),
]
