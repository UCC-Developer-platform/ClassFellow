"""
ClassFellow - Quick Add Class Modal (ui/quick_add_class_modal.py)
================================================================
Lightweight sub-dialog allowing on-the-fly class group registration
directly from the student admission modal.
"""

import sqlite3
from decimal import Decimal
from typing import Optional, Callable
import customtkinter as ctk

from ui.base_view import BaseModal, THEME_COLORS


class QuickAddClassModal(BaseModal):
    """
    Sub-dialog allowing on-the-fly class group creation.
    Saves new class group to SQLite and triggers `on_success(class_id, display_name)`.
    """

    def __init__(
        self,
        parent,
        db_conn: Optional[sqlite3.Connection] = None,
        on_success: Optional[Callable[[int, str], None]] = None,
    ):
        super().__init__(
            parent,
            title="➕ Add New Class Group",
            width=440,
            height=360
        )
        self.parent_modal = parent
        self.db_conn = db_conn
        if not self.db_conn and hasattr(parent, "parent_view") and hasattr(parent.parent_view, "db_conn"):
            self.db_conn = parent.parent_view.db_conn
        elif not self.db_conn and hasattr(parent, "db_conn"):
            self.db_conn = parent.db_conn

        self.on_success = on_success
        if not self.on_success and hasattr(parent, "on_class_created"):
            self.on_success = parent.on_class_created

        self._build_form()
        self.bind("<Escape>", lambda e: self.close())

    def _build_form(self) -> None:
        body = ctk.CTkFrame(self.card, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=4)

        # 1. Class Name
        f1 = ctk.CTkFrame(body, fg_color="transparent")
        f1.pack(fill="x", pady=4)
        ctk.CTkLabel(
            f1, text="Class Name *:", width=130, anchor="w", font=ctk.CTkFont(size=12, weight="bold")
        ).pack(side="left")
        self.name_entry = ctk.CTkEntry(f1, placeholder_text="e.g. Class 9, Prep", width=220)
        self.name_entry.pack(side="left")

        # 2. Section / Batch
        f2 = ctk.CTkFrame(body, fg_color="transparent")
        f2.pack(fill="x", pady=4)
        ctk.CTkLabel(
            f2, text="Section / Batch *:", width=130, anchor="w", font=ctk.CTkFont(size=12, weight="bold")
        ).pack(side="left")
        self.sec_entry = ctk.CTkEntry(f2, placeholder_text="e.g. Section A, Green", width=220)
        self.sec_entry.pack(side="left")

        # 3. Monthly Tuition Fee
        f3 = ctk.CTkFrame(body, fg_color="transparent")
        f3.pack(fill="x", pady=4)
        ctk.CTkLabel(
            f3, text="Monthly Fee (PKR):", width=130, anchor="w", font=ctk.CTkFont(size=12, weight="bold")
        ).pack(side="left")
        self.fee_entry = ctk.CTkEntry(f3, placeholder_text="e.g. 3500.00", width=220)
        self.fee_entry.insert(0, "3500.00")
        self.fee_entry.pack(side="left")

        # 4. Group Type
        f4 = ctk.CTkFrame(body, fg_color="transparent")
        f4.pack(fill="x", pady=4)
        ctk.CTkLabel(f4, text="Class Type:", width=130, anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        self.type_var = ctk.StringVar(value="SchoolClass")
        self.type_menu = ctk.CTkOptionMenu(f4, values=["SchoolClass", "AcademyBatch"], variable=self.type_var, width=220)
        self.type_menu.pack(side="left")

        # Error label
        self.error_label = ctk.CTkLabel(
            body,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="#EF4444",
            anchor="w"
        )
        self.error_label.pack(fill="x", pady=(2, 0))

        # Buttons
        btn_box = ctk.CTkFrame(self.card, fg_color="transparent")
        btn_box.pack(fill="x", padx=16, pady=(10, 14))

        self.btn_cancel = ctk.CTkButton(
            btn_box, text="Cancel", width=90, fg_color=THEME_COLORS["border_color"],
            hover_color="#334155", command=self.close
        )
        self.btn_cancel.pack(side="right", padx=6)

        self.btn_save = ctk.CTkButton(
            btn_box, text="Save & Select", width=120,
            fg_color=THEME_COLORS["brand_primary"], hover_color=THEME_COLORS["brand_accent"],
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._save_class
        )
        self.btn_save.pack(side="right", padx=6)

        # Tab Order
        self.name_entry.bind("<Return>", lambda e: self.sec_entry.focus_set())
        self.sec_entry.bind("<Return>", lambda e: self.fee_entry.focus_set())
        self.fee_entry.bind("<Return>", lambda e: self._save_class())
        self.name_entry.focus_set()

    def _save_class(self) -> None:
        name = self.name_entry.get().strip()
        sec = self.sec_entry.get().strip()
        fee_str = self.fee_entry.get().strip() or "0.00"
        group_type = self.type_var.get()

        if not name or not sec:
            self.error_label.configure(text="Please fill in Class Name and Section.")
            return

        try:
            fee = Decimal(fee_str)
        except Exception:
            self.error_label.configure(text="Invalid fee amount specified.")
            return

        if not self.db_conn:
            self.error_label.configure(text="No database connection available.")
            return

        cur = self.db_conn.cursor()
        cur.execute("SELECT id FROM academic_sessions WHERE is_active = 1 LIMIT 1;")
        s_row = cur.fetchone()
        if not s_row:
            cur.execute("""
                INSERT OR IGNORE INTO academic_sessions (name, start_date, end_date, is_active)
                VALUES ('2026-2027 Academic Session', '2026-04-01', '2027-03-31', 1);
            """)
            cur.execute("SELECT id FROM academic_sessions WHERE name = '2026-2027 Academic Session';")
            s_row = cur.fetchone()
        session_id = s_row[0] if s_row else 1

        try:
            cur.execute("""
                INSERT INTO class_groups (session_id, name, section_or_batch, group_type, monthly_tuition_fee)
                VALUES (?, ?, ?, ?, ?);
            """, (session_id, name, sec, group_type, str(fee)))
            new_id = cur.lastrowid
            display_name = f"{name} ({sec})"
            if self.on_success:
                self.on_success(new_id, display_name)
            self.close()
        except sqlite3.IntegrityError:
            cur.execute("SELECT id FROM class_groups WHERE session_id = ? AND name = ? AND section_or_batch = ?;",
                        (session_id, name, sec))
            existing = cur.fetchone()
            if existing:
                display_name = f"{name} ({sec})"
                if self.on_success:
                    self.on_success(existing[0], display_name)
                self.close()

    def close(self) -> None:
        super().close()
        try:
            if hasattr(self.parent_modal, "grab_set"):
                self.parent_modal.grab_set()
                self.parent_modal.focus_force()
        except Exception:
            pass
