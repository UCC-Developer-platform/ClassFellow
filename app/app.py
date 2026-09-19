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
if getattr(sys, "frozen", False):
    ROOT_DIR = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
else:
    ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from database import get_connection, init_database
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
    if not os.path.exists(config_dir) and getattr(sys, "frozen", False):
        alt_config = os.path.join(os.path.dirname(sys.executable), "config")
        if os.path.exists(alt_config):
            config_dir = alt_config

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


class SidebarNavButton(ctk.CTkFrame):
    """
    Fixed-width two-column navigation button for sidebar.
    Enforces a strict 40px icon grid column and anchored text to guarantee
    pixel-perfect vertical alignment across all operating system font renderers.
    """
    def __init__(self, parent, icon: str, title: str, command, **kwargs):
        super().__init__(parent, fg_color="transparent", corner_radius=6, cursor="hand2", height=38, **kwargs)
        self.pack_propagate(False)
        self.grid_propagate(False)
        self.command = command
        self.is_active = False

        self.grid_columnconfigure(0, minsize=40, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.icon_label = ctk.CTkLabel(
            self,
            text=icon,
            width=40,
            font=ctk.CTkFont(size=15),
            anchor="center",
            text_color="#F8FAFC",
            cursor="hand2"
        )
        self.icon_label.grid(row=0, column=0, padx=0, sticky="nsew")

        self.title_label = ctk.CTkLabel(
            self,
            text=title,
            font=ctk.CTkFont(size=13),
            text_color="#F8FAFC",
            anchor="w",
            cursor="hand2"
        )
        self.title_label.grid(row=0, column=1, padx=(6, 8), sticky="nsew")

        for widget in (self, self.icon_label, self.title_label):
            widget.bind("<Button-1>", lambda e: self._on_click())
            widget.bind("<Enter>", lambda e: self._on_enter())
            widget.bind("<Leave>", lambda e: self._on_leave())

    def _on_click(self):
        if self.command:
            self.command()

    def _on_enter(self):
        if not self.is_active:
            self.configure(fg_color="#1E293B")

    def _on_leave(self):
        if not self.is_active:
            self.configure(fg_color="transparent")

    def set_active(self, active: bool):
        self.is_active = active
        if active:
            self.configure(fg_color="#1E293B")
            self.title_label.configure(text_color="#10B981", font=ctk.CTkFont(size=13, weight="bold"))
        else:
            self.configure(fg_color="transparent")
            self.title_label.configure(text_color="#F8FAFC", font=ctk.CTkFont(size=13, weight="normal"))


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

        # Verify database connection and automatically bootstrap missing schema migrations (PRAGMA user_version < 3)
        self.db_path = db_path
        self.db_conn = init_database(db_path) if db_path else init_database()
        self.backup_service = BackupService(self.db_conn, self.db_path)

        self.sidebar_buttons = {}
        self._error_card_frame = None

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
            ("📊", "Dashboard", "dashboard"),
            ("🎓", "Students", "students"),
            ("🧾", "Fees & Receipts", "fees"),
            ("📅", "Attendance", "attendance"),
            ("📝", "Examinations", "examinations"),
            ("⚙️", "Settings", "settings"),
        ]

        active_modules = self.config.get("modules", {})
        self.sidebar_buttons.clear()
        for icon, label, mod_key in nav_items:
            # Check dynamic module entitlement
            if mod_key in active_modules and not active_modules[mod_key]:
                continue  # Gracefully hide unpurchased / disabled modules

            btn = SidebarNavButton(
                self.sidebar_frame,
                icon=icon,
                title=label,
                command=lambda k=mod_key: self._on_navigate(k)
            )
            btn.pack(fill="x", padx=10, pady=4)
            self.sidebar_buttons[mod_key] = btn

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
        Guards against unhandled instantiation errors by rendering an in-window recovery card.
        """
        active_modules = self.config.get("modules", {})
        if module_key not in ("dashboard", "settings"):
            if module_key in active_modules and not active_modules[module_key]:
                logging.getLogger(__name__).warning(f"Navigation blocked: {module_key} is unlicensed.")
                return False

        if module_key not in self.view_classes:
            return False

        # Clean up any lingering error card from previous attempts
        if self._error_card_frame:
            self._error_card_frame.destroy()
            self._error_card_frame = None

        if module_key not in self.views:
            view_cls = self.view_classes[module_key]
            try:
                self.views[module_key] = view_cls(self.workspace_frame, self)
            except Exception as exc:
                logging.getLogger(__name__).error(
                    f"Failed to instantiate view '{module_key}': {exc}", exc_info=True
                )
                self._render_view_error_card(module_key, str(exc))
                return False

        target_view = self.views[module_key]

        if self.current_view and self.current_view != target_view:
            self.current_view.pack_forget()

        target_view.pack(fill="both", expand=True)
        self.current_view = target_view
        try:
            target_view.on_show(**kwargs)
        except Exception as exc:
            logging.getLogger(__name__).warning(f"Error in {module_key}.on_show: {exc}")

        # Update sidebar button active indicators
        for k, btn in self.sidebar_buttons.items():
            btn.set_active(k == module_key)

        self.status_label.configure(
            text=f"Active Workspace: {module_key.capitalize()} • SQLite WAL Mode Active"
        )
        return True

    def _render_view_error_card(self, module_key: str, error_msg: str) -> None:
        """Renders an in-workspace recovery card when a view fails initialization."""
        if self.current_view:
            self.current_view.pack_forget()
            self.current_view = None

        if self._error_card_frame:
            self._error_card_frame.destroy()

        self._error_card_frame = ctk.CTkFrame(self.workspace_frame, fg_color="#1E293B", corner_radius=8)
        self._error_card_frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            self._error_card_frame,
            text=f"⚠️ Workspace Initialization Notice: {module_key.capitalize()}",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color="#F87171"
        ).pack(pady=(30, 8))

        ctk.CTkLabel(
            self._error_card_frame,
            text="The workspace could not be loaded because the underlying database or component encountered an issue:",
            font=ctk.CTkFont(size=12),
            text_color="#94A3B8"
        ).pack(pady=(0, 10))

        err_box = ctk.CTkTextbox(self._error_card_frame, height=90, width=540, fg_color="#0F172A", text_color="#FCA5A5")
        err_box.insert("0.0", error_msg)
        err_box.configure(state="disabled")
        err_box.pack(pady=10)

        btn_row = ctk.CTkFrame(self._error_card_frame, fg_color="transparent")
        btn_row.pack(pady=16)

        ctk.CTkButton(
            btn_row,
            text="🛠️ Run Database Auto-Repair",
            fg_color="#10B981",
            hover_color="#059669",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda: self._repair_database_and_reload(module_key)
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            btn_row,
            text="🔄 Retry Workspace",
            fg_color="#3B82F6",
            hover_color="#2563EB",
            font=ctk.CTkFont(size=12),
            command=lambda: self._retry_workspace(module_key)
        ).pack(side="left", padx=10)

    def _repair_database_and_reload(self, module_key: str) -> None:
        """Invokes init_database to apply missing migrations and reloads the view."""
        try:
            self.db_conn = init_database(self.db_path) if self.db_path else init_database()
            self.views.pop(module_key, None)
            self.navigate_to(module_key)
        except Exception as exc:
            logging.getLogger(__name__).error(f"Auto-repair failed: {exc}", exc_info=True)
            self._render_view_error_card(module_key, f"Auto-repair failed: {exc}")

    def _retry_workspace(self, module_key: str) -> None:
        """Retries loading workspace after removing cached instance."""
        self.views.pop(module_key, None)
        self.navigate_to(module_key)

    def _on_navigate(self, module_key: str) -> None:
        """Handles navigation sidebar button clicks."""
        self.navigate_to(module_key)

    def _run_async_startup_backup(self) -> None:
        """Executes Tier 1 daily backup and retention pruning in background."""
        try:
            thread_conn = get_connection(self.db_path) if self.db_path else get_connection()
            try:
                svc = BackupService(thread_conn, self.db_path)
                svc.run_startup_backup()
            finally:
                thread_conn.close()
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
