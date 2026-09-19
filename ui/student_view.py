"""
ClassFellow - Student & Enrollment View (ui/student_view.py)
===========================================================
Provides student registry search, read-only tabular records,
and modal dialog for new student admission mutations.
"""

import os
import sqlite3
import logging
from decimal import Decimal
from typing import Dict, Any, Optional, List
from tkinter import filedialog
import customtkinter as ctk

from models import StudentDTO
from services.student_service import (
    StudentService,
    normalize_pakistan_phone,
    generate_next_admission_number
)
from services.fee_service import FeeService, calculate_sibling_discount
from services.importer_service import StudentImporterService
from ui.base_view import BaseView, BaseModal, THEME_COLORS
from ui.quick_add_class_modal import QuickAddClassModal

logger = logging.getLogger(__name__)


class StudentView(BaseView):
    """Student management workspace."""

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, app, **kwargs)
        self.student_service = StudentService(self.db_conn) if self.db_conn else None
        self.importer_service = StudentImporterService(self.db_conn) if self.db_conn else None

        self._build_ui()
        self.refresh_data()

    def _build_ui(self) -> None:
        """Builds search controls and read-only student table."""
        # 1. Header Banner
        self.create_header(
            title="Student Registry & Admissions",
            subtitle="Manage student identities, guardian contacts, enrollments, and statuses",
            actions=[
                ("➕ New Admission", self._open_admission_modal, self.colors["brand_primary"]),
                ("📥 Import Excel", self._open_import_modal, self.colors["brand_accent"]),
                ("📄 Template", self._export_template, self.colors["border_color"]),
                ("🔄 Refresh", self.refresh_data, self.colors["border_color"]),
            ],
        )

        # 2. Search & Filter Bar
        filter_card = ctk.CTkFrame(self, fg_color=self.colors["bg_card"], corner_radius=8)
        filter_card.pack(fill="x", padx=16, pady=(0, 12))

        search_label = ctk.CTkLabel(
            filter_card,
            text="🔍 Search:",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=self.colors["text_primary"]
        )
        search_label.pack(side="left", padx=(16, 8), pady=12)

        self.search_entry = ctk.CTkEntry(
            filter_card,
            placeholder_text="Search by admission #, student name, Urdu script, or phone...",
            width=360,
            font=ctk.CTkFont(size=12)
        )
        self.search_entry.pack(side="left", padx=4, pady=12)
        self.search_entry.bind("<Return>", lambda e: self.refresh_data())

        btn_search = ctk.CTkButton(
            filter_card,
            text="Filter",
            width=80,
            command=self.refresh_data,
            fg_color=self.colors["brand_accent"],
            hover_color=self.colors["brand_primary"],
            font=ctk.CTkFont(size=12, weight="bold")
        )
        btn_search.pack(side="left", padx=8, pady=12)

        btn_clear = ctk.CTkButton(
            filter_card,
            text="Clear",
            width=70,
            command=self._clear_search,
            fg_color=self.colors["border_color"],
            font=ctk.CTkFont(size=12)
        )
        btn_clear.pack(side="left", padx=4, pady=12)

        # Status Filter Dropdown
        status_label = ctk.CTkLabel(
            filter_card,
            text="Status:",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=self.colors["text_primary"]
        )
        status_label.pack(side="left", padx=(20, 6), pady=12)

        self.status_var = ctk.StringVar(value="All")
        self.status_menu = ctk.CTkOptionMenu(
            filter_card,
            values=["All", "Active Only", "Withdrawn Only"],
            variable=self.status_var,
            command=lambda v: self.refresh_data(),
            width=130
        )
        self.status_menu.pack(side="left", padx=4, pady=12)

        # 3. Table Header
        self.table_header_frame = ctk.CTkFrame(
            self, fg_color=self.colors["bg_card"], corner_radius=6, height=36
        )
        self.table_header_frame.pack(fill="x", padx=16, pady=(0, 4))

        columns = [
            ("Admission #", 120),
            ("Student Name", 160),
            ("Urdu Name", 120),
            ("Gender", 70),
            ("Guardian Name", 140),
            ("Phone", 110),
            ("Status", 90),
            ("Actions", 110),
        ]
        for name, width in columns:
            lbl = ctk.CTkLabel(
                self.table_header_frame,
                text=name,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=self.colors["text_secondary"],
                width=width,
                anchor="w"
            )
            lbl.pack(side="left", padx=6, pady=6)

        # 4. Read-Only Scrollable Table Grid
        self.table_scroll = ctk.CTkScrollableFrame(
            self, fg_color=self.colors["bg_card"], corner_radius=8
        )
        self.table_scroll.pack(fill="both", expand=True, padx=16, pady=(0, 16))

    def _clear_search(self) -> None:
        self.search_entry.delete(0, "end")
        self.status_var.set("All")
        self.refresh_data()

    def refresh_data(self) -> None:
        """Loads students using StudentService search and populates read-only rows."""
        if not self.student_service:
            return

        for w in self.table_scroll.winfo_children():
            w.destroy()

        search_term = self.search_entry.get().strip()
        status_filter = self.status_var.get()
        active_only = True
        if status_filter in ("All", "Withdrawn Only"):
            active_only = False

        try:
            students = self.student_service.search_students(
                query=search_term,
                active_only=active_only
            )
            if status_filter == "Withdrawn Only":
                students = [s for s in students if not s.get("is_active")]
        except Exception as exc:
            logger.warning(f"Error querying student records: {exc}")
            no_lbl = ctk.CTkLabel(
                self.table_scroll,
                text="No student records available (Database table may be initializing).",
                font=ctk.CTkFont(size=13),
                text_color=self.colors["text_muted"]
            )
            no_lbl.pack(pady=30)
            return

        if not students:
            no_lbl = ctk.CTkLabel(
                self.table_scroll,
                text="No student records match the specified search criteria.",
                font=ctk.CTkFont(size=13),
                text_color=self.colors["text_muted"]
            )
            no_lbl.pack(pady=30)
            return

        for idx, student in enumerate(students):
            bg = self.colors["bg_app"] if idx % 2 == 0 else self.colors["bg_row_alt"]
            row_frame = ctk.CTkFrame(self.table_scroll, fg_color=bg, corner_radius=4, height=36)
            row_frame.pack(fill="x", pady=2, padx=2)

            # Read-only cell labels
            full_name = student.get("full_name") or f"{student.get('first_name', '')} {student.get('last_name') or ''}".strip()
            is_act = bool(student.get("is_active", 1))
            status_text = "Active" if is_act else "Withdrawn"
            status_color = self.colors["status_paid"] if is_act else self.colors["status_unpaid"]

            fields = [
                (student.get("admission_number", ""), 120, self.colors["brand_accent"], "bold"),
                (full_name, 160, self.colors["text_primary"], "normal"),
                (student.get("urdu_name") or "—", 120, self.colors["text_secondary"], "normal"),
                (student.get("gender", ""), 70, self.colors["text_secondary"], "normal"),
                (student.get("guardian_name", ""), 140, self.colors["text_primary"], "normal"),
                (student.get("guardian_phone", ""), 110, self.colors["text_secondary"], "normal"),
            ]

            for val, width, color, weight in fields:
                lbl = ctk.CTkLabel(
                    row_frame,
                    text=val,
                    width=width,
                    font=ctk.CTkFont(size=12, weight=weight),
                    text_color=color,
                    anchor="w"
                )
                lbl.pack(side="left", padx=6, pady=4)

            # Status pill
            status_lbl = ctk.CTkLabel(
                row_frame,
                text=status_text,
                width=90,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=status_color,
                anchor="w"
            )
            status_lbl.pack(side="left", padx=6, pady=4)

            # Action button on right
            btn_action = ctk.CTkButton(
                row_frame,
                text="Toggle" if is_act else "Reactivate",
                width=100,
                height=26,
                fg_color=self.colors["border_color"],
                hover_color=self.colors["brand_accent"],
                font=ctk.CTkFont(size=11),
                command=lambda s=student: self._toggle_status(s)
            )
            btn_action.pack(side="left", padx=6, pady=4)

    def _toggle_status(self, student: dict) -> None:
        """Toggles a student's active status atomically."""
        new_status = not bool(student.get("is_active", 1))
        self.student_service.update_student_status(student["id"], is_active=new_status)
        self.refresh_data()

    def _open_admission_modal(self) -> None:
        """Presents focus-trapped student admission dialog."""
        StudentAdmissionModal(self)

    def _open_import_modal(self) -> None:
        """Presents Excel/CSV bulk student ingestion dialog."""
        StudentImportModal(self)

    def _export_template(self) -> None:
        """Exports standardized blank Excel template for bulk student ingestion."""
        if not self.importer_service:
            self.show_error("Service Error", "Student importer service is not initialized.")
            return

        dest_path = filedialog.asksaveasfilename(
            title="Save Student Import Template",
            defaultextension=".xlsx",
            filetypes=[("Excel Workbooks", "*.xlsx"), ("All Files", "*.*")],
            initialfile="ClassFellow_Student_Import_Template.xlsx"
        )
        if not dest_path:
            return

        try:
            saved_path = self.importer_service.generate_excel_template(dest_path)
            self.show_info(
                "Template Exported",
                f"Student roster Excel template generated successfully:\n\n{saved_path}"
            )
        except Exception as exc:
            logger.error(f"Failed to export template: {exc}", exc_info=True)
            self.show_error("Export Failed", str(exc))


