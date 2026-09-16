"""
ClassFellow - Student & Enrollment View (ui/student_view.py)
===========================================================
Provides student registry search, read-only tabular records,
and modal dialog for new student admission mutations.
"""

import logging
from decimal import Decimal
from typing import Optional, List, Dict, Any
import customtkinter as ctk

from models import StudentDTO
from services.student_service import StudentService
from ui.base_view import BaseView, BaseModal, THEME_COLORS

logger = logging.getLogger(__name__)


class StudentView(BaseView):
    """Student management workspace."""

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, app, **kwargs)
        self.student_service = StudentService(self.db_conn) if self.db_conn else None

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
                ("🔄 Refresh", self.refresh_data, self.colors["brand_accent"]),
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

        students = self.student_service.search_students(
            query=search_term,
            active_only=active_only
        )
        if status_filter == "Withdrawn Only":
            students = [s for s in students if not s.get("is_active")]

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
