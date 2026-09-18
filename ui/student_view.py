"""
ClassFellow - Student & Enrollment View (ui/student_view.py)
===========================================================
Provides student registry search, read-only tabular records,
and modal dialog for new student admission mutations.
"""

import os
import logging
from decimal import Decimal
from typing import Dict, Any, Optional, List
from tkinter import filedialog
import customtkinter as ctk

from models import StudentDTO
from services.student_service import StudentService
from services.importer_service import StudentImporterService
from ui.base_view import BaseView, BaseModal, THEME_COLORS

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
# Modal Dialog: New Student Admission
# =============================================================================

class StudentAdmissionModal(BaseModal):
    """Focus-trapped modal dialog for student registration."""

    def __init__(self, parent_view: StudentView):
        super().__init__(
            parent_view,
            title="New Student Admission",
            width=540,
            height=580
        )
        self.parent_view = parent_view
        self.student_service = parent_view.student_service

        self._build_form()

    def _build_form(self) -> None:
        """Builds registration input controls."""
        form_scroll = ctk.CTkScrollableFrame(self.card, fg_color="transparent")
        form_scroll.pack(fill="both", expand=True, padx=12, pady=4)

        # 1. Names
        self.first_name = self._add_entry(form_scroll, "First Name *:", "e.g. Muhammad")
        self.last_name = self._add_entry(form_scroll, "Last Name:", "e.g. Ali")
        self.urdu_name = self._add_entry(form_scroll, "Urdu Name:", "مثال: محمد علی")

        # 2. Gender
        gender_frame = ctk.CTkFrame(form_scroll, fg_color="transparent")
        gender_frame.pack(fill="x", pady=4)
        ctk.CTkLabel(
            gender_frame, text="Gender *:", width=140, anchor="w",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(side="left")
        self.gender_var = ctk.StringVar(value="Male")
        self.gender_menu = ctk.CTkOptionMenu(
            gender_frame, values=["Male", "Female", "Other"], variable=self.gender_var, width=180
        )
        self.gender_menu.pack(side="left")

        # 3. Guardian Info
        self.guardian_name = self._add_entry(form_scroll, "Guardian Name *:", "Father / Guardian full name")
        self.guardian_phone = self._add_entry(form_scroll, "Guardian Phone *:", "03001234567 (11 digits)")

        # 4. Class Group Selection
        class_frame = ctk.CTkFrame(form_scroll, fg_color="transparent")
        class_frame.pack(fill="x", pady=4)
        ctk.CTkLabel(
            class_frame, text="Assign Class *:", width=140, anchor="w",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(side="left")

        self.class_groups_map: Dict[str, int] = {}
        if self.parent_view.db_conn:
            cur = self.parent_view.db_conn.cursor()
            cur.execute("SELECT id, name, section_or_batch FROM class_groups ORDER BY name;")
            for row in cur.fetchall():
                display_name = f"{row[1]} ({row[2]})"
                self.class_groups_map[display_name] = row[0]

        class_names = list(self.class_groups_map.keys()) or ["Default Class"]
        self.class_var = ctk.StringVar(value=class_names[0])
        self.class_menu = ctk.CTkOptionMenu(
            class_frame, values=class_names, variable=self.class_var, width=220
        )
        self.class_menu.pack(side="left")

        # 5. Monthly Fee Discount
        self.discount_entry = self._add_entry(form_scroll, "Monthly Discount (PKR):", "0.00")

        # Buttons on bottom
        btn_box = ctk.CTkFrame(self.card, fg_color="transparent")
        btn_box.pack(fill="x", padx=12, pady=(8, 12))

        btn_cancel = ctk.CTkButton(
            btn_box, text="Cancel", command=self.close,
            fg_color=THEME_COLORS["border_color"], width=100
        )
        btn_cancel.pack(side="right", padx=6)

        btn_save = ctk.CTkButton(
            btn_box, text="Save Admission", command=self._submit_admission,
            fg_color=THEME_COLORS["brand_primary"], hover_color=THEME_COLORS["brand_accent"],
            font=ctk.CTkFont(size=13, weight="bold"), width=140
        )
        btn_save.pack(side="right", padx=6)

    def _add_entry(self, parent, label: str, placeholder: str) -> ctk.CTkEntry:
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", pady=4)
        ctk.CTkLabel(f, text=label, width=140, anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        e = ctk.CTkEntry(f, placeholder_text=placeholder, width=280)
        e.pack(side="left")
        return e

    def _submit_admission(self) -> None:
        """Validates inputs and calls StudentService.register_student."""
        fn = self.first_name.get().strip()
        ln = self.last_name.get().strip()
        un = self.urdu_name.get().strip() or None
        gender = self.gender_var.get()
        gn = self.guardian_name.get().strip()
        phone = self.guardian_phone.get().strip()
        selected_class = self.class_var.get()
        class_id = self.class_groups_map.get(selected_class)
        discount_str = self.discount_entry.get().strip() or "0.00"

        if not fn or not gn or not phone:
            self.parent_view.show_error("Validation Error", "Please fill in all mandatory fields (*).")
            return

        try:
            discount = Decimal(discount_str)
        except Exception:
            self.parent_view.show_error("Validation Error", "Invalid discount amount specified.")
            return

        if not class_id:
            self.parent_view.show_error("Validation Error", "Please select a valid class group.")
            return

        try:
            # Query session_id for this class_group
            cur = self.parent_view.db_conn.cursor()
            cur.execute("SELECT session_id FROM class_groups WHERE id = ?;", (class_id,))
            s_row = cur.fetchone()
            if not s_row:
                raise ValueError("Could not find academic session for selected class.")
            session_id = s_row[0]

            dto = StudentDTO(
                first_name=fn,
                last_name=ln or None,
                urdu_name=un,
                gender=gender,
                guardian_name=gn,
                guardian_phone=phone,
            )
            student_id, enrollment_id = self.student_service.register_student(
                student_data=dto,
                class_group_id=class_id,
                session_id=session_id,
                custom_discount_amount=discount,
            )
            created_s = self.student_service.get_student_by_id(student_id)
            adm_no = created_s.get("admission_number", f"ID-{student_id}") if created_s else f"ID-{student_id}"

            self.parent_view.show_info(
                "Admission Complete",
                f"Student admitted successfully!\nAdmission #: {adm_no}"
            )
            self.parent_view.refresh_data()
            self.close()

        except Exception as exc:
            self.parent_view.show_error("Registration Failed", str(exc))


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
