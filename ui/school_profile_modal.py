"""
ClassFellow - School Profile & Institutional Setup Modal ("Mother Form")
========================================================================
Comprehensive onboarding wizard and institutional management dialog.
Configures:
  1. School Identity & Bilingual Branding (English, Urdu RTL, Logo).
  2. Academic Calendar & Session.
  3. Standard Initial Grade Classes & Monthly Tuition Rates.
  4. Regional Fee Surcharge Catalog (Generator, Paper, Security, Admission, etc.).
"""

import os
import shutil
import sqlite3
from decimal import Decimal, InvalidOperation
from typing import Optional, Callable, Any
from tkinter import filedialog
import customtkinter as ctk

from ui.base_view import BaseModal, THEME_COLORS
from services.school_service import (
    SchoolService,
    get_school_profile,
    get_all_fee_heads,
)
from models import SchoolProfileDTO


class SchoolProfileModal(BaseModal):
    """
    Onboarding Wizard & Institutional Profile Dialog ("Mother Form").
    Enforces atomic initial school configuration.
    """

    def __init__(
        self,
        parent,
        db_conn: Optional[sqlite3.Connection] = None,
        on_configured: Optional[Callable[[], None]] = None,
    ):
        super().__init__(
            parent,
            title="🏫 Institutional Setup & School Profile (Mother Form)",
            width=700,
            height=640
        )
        self.db_conn = db_conn
        if not self.db_conn and hasattr(parent, "db_conn"):
            self.db_conn = parent.db_conn
        elif not self.db_conn and hasattr(parent, "parent_view") and hasattr(parent.parent_view, "db_conn"):
            self.db_conn = parent.parent_view.db_conn

        self.on_configured = on_configured
        self.logo_path: Optional[str] = None
        self.school_svc = SchoolService(self.db_conn) if self.db_conn else None

        self._build_ui()
        self._load_existing_data()
        self.bind("<Escape>", lambda e: self.close())

    def _build_ui(self) -> None:
        # Instruction Banner
        banner = ctk.CTkFrame(self.card, fg_color=THEME_COLORS["bg_table_header"], corner_radius=6)
        banner.pack(fill="x", padx=16, pady=(0, 10))
        ctk.CTkLabel(
            banner,
            text="Configure your institution's branding, calendar, classes, and fee surcharges below.",
            font=ctk.CTkFont(size=12),
            text_color=THEME_COLORS["text_secondary"]
        ).pack(side="left", padx=12, pady=6)

        # Tabview
        self.tabview = ctk.CTkTabview(self.card, height=440)
        self.tabview.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        self.tab_identity = self.tabview.add("1. Identity & Branding")
        self.tab_calendar = self.tabview.add("2. Academic Calendar")
        self.tab_classes = self.tabview.add("3. Classes & Tuition")
        self.tab_fees = self.tabview.add("4. Regional Surcharges")

        self._build_tab_identity()
        self._build_tab_calendar()
        self._build_tab_classes()
        self._build_tab_fees()

        # Error label & action bar
        footer = ctk.CTkFrame(self.card, fg_color="transparent")
        footer.pack(fill="x", padx=16, pady=(6, 12))

        self.error_label = ctk.CTkLabel(
            footer,
            text="",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#EF4444",
            anchor="w"
        )
        self.error_label.pack(side="left", fill="x", expand=True)

        btn_cancel = ctk.CTkButton(
            footer,
            text="✖ Cancel",
            command=self.close,
            fg_color="#4B5563",
            hover_color="#374151",
            width=100,
            height=34
        )
        btn_cancel.pack(side="right", padx=(8, 0))

        btn_save = ctk.CTkButton(
            footer,
            text="💾 Save & Complete Setup",
            command=self._save_setup,
            fg_color=THEME_COLORS["brand_primary"],
            hover_color=THEME_COLORS["brand_accent"],
            font=ctk.CTkFont(size=13, weight="bold"),
            height=34
        )
        btn_save.pack(side="right")

    def _build_tab_identity(self) -> None:
        tab = self.tab_identity
        tab.grid_columnconfigure(1, weight=1)

        # School Name (English)
        ctk.CTkLabel(tab, text="School Name (English) *:", anchor="w", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=0, padx=8, pady=4, sticky="w"
        )
        self.name_entry = ctk.CTkEntry(tab, placeholder_text="e.g. Allied Grammar High School")
        self.name_entry.grid(row=0, column=1, padx=8, pady=4, sticky="ew")

        # Urdu Name (RTL)
        ctk.CTkLabel(tab, text="School Name (Urdu):", anchor="w", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=1, column=0, padx=8, pady=4, sticky="w"
        )
        self.urdu_name_entry = ctk.CTkEntry(
            tab,
            placeholder_text="مثلاً الائیڈ گرائمر ہائی اسکول",
            justify="right",
            font=ctk.CTkFont(family="Segoe UI", size=13)
        )
        self.urdu_name_entry.grid(row=1, column=1, padx=8, pady=4, sticky="ew")

        # Campus & Reg Number
        ctk.CTkLabel(tab, text="Campus / Branch Name:", anchor="w").grid(row=2, column=0, padx=8, pady=4, sticky="w")
        self.campus_entry = ctk.CTkEntry(tab, placeholder_text="e.g. Main Campus / Gulberg Branch")
        self.campus_entry.grid(row=2, column=1, padx=8, pady=4, sticky="ew")

        ctk.CTkLabel(tab, text="Registration / BISE Code:", anchor="w").grid(row=3, column=0, padx=8, pady=4, sticky="w")
        self.reg_entry = ctk.CTkEntry(tab, placeholder_text="e.g. BISE-LHR-49102")
        self.reg_entry.grid(row=3, column=1, padx=8, pady=4, sticky="ew")

        # Contact Phone & WhatsApp
        ctk.CTkLabel(tab, text="Official Phone / Mobile *:", anchor="w", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=4, column=0, padx=8, pady=4, sticky="w"
        )
        self.phone_entry = ctk.CTkEntry(tab, placeholder_text="03001234567")
        self.phone_entry.grid(row=4, column=1, padx=8, pady=4, sticky="ew")

        ctk.CTkLabel(tab, text="Official Email Address:", anchor="w").grid(row=5, column=0, padx=8, pady=4, sticky="w")
        self.email_entry = ctk.CTkEntry(tab, placeholder_text="info@school.edu.pk")
        self.email_entry.grid(row=5, column=1, padx=8, pady=4, sticky="ew")

        # Address & City
        ctk.CTkLabel(tab, text="Physical Campus Address:", anchor="w").grid(row=6, column=0, padx=8, pady=4, sticky="w")
        self.address_entry = ctk.CTkEntry(tab, placeholder_text="12-A, Education Avenue")
        self.address_entry.grid(row=6, column=1, padx=8, pady=4, sticky="ew")

        ctk.CTkLabel(tab, text="City / District:", anchor="w").grid(row=7, column=0, padx=8, pady=4, sticky="w")
        self.city_entry = ctk.CTkEntry(tab, placeholder_text="Lahore")
        self.city_entry.insert(0, "Lahore")
        self.city_entry.grid(row=7, column=1, padx=8, pady=4, sticky="ew")

        # Logo Upload Frame
        logo_box = ctk.CTkFrame(tab, fg_color="transparent")
        logo_box.grid(row=8, column=0, columnspan=2, padx=8, pady=8, sticky="ew")

        self.logo_label = ctk.CTkLabel(
            logo_box,
            text="No Logo Selected (Default crest will be used on vouchers)",
            text_color=THEME_COLORS["text_secondary"],
            font=ctk.CTkFont(size=11)
        )
        self.logo_label.pack(side="left", padx=4)

        btn_browse_logo = ctk.CTkButton(
            logo_box,
            text="📁 Browse School Crest / Logo...",
            command=self._browse_logo,
            width=200,
            fg_color="#3B82F6",
            hover_color="#2563EB"
        )
        btn_browse_logo.pack(side="right")

    def _browse_logo(self) -> None:
        filetypes = [("Image files", "*.png *.jpg *.jpeg *.bmp")]
        chosen = filedialog.askopenfilename(title="Select School Logo Image", filetypes=filetypes)
        if chosen:
            self.logo_path = chosen
            self.logo_label.configure(
                text=f"Selected: {os.path.basename(chosen)}",
                text_color=THEME_COLORS["status_paid"]
            )

    def _build_tab_calendar(self) -> None:
        tab = self.tab_calendar
        tab.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(tab, text="Academic Session Name *:", anchor="w", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=0, padx=8, pady=8, sticky="w"
        )
        self.session_entry = ctk.CTkEntry(tab, placeholder_text="e.g. 2026-2027 Academic Session")
        self.session_entry.insert(0, "2026-2027 Academic Session")
        self.session_entry.grid(row=0, column=1, padx=8, pady=8, sticky="ew")

        ctk.CTkLabel(tab, text="Session Start Date (YYYY-MM-DD):", anchor="w").grid(row=1, column=0, padx=8, pady=8, sticky="w")
        self.start_date_entry = ctk.CTkEntry(tab, placeholder_text="2026-04-01")
        self.start_date_entry.insert(0, "2026-04-01")
        self.start_date_entry.grid(row=1, column=1, padx=8, pady=8, sticky="ew")

        ctk.CTkLabel(tab, text="Session End Date (YYYY-MM-DD):", anchor="w").grid(row=2, column=0, padx=8, pady=8, sticky="w")
        self.end_date_entry = ctk.CTkEntry(tab, placeholder_text="2027-03-31")
        self.end_date_entry.insert(0, "2027-03-31")
        self.end_date_entry.grid(row=2, column=1, padx=8, pady=8, sticky="ew")

    def _build_tab_classes(self) -> None:
        tab = self.tab_classes
        ctk.CTkLabel(
            tab,
            text="Initial Class Structure & Baseline Monthly Tuition:",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w"
        ).pack(fill="x", padx=8, pady=(4, 4))

        # Scrollable container for standard classes
        scroll = ctk.CTkScrollableFrame(tab, height=330)
        scroll.pack(fill="both", expand=True, padx=4, pady=4)

        # Standard grade template: (Name, Section, Default Tuition)
        self.standard_classes = [
            ("Playgroup", "Rose", "3000.00"),
            ("Nursery", "Tulip", "3000.00"),
            ("Prep", "Jasmine", "3000.00"),
            ("Class 1", "Section A", "3500.00"),
            ("Class 2", "Section A", "3500.00"),
            ("Class 3", "Section A", "3500.00"),
            ("Class 4", "Section A", "3800.00"),
            ("Class 5", "Section A", "3800.00"),
            ("Class 6", "Section A", "4000.00"),
            ("Class 7", "Section A", "4000.00"),
            ("Class 8", "Section A", "4200.00"),
            ("Class 9", "Section A", "4500.00"),
            ("Class 10", "Section A", "5000.00"),
        ]

        self.class_rows = []
        for name, sec, tuition in self.standard_classes:
            row_frame = ctk.CTkFrame(scroll, fg_color="transparent")
            row_frame.pack(fill="x", pady=2)

            include_var = ctk.BooleanVar(value=True)
            chk = ctk.CTkCheckBox(row_frame, text="", variable=include_var, width=28)
            chk.pack(side="left")

            name_entry = ctk.CTkEntry(row_frame, width=140)
            name_entry.insert(0, name)
            name_entry.pack(side="left", padx=4)

            sec_entry = ctk.CTkEntry(row_frame, width=110)
            sec_entry.insert(0, sec)
            sec_entry.pack(side="left", padx=4)

            ctk.CTkLabel(row_frame, text="Fee: Rs.", font=ctk.CTkFont(size=11)).pack(side="left", padx=(6, 2))
            fee_entry = ctk.CTkEntry(row_frame, width=110)
            fee_entry.insert(0, tuition)
            fee_entry.pack(side="left", padx=4)

            self.class_rows.append((include_var, name_entry, sec_entry, fee_entry))

    def _build_tab_fees(self) -> None:
        tab = self.tab_fees
        ctk.CTkLabel(
            tab,
            text="Regional Operational Funds & Surcharge Catalog (fee_heads):",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w"
        ).pack(fill="x", padx=8, pady=(4, 4))

        scroll = ctk.CTkScrollableFrame(tab, height=330)
        scroll.pack(fill="both", expand=True, padx=4, pady=4)

        # Standard fee heads
        default_heads = [
            {"id": None, "name": "Generator & Fuel Surcharge", "urdu_name": "جنریٹر و ایندھن چارجز", "is_recurring": 1, "default_amount": "500.00", "is_active": 1},
            {"id": None, "name": "Stationery & Exam Paper Fund", "urdu_name": "کاغذ و اسٹیشنری فنڈ", "is_recurring": 0, "default_amount": "1000.00", "is_active": 1},
            {"id": None, "name": "Campus Security Fund", "urdu_name": "سیکیورٹی فنڈ", "is_recurring": 1, "default_amount": "300.00", "is_active": 1},
            {"id": None, "name": "Admission Fee", "urdu_name": "داخلہ فیس", "is_recurring": 0, "default_amount": "5000.00", "is_active": 1},
            {"id": None, "name": "Registration / Prospectus", "urdu_name": "رجسٹریشن و پراسپیکٹس", "is_recurring": 0, "default_amount": "1000.00", "is_active": 1},
            {"id": None, "name": "Caution Deposit (Refundable)", "urdu_name": "سیکیورٹی ڈپازٹ", "is_recurring": 0, "default_amount": "3000.00", "is_active": 1},
        ]

        if self.db_conn:
            existing = get_all_fee_heads(self.db_conn)
            # Filter out Tuition Fee since it's class-based
            existing_filtered = [h for h in existing if h.get("name") != "Tuition Fee"]
            if existing_filtered:
                default_heads = existing_filtered

        self.fee_rows = []
        for fh in default_heads:
            row_frame = ctk.CTkFrame(scroll, fg_color="transparent")
            row_frame.pack(fill="x", pady=4)

            active_var = ctk.BooleanVar(value=bool(fh.get("is_active", 1)))
            chk = ctk.CTkCheckBox(row_frame, text="", variable=active_var, width=28)
            chk.pack(side="left")

            name_lbl = ctk.CTkLabel(row_frame, text=fh["name"], width=200, anchor="w", font=ctk.CTkFont(size=12, weight="bold"))
            name_lbl.pack(side="left", padx=4)

            rec_badge = "Recurring (Monthly)" if fh.get("is_recurring") else "One-Time (Upfront)"
            rec_color = "#3B82F6" if fh.get("is_recurring") else "#10B981"
            lbl_type = ctk.CTkLabel(row_frame, text=rec_badge, text_color=rec_color, width=130, font=ctk.CTkFont(size=10))
            lbl_type.pack(side="left", padx=4)

            ctk.CTkLabel(row_frame, text="Default Rs.", font=ctk.CTkFont(size=11)).pack(side="left", padx=(4, 2))
            amt_entry = ctk.CTkEntry(row_frame, width=90)
            amt_entry.insert(0, str(fh.get("default_amount") or "0.00"))
            amt_entry.pack(side="left", padx=4)

            self.fee_rows.append({
                "id": fh.get("id"),
                "name": fh["name"],
                "urdu_name": fh.get("urdu_name"),
                "is_recurring": fh.get("is_recurring"),
                "active_var": active_var,
                "amt_entry": amt_entry
            })

    def _load_existing_data(self) -> None:
        """Prefills existing data if school profile was previously saved."""
        if not self.db_conn:
            return

        profile = get_school_profile(self.db_conn)
        if profile:
            if profile.get("school_name"):
                self.name_entry.delete(0, "end")
                self.name_entry.insert(0, profile["school_name"])
            if profile.get("school_urdu_name"):
                self.urdu_name_entry.delete(0, "end")
                self.urdu_name_entry.insert(0, profile["school_urdu_name"])
            if profile.get("campus_name"):
                self.campus_entry.delete(0, "end")
                self.campus_entry.insert(0, profile["campus_name"])
            if profile.get("registration_number"):
                self.reg_entry.delete(0, "end")
                self.reg_entry.insert(0, profile["registration_number"])
            if profile.get("contact_number"):
                self.phone_entry.delete(0, "end")
                self.phone_entry.insert(0, profile["contact_number"])
            if profile.get("email"):
                self.email_entry.delete(0, "end")
                self.email_entry.insert(0, profile["email"])
            if profile.get("address"):
                self.address_entry.delete(0, "end")
                self.address_entry.insert(0, profile["address"])
            if profile.get("city"):
                self.city_entry.delete(0, "end")
                self.city_entry.insert(0, profile["city"])
            if profile.get("logo_path"):
                self.logo_path = profile["logo_path"]
                self.logo_label.configure(
                    text=f"Active: {os.path.basename(profile['logo_path'])}",
                    text_color=THEME_COLORS["status_paid"]
                )

        # Check existing active session
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT name, start_date, end_date FROM academic_sessions WHERE is_active = 1 LIMIT 1;")
        sess_row = cursor.fetchone()
        if sess_row:
            s_name = sess_row[0] if isinstance(sess_row, (tuple, list)) else sess_row["name"]
            s_start = sess_row[1] if isinstance(sess_row, (tuple, list)) else sess_row["start_date"]
            s_end = sess_row[2] if isinstance(sess_row, (tuple, list)) else sess_row["end_date"]
            if s_name:
                self.session_entry.delete(0, "end")
                self.session_entry.insert(0, s_name)
            if s_start:
                self.start_date_entry.delete(0, "end")
                self.start_date_entry.insert(0, s_start)
            if s_end:
                self.end_date_entry.delete(0, "end")
                self.end_date_entry.insert(0, s_end)

    def _save_setup(self) -> None:
        self.error_label.configure(text="")

        school_name = self.name_entry.get().strip()
        if not school_name:
            self.error_label.configure(text="School Name (English) is required.")
            self.tabview.set("1. Identity & Branding")
            self.name_entry.focus()
            return

        phone = self.phone_entry.get().strip()
        if not phone:
            self.error_label.configure(text="Official Phone / Mobile is required.")
            self.tabview.set("1. Identity & Branding")
            self.phone_entry.focus()
            return

        session_name = self.session_entry.get().strip()
        if not session_name:
            self.error_label.configure(text="Academic Session Name is required.")
            self.tabview.set("2. Academic Calendar")
            self.session_entry.focus()
            return

        # Handle Logo copy if selected
        final_logo_path = self.logo_path
        if self.logo_path and os.path.exists(self.logo_path):
            try:
                dest_dir = os.path.join(os.getcwd(), "data", "assets")
                os.makedirs(dest_dir, exist_ok=True)
                ext = os.path.splitext(self.logo_path)[1]
                target_dest = os.path.join(dest_dir, f"school_logo{ext}")
                if os.path.abspath(self.logo_path) != os.path.abspath(target_dest):
                    shutil.copy2(self.logo_path, target_dest)
                    final_logo_path = target_dest
            except Exception:
                final_logo_path = self.logo_path

        # 1. Profile DTO
        profile_dto = SchoolProfileDTO(
            school_name=school_name,
            school_urdu_name=self.urdu_name_entry.get().strip() or None,
            campus_name=self.campus_entry.get().strip() or None,
            registration_number=self.reg_entry.get().strip() or None,
            contact_number=phone,
            email=self.email_entry.get().strip() or None,
            address=self.address_entry.get().strip() or None,
            city=self.city_entry.get().strip() or "Lahore",
            logo_path=final_logo_path
        )

        # 2. Session Data
        session_data = {
            "name": session_name,
            "start_date": self.start_date_entry.get().strip() or "2026-04-01",
            "end_date": self.end_date_entry.get().strip() or "2027-03-31"
        }

        # 3. Classes Data
        classes_data = []
        for inc_var, n_ent, s_ent, f_ent in self.class_rows:
            if inc_var.get():
                c_name = n_ent.get().strip()
                c_sec = s_ent.get().strip() or "A"
                raw_fee = f_ent.get().strip()
                try:
                    c_fee = Decimal(raw_fee)
                except (InvalidOperation, ValueError):
                    c_fee = Decimal("0.00")
                if c_name:
                    classes_data.append({
                        "name": c_name,
                        "section_or_batch": c_sec,
                        "monthly_tuition_fee": c_fee,
                        "group_type": "SchoolClass"
                    })

        if not classes_data:
            self.error_label.configure(text="At least one class must be selected in Classes & Tuition.")
            self.tabview.set("3. Classes & Tuition")
            return

        # 4. Fee Heads Data
        fee_heads_data = []
        for fh in self.fee_rows:
            raw_amt = fh["amt_entry"].get().strip()
            try:
                amt = Decimal(raw_amt)
            except (InvalidOperation, ValueError):
                amt = Decimal("0.00")
            fee_heads_data.append({
                "id": fh.get("id"),
                "name": fh["name"],
                "urdu_name": fh.get("urdu_name"),
                "is_recurring": fh.get("is_recurring"),
                "is_active": 1 if fh["active_var"].get() else 0,
                "default_amount": amt
            })

        # Save Atomically via SchoolService
        try:
            SchoolService(self.db_conn).setup_initial_school(
                profile_data=profile_dto,
                session_data=session_data,
                classes_data=classes_data,
                fee_heads_data=fee_heads_data
            )
        except Exception as ex:
            self.error_label.configure(text=f"Save Error: {str(ex)}")
            return

        self.close()

        if self.on_configured:
            try:
                self.on_configured()
            except Exception:
                pass
