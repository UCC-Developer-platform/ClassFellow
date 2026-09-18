"""
ClassFellow - Attendance & Notification View (ui/attendance_view.py)
===================================================================
Daily class roll call, atomic bulk UPSERT attendance marking,
monthly attendance summary, and bilingual WhatsApp absence notification links.
"""

import logging
import webbrowser
from datetime import datetime
from typing import Optional, List, Dict, Any
import customtkinter as ctk

from services.attendance_service import AttendanceService
from ui.base_view import BaseView, BaseModal, THEME_COLORS

logger = logging.getLogger(__name__)


class AttendanceView(BaseView):
    """Attendance management and absence notification workspace."""

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, app, **kwargs)
        self.attendance_service = AttendanceService(self.db_conn) if self.db_conn else None
        self.roster_rows: List[Dict[str, Any]] = []

        self._build_ui()
        self._load_classes()

    def _build_ui(self) -> None:
        """Builds class/date selectors, summary KPI strip, and roster grid."""
        # 1. Header Banner
        self.create_header(
            title="Class Attendance & Absence Alerts",
            subtitle="Record daily attendance, bulk roster marking, and zero-cost WhatsApp absence notices",
            actions=[
                ("⚡ All Present", self._mark_all_present, self.colors["brand_accent"]),
                ("💾 Save Roster", self._save_roster, self.colors["brand_primary"]),
                ("🔄 Refresh", self.refresh_data, self.colors["border_color"]),
            ],
        )

        # 2. Class & Date Selector Bar
        selector_card = ctk.CTkFrame(self, fg_color=self.colors["bg_card"], corner_radius=8)
        selector_card.pack(fill="x", padx=16, pady=(0, 12))

        ctk.CTkLabel(
            selector_card, text="Class / Batch *:", font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self.colors["text_primary"]
        ).pack(side="left", padx=(16, 6), pady=12)

        self.classes_map: Dict[str, int] = {}
        self.class_var = ctk.StringVar(value="Select Class")
        self.class_menu = ctk.CTkOptionMenu(
            selector_card, values=["Select Class"], variable=self.class_var,
            command=lambda v: self.refresh_data(), width=180
        )
        self.class_menu.pack(side="left", padx=4, pady=12)

        ctk.CTkLabel(
            selector_card, text="Date (YYYY-MM-DD) *:", font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self.colors["text_primary"]
        ).pack(side="left", padx=(16, 6), pady=12)

        self.date_entry = ctk.CTkEntry(selector_card, width=120)
        self.date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.date_entry.pack(side="left", padx=4, pady=12)

        btn_load = ctk.CTkButton(
            selector_card, text="Load Roster", width=100, command=self.refresh_data,
            fg_color=self.colors["brand_accent"], font=ctk.CTkFont(size=12, weight="bold")
        )
        btn_load.pack(side="left", padx=12, pady=12)

        # Quick stats on right of selector bar
        self.stats_lbl = ctk.CTkLabel(
            selector_card,
            text="Students: 0  |  Present: 0  |  Absent: 0  |  Attendance: 0%",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self.colors["brand_primary"]
        )
        self.stats_lbl.pack(side="right", padx=16, pady=12)

        # 3. Table Header
        self.table_header_frame = ctk.CTkFrame(
            self, fg_color=self.colors["bg_card"], corner_radius=6, height=36
        )
        self.table_header_frame.pack(fill="x", padx=16, pady=(0, 4))

        columns = [
            ("Roll #", 70),
            ("Student Name", 160),
            ("Guardian Name", 140),
            ("Guardian Phone", 120),
            ("Attendance Status", 150),
            ("Remarks", 160),
            ("WhatsApp Alert", 130),
        ]
        for name, width in columns:
            lbl = ctk.CTkLabel(
                self.table_header_frame,
                text=name,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=self.colors["text_secondary"],
                width=width,
                anchor="w"
            )
            lbl.pack(side="left", padx=4, pady=6)

        # 4. Scrollable Roster Frame
        self.table_scroll = ctk.CTkScrollableFrame(
            self, fg_color=self.colors["bg_card"], corner_radius=8
        )
        self.table_scroll.pack(fill="both", expand=True, padx=16, pady=(0, 16))

    def _load_classes(self) -> None:
        """Loads available class groups into dropdown."""
        if not self.db_conn:
            return
        try:
            cur = self.db_conn.cursor()
            cur.execute("SELECT id, name, section_or_batch FROM class_groups ORDER BY name;")
            rows = cur.fetchall()
        except Exception as exc:
            logger.warning(f"Error loading class groups: {exc}")
            rows = []

        self.classes_map.clear()
        opts = []
        for r in rows:
            display_name = f"{r[1]} ({r[2]})"
            self.classes_map[display_name] = r[0]
            opts.append(display_name)

        if opts:
            self.class_menu.configure(values=opts)
            self.class_var.set(opts[0])
            self.refresh_data()
        else:
            self.class_menu.configure(values=["No Classes Available"])
            self.class_var.set("No Classes Available")

    def refresh_data(self) -> None:
        """Loads class roster for chosen date and populates attendance rows."""
        if not self.attendance_service or not self.db_conn:
            return

        for w in self.table_scroll.winfo_children():
            w.destroy()
        self.roster_rows.clear()

        class_name = self.class_var.get()
        class_id = self.classes_map.get(class_name)
        att_date = self.date_entry.get().strip()

        if not class_id:
            no_lbl = ctk.CTkLabel(
                self.table_scroll, text="Please select a class group above.",
                font=ctk.CTkFont(size=13), text_color=self.colors["text_muted"]
            )
            no_lbl.pack(pady=30)
            return

        try:
            roster = self.attendance_service.load_class_roster_for_attendance(class_group_id=class_id, date=att_date)
        except Exception as exc:
            logger.warning(f"Error loading attendance roster: {exc}")
            no_lbl = ctk.CTkLabel(
                self.table_scroll, text="No attendance roster available (Database table may be initializing).",
                font=ctk.CTkFont(size=13), text_color=self.colors["text_muted"]
            )
            no_lbl.pack(pady=30)
            self.stats_lbl.configure(text="Students: 0  |  Present: 0  |  Absent: 0  |  Attendance: 0%")
            return

        if not roster:
            no_lbl = ctk.CTkLabel(
                self.table_scroll, text="No enrolled students found in this class.",
                font=ctk.CTkFont(size=13), text_color=self.colors["text_muted"]
            )
            no_lbl.pack(pady=30)
            self.stats_lbl.configure(text="Students: 0  |  Present: 0  |  Absent: 0  |  Attendance: 0%")
            return

        try:
            present_count = 0
            absent_count = 0

            for idx, item in enumerate(roster):
                status_val = item["status"] or "Present"
                if status_val == "Present":
                    present_count += 1
                elif status_val == "Absent":
                    absent_count += 1

                bg = self.colors["bg_app"] if idx % 2 == 0 else self.colors["bg_row_alt"]
                row_frame = ctk.CTkFrame(self.table_scroll, fg_color=bg, corner_radius=4, height=36)
                row_frame.pack(fill="x", pady=2, padx=2)

                # Read-only student labels
                s_name = f"{item['first_name']} {item['last_name'] or ''}".strip()
                fields = [
                    (item.get("roll_number") or "—", 70, self.colors["brand_accent"], "bold"),
                    (s_name, 160, self.colors["text_primary"], "normal"),
                    (item.get("guardian_name") or "—", 140, self.colors["text_secondary"], "normal"),
                    (item.get("guardian_phone") or "—", 120, self.colors["text_secondary"], "normal"),
                ]
                for val, width, color, weight in fields:
                    lbl = ctk.CTkLabel(
                        row_frame, text=val, width=width, font=ctk.CTkFont(size=11, weight=weight),
                        text_color=color, anchor="w"
                    )
                    lbl.pack(side="left", padx=4, pady=4)

                # Status OptionMenu
                status_var = ctk.StringVar(value=status_val)
                status_menu = ctk.CTkOptionMenu(
                    row_frame,
                    values=["Present", "Absent", "Late", "Excused"],
                    variable=status_var,
                    width=120,
                    height=24,
                    font=ctk.CTkFont(size=11, weight="bold"),
                    command=lambda v: self._update_stats_label()
                )
                status_menu.pack(side="left", padx=4, pady=4)

                # Remarks entry
                remarks_entry = ctk.CTkEntry(row_frame, width=150, height=24, placeholder_text="Remarks...")
                if item.get("remarks"):
                    remarks_entry.insert(0, item["remarks"])
                remarks_entry.pack(side="left", padx=4, pady=4)

                # WhatsApp Action button (for absent notifications)
                wa_btn = ctk.CTkButton(
                    row_frame,
                    text="📲 Alert",
                    width=75,
                    height=24,
                    fg_color=self.colors["status_unpaid"] if status_val == "Absent" else self.colors["border_color"],
                    hover_color=self.colors["brand_accent"],
                    font=ctk.CTkFont(size=11),
                    command=lambda en=item["enrollment_id"], fn=item["first_name"], gp=item["guardian_phone"], sv=status_var: self._send_whatsapp_alert(en, fn, gp, sv.get())
                )
                wa_btn.pack(side="left", padx=6, pady=4)

                self.roster_rows.append({
                    "enrollment_id": item["enrollment_id"],
                    "status_var": status_var,
                    "remarks_entry": remarks_entry,
                    "first_name": item["first_name"],
                    "guardian_phone": item["guardian_phone"],
                })

            pct = (present_count / len(roster) * 100) if roster else 0
            self.stats_lbl.configure(
                text=f"Students: {len(roster)}  |  Present: {present_count}  |  Absent: {absent_count}  |  Rate: {pct:.1f}%"
            )

        except Exception as exc:
            logger.error(f"Error loading attendance roster: {exc}", exc_info=True)

    def _mark_all_present(self) -> None:
        """Sets all status dropdowns in active roster to 'Present'."""
        for item in self.roster_rows:
            item["status_var"].set("Present")
        self._update_stats_label()

    def _update_stats_label(self) -> None:
        """Recalculates present/absent counts from active dropdowns."""
        total = len(self.roster_rows)
        present = sum(1 for r in self.roster_rows if r["status_var"].get() == "Present")
        absent = sum(1 for r in self.roster_rows if r["status_var"].get() == "Absent")
        pct = (present / total * 100) if total else 0
        self.stats_lbl.configure(
            text=f"Students: {total}  |  Present: {present}  |  Absent: {absent}  |  Rate: {pct:.1f}%"
        )

    def _save_roster(self) -> None:
        """Saves current roster state atomically via AttendanceService.save_bulk_attendance."""
        if not self.attendance_service or not self.roster_rows:
            return

        att_date = self.date_entry.get().strip()
        records = []
        for r in self.roster_rows:
            records.append({
                "enrollment_id": r["enrollment_id"],
                "status": r["status_var"].get(),
                "reason_note": r["remarks_entry"].get().strip() or None,
            })

        try:
            saved_count = self.attendance_service.save_bulk_attendance(
                date=att_date,
                entries=records
            )
            self.show_info("Attendance Saved", f"Successfully saved {saved_count} attendance records for {att_date}.")
            self.refresh_data()
        except Exception as exc:
            self.show_error("Save Failed", str(exc))

    def _send_whatsapp_alert(self, enrollment_id: int, student_name: str, phone: str, status: str) -> None:
        """Generates WhatsApp URL payload and displays formatted modal with copy and browser launch."""
        if status != "Absent":
            self.show_info("Notice", f"{student_name} is marked as '{status}'. Absence notices are for Absent students.")
            return

        att_date = self.date_entry.get().strip()
        try:
            payload = self.attendance_service.generate_absence_whatsapp_payload(
                enrollment_id=enrollment_id,
                date=att_date,
                institution_name="ClassFellow Grammar School"
            )
            WhatsAppNotificationModal(self, payload)
        except Exception as exc:
            self.show_error("WhatsApp Alert Error", str(exc))


