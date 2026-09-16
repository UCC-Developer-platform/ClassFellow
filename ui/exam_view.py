"""
ClassFellow - Examination & Report Card View (ui/exam_view.py)
==============================================================
Manages institutional examination cycles, dynamic subject limits,
atomic marks entry with strict boundary guards, class ranking,
and single-sheet ReportLab A4 terminal report card PDF rendering.
"""

import logging
import os
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
import customtkinter as ctk

from services.exam_service import ExamService
from ui.base_view import BaseView, BaseModal, THEME_COLORS

logger = logging.getLogger(__name__)


class ExamView(BaseView):
    """Examination and terminal report card workspace."""

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, app, **kwargs)
        self.exam_service = ExamService(self.db_conn) if self.db_conn else None

        self.exams_map: Dict[str, int] = {}
        self.classes_map: Dict[str, int] = {}

        self._build_ui()
        self._load_selectors()

    def _build_ui(self) -> None:
        """Constructs exam cycle selector, ranking summary, and marks table."""
        # 1. Header Banner
        self.create_header(
            title="Examinations & Report Cards",
            subtitle="Configure exam papers, enter marks with bounds checking, compute BISE ranks, and generate A4 report cards",
            actions=[
                ("➕ New Exam", self._open_create_exam_modal, self.colors["brand_primary"]),
                ("⚙️ Configure Subjects", self._open_config_subject_modal, self.colors["border_color"]),
                ("🔄 Refresh", self.refresh_data, self.colors["brand_accent"]),
            ],
        )

        # 2. Selector & Actions Card
        selector_card = ctk.CTkFrame(self, fg_color=self.colors["bg_card"], corner_radius=8)
        selector_card.pack(fill="x", padx=16, pady=(0, 12))

        ctk.CTkLabel(
            selector_card, text="Exam Cycle *:", font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self.colors["text_primary"]
        ).pack(side="left", padx=(16, 6), pady=12)

        self.exam_var = ctk.StringVar(value="Select Exam")
        self.exam_menu = ctk.CTkOptionMenu(
            selector_card, values=["Select Exam"], variable=self.exam_var,
            command=lambda v: self.refresh_data(), width=180
        )
        self.exam_menu.pack(side="left", padx=4, pady=12)

        ctk.CTkLabel(
            selector_card, text="Class Group *:", font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self.colors["text_primary"]
        ).pack(side="left", padx=(16, 6), pady=12)

        self.class_var = ctk.StringVar(value="Select Class")
        self.class_menu = ctk.CTkOptionMenu(
            selector_card, values=["Select Class"], variable=self.class_var,
            command=lambda v: self.refresh_data(), width=160
        )
        self.class_menu.pack(side="left", padx=4, pady=12)

        btn_calc = ctk.CTkButton(
            selector_card, text="Calculate Ranks", width=120, command=self.refresh_data,
            fg_color=self.colors["brand_accent"], font=ctk.CTkFont(size=12, weight="bold")
        )
        btn_calc.pack(side="left", padx=12, pady=12)

        # 3. Table Header
        self.table_header_frame = ctk.CTkFrame(
            self, fg_color=self.colors["bg_card"], corner_radius=6, height=36
        )
        self.table_header_frame.pack(fill="x", padx=16, pady=(0, 4))

        columns = [
            ("Roll #", 70),
            ("Student Name", 160),
            ("Total Max", 90),
            ("Total Obtained", 100),
            ("Percentage", 90),
            ("Terminal Grade", 110),
            ("Class Rank", 90),
            ("Actions", 170),
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

        # 4. Scrollable Marks Frame
        self.table_scroll = ctk.CTkScrollableFrame(
            self, fg_color=self.colors["bg_card"], corner_radius=8
        )
        self.table_scroll.pack(fill="both", expand=True, padx=16, pady=(0, 16))

    def _load_selectors(self) -> None:
        """Loads available exams and class groups into dropdowns."""
        if not self.db_conn:
            return
        cur = self.db_conn.cursor()

        # Load Exams
        cur.execute("SELECT id, name FROM exams ORDER BY id DESC;")
        exams = cur.fetchall()
        self.exams_map.clear()
        ex_opts = []
        for e in exams:
            self.exams_map[e[1]] = e[0]
            ex_opts.append(e[1])
        if ex_opts:
            self.exam_menu.configure(values=ex_opts)
            self.exam_var.set(ex_opts[0])

        # Load Classes
        cur.execute("SELECT id, name, section_or_batch FROM class_groups ORDER BY name;")
        classes = cur.fetchall()
        self.classes_map.clear()
        cl_opts = []
        for c in classes:
            disp = f"{c[1]} ({c[2]})"
            self.classes_map[disp] = c[0]
            cl_opts.append(disp)
        if cl_opts:
            self.class_menu.configure(values=cl_opts)
            self.class_var.set(cl_opts[0])

        if ex_opts and cl_opts:
            self.refresh_data()

    def refresh_data(self) -> None:
        """Computes and renders class examination results."""
        if not self.exam_service or not self.db_conn:
            return

        for w in self.table_scroll.winfo_children():
            w.destroy()

        exam_name = self.exam_var.get()
        class_name = self.class_var.get()

        exam_id = self.exams_map.get(exam_name)
        class_id = self.classes_map.get(class_name)

        if not exam_id or not class_id:
            no_lbl = ctk.CTkLabel(
                self.table_scroll, text="Please select an exam cycle and class group.",
                font=ctk.CTkFont(size=13), text_color=self.colors["text_muted"]
            )
            no_lbl.pack(pady=30)
            return

        try:
            results = self.exam_service.calculate_class_results(exam_id=exam_id, class_group_id=class_id)
            if not results:
                no_lbl = ctk.CTkLabel(
                    self.table_scroll,
                    text="No examination results or marks registered for this class.",
                    font=ctk.CTkFont(size=13),
                    text_color=self.colors["text_muted"]
                )
                no_lbl.pack(pady=30)
                return

            for idx, r in enumerate(results):
                bg = self.colors["bg_app"] if idx % 2 == 0 else self.colors["bg_row_alt"]
                row_frame = ctk.CTkFrame(self.table_scroll, fg_color=bg, corner_radius=4, height=36)
                row_frame.pack(fill="x", pady=2, padx=2)

                s_name = r.student_name
                is_pass = r.final_grade != "F"
                gr_color = self.colors["status_paid"] if is_pass else self.colors["status_unpaid"]

                fields = [
                    (r.roll_number or "—", 70, self.colors["brand_accent"], "bold"),
                    (s_name, 160, self.colors["text_primary"], "normal"),
                    (f"{r.total_maximum:,.0f}", 90, self.colors["text_secondary"], "normal"),
                    (f"{r.total_obtained:,.0f}", 100, self.colors["text_primary"], "bold"),
                    (f"{r.percentage}%", 90, self.colors["brand_accent"], "bold"),
                    (f"{r.final_grade} ({'Pass' if is_pass else 'Fail'})", 110, gr_color, "bold"),
                    (f"#{r.rank_in_class}", 90, self.colors["brand_primary"], "bold"),
                ]

                for val, width, color, weight in fields:
                    lbl = ctk.CTkLabel(
                        row_frame, text=val, width=width, font=ctk.CTkFont(size=11, weight=weight),
                        text_color=color, anchor="w"
                    )
                    lbl.pack(side="left", padx=4, pady=4)

                # Action buttons
                action_box = ctk.CTkFrame(row_frame, fg_color="transparent")
                action_box.pack(side="left", padx=4, pady=4)

                en_id = r.enrollment_id
                btn_marks = ctk.CTkButton(
                    action_box,
                    text="📝 Enter",
                    width=65,
                    height=24,
                    fg_color=self.colors["brand_primary"],
                    hover_color=self.colors["brand_accent"],
                    font=ctk.CTkFont(size=11, weight="bold"),
                    command=lambda eid=exam_id, cgid=class_id, enid=en_id, sn=s_name: self._open_marks_modal(eid, cgid, enid, sn)
                )
                btn_marks.pack(side="left", padx=2)

                btn_pdf = ctk.CTkButton(
                    action_box,
                    text="📄 Report Card",
                    width=90,
                    height=24,
                    fg_color=self.colors["border_color"],
                    hover_color=self.colors["brand_accent"],
                    font=ctk.CTkFont(size=11),
                    command=lambda card=r: self._generate_report_card(card)
                )
                btn_pdf.pack(side="left", padx=2)

        except Exception as exc:
            logger.error(f"Error loading exam results: {exc}", exc_info=True)

    def _open_create_exam_modal(self) -> None:
        CreateExamModal(self)

    def _open_config_subject_modal(self) -> None:
        ConfigureExamSubjectModal(self)

    def _open_marks_modal(self, exam_id: int, class_group_id: int, enrollment_id: int, student_name: str) -> None:
        MarksEntryModal(self, exam_id=exam_id, class_group_id=class_group_id, enrollment_id=enrollment_id, student_name=student_name)

    def _generate_report_card(self, report_card) -> None:
        """Generates single-sheet bilingual A4 terminal report card PDF."""
        try:
            out_dir = os.path.join("data", "report_cards")
            os.makedirs(out_dir, exist_ok=True)
            adm = (report_card.admission_number or "student").replace("/", "_")
            out_path = os.path.join(out_dir, f"report_card_{adm}.pdf")

            self.exam_service.generate_report_card_pdf_file(
                report_card=report_card,
                output_path=out_path,
                institution_name="ClassFellow Grammar School"
            )
            self.show_info("Report Card Generated", f"Terminal Report Card PDF generated successfully:\n{out_path}")
        except Exception as exc:
            self.show_error("Report Card Failed", str(exc))


# =============================================================================
# Modal Dialogs: Create Exam, Configure Subjects & Marks Entry
# =============================================================================

class CreateExamModal(BaseModal):
    """Focus-trapped dialog for creating examination terms."""

    def __init__(self, parent_view: ExamView):
        super().__init__(parent_view, title="Create Examination Term", width=460, height=380)
        self.parent_view = parent_view
        self.exam_service = parent_view.exam_service
        self._build_form()

    def _build_form(self) -> None:
        content = ctk.CTkFrame(self.card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=16, pady=8)

        ctk.CTkLabel(content, text="Examination Name *:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        self.name_entry = ctk.CTkEntry(content, placeholder_text="e.g. Final Term Examination 2026", width=280)
        self.name_entry.pack(anchor="w", pady=(2, 8))

        ctk.CTkLabel(content, text="Exam Type *:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        self.type_var = ctk.StringVar(value="TermExam")
        self.type_menu = ctk.CTkOptionMenu(
            content, values=["TermExam", "MonthlyTest", "AnnualExam", "MockTest"],
            variable=self.type_var, width=280
        )
        self.type_menu.pack(anchor="w", pady=(2, 8))

        # Academic Session
        ctk.CTkLabel(content, text="Academic Session *:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        self.sessions_map = {}
        if self.parent_view.db_conn:
            cur = self.parent_view.db_conn.cursor()
            cur.execute("SELECT id, name FROM academic_sessions ORDER BY id DESC;")
            for r in cur.fetchall():
                self.sessions_map[r[1]] = r[0]

        sess_opts = list(self.sessions_map.keys()) or ["None"]
        self.sess_var = ctk.StringVar(value=sess_opts[0])
        self.sess_menu = ctk.CTkOptionMenu(content, values=sess_opts, variable=self.sess_var, width=280)
        self.sess_menu.pack(anchor="w", pady=(2, 8))

        # Start and End Dates
        now_str = datetime.now().strftime("%Y-%m-%d")
        ctk.CTkLabel(content, text="Start & End Date (YYYY-MM-DD):", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        dates_frame = ctk.CTkFrame(content, fg_color="transparent")
        dates_frame.pack(anchor="w", pady=(2, 16))
        self.start_date_entry = ctk.CTkEntry(dates_frame, width=130)
        self.start_date_entry.insert(0, now_str)
        self.start_date_entry.pack(side="left", padx=(0, 8))
        self.end_date_entry = ctk.CTkEntry(dates_frame, width=130)
        self.end_date_entry.insert(0, now_str)
        self.end_date_entry.pack(side="left")

        # Buttons
        btn_box = ctk.CTkFrame(self.card, fg_color="transparent")
        btn_box.pack(fill="x", padx=16, pady=(0, 16))

        btn_cancel = ctk.CTkButton(btn_box, text="Cancel", command=self.close, fg_color=THEME_COLORS["border_color"], width=90)
        btn_cancel.pack(side="right", padx=6)

        btn_save = ctk.CTkButton(
            btn_box, text="Create Exam", command=self._submit,
            fg_color=THEME_COLORS["brand_primary"], font=ctk.CTkFont(size=12, weight="bold"), width=120
        )
        btn_save.pack(side="right", padx=6)

    def _submit(self) -> None:
        name = self.name_entry.get().strip()
        etype = self.type_var.get()
        sid = self.sessions_map.get(self.sess_var.get())
        s_date = self.start_date_entry.get().strip()
        e_date = self.end_date_entry.get().strip()

        if not name or not sid or not s_date or not e_date:
            self.parent_view.show_error("Validation Error", "Please fill in all mandatory fields.")
            return

        try:
            self.exam_service.create_exam(
                session_id=sid,
                name=name,
                exam_type=etype,
                start_date=s_date,
                end_date=e_date
            )
            self.parent_view.show_info("Exam Created", f"Examination '{name}' successfully created.")
            self.parent_view._load_selectors()
            self.close()
        except Exception as exc:
            self.parent_view.show_error("Creation Failed", str(exc))


class ConfigureExamSubjectModal(BaseModal):
    """Dialog to attach subjects to an exam with maximum and passing marks."""

    def __init__(self, parent_view: ExamView):
        super().__init__(parent_view, title="Configure Exam Subject Limits", width=480, height=440)
        self.parent_view = parent_view
        self.exam_service = parent_view.exam_service
        self._build_form()

    def _build_form(self) -> None:
        content = ctk.CTkFrame(self.card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=16, pady=8)

        # Subject Dropdown
        ctk.CTkLabel(content, text="Select Subject *:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        self.subjects_map = {}
        if self.parent_view.db_conn:
            cur = self.parent_view.db_conn.cursor()
            cur.execute("SELECT id, name FROM subjects ORDER BY name;")
            for r in cur.fetchall():
                self.subjects_map[r[1]] = r[0]

        sub_opts = list(self.subjects_map.keys()) or ["None"]
        self.sub_var = ctk.StringVar(value=sub_opts[0])
        self.sub_menu = ctk.CTkOptionMenu(content, values=sub_opts, variable=self.sub_var, width=280)
        self.sub_menu.pack(anchor="w", pady=(2, 8))

        # Max Marks
        ctk.CTkLabel(content, text="Maximum Marks *:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        self.max_entry = ctk.CTkEntry(content, width=150)
        self.max_entry.insert(0, "100.00")
        self.max_entry.pack(anchor="w", pady=(2, 8))

        # Passing Marks
        ctk.CTkLabel(content, text="Passing Marks *:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        self.pass_entry = ctk.CTkEntry(content, width=150)
        self.pass_entry.insert(0, "33.00")
        self.pass_entry.pack(anchor="w", pady=(2, 16))

        # Buttons
        btn_box = ctk.CTkFrame(self.card, fg_color="transparent")
        btn_box.pack(fill="x", padx=16, pady=(0, 16))

        btn_cancel = ctk.CTkButton(btn_box, text="Cancel", command=self.close, fg_color=THEME_COLORS["border_color"], width=90)
        btn_cancel.pack(side="right", padx=6)

        btn_save = ctk.CTkButton(
            btn_box, text="Save Limits", command=self._submit,
            fg_color=THEME_COLORS["brand_primary"], font=ctk.CTkFont(size=12, weight="bold"), width=120
        )
        btn_save.pack(side="right", padx=6)

    def _submit(self) -> None:
        sub_id = self.subjects_map.get(self.sub_var.get())
        exam_id = self.parent_view.exams_map.get(self.parent_view.exam_var.get())
        class_id = self.parent_view.classes_map.get(self.parent_view.class_var.get())

        if not sub_id or not exam_id or not class_id:
            self.parent_view.show_error("Selection Error", "Please ensure Exam, Class, and Subject are selected.")
            return

        try:
            max_m = Decimal(self.max_entry.get().strip())
            pass_m = Decimal(self.pass_entry.get().strip())
        except Exception:
            self.parent_view.show_error("Validation Error", "Invalid mark numeric values.")
            return

        try:
            self.exam_service.configure_exam_subject(
                exam_id=exam_id,
                class_group_id=class_id,
                subject_id=sub_id,
                maximum_marks=max_m,
                passing_marks=pass_m
            )
            self.parent_view.show_info("Configured", f"Configured {self.sub_var.get()} limits successfully.")
            self.parent_view.refresh_data()
            self.close()
        except Exception as exc:
            self.parent_view.show_error("Configuration Error", str(exc))


class MarksEntryModal(BaseModal):
    """Focus-trapped dialog enforcing upper-bound marks entry validation."""

    def __init__(self, parent_view: ExamView, exam_id: int, class_group_id: int, enrollment_id: int, student_name: str):
        super().__init__(parent_view, title=f"Enter Marks — {student_name}", width=480, height=440)
        self.parent_view = parent_view
        self.exam_service = parent_view.exam_service
        self.exam_id = exam_id
        self.class_group_id = class_group_id
        self.enrollment_id = enrollment_id

        self._build_form()

    def _build_form(self) -> None:
        content = ctk.CTkFrame(self.card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=16, pady=8)

        # Subject Selector
        ctk.CTkLabel(content, text="Subject *:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        self.exam_subjects = self.exam_service.get_exam_subjects(self.exam_id, self.class_group_id)
        self.subj_map: Dict[str, Any] = {}
        for es in self.exam_subjects:
            self.subj_map[f"{es.subject_name} (Max: {es.maximum_marks})"] = es

        s_opts = list(self.subj_map.keys()) or ["No subjects configured"]
        self.sub_var = ctk.StringVar(value=s_opts[0])
        self.sub_menu = ctk.CTkOptionMenu(content, values=s_opts, variable=self.sub_var, width=280)
        self.sub_menu.pack(anchor="w", pady=(2, 8))

        # Marks Entry
        ctk.CTkLabel(content, text="Marks Obtained *:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        self.marks_entry = ctk.CTkEntry(content, width=150)
        self.marks_entry.insert(0, "0.00")
        self.marks_entry.pack(anchor="w", pady=(2, 8))

        # Absent Checkbox
        self.absent_var = ctk.BooleanVar(value=False)
        self.absent_chk = ctk.CTkCheckBox(content, text="Student Absent (ABS)", variable=self.absent_var)
        self.absent_chk.pack(anchor="w", pady=(2, 8))

        # Teacher Remarks
        ctk.CTkLabel(content, text="Teacher Remarks:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        self.remarks_entry = ctk.CTkEntry(content, placeholder_text="e.g. Excellent conceptual grasp", width=280)
        self.remarks_entry.pack(anchor="w", pady=(2, 16))

        # Buttons
        btn_box = ctk.CTkFrame(self.card, fg_color="transparent")
        btn_box.pack(fill="x", padx=16, pady=(0, 16))

        btn_cancel = ctk.CTkButton(btn_box, text="Cancel", command=self.close, fg_color=THEME_COLORS["border_color"], width=90)
        btn_cancel.pack(side="right", padx=6)

        btn_save = ctk.CTkButton(
            btn_box, text="Record Mark", command=self._submit,
            fg_color=THEME_COLORS["brand_primary"], font=ctk.CTkFont(size=12, weight="bold"), width=120
        )
        btn_save.pack(side="right", padx=6)

    def _submit(self) -> None:
        es = self.subj_map.get(self.sub_var.get())
        if not es:
            self.parent_view.show_error("Validation Error", "No valid exam subject selected.")
            return

        is_abs = self.absent_var.get()
        remarks = self.remarks_entry.get().strip() or None

        try:
            obt_m = Decimal(self.marks_entry.get().strip())
        except Exception:
            self.parent_view.show_error("Validation Error", "Invalid mark numeric value.")
            return

        try:
            self.exam_service.record_student_marks(
                exam_subject_id=es.id,
                marks_entries=[{
                    "enrollment_id": self.enrollment_id,
                    "marks_obtained": obt_m,
                    "is_absent": is_abs,
                    "teacher_remarks": remarks
                }]
            )
            self.parent_view.show_info("Recorded", "Marks recorded successfully.")
            self.parent_view.refresh_data()
            self.close()
        except Exception as exc:
            self.parent_view.show_error("Record Failed", str(exc))
