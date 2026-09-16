"""
ClassFellow - Main Application Runtime & Entry Point
=====================================================
Initializes Windows High-DPI scaling, CustomTkinter appearance,
theme configuration, and database connection.
"""

import os
import sys
import json
import ctypes
import threading
import logging
import customtkinter as ctk

# Ensure root directory is in sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from database import get_connection
from services.backup_service import BackupService
from ui import (
    has_active_display,
    DashboardView,
    StudentView,
    FeeView,
    AttendanceView,
    ExamView,
    SettingsView,
)


def init_windows_dpi() -> None:
    """
    Declares per-monitor DPI awareness v2 on Windows to ensure crisp font rendering
    on 1080p, 2K, and 4K displays.
    
    Wrapped in an exception guard to prevent crashes on Windows 11 if DPI context
    is already locked by CustomTkinter.
    """
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass  # Fall back gracefully to CustomTkinter's internal scaling tracker


def load_configuration() -> dict:
    """Loads application theme, system, and module configuration."""
    config_dir = os.path.join(ROOT_DIR, "config")
    theme_path = os.path.join(config_dir, "theme.json")
    modules_path = os.path.join(config_dir, "modules.json")

    config = {"theme": {}, "modules": {}, "system": {}}
    if os.path.exists(theme_path):
        with open(theme_path, "r", encoding="utf-8") as f:
            config["theme"] = json.load(f)

    if os.path.exists(modules_path):
        with open(modules_path, "r", encoding="utf-8") as f:
            mod_data = json.load(f)
            config["system"] = mod_data.get("system", {})
            config["modules"] = mod_data.get("modules", {})

    return config


class ClassFellowApp(ctk.CTk):
    """Main desktop application window for ClassFellow."""

    def __init__(self, db_path: str = None):
        super().__init__()

        self.title("ClassFellow - School & Academy Management Software")
        self.geometry("1100x700")
        self.minsize(960, 600)

        # Apply default appearance mode
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # Load configurations
        self.config = load_configuration()

        # Verify database connection
        self.db_path = db_path
        self.db_conn = get_connection(db_path) if db_path else get_connection()
        self.backup_service = BackupService(self.db_conn, self.db_path)

        self._build_shell_ui()

        # Lifecycle Hook: Asynchronous startup backup & 30-day retention pruning
        threading.Thread(target=self._run_async_startup_backup, daemon=True).start()

        # Lifecycle Hook: Clean window close with bounded shutdown backup
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _build_shell_ui(self) -> None:
        """Constructs baseline application shell: Sidebar + Header + Workspace."""
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # 1. Top Header Bar
        self.header_frame = ctk.CTkFrame(self, height=50, corner_radius=0, fg_color="#1E293B")
        self.header_frame.grid(row=0, column=0, columnspan=2, sticky="ew")

        self.logo_label = ctk.CTkLabel(
            self.header_frame,
            text="🎓 ClassFellow",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#10B981"
        )
        self.logo_label.pack(side="left", padx=20)

        self.status_label = ctk.CTkLabel(
            self.header_frame,
            text="Offline Ready • SQLite WAL Mode Active",
            font=ctk.CTkFont(size=12),
            text_color="#94A3B8"
        )
        self.status_label.pack(side="right", padx=20)

        # 2. Navigation Sidebar
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0, fg_color="#020617")
        self.sidebar_frame.grid(row=1, column=0, sticky="nsew")

        nav_items = [
            ("📊 Dashboard", "dashboard"),
            ("👨‍🎓 Students", "students"),
            ("💳 Fees & Receipts", "fees"),
            ("🗓️ Attendance", "attendance"),
            ("📝 Examinations", "examinations"),
            ("📄 Reports", "reports"),
            ("⚙️ Settings", "settings"),
        ]

        active_modules = self.config.get("modules", {})
        for label, mod_key in nav_items:
            # Check dynamic module entitlement
            if mod_key in active_modules and not active_modules[mod_key]:
                continue  # Gracefully hide unpurchased / disabled modules

            btn = ctk.CTkButton(
                self.sidebar_frame,
                text=label,
                anchor="w",
                fg_color="transparent",
                text_color="#F8FAFC",
                hover_color="#1E293B",
                font=ctk.CTkFont(size=13),
                command=lambda k=mod_key: self._on_navigate(k)
            )
            btn.pack(fill="x", padx=10, pady=5)

        # 3. Main Workspace Area
        self.workspace_frame = ctk.CTkFrame(self, corner_radius=8, fg_color="#0F172A")
        self.workspace_frame.grid(row=1, column=1, sticky="nsew", padx=15, pady=15)

        self.views = {}
        self.current_view = None
        self.view_classes = {
            "dashboard": DashboardView,
            "students": StudentView,
            "fees": FeeView,
            "attendance": AttendanceView,
            "examinations": ExamView,
            "settings": SettingsView,
        }

        # Navigate to Dashboard workspace by default
        self.navigate_to("dashboard")

    def navigate_to(self, module_key: str, **kwargs) -> bool:
        """
        Dynamically swaps active workspace view inside self.workspace_frame.
        Enforces commercial feature-flag entitlements from config/modules.json.
        """
        active_modules = self.config.get("modules", {})
        # Dashboard and Settings are core views; others check active module feature flags
        if module_key not in ("dashboard", "settings"):
            if module_key in active_modules and not active_modules[module_key]:
                logging.getLogger(__name__).warning(f"Navigation blocked: {module_key} is unlicensed.")
                return False

        if module_key not in self.view_classes:
            return False

        if module_key not in self.views:
            view_cls = self.view_classes[module_key]
            self.views[module_key] = view_cls(self.workspace_frame, self)

        target_view = self.views[module_key]

        if self.current_view and self.current_view != target_view:
            self.current_view.pack_forget()

        target_view.pack(fill="both", expand=True)
        self.current_view = target_view
        target_view.on_show(**kwargs)

        self.status_label.configure(
            text=f"Active Workspace: {module_key.capitalize()} • SQLite WAL Mode Active"
        )
        return True

    def _on_navigate(self, module_key: str) -> None:
        """Handles navigation sidebar button clicks."""
        self.navigate_to(module_key)

    def _run_async_startup_backup(self) -> None:
        """Executes Tier 1 daily backup and retention pruning in background."""
        try:
            if hasattr(self, "backup_service") and self.backup_service:
                self.backup_service.run_startup_backup()
        except Exception as exc:
            logging.getLogger(__name__).warning(f"Startup backup error: {exc}")

    def _on_closing(self) -> None:
        """Handles graceful window shutdown with bounded backup and connection cleanup."""
        try:
            if hasattr(self, "backup_service") and self.backup_service:
                self.backup_service.run_shutdown_backup()
        except Exception as exc:
            logging.getLogger(__name__).warning(f"Shutdown backup error: {exc}")
        finally:
            try:
                if hasattr(self, "db_conn") and self.db_conn:
                    self.db_conn.close()
            except Exception:
                pass
            self.destroy()


def main() -> None:
    init_windows_dpi()
    if not has_active_display():
        print("No active display detected. Headless environment active.")
        return
    app = ClassFellowApp()
    app.mainloop()


if __name__ == "__main__":
    main()