class WhatsAppNotificationModal(BaseModal):
    """Bilingual absence notification modal with direct browser launch and copy action."""

    def __init__(self, parent, payload: Dict[str, str]):
        super().__init__(parent, title="WhatsApp Absence Notification", width=560, height=480)
        self.payload = payload

        # Subtitle / Guardian Info
        info_frame = ctk.CTkFrame(self.card, fg_color="transparent")
        info_frame.pack(fill="x", padx=16, pady=(0, 10))

        student_name = payload.get("student_name", "Student")
        guardian_phone = payload.get("guardian_phone", "—")
        ctk.CTkLabel(
            info_frame,
            text=f"Student: {student_name}   |   Guardian: {guardian_phone}",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=THEME_COLORS["brand_primary"],
            anchor="w"
        ).pack(anchor="w")

        # Message Preview Area bound to payload["message_text"]
        message_text = payload.get("message_text", "")

        preview_scroll = ctk.CTkScrollableFrame(
            self.card, fg_color=THEME_COLORS["bg_app"], corner_radius=6, height=240
        )
        preview_scroll.pack(fill="both", expand=True, padx=16, pady=(0, 10))

        self.message_label = ctk.CTkLabel(
            preview_scroll,
            text=message_text,
            wraplength=480,
            font=ctk.CTkFont(size=12),
            text_color=THEME_COLORS["text_primary"],
            justify="left",
            anchor="nw"
        )
        self.message_label.pack(fill="both", expand=True, padx=12, pady=12)

        # Status / Feedback label (e.g. "Message copied to clipboard!")
        self.status_lbl = ctk.CTkLabel(
            self.card,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=THEME_COLORS["brand_primary"]
        )
        self.status_lbl.pack(anchor="w", padx=16, pady=(0, 6))

        # Action Buttons Container
        btn_frame = ctk.CTkFrame(self.card, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=(0, 16))

        # 1. Open in Browser / WhatsApp Web
        self.btn_open = ctk.CTkButton(
            btn_frame,
            text="🚀 Open WhatsApp",
            fg_color=THEME_COLORS["brand_primary"],
            hover_color=THEME_COLORS["brand_accent"],
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._open_whatsapp_url
        )
        self.btn_open.pack(side="left", padx=(0, 8))

        # 2. Copy Message
        self.btn_copy = ctk.CTkButton(
            btn_frame,
            text="📋 Copy Message",
            fg_color=THEME_COLORS["bg_card"],
            hover_color=THEME_COLORS["border_color"],
            border_width=1,
            border_color=THEME_COLORS["border_color"],
            text_color=THEME_COLORS["text_primary"],
            font=ctk.CTkFont(size=12),
            command=self._copy_message
        )
        self.btn_copy.pack(side="left", padx=(0, 8))

        # 3. Dismiss
        self.btn_close = ctk.CTkButton(
            btn_frame,
            text="Dismiss",
            fg_color="transparent",
            hover_color=THEME_COLORS["border_color"],
            text_color=THEME_COLORS["text_secondary"],
            font=ctk.CTkFont(size=12),
            width=80,
            command=self.close
        )
        self.btn_close.pack(side="right")

    def _open_whatsapp_url(self) -> None:
        """Launches the wa.me deep-link in default web browser."""
        url = self.payload.get("whatsapp_url", "")
        if url:
            webbrowser.open(url)
            self.status_lbl.configure(text="Opening WhatsApp in default browser...")

    def _copy_message(self) -> None:
        """Copies message text to OS clipboard."""
        msg = self.payload.get("message_text", "")
        try:
            self.clipboard_clear()
            self.clipboard_append(msg)
            self.status_lbl.configure(text="Message copied to clipboard!")
        except Exception:
            self.status_lbl.configure(text="Failed to copy message.")
