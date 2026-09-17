"""
ClassFellow Web - Core App URL Configuration
"""

from django.urls import path
from apps.core import views

app_name = "core"

urlpatterns = [
    path("", views.dashboard_view, name="dashboard"),
    path("analytics/", views.analytics_view, name="analytics"),
    path("notices/", views.notices_view, name="notices"),
    path(
        "reports/monthly-audit-packet/<int:session_id>/<str:month_year>/pdf/",
        views.stream_monthly_audit_packet_pdf,
        name="monthly_audit_packet_pdf",
    ),
    path("api/v1/sync/upload/", views.sync_backup_upload_view, name="sync_backup_upload"),
]
