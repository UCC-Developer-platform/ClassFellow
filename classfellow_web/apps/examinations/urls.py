"""
ClassFellow Web - Examinations App URL Configuration
"""

from django.urls import path
from apps.examinations import views

app_name = "examinations"

urlpatterns = [
    path("", views.exam_workspace_view, name="workspace"),
    path("save-marks/", views.save_marks_view, name="save_marks"),
    path(
        "report-card/<int:exam_id>/<int:enrollment_id>/pdf/",
        views.stream_report_card_pdf,
        name="stream_report_card_pdf",
    ),
]
