"""
ClassFellow - Base UI View & Modal Framework (ui/base_view.py)
=============================================================
Provides common styling tokens, header banners, read-only grid helpers,
and focus-trapping modal dialogs (CTkToplevel) for record mutations.
"""

import os
import sys
import logging
from typing import Optional, List, Tuple, Callable, Any, Dict
import customtkinter as ctk

logger = logging.getLogger(__name__)


def has_active_display() -> bool:
    """
    Detects if an active GUI display is available.
    Returns True on Windows desktop, or on Linux when DISPLAY is set.
    """
    if sys.platform == "win32":
        return True
    return bool(os.environ.get("DISPLAY"))


# Standardized Dark-Mode Theme Color Palette
THEME_COLORS = {
    "bg_app": "#0F172A",          # Deep slate background
    "bg_card": "#1E293B",         # Slate card container
    "bg_row_alt": "#141E33",      # Alternating row background
    "bg_sidebar": "#020617",      # Jet black sidebar
    "brand_primary": "#10B981",   # Emerald green accent
    "brand_accent": "#3B82F6",    # Indigo blue
    "text_primary": "#F8FAFC",    # High contrast white/slate
    "text_secondary": "#94A3B8",  # Muted slate
    "text_muted": "#64748B",      # Dim slate
    "status_paid": "#10B981",     # Green badge
    "status_partial": "#F59E0B",  # Amber badge
    "status_unpaid": "#EF4444",   # Red badge
    "border_color": "#334155",    # Slate border
}


class BaseView(ctk.CTkFrame):
    """
    Abstract base frame for all ClassFellow modular workspaces.
    Encapsulates service access, standard header layouts, and notification toasts.
    """

    def __init__(self, parent, app, **kwargs):
        super().__init__(
            parent,
            fg_color=THEME_COLORS["bg_app"],
            corner_radius=0,
            **kwargs
        )
        self.app = app
        self.db_conn = getattr(app, "db_conn", None)
        self.colors = THEME_COLORS

    def create_header(
        self,
        title: str,
        subtitle: Optional[str] = None,
        actions: Optional[List[Tuple[str, Callable, str]]] = None,
    ) -> ctk.CTkFrame:
        """
        Renders a standardized view header with title, subtitle, and action buttons.

        Args:
            title: View title (e.g., 'Student Registry').
            subtitle: Descriptive sub-label.
            actions: List of tuples (Button Text, Callback, Color Hex).
        """
        header_frame = ctk.CTkFrame(
            self,
            fg_color=self.colors["bg_card"],
            corner_radius=8,
            height=70
        )
        header_frame.pack(fill="x", padx=16, pady=(16, 12))

        # Title and subtitle container
        text_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        text_frame.pack(side="left", padx=16, pady=12)

        title_label = ctk.CTkLabel(
            text_frame,
            text=title,
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=self.colors["text_primary"]
        )
        title_label.pack(anchor="w")

        if subtitle:
            sub_label = ctk.CTkLabel(
                text_frame,
                text=subtitle,
                font=ctk.CTkFont(size=12),
                text_color=self.colors["text_secondary"]
            )
            sub_label.pack(anchor="w")

        # Action buttons container
        if actions:
            btn_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
            btn_frame.pack(side="right", padx=16, pady=12)

            for label, command, color in actions:
                btn = ctk.CTkButton(
                    btn_frame,
                    text=label,
                    command=command,
                    fg_color=color,
                    hover_color=self.colors["brand_accent"],
                    text_color="#FFFFFF",
                    font=ctk.CTkFont(size=13, weight="bold"),
                    height=34
                )
                btn.pack(side="left", padx=6)

        return header_frame

    def show_info(self, title: str, message: str) -> None:
        """Displays an informative modal toast."""
        InfoDialog(self, title=title, message=message, is_error=False)

    def show_error(self, title: str, message: str) -> None:
        """Displays an error modal toast."""
        InfoDialog(self, title=title, message=message, is_error=True)

    def refresh_data(self) -> None:
        """Subclasses override this method to reload data from domain services."""
        pass

    def on_show(self, **kwargs) -> None:
        """Called whenever this workspace is swapped into view."""
        self.refresh_data()


class BaseModal(ctk.CTkToplevel):
    """
    Standard modal dialog enforcing architectural focus trapping rules:
      - transient(parent) keeps the dialog on top.
      - grab_set() traps focus (blocks clicks to parent window).
      - focus_force() gives immediate keyboard control.
    """

    def __init__(
        self,
        parent,
        title: str = "ClassFellow Dialog",
        width: int = 500,
        height: int = 420,
    ):
        super().__init__(parent)

        self.title(title)
        self.geometry(f"{width}x{height}")
        self.resizable(False, False)
        self.configure(fg_color=THEME_COLORS["bg_app"])

        # Modal focus trapping rules
        self.transient(parent)
        self.grab_set()
        self.focus_force()

        # Center modal over parent
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (width // 2)
        y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")

        # Container card
        self.card = ctk.CTkFrame(
            self,
            fg_color=THEME_COLORS["bg_card"],
            corner_radius=8
        )
        self.card.pack(fill="both", expand=True, padx=16, pady=16)

        # Modal Title
        self.title_label = ctk.CTkLabel(
            self.card,
            text=title,
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=THEME_COLORS["text_primary"]
        )
        self.title_label.pack(anchor="w", padx=16, pady=(16, 12))

    def close(self) -> None:
        """Safely releases grab and closes dialog."""
        try:
            self.grab_release()
        except Exception:
            pass
        try:
            self.withdraw()
        except Exception:
            pass
        try:
            self.after(50, self._safe_destroy)
        except Exception:
            try:
                self.destroy()
            except Exception:
                pass

    def _safe_destroy(self) -> None:
        """Destroys window safely after pending Tk event loop callbacks finish."""
        try:
            self.destroy()
        except Exception:
            pass


class InfoDialog(BaseModal):
    """Simple confirmation or alert modal dialog."""

    def __init__(self, parent, title: str, message: str, is_error: bool = False):
        super().__init__(parent, title=title, width=420, height=220)

        icon_color = THEME_COLORS["status_unpaid"] if is_error else THEME_COLORS["brand_primary"]
        icon_text = "⚠️" if is_error else "ℹ️"

        content_frame = ctk.CTkFrame(self.card, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=16, pady=8)

        msg_label = ctk.CTkLabel(
            content_frame,
            text=f"{icon_text}  {message}",
            wraplength=360,
            font=ctk.CTkFont(size=13),
            text_color=THEME_COLORS["text_primary"],
            justify="left"
        )
        msg_label.pack(pady=20)

        btn_ok = ctk.CTkButton(
            self.card,
            text="Dismiss",
            command=self.close,
            fg_color=icon_color,
            hover_color=THEME_COLORS["brand_accent"],
            width=100
        )
        btn_ok.pack(pady=(0, 16))
