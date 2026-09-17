"""
ClassFellow Web - Core App URL Configuration
"""

from django.urls import path
from apps.core import views

app_name = "core"

urlpatterns = [
    path("", views.dashboard_view, name="dashboard"),
    path("api/v1/sync/upload/", views.sync_backup_upload_view, name="sync_backup_upload"),
]
