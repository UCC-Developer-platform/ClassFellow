"""
ClassFellow - Examination & Report Card Domain Service
======================================================
Governs academic subjects, examination sessions, dynamic contextual mark limits,
grading tiers, atomic student marks entry ledger, aggregate percentages,
class rank computation, and student report card assembly as specified in CF-SRS-05.
"""

import sqlite3
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Any

from database import transaction
from models import (
    SubjectDTO,
    ExamDTO,
    ExamSubjectDTO,
    GradingTierDTO,
    SubjectResultDTO,
    StudentReportCardDTO,
)
from app.reports.report_card_generator import generate_report_card_pdf


class ExamService:
    """Encapsulates examination configuration, marks ledger recording, grading, and report generation."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # --- 1. Subject Management ---

    def create_subject(self, name: str, urdu_name: Optional[str] = None, code: Optional[str] = None) -> int:
        """Creates a master subject definition."""
        if not name or not name.strip():
            raise ValueError("Subject name cannot be empty.")

        with transaction(self.conn):
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO subjects (name, urdu_name, code)
                VALUES (?, ?, ?);
                """,
                (name.strip(), urdu_name.strip() if urdu_name else None, code.strip() if code else None),
            )
            return cursor.lastrowid

    def get_subjects(self) -> list[SubjectDTO]:
        """Retrieves all defined subjects."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name, urdu_name, code FROM subjects ORDER BY name ASC;")
        rows = cursor.fetchall()
        return [
            SubjectDTO(
                id=row["id"],
                name=row["name"],
                urdu_name=row["urdu_name"],
                code=row["code"],
            )
            for row in rows
        ]

    # --- 2. Exam Cycles ---

    def create_exam(
        self,
        session_id: int,
        name: str,
        exam_type: str,
        start_date: str,
        end_date: str,
        is_published: bool = False,
    ) -> int:
        """Creates an examination cycle within an academic session."""
        valid_types = ("MonthlyTest", "TermExam", "AnnualExam", "MockTest")
        if exam_type not in valid_types:
            raise ValueError(f"Invalid exam_type '{exam_type}'. Must be one of {valid_types}.")

        if not name or not name.strip():
            raise ValueError("Exam name cannot be empty.")

        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM academic_sessions WHERE id = ?;", (session_id,))
        if not cursor.fetchone():
            raise ValueError(f"Academic session id={session_id} does not exist.")

        with transaction(self.conn):
            cursor.execute(
                """
                INSERT INTO exams (session_id, name, exam_type, start_date, end_date, is_published)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (session_id, name.strip(), exam_type, start_date.strip(), end_date.strip(), 1 if is_published else 0),
            )
            return cursor.lastrowid

    def get_exams(self, session_id: Optional[int] = None) -> list[ExamDTO]:
        """Retrieves exams, optionally filtered by academic session."""
        cursor = self.conn.cursor()
        if session_id:
            cursor.execute(
                "SELECT id, session_id, name, exam_type, start_date, end_date, is_published FROM exams WHERE session_id = ? ORDER BY start_date DESC;",
                (session_id,),
            )
        else:
            cursor.execute(
                "SELECT id, session_id, name, exam_type, start_date, end_date, is_published FROM exams ORDER BY start_date DESC;"
            )
        rows = cursor.fetchall()
        return [
            ExamDTO(
                id=row["id"],
                session_id=row["session_id"],
                name=row["name"],
                exam_type=row["exam_type"],
                start_date=row["start_date"],
                end_date=row["end_date"],
                is_published=bool(row["is_published"]),
            )
            for row in rows
        ]

    # --- 3. Dynamic Exam-Subject Configuration ---

    def configure_exam_subject(
        self,
        exam_id: int,
        class_group_id: int,
        subject_id: int,
        maximum_marks: Decimal,
        passing_marks: Decimal,
        weightage_percent: Decimal = Decimal("100.00"),
        exam_date: Optional[str] = None,
    ) -> int:
        """
        Configures dynamic maximum and passing marks for a subject in a specific exam and class.
        Uses UPSERT logic on UNIQUE(exam_id, class_group_id, subject_id).
        """
        if maximum_marks <= Decimal("0.00"):
            raise ValueError("Maximum marks must be greater than zero.")
        if passing_marks < Decimal("0.00"):
            raise ValueError("Passing marks cannot be negative.")
        if passing_marks > maximum_marks:
            raise ValueError(f"Passing marks ({passing_marks}) cannot exceed maximum marks ({maximum_marks}).")

        with transaction(self.conn):
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO exam_subjects (
                    exam_id, class_group_id, subject_id, maximum_marks, passing_marks, weightage_percent, exam_date
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(exam_id, class_group_id, subject_id) DO UPDATE SET
                    maximum_marks = excluded.maximum_marks,
                    passing_marks = excluded.passing_marks,
                    weightage_percent = excluded.weightage_percent,
                    exam_date = excluded.exam_date;
                """,
                (
                    exam_id,
                    class_group_id,
                    subject_id,
                    str(maximum_marks),
                    str(passing_marks),
                    str(weightage_percent),
                    exam_date.strip() if exam_date else None,
                ),
            )
            cursor.execute(
                "SELECT id FROM exam_subjects WHERE exam_id = ? AND class_group_id = ? AND subject_id = ?;",
                (exam_id, class_group_id, subject_id),
            )
            row = cursor.fetchone()
            return row["id"]

    def get_exam_subjects(self, exam_id: int, class_group_id: int) -> list[ExamSubjectDTO]:
        """Returns all configured exam subjects for an exam and class group."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT es.id, es.exam_id, es.class_group_id, es.subject_id, s.name as subject_name,
                   es.maximum_marks, es.passing_marks, es.weightage_percent, es.exam_date
            FROM exam_subjects es
            JOIN subjects s ON s.id = es.subject_id
            WHERE es.exam_id = ? AND es.class_group_id = ?
            ORDER BY s.name ASC;
            """,
            (exam_id, class_group_id),
        )
        rows = cursor.fetchall()
        return [
            ExamSubjectDTO(
                id=row["id"],
                exam_id=row["exam_id"],
                class_group_id=row["class_group_id"],
                subject_id=row["subject_id"],
                subject_name=row["subject_name"],
                maximum_marks=Decimal(row["maximum_marks"]),
                passing_marks=Decimal(row["passing_marks"]),
                weightage_percent=Decimal(row["weightage_percent"]),
                exam_date=row["exam_date"],
            )
            for row in rows
        ]

    # --- 4. Grading Tiers ---

    def create_grading_tier(
        self,
        session_id: int,
        grade_name: str,
        min_percentage: Decimal,
        max_percentage: Decimal,
        gpa_point: Decimal = Decimal("0.0"),
        remarks_en: Optional[str] = None,
        remarks_ur: Optional[str] = None,
        is_passing: bool = True,
    ) -> int:
        """Configures a grading boundary tier for an academic session."""
        if min_percentage < Decimal("0.00") or max_percentage > Decimal("100.00"):
            raise ValueError("Percentages must be within 0.00 and 100.00.")
        if min_percentage > max_percentage:
            raise ValueError("min_percentage cannot exceed max_percentage.")

        with transaction(self.conn):
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO grading_tiers (
                    session_id, grade_name, min_percentage, max_percentage, gpa_point, remarks_en, remarks_ur, is_passing
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id, grade_name) DO UPDATE SET
                    min_percentage = excluded.min_percentage,
                    max_percentage = excluded.max_percentage,
                    gpa_point = excluded.gpa_point,
                    remarks_en = excluded.remarks_en,
                    remarks_ur = excluded.remarks_ur,
                    is_passing = excluded.is_passing;
                """,
                (
                    session_id,
                    grade_name.strip(),
                    str(min_percentage),
                    str(max_percentage),
                    str(gpa_point),
                    remarks_en.strip() if remarks_en else None,
                    remarks_ur.strip() if remarks_ur else None,
                    1 if is_passing else 0,
                ),
            )
            cursor.execute(
                "SELECT id FROM grading_tiers WHERE session_id = ? AND grade_name = ?;",
                (session_id, grade_name.strip()),
            )
            row = cursor.fetchone()
            return row["id"]

    def seed_default_grading_tiers(self, session_id: int) -> None:
        """Seeds standard BISE Punjab educational grading tiers for an academic session."""
        tiers = [
            ("A+", Decimal("80.00"), Decimal("100.00"), Decimal("4.0"), "Exceptional", "شاندار کارکردگی", True),
            ("A", Decimal("70.00"), Decimal("79.99"), Decimal("3.7"), "Excellent", "بہترین کارکردگی", True),
            ("B", Decimal("60.00"), Decimal("69.99"), Decimal("3.0"), "Very Good", "بہت خوب", True),
            ("C", Decimal("50.00"), Decimal("59.99"), Decimal("2.0"), "Good", "مناسب کارکردگی", True),
            ("D", Decimal("33.00"), Decimal("49.99"), Decimal("1.0"), "Fair / Pass", "قابل قبول", True),
            ("F", Decimal("0.00"), Decimal("32.99"), Decimal("0.0"), "Fail", "ناکام / محنت درکار", False),
        ]
        for grade_name, min_p, max_p, gpa, rem_en, rem_ur, passing in tiers:
            self.create_grading_tier(session_id, grade_name, min_p, max_p, gpa, rem_en, rem_ur, passing)

    def get_grade_for_percentage(self, session_id: int, percentage: Decimal) -> GradingTierDTO:
        """Finds the matching grading tier for a given percentage."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, session_id, grade_name, min_percentage, max_percentage, gpa_point, remarks_en, remarks_ur, is_passing
            FROM grading_tiers
            WHERE session_id = ?
            ORDER BY CAST(min_percentage AS NUMERIC) DESC;
            """,
            (session_id,),
        )
        rows = cursor.fetchall()
        for row in rows:
            min_p = Decimal(row["min_percentage"])
            max_p = Decimal(row["max_percentage"])
            # Inclusive matching
            if min_p <= percentage <= max_p:
                return GradingTierDTO(
                    id=row["id"],
                    session_id=row["session_id"],
                    grade_name=row["grade_name"],
                    min_percentage=min_p,
                    max_percentage=max_p,
                    gpa_point=Decimal(row["gpa_point"]),
                    remarks_en=row["remarks_en"],
                    remarks_ur=row["remarks_ur"],
                    is_passing=bool(row["is_passing"]),
                )

        # Fallback if no tier matches
        return GradingTierDTO(
            id=None,
            session_id=session_id,
            grade_name="N/A",
            min_percentage=Decimal("0.00"),
            max_percentage=Decimal("100.00"),
            gpa_point=Decimal("0.0"),
            remarks_en="Ungraded",
            remarks_ur=None,
            is_passing=False,
        )

    # --- 5. Marks Entry Ledger ---

    def record_student_marks(
        self,
        exam_subject_id: int,
        marks_entries: list[dict[str, Any]],
        user_id: Optional[int] = None,
    ) -> int:
        """
        Records student marks into the ledger atomically.
        Validates:
          1. exam_subject exists.
          2. 0 <= marks_obtained <= maximum_marks.
          3. Atomic UPSERT on UNIQUE(exam_subject_id, enrollment_id).

        Args:
            exam_subject_id: Target exam subject ID.
            marks_entries: List of dicts: {'enrollment_id': int, 'marks_obtained': Decimal|float|str, 'is_absent': bool, 'teacher_remarks': str}
            user_id: User recording the marks.

        Returns:
            Count of rows recorded or updated.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT maximum_marks FROM exam_subjects WHERE id = ?;", (exam_subject_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Exam subject id={exam_subject_id} not found.")

        max_marks = Decimal(row["maximum_marks"])

        count = 0
        with transaction(self.conn):
            for entry in marks_entries:
                enrollment_id = int(entry["enrollment_id"])
                is_absent = bool(entry.get("is_absent", False))
                remarks = entry.get("teacher_remarks")

                raw_marks = entry.get("marks_obtained", Decimal("0.00"))
                marks_obtained = Decimal(str(raw_marks))

                if is_absent:
                    marks_obtained = Decimal("0.00")
                else:
                    if marks_obtained < Decimal("0.00"):
                        raise ValueError(
                            f"Marks obtained ({marks_obtained}) cannot be negative for enrollment_id={enrollment_id}."
                        )
                    if marks_obtained > max_marks:
                        raise ValueError(
                            f"Marks obtained ({marks_obtained}) exceeds maximum marks ({max_marks}) for enrollment_id={enrollment_id}."
                        )

                cursor.execute(
                    """
                    INSERT INTO marks (exam_subject_id, enrollment_id, marks_obtained, is_absent, teacher_remarks, recorded_by_user_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(exam_subject_id, enrollment_id) DO UPDATE SET
                        marks_obtained = excluded.marks_obtained,
                        is_absent = excluded.is_absent,
                        teacher_remarks = excluded.teacher_remarks,
                        recorded_by_user_id = excluded.recorded_by_user_id,
                        updated_at = DATETIME('now');
                    """,
                    (
                        exam_subject_id,
                        enrollment_id,
                        str(marks_obtained),
                        1 if is_absent else 0,
                        remarks.strip() if remarks else None,
                        user_id,
                    ),
                )
                count += 1

        return count

    # --- 6. Results Calculation, Ranking & Report Card Assembly ---

    def calculate_class_results(self, exam_id: int, class_group_id: int) -> list[StudentReportCardDTO]:
        """
        Computes aggregate percentages, subject results, grades, and ranks for all enrolled students in a class.
        Rank ordering:
          1. Total Obtained Marks DESC
          2. Aggregate Percentage DESC
          Students with equal totals share the same rank (e.g., joint 2nd position).
        """
        cursor = self.conn.cursor()

        # Fetch Exam and Session Details
        cursor.execute(
            """
            SELECT e.name as exam_name, e.session_id, s.name as session_name, cg.name as class_name
            FROM exams e
            JOIN academic_sessions s ON s.id = e.session_id
            JOIN class_groups cg ON cg.id = ?
            WHERE e.id = ?;
            """,
            (class_group_id, exam_id),
        )
        meta = cursor.fetchone()
        if not meta:
            raise ValueError(f"Exam id={exam_id} or ClassGroup id={class_group_id} not found.")

        session_id = meta["session_id"]
        exam_name = meta["exam_name"]
        session_name = meta["session_name"]
        class_name = meta["class_name"]

        # Fetch all configured subjects for this exam and class
        exam_subjects = self.get_exam_subjects(exam_id, class_group_id)
        if not exam_subjects:
            return []

        # Fetch all active enrollments in this class
        cursor.execute(
            """
            SELECT e.id as enrollment_id, e.roll_number, st.admission_number,
                   st.first_name, st.last_name, st.urdu_name
            FROM enrollments e
            JOIN students st ON st.id = e.student_id
            WHERE e.class_group_id = ? AND e.status = 'Active'
            ORDER BY e.roll_number ASC, st.first_name ASC;
            """,
            (class_group_id,),
        )
        enrollments = cursor.fetchall()
        if not enrollments:
            return []

        # Calculate student scores
        student_scores: list[dict[str, Any]] = []

        for enr in enrollments:
            enr_id = enr["enrollment_id"]
            student_full_name = f"{enr['first_name']} {enr['last_name'] or ''}".strip()

            results: list[SubjectResultDTO] = []
            total_max = Decimal("0.00")
            total_obt = Decimal("0.00")
            all_passed = True
            latest_teacher_remarks = None

            for es in exam_subjects:
                # Query mark for this subject
                cursor.execute(
                    """
                    SELECT m.marks_obtained, m.is_absent, m.teacher_remarks, s.urdu_name as subject_urdu_name
                    FROM marks m
                    JOIN exam_subjects exs ON exs.id = m.exam_subject_id
                    JOIN subjects s ON s.id = exs.subject_id
                    WHERE m.exam_subject_id = ? AND m.enrollment_id = ?;
                    """,
                    (es.id, enr_id),
                )
                mark_row = cursor.fetchone()

                sub_max = es.maximum_marks
                sub_pass = es.passing_marks
                total_max += sub_max

                if mark_row:
                    is_absent = bool(mark_row["is_absent"])
                    marks_obtained = Decimal(mark_row["marks_obtained"])
                    sub_urdu = mark_row["subject_urdu_name"]
                    if mark_row["teacher_remarks"]:
                        latest_teacher_remarks = mark_row["teacher_remarks"]
                else:
                    is_absent = False
                    marks_obtained = Decimal("0.00")
                    sub_urdu = None

                is_passed = (not is_absent) and (marks_obtained >= sub_pass)
                if not is_passed:
                    all_passed = False

                total_obt += marks_obtained

                # Subject grade
                sub_pct = (marks_obtained / sub_max * Decimal("100.00")) if sub_max > Decimal("0.00") else Decimal("0.00")
                sub_grade_dto = self.get_grade_for_percentage(session_id, sub_pct)

                results.append(
                    SubjectResultDTO(
                        subject_name=es.subject_name,
                        subject_urdu_name=sub_urdu,
                        maximum_marks=sub_max,
                        passing_marks=sub_pass,
                        marks_obtained=marks_obtained,
                        is_absent=is_absent,
                        is_passed=is_passed,
                        grade=sub_grade_dto.grade_name if is_passed else "F",
                    )
                )

            # Aggregate percentage
            if total_max > Decimal("0.00"):
                agg_percentage = ((total_obt / total_max) * Decimal("100.00")).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
            else:
                agg_percentage = Decimal("0.00")

            grade_dto = self.get_grade_for_percentage(session_id, agg_percentage)
            final_grade = grade_dto.grade_name if all_passed else "F"

            # Query attendance stats for this student
            cursor.execute(
                """
                SELECT 
                    COUNT(*) as total_days,
                    SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as present_days
                FROM attendance_records
                WHERE enrollment_id = ?;
                """,
                (enr_id,),
            )
            att_row = cursor.fetchone()
            att_total = att_row["total_days"] or 0
            att_present = att_row["present_days"] or 0
            att_percentage = (float(att_present) / float(att_total) * 100.0) if att_total > 0 else 100.0

            student_scores.append(
                {
                    "enrollment_id": enr_id,
                    "student_name": student_full_name,
                    "urdu_name": enr["urdu_name"],
                    "roll_number": enr["roll_number"],
                    "class_name": class_name,
                    "admission_number": enr["admission_number"],
                    "exam_name": exam_name,
                    "session_name": session_name,
                    "results": results,
                    "total_maximum": total_max,
                    "total_obtained": total_obt,
                    "percentage": agg_percentage,
                    "final_grade": final_grade,
                    "gpa_point": grade_dto.gpa_point,
                    "attendance_percentage": att_percentage,
                    "teacher_remarks": latest_teacher_remarks or grade_dto.remarks_en,
                    "teacher_urdu_remarks": grade_dto.remarks_ur,
                }
            )

        # Compute Ranking: Sort by total_obtained DESC, percentage DESC
        student_scores.sort(key=lambda s: (s["total_obtained"], s["percentage"]), reverse=True)

        total_students = len(student_scores)
        report_cards: list[StudentReportCardDTO] = []

        current_rank = 1
        for i, s in enumerate(student_scores):
            if i > 0:
                prev = student_scores[i - 1]
                if s["total_obtained"] == prev["total_obtained"] and s["percentage"] == prev["percentage"]:
                    # Same score gets same rank
                    s["rank"] = prev["rank"]
                else:
                    s["rank"] = i + 1
            else:
                s["rank"] = 1

            report_cards.append(
                StudentReportCardDTO(
                    student_name=s["student_name"],
                    urdu_name=s["urdu_name"],
                    roll_number=s["roll_number"],
                    class_name=s["class_name"],
                    admission_number=s["admission_number"],
                    exam_name=s["exam_name"],
                    session_name=s["session_name"],
                    results=s["results"],
                    total_maximum=s["total_maximum"],
                    total_obtained=s["total_obtained"],
                    percentage=s["percentage"],
                    final_grade=s["final_grade"],
                    gpa_point=s["gpa_point"],
                    rank_in_class=s["rank"],
                    total_students_in_class=total_students,
                    attendance_percentage=s["attendance_percentage"],
                    teacher_remarks=s["teacher_remarks"],
                    teacher_urdu_remarks=s["teacher_urdu_remarks"],
                    enrollment_id=s["enrollment_id"],
                )
            )

        return report_cards

    def get_student_report_card(
        self, exam_id: int, class_group_id: int, enrollment_id: int
    ) -> Optional[StudentReportCardDTO]:
        """Calculates results for the entire class and returns the specific student's report card."""
        class_results = self.calculate_class_results(exam_id, class_group_id)
        # Find student by admission_number / enrollment
        cursor = self.conn.cursor()
        cursor.execute("SELECT st.admission_number FROM enrollments e JOIN students st ON st.id = e.student_id WHERE e.id = ?;", (enrollment_id,))
        row = cursor.fetchone()
        if not row:
            return None
        adm_no = row["admission_number"]
        for card in class_results:
            if card.admission_number == adm_no:
                return card
        return None

    def generate_report_card_pdf_file(
        self, report_card: StudentReportCardDTO, output_path: str, institution_name: str = "CLASSFELLOW HIGH SCHOOL & ACADEMY"
    ) -> str:
        """Renders report card to PDF file and returns file path."""
        generate_report_card_pdf(report_card, output=output_path, institution_name=institution_name)
        return output_path
