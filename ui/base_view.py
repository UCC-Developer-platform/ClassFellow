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


# Standardized Institutional Dark-Mode Theme Palettes
THEME_PALETTES: Dict[str, Dict[str, str]] = {
    "Emerald Classic": {
        "name": "Emerald Classic",
        "description": "Default educational theme featuring deep slate foundation and emerald green vitality.",
        "bg_app": "#0F172A",
        "bg_card": "#1E293B",
        "bg_row_alt": "#141E33",
        "bg_sidebar": "#020617",
        "brand_primary": "#10B981",
        "brand_accent": "#3B82F6",
        "text_primary": "#F8FAFC",
        "text_secondary": "#94A3B8",
        "text_muted": "#64748B",
        "status_paid": "#10B981",
        "status_partial": "#F59E0B",
        "status_unpaid": "#EF4444",
        "border_color": "#334155",
        "bg_table_header": "#0B1120",
    },
    "Royal Navy": {
        "name": "Royal Navy",
        "description": "Prestigious academic maritime navy with royal blue highlights.",
        "bg_app": "#0B132B",
        "bg_card": "#1C2541",
        "bg_row_alt": "#141F3D",
        "bg_sidebar": "#050A18",
        "brand_primary": "#2563EB",
        "brand_accent": "#38BDF8",
        "text_primary": "#F8FAFC",
        "text_secondary": "#94A3B8",
        "text_muted": "#64748B",
        "status_paid": "#10B981",
        "status_partial": "#F59E0B",
        "status_unpaid": "#EF4444",
        "border_color": "#3A506B",
        "bg_table_header": "#080E20",
    },
    "Executive Burgundy": {
        "name": "Executive Burgundy",
        "description": "Authoritative zinc and deep burgundy palette for prestigious institutional boards.",
        "bg_app": "#18181B",
        "bg_card": "#27272A",
        "bg_row_alt": "#202024",
        "bg_sidebar": "#09090B",
        "brand_primary": "#991B1B",
        "brand_accent": "#F59E0B",
        "text_primary": "#F8FAFC",
        "text_secondary": "#A1A1AA",
        "text_muted": "#71717A",
        "status_paid": "#10B981",
        "status_partial": "#F59E0B",
        "status_unpaid": "#EF4444",
        "border_color": "#3F3F46",
        "bg_table_header": "#141417",
    },
    "Charcoal Modern": {
        "name": "Charcoal Modern",
        "description": "Minimalist high-contrast charcoal black with vibrant sky blue accents.",
        "bg_app": "#09090B",
        "bg_card": "#18181B",
        "bg_row_alt": "#131316",
        "bg_sidebar": "#030712",
        "brand_primary": "#0284C7",
        "brand_accent": "#38BDF8",
        "text_primary": "#F8FAFC",
        "text_secondary": "#94A3B8",
        "text_muted": "#64748B",
        "status_paid": "#10B981",
        "status_partial": "#F59E0B",
        "status_unpaid": "#EF4444",
        "border_color": "#27272A",
        "bg_table_header": "#050507",
    },
}

THEME_COLORS: Dict[str, str] = dict(THEME_PALETTES["Emerald Classic"])


def get_available_theme_palettes() -> Dict[str, Dict[str, str]]:
    """Returns mapping of available institutional color palettes."""
    return THEME_PALETTES


def apply_theme_palette(palette_name: str, config_dir: Optional[str] = None) -> Dict[str, str]:
    """
    Applies the specified theme palette in-memory and persists the choice to config/theme.json.
    """
    if palette_name not in THEME_PALETTES:
        matched = None
        for k in THEME_PALETTES:
            if palette_name.lower() in k.lower():
                matched = k
                break
        palette_name = matched or "Emerald Classic"

    selected = THEME_PALETTES[palette_name]
    THEME_COLORS.update(selected)

    try:
        import json
        if not config_dir:
            config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
        theme_json_path = os.path.join(config_dir, "theme.json")
        if os.path.exists(theme_json_path):
            with open(theme_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["active_palette"] = palette_name
            with open(theme_json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
    except Exception as exc:
        logger.warning(f"Could not persist active theme palette to theme.json: {exc}")

    return dict(THEME_COLORS)


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
