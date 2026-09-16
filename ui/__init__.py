"""
ClassFellow UI Modular View Package (ui/)
========================================
Exports desktop views and modal dialog components.
"""

from ui.base_view import BaseView, BaseModal, THEME_COLORS, has_active_display
from ui.dashboard_view import DashboardView
from ui.student_view import StudentView
from ui.fee_view import FeeView
from ui.attendance_view import AttendanceView
from ui.exam_view import ExamView
from ui.settings_view import SettingsView

__all__ = [
    "BaseView",
    "BaseModal",
    "THEME_COLORS",
    "has_active_display",
    "DashboardView",
    "StudentView",
    "FeeView",
    "AttendanceView",
    "ExamView",
    "SettingsView",
]
