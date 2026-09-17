"""
ClassFellow Web - Students App URL Configuration
"""

from django.urls import path
from apps.students import views

app_name = "students"

urlpatterns = [
    path("", views.student_list_view, name="list"),
    path("admit/", views.student_create_view, name="create"),
]
