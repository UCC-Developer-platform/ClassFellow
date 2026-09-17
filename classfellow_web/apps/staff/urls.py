"""
ClassFellow Web - Staff App URL Configuration
"""

from django.urls import path
from apps.staff import views

app_name = "staff"

urlpatterns = [
    path("", views.staff_list_view, name="staff_list"),
    path("create/", views.staff_create_view, name="staff_create"),
]