# =============================================================================
# Modal Dialog: Quick Add Class Group (Inline Sub-Modal)
# =============================================================================

# =============================================================================
def _clean_numeric_input(val: Any) -> str:
    """Sanitizes text inputs to prevent syntax errors when user inserts over default values."""
    s = str(val or "").strip()
    if not s:
        return "0.00"
    if s.count(".") > 1 and s.endswith("0.00"):
        s = s[:-4]
    if s.count(".") > 1:
        parts = s.split(".")
        s = f"{parts[0]}.{parts[1]}"
    return s


class StudentAdmissionModal(BaseModal):
    """
    Structured two-stage modal dialog for Punjab school admissions:
      Stage 1: Student Identity & Demographics (Bilingual English/Urdu RTL)
      Stage 2: Academic Class Allocation & Financial Structure (Concessions, One-Time Heads)
    Features dynamic net payable calculation and 3-panel A4 fee voucher PDF generation.
    """

    def __init__(self, parent_view: StudentView):
        super().__init__(
            parent_view,
            title="🎓 New Student Admission & Enrollment (داخلہ فارم)",
            width=700,
            height=720
        )
        self.parent_view = parent_view
        self.student_service = parent_view.student_service
        self.fee_service = FeeService(parent_view.db_conn) if parent_view.db_conn else None

        self.class_groups_map: Dict[str, int] = {}
        self.class_sessions_map: Dict[str, int] = {}
        self.class_tuition_map: Dict[str, Decimal] = {}

        self._build_form()
        self._setup_shortcuts()

    def _setup_shortcuts(self) -> None:
        """Configures keyboard accelerators and safe close unbinding."""
        self.bind("<Escape>", lambda e: self.close())
        try:
            self.bind_all("<Control-p>", lambda e: self._on_submit_and_print())
            self.bind_all("<Control-P>", lambda e: self._on_submit_and_print())
        except Exception:
            pass

    def close(self) -> None:
        """Safely unbinds global shortcuts before closing dialog."""
        try:
            self.unbind_all("<Control-p>")
            self.unbind_all("<Control-P>")
        except Exception:
            pass
        super().close()

    def _build_form(self) -> None:
        """Builds two-stage registration layout inside a scrollable container."""
        form_scroll = ctk.CTkScrollableFrame(self.card, fg_color="transparent")
        form_scroll.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        # =====================================================================
        # STAGE 1: Identity & Demographics (شناخت و کوائف)
        # =====================================================================
        stage1_card = ctk.CTkFrame(form_scroll, fg_color="#1E293B", corner_radius=8)
        stage1_card.pack(fill="x", padx=4, pady=4)

        stage1_header = ctk.CTkFrame(stage1_card, fg_color="#0F172A", corner_radius=6, height=32)
        stage1_header.pack(fill="x", padx=6, pady=6)
        ctk.CTkLabel(
            stage1_header,
            text="📌 Stage 1: Identity & Demographics (شناخت و کوائف طالب علم)",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#38BDF8"
        ).pack(side="left", padx=10, pady=4)

        s1_body = ctk.CTkFrame(stage1_card, fg_color="transparent")
        s1_body.pack(fill="x", padx=12, pady=(0, 10))

        # Row 1: Admission No & Gender
        r1 = ctk.CTkFrame(s1_body, fg_color="transparent")
        r1.pack(fill="x", pady=3)

        ctk.CTkLabel(r1, text="Admission #:", width=110, anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        self.admission_no_entry = ctk.CTkEntry(r1, width=170, font=ctk.CTkFont(size=12, weight="bold"))
        self.admission_no_entry.pack(side="left", padx=(0, 16))
        self._populate_next_admission_no()

        ctk.CTkLabel(r1, text="Gender *:", width=80, anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        self.gender_var = ctk.StringVar(value="Male")
        self.gender_menu = ctk.CTkOptionMenu(
            r1, values=["Male", "Female", "Other"], variable=self.gender_var, width=150
        )
        self.gender_menu.pack(side="left")

        # Row 2: First Name & Last Name
        r2 = ctk.CTkFrame(s1_body, fg_color="transparent")
        r2.pack(fill="x", pady=3)

        ctk.CTkLabel(r2, text="First Name *:", width=110, anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        self.first_name_entry = ctk.CTkEntry(r2, placeholder_text="e.g. Muhammad", width=170)
        self.first_name_entry.pack(side="left", padx=(0, 16))

        ctk.CTkLabel(r2, text="Last Name:", width=80, anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        self.last_name_entry = ctk.CTkEntry(r2, placeholder_text="e.g. Ali", width=150)
        self.last_name_entry.pack(side="left")

        # Row 3: Urdu Name (RTL Justified)
        r3 = ctk.CTkFrame(s1_body, fg_color="transparent")
        r3.pack(fill="x", pady=3)

        ctk.CTkLabel(r3, text="Urdu Name:", width=110, anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        self.urdu_name_entry = ctk.CTkEntry(
            r3,
            placeholder_text="مثال: محمد علی",
            width=420,
            justify="right",
            font=ctk.CTkFont(family="Segoe UI", size=13)
        )
        self.urdu_name_entry.pack(side="left")

        # Row 4: Date of Birth & B-Form
        r4 = ctk.CTkFrame(s1_body, fg_color="transparent")
        r4.pack(fill="x", pady=3)

        ctk.CTkLabel(r4, text="Date of Birth:", width=110, anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        self.dob_entry = ctk.CTkEntry(r4, placeholder_text="YYYY-MM-DD", width=170)
        self.dob_entry.pack(side="left", padx=(0, 16))

        ctk.CTkLabel(r4, text="B-Form #:", width=80, anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        self.b_form_entry = ctk.CTkEntry(r4, placeholder_text="e.g. 35201-1234567-1", width=150)
        self.b_form_entry.pack(side="left")

        # Row 5: Guardian Name & Guardian Urdu (RTL Justified)
        r5 = ctk.CTkFrame(s1_body, fg_color="transparent")
        r5.pack(fill="x", pady=3)

        ctk.CTkLabel(r5, text="Guardian Name *:", width=110, anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        self.guardian_name_entry = ctk.CTkEntry(r5, placeholder_text="Father / Guardian name", width=170)
        self.guardian_name_entry.pack(side="left", padx=(0, 16))

        ctk.CTkLabel(r5, text="Urdu Name:", width=80, anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        self.guardian_urdu_entry = ctk.CTkEntry(
            r5,
            placeholder_text="والد / سرپرست کا نام",
            width=150,
            justify="right",
            font=ctk.CTkFont(family="Segoe UI", size=13)
        )
        self.guardian_urdu_entry.pack(side="left")

        # Row 6: Relation & Guardian CNIC
        r6 = ctk.CTkFrame(s1_body, fg_color="transparent")
        r6.pack(fill="x", pady=3)

        ctk.CTkLabel(r6, text="Relation:", width=110, anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        self.relation_var = ctk.StringVar(value="Father")
        self.relation_menu = ctk.CTkOptionMenu(
            r6, values=["Father", "Mother", "Uncle", "Grandfather", "Guardian"], variable=self.relation_var, width=170
        )
        self.relation_menu.pack(side="left", padx=(0, 16))

        ctk.CTkLabel(r6, text="CNIC #:", width=80, anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        self.guardian_cnic_entry = ctk.CTkEntry(r6, placeholder_text="e.g. 35201-7654321-1", width=150)
        self.guardian_cnic_entry.pack(side="left")

        # Row 7: Phone (with FocusOut Normalization) & WhatsApp
        r7 = ctk.CTkFrame(s1_body, fg_color="transparent")
        r7.pack(fill="x", pady=3)

        ctk.CTkLabel(r7, text="Mobile Phone *:", width=110, anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        self.guardian_phone = ctk.CTkEntry(r7, placeholder_text="03001234567 (11 digits)", width=170)
        self.guardian_phone.pack(side="left", padx=(0, 16))
        self.guardian_phone.bind("<FocusOut>", self._on_phone_focus_out)

        ctk.CTkLabel(r7, text="WhatsApp:", width=80, anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        self.guardian_whatsapp = ctk.CTkEntry(r7, placeholder_text="03001234567", width=150)
        self.guardian_whatsapp.pack(side="left")
        self.guardian_whatsapp.bind("<FocusOut>", self._on_whatsapp_focus_out)

        # Row 8: Residential Address
        r8 = ctk.CTkFrame(s1_body, fg_color="transparent")
        r8.pack(fill="x", pady=3)

        ctk.CTkLabel(r8, text="Address:", width=110, anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        self.address_entry = ctk.CTkEntry(r8, placeholder_text="Residential Street / Mohallah / City", width=420)
        self.address_entry.pack(side="left")

        # Row 9: Previous School SLC
        r9 = ctk.CTkFrame(s1_body, fg_color="transparent")
        r9.pack(fill="x", pady=3)

        ctk.CTkLabel(r9, text="Previous SLC:", width=110, anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        self.previous_slc_entry = ctk.CTkEntry(r9, placeholder_text="Previous School Leaving Certificate # & School Name", width=420)
        self.previous_slc_entry.pack(side="left")

        # =====================================================================
        # STAGE 2: Academic & Fee Enrollment (تعلیمی و فیس اندراج)
        # =====================================================================
        stage2_card = ctk.CTkFrame(form_scroll, fg_color="#1E293B", corner_radius=8)
        stage2_card.pack(fill="x", padx=4, pady=(6, 4))

        stage2_header = ctk.CTkFrame(stage2_card, fg_color="#0F172A", corner_radius=6, height=32)
        stage2_header.pack(fill="x", padx=6, pady=6)
        ctk.CTkLabel(
            stage2_header,
            text="💰 Stage 2: Academic & Fee Enrollment (تعلیمی و فیس اندراج)",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#10B981"
        ).pack(side="left", padx=10, pady=4)

        s2_body = ctk.CTkFrame(stage2_card, fg_color="transparent")
        s2_body.pack(fill="x", padx=12, pady=(0, 10))

        # Row 1: Class Selection + Inline Quick Add Class + Base Tuition
        cr1 = ctk.CTkFrame(s2_body, fg_color="transparent")
        cr1.pack(fill="x", pady=3)

        ctk.CTkLabel(cr1, text="Assign Class *:", width=110, anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        self._refresh_class_groups()

        initial_class = self.class_names[0] if self.class_names else "Class 1 (Section A)"
        self.class_var = ctk.StringVar(value=initial_class)
        self.class_menu = ctk.CTkOptionMenu(
            cr1, values=self.class_names or [initial_class], variable=self.class_var,
            command=self._on_class_changed, width=170
        )
        self.class_menu.pack(side="left", padx=(0, 6))

        add_class_btn = ctk.CTkButton(
            cr1, text="➕", width=34, height=28,
            fg_color="#334155", hover_color="#475569",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._open_quick_add_class
        )
        add_class_btn.pack(side="left", padx=(0, 16))

        ctk.CTkLabel(cr1, text="Base Fee:", width=70, anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        self.base_tuition_label = ctk.CTkLabel(
            cr1, text="PKR 0.00", width=120, anchor="w",
            font=ctk.CTkFont(size=12, weight="bold"), text_color="#38BDF8"
        )
        self.base_tuition_label.pack(side="left")

        # Row 2: One-Time Upfront Charges
        cr2 = ctk.CTkFrame(s2_body, fg_color="transparent")
        cr2.pack(fill="x", pady=3)

        ctk.CTkLabel(cr2, text="One-Time Heads:", width=110, anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")

        # Admission Fee
        ctk.CTkLabel(cr2, text="Admission:", font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 4))
        self.adm_fee_entry = ctk.CTkEntry(cr2, width=72, font=ctk.CTkFont(size=11))
        self.adm_fee_entry.insert(0, "0.00")
        self.adm_fee_entry.pack(side="left", padx=(0, 10))
        self.adm_fee_entry.bind("<KeyRelease>", self._recalculate_totals)

        # Prospectus / Registration
        ctk.CTkLabel(cr2, text="Prospectus:", font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 4))
        self.prospectus_fee_entry = ctk.CTkEntry(cr2, width=72, font=ctk.CTkFont(size=11))
        self.prospectus_fee_entry.insert(0, "0.00")
        self.prospectus_fee_entry.pack(side="left", padx=(0, 10))
        self.prospectus_fee_entry.bind("<KeyRelease>", self._recalculate_totals)

        # Security Deposit
        ctk.CTkLabel(cr2, text="Security:", font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 4))
        self.security_entry = ctk.CTkEntry(cr2, width=72, font=ctk.CTkFont(size=11))
        self.security_entry.insert(0, "0.00")
        self.security_entry.pack(side="left")
        self.security_entry.bind("<KeyRelease>", self._recalculate_totals)

        # Row 3: Concession Selection & Sibling Auto-Detect
        cr3 = ctk.CTkFrame(s2_body, fg_color="transparent")
        cr3.pack(fill="x", pady=3)

        ctk.CTkLabel(cr3, text="Concession:", width=110, anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        self.concession_var = ctk.StringVar(value="Standard (0%)")
        concession_options = [
            "Standard (0%)",
            "Sibling Auto-Detect",
            "Kinship / Staff (50%)",
            "Scholarship (100%)",
            "Custom Flat Discount"
        ]
        self.concession_menu = ctk.CTkOptionMenu(
            cr3, values=concession_options, variable=self.concession_var,
            command=self._on_concession_mode_changed, width=170
        )
        self.concession_menu.pack(side="left", padx=(0, 16))

        ctk.CTkLabel(cr3, text="Discount:", width=70, anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        self.concession_amount_entry = ctk.CTkEntry(cr3, width=120, font=ctk.CTkFont(size=12))
        self.concession_amount_entry.insert(0, "0.00")
        self.concession_amount_entry.pack(side="left")
        self.concession_amount_entry.bind("<KeyRelease>", self._recalculate_totals)

        # Concession Detection Feedback Label
        self.concession_info_label = ctk.CTkLabel(
            s2_body,
            text="Standard enrollment: 0% concession applied.",
            font=ctk.CTkFont(size=11),
            text_color="#94A3B8",
            anchor="w"
        )
        self.concession_info_label.pack(fill="x", padx=(110, 0), pady=(0, 4))

        # Row 4: Live Dynamic Summary Card
        summary_card = ctk.CTkFrame(s2_body, fg_color="#0F172A", corner_radius=6)
        summary_card.pack(fill="x", pady=(4, 0))

        sc_grid = ctk.CTkFrame(summary_card, fg_color="transparent")
        sc_grid.pack(fill="x", padx=12, pady=6)

        ctk.CTkLabel(sc_grid, text="Net Monthly Tuition:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#F8FAFC").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.net_monthly_label = ctk.CTkLabel(sc_grid, text="PKR 0.00", font=ctk.CTkFont(size=13, weight="bold"), text_color="#10B981")
        self.net_monthly_label.grid(row=0, column=1, sticky="w", padx=(0, 24))

        ctk.CTkLabel(sc_grid, text="Total Upfront Initial Payable:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#F8FAFC").grid(row=0, column=2, sticky="w", padx=(0, 8))
        self.total_payable_label = ctk.CTkLabel(sc_grid, text="PKR 0.00", font=ctk.CTkFont(size=13, weight="bold"), text_color="#F59E0B")
        self.total_payable_label.grid(row=0, column=3, sticky="w")

        # =====================================================================
        # ACTION BAR & ACCELERATORS
        # =====================================================================
        btn_box = ctk.CTkFrame(self.card, fg_color="transparent")
        btn_box.pack(fill="x", padx=12, pady=(6, 10))

        self.btn_cancel = ctk.CTkButton(
            btn_box, text="✖ Cancel [Esc]", width=110, fg_color=THEME_COLORS["border_color"],
            hover_color="#334155", command=self.close
        )
        self.btn_cancel.pack(side="left", padx=4)

        self.btn_submit_print = ctk.CTkButton(
            btn_box,
            text="🖨️ Submit & Print Voucher [Ctrl+P]",
            width=230,
            fg_color=THEME_COLORS["brand_primary"],
            hover_color=THEME_COLORS["brand_accent"],
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._on_submit_and_print
        )
        self.btn_submit_print.pack(side="right", padx=4)

        self.btn_save_only = ctk.CTkButton(
            btn_box,
            text="💾 Save Only",
            width=120,
            fg_color="#334155",
            hover_color="#475569",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._on_save_only
        )
        self.btn_save_only.pack(side="right", padx=4)

        # Explicit Return-key navigation for rapid clerk data-entry
        self.first_name_entry.bind("<Return>", lambda e: self.last_name_entry.focus_set())
        self.last_name_entry.bind("<Return>", lambda e: self.urdu_name_entry.focus_set())
        self.urdu_name_entry.bind("<Return>", lambda e: self.dob_entry.focus_set())
        self.dob_entry.bind("<Return>", lambda e: self.b_form_entry.focus_set())
        self.b_form_entry.bind("<Return>", lambda e: self.guardian_name_entry.focus_set())
        self.guardian_name_entry.bind("<Return>", lambda e: self.guardian_urdu_entry.focus_set())
        self.guardian_urdu_entry.bind("<Return>", lambda e: self.guardian_cnic_entry.focus_set())
        self.guardian_cnic_entry.bind("<Return>", lambda e: self.guardian_phone.focus_set())
        self.guardian_phone.bind("<Return>", lambda e: self.guardian_whatsapp.focus_set())
        self.guardian_whatsapp.bind("<Return>", lambda e: self.address_entry.focus_set())
        self.address_entry.bind("<Return>", lambda e: self.previous_slc_entry.focus_set())
        self.previous_slc_entry.bind("<Return>", lambda e: self.adm_fee_entry.focus_set())
        self.adm_fee_entry.bind("<Return>", lambda e: self.prospectus_fee_entry.focus_set())
        self.prospectus_fee_entry.bind("<Return>", lambda e: self.security_entry.focus_set())
        self.security_entry.bind("<Return>", lambda e: self.concession_amount_entry.focus_set())
        self.concession_amount_entry.bind("<Return>", lambda e: self._on_submit_and_print())

        # Backward compatibility aliases for test assertions
        self.urdu_name = self.urdu_name_entry
        self.guardian_urdu_name = self.guardian_urdu_entry
        self.first_name = self.first_name_entry
        self.last_name = self.last_name_entry
        self.guardian_name = self.guardian_name_entry
        self.discount_entry = self.concession_amount_entry

        # Initial Calculations & Focus
        self._on_class_changed(self.class_var.get())
        self.first_name_entry.focus_set()

    def _populate_next_admission_no(self) -> None:
        """Prefills sequential admission number preview."""
        if self.parent_view.db_conn:
            try:
                next_no = generate_next_admission_number(self.parent_view.db_conn)
                self.admission_no_entry.delete(0, "end")
                self.admission_no_entry.insert(0, next_no)
            except Exception:
                pass

    def _refresh_class_groups(self) -> None:
        """Loads available classes and their tuition fees from SQLite."""
        self.class_groups_map = {}
        self.class_sessions_map = {}
        self.class_tuition_map = {}
        if self.parent_view.db_conn:
            cur = self.parent_view.db_conn.cursor()
            cur.execute("""
                SELECT id, name, section_or_batch, monthly_tuition_fee, session_id
                FROM class_groups
                ORDER BY name, section_or_batch;
            """)
            for row in cur.fetchall():
                c_id, c_name, c_sec, c_fee, c_sess = row[0], row[1], row[2], row[3], row[4]
                display_name = f"{c_name} ({c_sec})"
                self.class_groups_map[display_name] = c_id
                self.class_sessions_map[display_name] = c_sess
                try:
                    self.class_tuition_map[display_name] = Decimal(str(c_fee))
                except Exception:
                    self.class_tuition_map[display_name] = Decimal("0.00")

        self.class_names = list(self.class_groups_map.keys())

    def _open_quick_add_class(self) -> None:
        """Opens standalone QuickAddClassModal dialog."""
        QuickAddClassModal(self)

    def on_class_created(self, class_id: int, display_name: str) -> None:
        """Callback from QuickAddClassModal when a class is registered."""
        self._refresh_class_groups()
        if hasattr(self, "class_menu"):
            self.class_menu.configure(values=self.class_names)
            self.class_var.set(display_name)
            self._on_class_changed(display_name)

    def _on_class_changed(self, choice: str) -> None:
        """Updates tuition display and triggers recalculation."""
        tuition = self.class_tuition_map.get(choice, Decimal("0.00"))
        self.base_tuition_label.configure(text=f"PKR {tuition:,.2f}")
        self._on_concession_mode_changed(self.concession_var.get())

    def _on_phone_focus_out(self, event=None) -> None:
        """Normalizes guardian mobile phone on blur without interrupting cursor typing."""
        val = self.guardian_phone.get().strip()
        if val:
            try:
                normalized = normalize_pakistan_phone(val)
                if normalized != val:
                    self.guardian_phone.delete(0, "end")
                    self.guardian_phone.insert(0, normalized)
            except Exception:
                pass
        if self.concession_var.get() == "Sibling Auto-Detect":
            self._on_concession_mode_changed("Sibling Auto-Detect")

    def _on_whatsapp_focus_out(self, event=None) -> None:
        """Normalizes guardian WhatsApp on blur."""
        val = self.guardian_whatsapp.get().strip()
        if val:
            try:
                normalized = normalize_pakistan_phone(val)
                if normalized != val:
                    self.guardian_whatsapp.delete(0, "end")
                    self.guardian_whatsapp.insert(0, normalized)
            except Exception:
                pass

    def _on_concession_mode_changed(self, mode: str) -> None:
        """Applies concession formulas and updates discount entry."""
        sel_class = self.class_var.get()
        base_tuition = self.class_tuition_map.get(sel_class, Decimal("0.00"))

        if mode == "Standard (0%)":
            self.concession_amount_entry.configure(state="normal")
            self.concession_amount_entry.delete(0, "end")
            self.concession_amount_entry.insert(0, "0.00")
            self.concession_info_label.configure(text="Standard enrollment: 0% concession applied.")
        elif mode == "Sibling Auto-Detect":
            phone = self.guardian_phone.get().strip()
            if phone and self.parent_view.db_conn:
                try:
                    disc = calculate_sibling_discount(self.parent_view.db_conn, phone, base_tuition)
                    # Count existing active siblings
                    cur = self.parent_view.db_conn.cursor()
                    try:
                        norm = normalize_pakistan_phone(phone)
                    except Exception:
                        norm = phone
                    cur.execute(
                        """
                        SELECT COUNT(DISTINCT s.id)
                        FROM students s
                        JOIN enrollments e ON s.id = e.student_id
                        WHERE (s.guardian_phone = ? OR s.guardian_phone = ?) AND e.status = 'Active';
                        """,
                        (norm, phone)
                    )
                    count = cur.fetchone()[0]
                    rank_str = "1st child (0%)" if count == 0 else ("2nd child (25%)" if count == 1 else f"{count + 1}th child (50%)")
                    self.concession_amount_entry.configure(state="normal")
                    self.concession_amount_entry.delete(0, "end")
                    self.concession_amount_entry.insert(0, str(disc))
                    self.concession_info_label.configure(
                        text=f"Detected {count} active sibling(s) -> {rank_str}: PKR {disc:,.2f} concession."
                    )
                except Exception as ex:
                    self.concession_info_label.configure(text=f"Sibling detection error: {ex}")
            else:
                self.concession_amount_entry.configure(state="normal")
                self.concession_amount_entry.delete(0, "end")
                self.concession_amount_entry.insert(0, "0.00")
                self.concession_info_label.configure(text="Enter valid 11-digit guardian mobile to auto-detect siblings.")
        elif mode == "Kinship / Staff (50%)":
            disc = (base_tuition * Decimal("0.50")).quantize(Decimal("0.01"))
            self.concession_amount_entry.configure(state="normal")
            self.concession_amount_entry.delete(0, "end")
            self.concession_amount_entry.insert(0, str(disc))
            self.concession_info_label.configure(text="Staff / Kinship quota: 50% tuition discount applied.")
        elif mode == "Scholarship (100%)":
            disc = base_tuition.quantize(Decimal("0.01"))
            self.concession_amount_entry.configure(state="normal")
            self.concession_amount_entry.delete(0, "end")
            self.concession_amount_entry.insert(0, str(disc))
            self.concession_info_label.configure(text="Full Merit / Need Scholarship: 100% tuition waiver.")
        elif mode == "Custom Flat Discount":
            self.concession_amount_entry.configure(state="normal")
            self.concession_info_label.configure(text="Enter custom monthly discount amount in PKR.")

        self._recalculate_totals()

    def _recalculate_totals(self, event=None) -> None:
        """Recalculates net monthly fee and total upfront initial payable."""
        sel_class = self.class_var.get()
        base_tuition = self.class_tuition_map.get(sel_class, Decimal("0.00"))

        try:
            concession = Decimal(_clean_numeric_input(self.concession_amount_entry.get()))
        except Exception:
            concession = Decimal("0.00")

        try:
            adm_fee = Decimal(_clean_numeric_input(self.adm_fee_entry.get()))
        except Exception:
            adm_fee = Decimal("0.00")

        try:
            pros_fee = Decimal(_clean_numeric_input(self.prospectus_fee_entry.get()))
        except Exception:
            pros_fee = Decimal("0.00")

        try:
            sec_dep = Decimal(_clean_numeric_input(self.security_entry.get()))
        except Exception:
            sec_dep = Decimal("0.00")

        net_monthly = max(Decimal("0.00"), base_tuition - concession)
        one_time_total = adm_fee + pros_fee + sec_dep
        initial_payable = net_monthly + one_time_total

        self.net_monthly_label.configure(text=f"PKR {net_monthly:,.2f}")
        self.total_payable_label.configure(text=f"PKR {initial_payable:,.2f}")

    def _submit_admission(self) -> None:
        """Compatibility method for test automation."""
        self._on_save_only()

    def _on_save_only(self) -> None:
        """Executes admission without generating or printing paper voucher."""
        self._execute_admission(generate_voucher=False)

    def _on_submit_and_print(self) -> None:
        """Executes admission and generates 3-panel fee voucher with printer spooler safety."""
        self._execute_admission(generate_voucher=True)

    def _execute_admission(self, generate_voucher: bool = True) -> None:
        """Validates inputs and commits atomic walk-in admission transaction."""
        fn = self.first_name_entry.get().strip()
        ln = self.last_name_entry.get().strip()
        un = self.urdu_name_entry.get().strip() or None
        gender = self.gender_var.get()
        dob = self.dob_entry.get().strip() or None
        b_form = self.b_form_entry.get().strip() or None
        gn = self.guardian_name_entry.get().strip()
        gun = self.guardian_urdu_entry.get().strip() or None
        rel = self.relation_var.get()
        phone = self.guardian_phone.get().strip()
        wa = self.guardian_whatsapp.get().strip() or None
        cnic = self.guardian_cnic_entry.get().strip() or None
        address = self.address_entry.get().strip() or None
        prev_slc = self.previous_slc_entry.get().strip() or None
        adm_no = self.admission_no_entry.get().strip()

        if not fn:
            self.parent_view.show_error("Validation Error", "Student First Name is required.")
            self.first_name_entry.focus_set()
            return

        if not gn:
            self.parent_view.show_error("Validation Error", "Guardian Name is required.")
            self.guardian_name_entry.focus_set()
            return

        if not phone:
            self.parent_view.show_error("Validation Error", "Guardian Mobile Phone is required.")
            self.guardian_phone.focus_set()
            return

        try:
            valid_phone = normalize_pakistan_phone(phone)
        except Exception as p_err:
            self.parent_view.show_error("Phone Error", str(p_err))
            self.guardian_phone.focus_set()
            return

        selected_class = self.class_var.get()
        class_id = self.class_groups_map.get(selected_class)
        session_id = self.class_sessions_map.get(selected_class)
        if not class_id:
            self.parent_view.show_error("Validation Error", "Please select a valid class group.")
            return

        if not session_id and self.parent_view.db_conn:
            cur = self.parent_view.db_conn.cursor()
            cur.execute("SELECT session_id FROM class_groups WHERE id = ?;", (class_id,))
            s_row = cur.fetchone()
            if s_row:
                session_id = s_row[0]

        try:
            concession = Decimal(_clean_numeric_input(self.concession_amount_entry.get()))
            adm_fee = Decimal(_clean_numeric_input(self.adm_fee_entry.get()))
            pros_fee = Decimal(_clean_numeric_input(self.prospectus_fee_entry.get()))
            sec_dep = Decimal(_clean_numeric_input(self.security_entry.get()))
        except Exception:
            self.parent_view.show_error("Validation Error", "Fee and discount amounts must be numeric.")
            return

        try:
            student_dto = StudentDTO(
                admission_number=adm_no,
                first_name=fn,
                last_name=ln or None,
                urdu_name=un,
                gender=gender,
                date_of_birth=dob,
                b_form_number=b_form,
                guardian_name=gn,
                guardian_urdu_name=gun,
                guardian_relation=rel,
                guardian_phone=valid_phone,
                guardian_whatsapp=wa,
                guardian_cnic=cnic,
                residential_address=address,
                previous_school_slc=prev_slc,
            )

            voucher_pdf = self.fee_service.process_walkin_admission(
                student_data=student_dto,
                class_group_id=class_id,
                session_id=session_id,
                concession_discount=concession,
                admission_fee=adm_fee,
                prospectus_fee=pros_fee,
                security_deposit=sec_dep,
                generate_voucher=generate_voucher
            )

            # Spooler safety on Windows
            if generate_voucher and voucher_pdf and os.path.exists(voucher_pdf):
                try:
                    os.startfile(voucher_pdf, "print")
                except (OSError, AttributeError):
                    try:
                        os.startfile(voucher_pdf)
                    except Exception:
                        pass

                self.parent_view.show_info(
                    "Admission & Voucher Ready",
                    f"Student admitted successfully!\nAdmission #: {adm_no}\n\n3-Panel Fee Voucher generated:\n{voucher_pdf}"
                )
            else:
                self.parent_view.show_info(
                    "Admission Complete",
                    f"Student admitted successfully!\nAdmission #: {adm_no}"
                )

            self.parent_view.refresh_data()
            self.close()

        except Exception as exc:
            logger.error(f"Admission processing error: {exc}", exc_info=True)
            self.parent_view.show_error("Admission Failed", str(exc))


# =============================================================================
# Modal Dialog: Bulk Student Import
# =============================================================================

class StudentImportModal(BaseModal):
    """Modal dialog to configure and execute bulk student ingestion from Excel/CSV."""

    def __init__(self, parent_view: StudentView):
        super().__init__(
            parent_view,
            title="Bulk Student Import (Excel / CSV)",
            width=560,
            height=490
        )
        self.parent_view = parent_view
        self.importer_service = parent_view.importer_service

        self._build_form()

    def _build_form(self) -> None:
        content = ctk.CTkFrame(self.card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=16, pady=8)

        # 1. File Selection
        ctk.CTkLabel(
            content, text="Spreadsheet File (.xlsx, .csv) *:", font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w", pady=(0, 2))

        file_box = ctk.CTkFrame(content, fg_color="transparent")
        file_box.pack(fill="x", pady=(0, 10))

        self.file_entry = ctk.CTkEntry(
            file_box, placeholder_text="Select an Excel or CSV file...", font=ctk.CTkFont(size=12), width=360
        )
        self.file_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_browse = ctk.CTkButton(
            file_box,
            text="📁 Browse...",
            width=95,
            fg_color=THEME_COLORS["border_color"],
            hover_color=THEME_COLORS["brand_accent"],
            command=self._browse_file
        )
        btn_browse.pack(side="right")

        # 2. Target Class Group Selection
        ctk.CTkLabel(
            content, text="Target Class / Batch *:", font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w", pady=(0, 2))

        self.classes_map: Dict[str, int] = {}
        if self.parent_view.db_conn:
            cur = self.parent_view.db_conn.cursor()
            cur.execute("SELECT id, name, section_or_batch FROM class_groups ORDER BY name, section_or_batch;")
            for r in cur.fetchall():
                label = f"{r[1]} ({r[2]})"
                self.classes_map[label] = r[0]

        class_opts = list(self.classes_map.keys()) or ["No Classes Found"]
        self.class_var = ctk.StringVar(value=class_opts[0])
        self.class_menu = ctk.CTkOptionMenu(content, values=class_opts, variable=self.class_var, width=320)
        self.class_menu.pack(anchor="w", pady=(0, 10))

        # 3. Target Academic Session Selection
        ctk.CTkLabel(
            content, text="Target Academic Session *:", font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w", pady=(0, 2))

        self.sessions_map: Dict[str, int] = {}
        if self.parent_view.db_conn:
            cur = self.parent_view.db_conn.cursor()
            cur.execute("SELECT id, name FROM academic_sessions WHERE is_active = 1 ORDER BY name DESC;")
            for r in cur.fetchall():
                self.sessions_map[r[1]] = r[0]

        sess_opts = list(self.sessions_map.keys()) or ["No Active Sessions"]
        self.sess_var = ctk.StringVar(value=sess_opts[0])
        self.sess_menu = ctk.CTkOptionMenu(content, values=sess_opts, variable=self.sess_var, width=320)
        self.sess_menu.pack(anchor="w", pady=(0, 12))

        # Info Callout
        info_card = ctk.CTkFrame(content, fg_color=THEME_COLORS["bg_app"], corner_radius=6)
        info_card.pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(
            info_card,
            text="💡 Tip: Mobile numbers are automatically normalized to 03XXXXXXXXX. Empty admission numbers are generated sequentially (CF-YYYY-XXXX).",
            font=ctk.CTkFont(size=11),
            text_color=THEME_COLORS["text_secondary"],
            wraplength=480,
            justify="left"
        ).pack(padx=12, pady=8)

        # Action Buttons
        btn_box = ctk.CTkFrame(self.card, fg_color="transparent")
        btn_box.pack(fill="x", padx=16, pady=(0, 16))

        btn_cancel = ctk.CTkButton(
            btn_box, text="Cancel", command=self.close, fg_color=THEME_COLORS["border_color"], width=90
        )
        btn_cancel.pack(side="right", padx=6)

        btn_import = ctk.CTkButton(
            btn_box,
            text="📥 Import Students",
            command=self._submit_import,
            fg_color=THEME_COLORS["brand_primary"],
            hover_color=THEME_COLORS["brand_accent"],
            font=ctk.CTkFont(size=12, weight="bold"),
            width=140
        )
        btn_import.pack(side="right", padx=6)

    def _browse_file(self) -> None:
        """Opens file dialog for spreadsheet selection."""
        path = filedialog.askopenfilename(
            title="Select Student Roster File",
            filetypes=[
                ("Spreadsheet Files", "*.xlsx *.csv"),
                ("Excel Workbooks", "*.xlsx"),
                ("CSV Files", "*.csv"),
                ("All Files", "*.*"),
            ]
        )
        if path:
            self.file_entry.delete(0, "end")
            self.file_entry.insert(0, path)

    def _submit_import(self) -> None:
        """Validates selection and executes bulk import via StudentImporterService."""
        file_path = self.file_entry.get().strip()
        if not file_path or not os.path.exists(file_path):
            self.parent_view.show_error("File Error", "Please select a valid existing Excel (.xlsx) or CSV (.csv) file.")
            return

        class_id = self.classes_map.get(self.class_var.get())
        session_id = self.sessions_map.get(self.sess_var.get())

        if not class_id or not session_id:
            self.parent_view.show_error("Selection Error", "Please select a valid class group and active academic session.")
            return

        try:
            summary = self.importer_service.import_students_from_excel(
                file_path=file_path,
                class_group_id=class_id,
                session_id=session_id
            )
            self.parent_view.refresh_data()
            self.close()
            ImportSummaryModal(self.parent_view, summary)

        except Exception as exc:
            logger.error(f"Bulk student import failed: {exc}", exc_info=True)
            self.parent_view.show_error("Import Failure", str(exc))


# =============================================================================
# Modal Dialog: Ingestion Results Summary
# =============================================================================

class ImportSummaryModal(BaseModal):
    """Presents a detailed results breakdown after student bulk ingestion."""

    def __init__(self, parent_view: StudentView, summary: Dict[str, Any]):
        super().__init__(
            parent_view,
            title="Student Ingestion Results",
            width=560,
            height=500
        )
        self.summary = summary
        self._build_ui()

    def _build_ui(self) -> None:
        # Metrics KPI strip
        kpi_frame = ctk.CTkFrame(self.card, fg_color="transparent")
        kpi_frame.pack(fill="x", padx=16, pady=(0, 12))
        kpi_frame.grid_columnconfigure((0, 1, 2), weight=1)

        total = self.summary.get("total_rows", 0)
        imported = self.summary.get("imported_count", 0)
        failed = self.summary.get("failed_count", 0)

        # Total Card
        c1 = ctk.CTkFrame(kpi_frame, fg_color=THEME_COLORS["bg_app"], corner_radius=6)
        c1.grid(row=0, column=0, padx=4, sticky="ew")
        ctk.CTkLabel(c1, text="Total Rows", font=ctk.CTkFont(size=11), text_color=THEME_COLORS["text_secondary"]).pack(pady=(6, 0))
        ctk.CTkLabel(c1, text=str(total), font=ctk.CTkFont(size=18, weight="bold"), text_color=THEME_COLORS["text_primary"]).pack(pady=(0, 6))

        # Imported Card (Emerald)
        c2 = ctk.CTkFrame(kpi_frame, fg_color=THEME_COLORS["bg_app"], corner_radius=6)
        c2.grid(row=0, column=1, padx=4, sticky="ew")
        ctk.CTkLabel(c2, text="Imported", font=ctk.CTkFont(size=11), text_color=THEME_COLORS["text_secondary"]).pack(pady=(6, 0))
        ctk.CTkLabel(c2, text=str(imported), font=ctk.CTkFont(size=18, weight="bold"), text_color=THEME_COLORS["brand_primary"]).pack(pady=(0, 6))

        # Failed Card (Red / Muted)
        failed_color = THEME_COLORS["status_unpaid"] if failed > 0 else THEME_COLORS["text_muted"]
        c3 = ctk.CTkFrame(kpi_frame, fg_color=THEME_COLORS["bg_app"], corner_radius=6)
        c3.grid(row=0, column=2, padx=4, sticky="ew")
        ctk.CTkLabel(c3, text="Failed / Skipped", font=ctk.CTkFont(size=11), text_color=THEME_COLORS["text_secondary"]).pack(pady=(6, 0))
        ctk.CTkLabel(c3, text=str(failed), font=ctk.CTkFont(size=18, weight="bold"), text_color=failed_color).pack(pady=(0, 6))

        # Detailed error log (if any)
        errors = self.summary.get("errors", [])
        if errors:
            ctk.CTkLabel(
                self.card,
                text="⚠️ Skipped Rows / Validation Errors:",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=THEME_COLORS["status_unpaid"]
            ).pack(anchor="w", padx=16, pady=(4, 4))

            err_scroll = ctk.CTkScrollableFrame(self.card, fg_color=THEME_COLORS["bg_app"], corner_radius=6, height=220)
            err_scroll.pack(fill="both", expand=True, padx=16, pady=(0, 12))

            for err in errors:
                err_row = ctk.CTkFrame(err_scroll, fg_color=THEME_COLORS["bg_card"], corner_radius=4)
                err_row.pack(fill="x", pady=2, padx=2)

                row_txt = f"Row {err.get('row', '?')}: {err.get('student_name', 'Unknown')}"
                ctk.CTkLabel(
                    err_row,
                    text=row_txt,
                    font=ctk.CTkFont(size=11, weight="bold"),
                    text_color=THEME_COLORS["brand_accent"],
                    anchor="w"
                ).pack(anchor="w", padx=8, pady=(4, 0))

                ctk.CTkLabel(
                    err_row,
                    text=err.get("error", "Unknown error"),
                    font=ctk.CTkFont(size=11),
                    text_color=THEME_COLORS["text_primary"],
                    wraplength=480,
                    justify="left",
                    anchor="w"
                ).pack(anchor="w", padx=8, pady=(0, 4))
        else:
            success_card = ctk.CTkFrame(self.card, fg_color=THEME_COLORS["bg_app"], corner_radius=6)
            success_card.pack(fill="both", expand=True, padx=16, pady=(8, 12))
            ctk.CTkLabel(
                success_card,
                text="🎉 All student records imported cleanly with zero validation errors!",
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=THEME_COLORS["brand_primary"]
            ).pack(pady=40)

        # Close button
        btn_done = ctk.CTkButton(
            self.card,
            text="Done",
            command=self.close,
            fg_color=THEME_COLORS["brand_primary"],
            hover_color=THEME_COLORS["brand_accent"],
            width=100
        )
        btn_done.pack(pady=(0, 16))
