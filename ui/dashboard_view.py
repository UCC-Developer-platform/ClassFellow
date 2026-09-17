"""
ClassFellow - Dashboard View (ui/dashboard_view.py)
==================================================
Executive operational overview featuring real-time KPI metrics,
commercial licensing tier indicators, and quick-action shortcuts.
"""

import logging
from decimal import Decimal
from typing import Optional
import customtkinter as ctk

from ui.base_view import BaseView, THEME_COLORS

logger = logging.getLogger(__name__)


class DashboardView(BaseView):
    """Main executive dashboard workspace."""

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, app, **kwargs)

        self._build_ui()
        self.refresh_data()

    def _build_ui(self) -> None:
        """Constructs metric KPI cards, action shortcuts, and summary sections."""
        # 1. Header Banner
        tier_name = self.app.config.get("system", {}).get(
            "licensed_tier", "Tier 3: Professional Suite"
        )
        self.create_header(
            title="Institutional Dashboard",
            subtitle=f"ClassFellow Management Suite • {tier_name}",
            actions=[
                ("🔄 Refresh", self.refresh_data, self.colors["brand_accent"]),
                ("💾 Daily Backup", self._on_quick_backup, self.colors["brand_primary"]),
            ],
        )

        # 2. Main Scrollable Container
        self.content_scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent"
        )
        self.content_scroll.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        # 3. KPI Metrics Row (4 Cards)
        self.kpi_container = ctk.CTkFrame(self.content_scroll, fg_color="transparent")
        self.kpi_container.pack(fill="x", pady=(0, 16))
        self.kpi_container.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="kpi")

        self.card_students = self._create_kpi_card(
            self.kpi_container, 0, "👨‍🎓 Active Students", "0", self.colors["brand_primary"]
        )
        self.card_classes = self._create_kpi_card(
            self.kpi_container, 1, "🏫 Active Classes", "0", self.colors["brand_accent"]
        )
        self.card_revenue = self._create_kpi_card(
            self.kpi_container, 2, "💳 Monthly Fees (PKR)", "Rs. 0.00", self.colors["status_paid"]
        )
        self.card_sessions = self._create_kpi_card(
            self.kpi_container, 3, "📅 Academic Sessions", "0", self.colors["status_partial"]
        )

        # 4. Quick Action Shortcuts
        actions_title = ctk.CTkLabel(
            self.content_scroll,
            text="⚡ Operational Shortcuts",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=self.colors["text_primary"]
        )
        actions_title.pack(anchor="w", pady=(8, 8))

        self.actions_bar = ctk.CTkFrame(
            self.content_scroll, fg_color=self.colors["bg_card"], corner_radius=8
        )
        self.actions_bar.pack(fill="x", pady=(0, 16))

        shortcuts = [
            ("👨‍🎓 Register Student", "students", self.colors["brand_primary"]),
            ("💳 Collect Fee Receipt", "fees", self.colors["brand_accent"]),
            ("🗓️ Mark Class Attendance", "attendance", self.colors["status_partial"]),
            ("📝 Examinations & Reports", "examinations", self.colors["brand_primary"]),
            ("⚙️ System & Backups", "settings", self.colors["border_color"]),
        ]

        for label, mod_key, color in shortcuts:
            btn = ctk.CTkButton(
                self.actions_bar,
                text=label,
                command=lambda k=mod_key: self.app.navigate_to(k),
                fg_color=color,
                hover_color=self.colors["brand_accent"],
                text_color="#FFFFFF",
                font=ctk.CTkFont(size=12, weight="bold"),
                height=38,
            )
            btn.pack(side="left", padx=10, pady=12, expand=True, fill="x")

        # 5. Recent Activity / Student Roster Preview
        roster_title = ctk.CTkLabel(
            self.content_scroll,
            text="📋 Recent Student Admissions",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=self.colors["text_primary"]
        )
        roster_title.pack(anchor="w", pady=(8, 8))

        self.recent_container = ctk.CTkFrame(
            self.content_scroll, fg_color=self.colors["bg_card"], corner_radius=8
        )
        self.recent_container.pack(fill="x", pady=(0, 16))

        self.recent_list_frame = ctk.CTkFrame(self.recent_container, fg_color="transparent")
        self.recent_list_frame.pack(fill="x", padx=12, pady=12)

    def _create_kpi_card(
        self, parent, col: int, title: str, initial_value: str, accent_color: str
    ) -> dict:
        """Helper rendering a high-contrast KPI metric tile."""
        card = ctk.CTkFrame(parent, fg_color=self.colors["bg_card"], corner_radius=8, height=100)
        card.grid(row=0, column=col, padx=6, sticky="nsew")

        title_lbl = ctk.CTkLabel(
            card,
            text=title,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self.colors["text_secondary"]
        )
        title_lbl.pack(anchor="w", padx=14, pady=(12, 4))

        val_lbl = ctk.CTkLabel(
            card,
            text=initial_value,
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=accent_color
        )
        val_lbl.pack(anchor="w", padx=14, pady=(0, 12))

        return {"card": card, "val_label": val_lbl}

    def refresh_data(self) -> None:
        """Queries live SQLite database and updates metric cards and recent records."""
        if not self.db_conn:
            return

        try:
            cur = self.db_conn.cursor()

            # 1. Total Active Students
            cur.execute("SELECT COUNT(*) FROM students WHERE is_active = 1;")
            active_students = cur.fetchone()[0]
            self.card_students["val_label"].configure(text=str(active_students))

            # 2. Total Class Groups
            cur.execute("SELECT COUNT(*) FROM class_groups;")
            total_classes = cur.fetchone()[0]
            self.card_classes["val_label"].configure(text=str(total_classes))

            # 3. Monthly Fee Revenue Collected
            cur.execute(
                "SELECT COALESCE(SUM(amount), '0.00') FROM payments "
                "WHERE status = 'Issued' AND STRFTIME('%Y-%m', payment_date) = STRFTIME('%Y-%m', 'now');"
            )
            revenue_val = cur.fetchone()[0]
            rev_dec = Decimal(str(revenue_val)) if revenue_val else Decimal("0.00")
            self.card_revenue["val_label"].configure(text=f"Rs. {rev_dec:,.2f}")

            # 4. Total Academic Sessions
            cur.execute("SELECT COUNT(*) FROM academic_sessions;")
            total_sessions = cur.fetchone()[0]
            self.card_sessions["val_label"].configure(text=str(total_sessions))

            # 5. Populate Recent Admissions
            for widget in self.recent_list_frame.winfo_children():
                widget.destroy()

            cur.execute(
                "SELECT admission_number, first_name, last_name, guardian_name, guardian_phone, created_at "
                "FROM students ORDER BY id DESC LIMIT 5;"
            )
            recent_rows = cur.fetchall()

            if not recent_rows:
                no_data = ctk.CTkLabel(
                    self.recent_list_frame,
                    text="No student admissions registered yet. Use '+ Register Student' to begin.",
                    font=ctk.CTkFont(size=13),
                    text_color=self.colors["text_muted"]
                )
                no_data.pack(pady=12)
            else:
                for idx, row in enumerate(recent_rows):
                    bg = self.colors["bg_app"] if idx % 2 == 0 else self.colors["bg_row_alt"]
                    item_frame = ctk.CTkFrame(self.recent_list_frame, fg_color=bg, corner_radius=4)
                    item_frame.pack(fill="x", pady=2, padx=4)

                    info_text = (
                        f"🎓 {row[0]} — {row[1]} {row[2] or ''}  |  "
                        f"Guardian: {row[3]} ({row[4]})  |  Admitted: {row[5][:10]}"
                    )
                    lbl = ctk.CTkLabel(
                        item_frame,
                        text=info_text,
                        font=ctk.CTkFont(size=12),
                        text_color=self.colors["text_primary"]
                    )
                    lbl.pack(side="left", padx=12, pady=8)

        except Exception as exc:
            logger.error(f"Dashboard data refresh error: {exc}", exc_info=True)

    def _on_quick_backup(self) -> None:
        """Triggered from header: performs instant online snapshot."""
        if hasattr(self.app, "backup_service") and self.app.backup_service:
            path = self.app.backup_service.run_startup_backup()
            if path:
                self.show_info("Daily Backup Complete", f"Snapshot saved:\n{path}")
            else:
                self.show_error("Backup Failed", "Encountered an error generating snapshot.")
