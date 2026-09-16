"""
ClassFellow - Student & Enrollment Domain Service
=================================================
Implements business logic for student identity, guardian records, admission
number auto-generation, Pakistani phone validation, and academic enrollments
as specified in SRS_02.
"""

import re
import sqlite3
import datetime
from decimal import Decimal
from typing import Optional, Any
from database import transaction
from models import StudentDTO, EnrollmentDTO


def normalize_pakistan_phone(phone: str) -> str:
    """
    Normalizes and validates a Pakistani mobile number.
    Accepts: '03001234567', '+923001234567', '00923001234567', '0300-1234567', '0300 1234567'.
    
    Returns:
        Standard 11-digit string matching regex: ^03[0-9]{9}$
        
    Raises:
        ValueError: If phone number does not conform to Pakistani mobile standard.
    """
    if not phone or not str(phone).strip():
        raise ValueError("Phone number cannot be empty.")

    cleaned = str(phone).strip()
    # Remove hyphens, spaces, parentheses, dots
    cleaned = re.sub(r"[\s\-\(\)\.]", "", cleaned)

    # Convert international prefixes 0092, +92, or 92 to 0
    if cleaned.startswith("0092"):
        cleaned = "0" + cleaned[4:]
    elif cleaned.startswith("+92"):
        cleaned = "0" + cleaned[3:]
    elif cleaned.startswith("92") and len(cleaned) == 12:
        cleaned = "0" + cleaned[2:]

    if not re.match(r"^03\d{9}$", cleaned):
        raise ValueError(
            f"Invalid Pakistani phone number: '{phone}'. Must be 11 digits starting with '03' (e.g., 03001234567)."
        )

    return cleaned



def generate_next_admission_number(conn: sqlite3.Connection, year: Optional[int] = None) -> str:
    """
    Generates the next sequential admission number for the given calendar year.
    Format: 'CF-YYYY-XXXX' (e.g., 'CF-2025-0001').
    """
    if year is None:
        year = datetime.date.today().year

    prefix = f"CF-{year}-"
    cursor = conn.cursor()
    cursor.execute(
        "SELECT admission_number FROM students WHERE admission_number LIKE ? ORDER BY id DESC LIMIT 1;",
        (f"{prefix}%",)
    )
    row = cursor.fetchone()
    if not row:
        return f"{prefix}0001"

    last_num_str = row["admission_number"] if isinstance(row, sqlite3.Row) else row[0]
    try:
        parts = last_num_str.split("-")
        seq = int(parts[-1])
        return f"{prefix}{seq + 1:04d}"
    except (ValueError, IndexError):
        return f"{prefix}0001"


class StudentService:
    """Encapsulates student and enrollment operations with strict relational integrity."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create_academic_session(
        self,
        name: str,
        start_date: str,
        end_date: str,
        is_active: bool = True
    ) -> int:
        """Creates an academic session (e.g., '2025-2026')."""
        with self.conn:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO academic_sessions (name, start_date, end_date, is_active)
                VALUES (?, ?, ?, ?);
                """,
                (name.strip(), start_date.strip(), end_date.strip(), 1 if is_active else 0)
            )
            return cursor.lastrowid

    def create_class_group(
        self,
        session_id: int,
        name: str,
        section_or_batch: str,
        group_type: str = "SchoolClass",
        monthly_tuition_fee: Decimal = Decimal("0.00")
    ) -> int:
        """
        Creates a class section (School Model) or subject batch (Academy Model).
        """
        if group_type not in ("SchoolClass", "AcademyBatch"):
            raise ValueError(f"Invalid group_type '{group_type}'. Must be 'SchoolClass' or 'AcademyBatch'.")

        with self.conn:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO class_groups (session_id, name, section_or_batch, group_type, monthly_tuition_fee)
                VALUES (?, ?, ?, ?, ?);
                """,
                (session_id, name.strip(), section_or_batch.strip(), group_type, str(monthly_tuition_fee))
            )
            return cursor.lastrowid

    def register_student(
        self,
        student_data: StudentDTO,
        class_group_id: int,
        session_id: int,
        roll_number: Optional[str] = None,
        custom_discount_amount: Decimal = Decimal("0.00"),
        enrollment_date: Optional[str] = None
    ) -> tuple[int, int]:
        """
        Registers a new student and enrolls them in a class group atomically.

        Args:
            student_data: Student profile metadata.
            class_group_id: Target class_group foreign key.
            session_id: Target academic session foreign key.
            roll_number: Optional class roll number.
            custom_discount_amount: Monthly recurring discount.
            enrollment_date: Date of enrollment (defaults to current UTC date).

        Returns:
            Tuple of (student_id, enrollment_id).
        """
        # 1. Validation
        if not student_data.first_name or not student_data.first_name.strip():
            raise ValueError("Student first name cannot be empty.")

        if not student_data.guardian_name or not student_data.guardian_name.strip():
            raise ValueError("Guardian name cannot be empty.")

        if student_data.gender not in ("Male", "Female", "Other"):
            raise ValueError(f"Invalid gender '{student_data.gender}'. Must be 'Male', 'Female', or 'Other'.")

        valid_phone = normalize_pakistan_phone(student_data.guardian_phone)

        valid_whatsapp = None
        if student_data.guardian_whatsapp and str(student_data.guardian_whatsapp).strip():
            valid_whatsapp = normalize_pakistan_phone(student_data.guardian_whatsapp)

        # 2. Foreign Key Existence Checks & Session Name Extraction
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name FROM academic_sessions WHERE id = ?;", (session_id,))
        sess_row = cursor.fetchone()
        if not sess_row:
            raise ValueError(f"Academic session with id={session_id} does not exist.")

        session_name = sess_row["name"] if isinstance(sess_row, sqlite3.Row) else sess_row[1]
        year_match = re.search(r"\d{4}", session_name)
        session_year = int(year_match.group(0)) if year_match else datetime.date.today().year

        cursor.execute("SELECT id FROM class_groups WHERE id = ? AND session_id = ?;", (class_group_id, session_id))
        if not cursor.fetchone():
            raise ValueError(f"Class group id={class_group_id} does not exist in session id={session_id}.")

        if not enrollment_date:
            enrollment_date = datetime.date.today().isoformat()

        # 3. Atomic Composite Transaction with immediate write lock
        with transaction(self.conn):
            # Admission Number Allocation inside exclusive transaction lock
            admission_no = student_data.admission_number
            if not admission_no or not admission_no.strip():
                admission_no = generate_next_admission_number(self.conn, year=session_year)
            else:
                admission_no = admission_no.strip()
                cursor.execute("SELECT id FROM students WHERE admission_number = ?;", (admission_no,))
                if cursor.fetchone():
                    raise ValueError(f"Admission number '{admission_no}' is already registered.")

            cursor.execute(
                """
                INSERT INTO students (
                    admission_number, first_name, last_name, urdu_name, gender,
                    date_of_birth, b_form_number, guardian_name, guardian_urdu_name,
                    guardian_relation, guardian_phone, guardian_whatsapp, guardian_cnic,
                    residential_address, emergency_contact, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    admission_no,
                    student_data.first_name.strip(),
                    student_data.last_name.strip() if student_data.last_name else None,
                    student_data.urdu_name.strip() if student_data.urdu_name else None,
                    student_data.gender,
                    student_data.date_of_birth,
                    student_data.b_form_number,
                    student_data.guardian_name.strip(),
                    student_data.guardian_urdu_name.strip() if student_data.guardian_urdu_name else None,
                    student_data.guardian_relation or "Father",
                    valid_phone,
                    valid_whatsapp,
                    student_data.guardian_cnic,
                    student_data.residential_address,
                    student_data.emergency_contact,
                    1 if student_data.is_active else 0
                )
            )
            student_id = cursor.lastrowid

            cursor.execute(
                """
                INSERT INTO enrollments (
                    student_id, class_group_id, session_id, roll_number,
                    enrollment_date, status, custom_discount_amount
                ) VALUES (?, ?, ?, ?, ?, 'Active', ?);
                """,
                (
                    student_id,
                    class_group_id,
                    session_id,
                    roll_number.strip() if roll_number else None,
                    enrollment_date,
                    str(custom_discount_amount)
                )
            )
            enrollment_id = cursor.lastrowid

        return student_id, enrollment_id

    def search_students(
        self,
        query: str = "",
        session_id: Optional[int] = None,
        class_group_id: Optional[int] = None,
        active_only: bool = True
    ) -> list[dict[str, Any]]:
        """
        Performs high-performance multi-field search across admission number, names,
        Urdu script, and guardian mobile numbers with whitespace normalization.
        """
        cursor = self.conn.cursor()
        clean_q = " ".join(query.strip().split()) if query else ""

        sql = """
        SELECT 
            s.*,
            s.id AS student_id,
            TRIM(s.first_name || ' ' || COALESCE(s.last_name, '')) AS full_name,
            e.id AS enrollment_id,
            e.class_group_id,
            cg.name AS class_name,
            cg.section_or_batch,
            cg.group_type,
            cg.monthly_tuition_fee,
            e.session_id,
            sess.name AS session_name,
            e.roll_number,
            e.enrollment_date,
            e.status AS enrollment_status,
            e.custom_discount_amount
        FROM students s
        JOIN enrollments e ON s.id = e.student_id
        LEFT JOIN class_groups cg ON e.class_group_id = cg.id
        LEFT JOIN academic_sessions sess ON e.session_id = sess.id
        WHERE (:active_only = 0 OR s.is_active = 1)
        """
        params: dict[str, Any] = {
            "active_only": 1 if active_only else 0,
            "session_id": session_id,
            "class_group_id": class_group_id,
            "q": clean_q,
            "like_q": f"%{clean_q}%" if clean_q else "%",
        }

        if session_id is not None:
            sql += " AND e.session_id = :session_id"

        if class_group_id is not None:
            sql += " AND e.class_group_id = :class_group_id"

        if clean_q:
            sql += """
            AND (
                s.admission_number LIKE :like_q OR
                s.first_name LIKE :like_q OR
                s.last_name LIKE :like_q OR
                s.urdu_name LIKE :like_q OR
                s.guardian_name LIKE :like_q OR
                s.guardian_phone LIKE :like_q OR
                e.roll_number LIKE :like_q
            )
            """

        sql += " ORDER BY s.admission_number ASC;"
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        return [{k: r[k] for k in r.keys()} for r in rows]


    def get_student_by_id(self, student_id: int) -> Optional[dict[str, Any]]:
        """Retrieves a single student's profile and latest enrollment details."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT 
                s.*,
                TRIM(s.first_name || ' ' || COALESCE(s.last_name, '')) AS full_name,
                e.id AS enrollment_id,
                e.class_group_id,
                cg.name AS class_name,
                cg.section_or_batch,
                cg.group_type,
                cg.monthly_tuition_fee,
                e.session_id,
                sess.name AS session_name,
                e.roll_number,
                e.enrollment_date,
                e.status AS enrollment_status,
                e.custom_discount_amount
            FROM students s
            LEFT JOIN enrollments e ON s.id = e.student_id
            LEFT JOIN class_groups cg ON e.class_group_id = cg.id
            LEFT JOIN academic_sessions sess ON e.session_id = sess.id
            WHERE s.id = ?
            ORDER BY e.id DESC LIMIT 1;
            """,
            (student_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        data = {k: row[k] for k in row.keys()}
        data["student_id"] = data["id"]
        return data


    def get_student_by_admission_number(self, admission_number: str) -> Optional[dict[str, Any]]:
        """Retrieves a student by their unique admission number."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM students WHERE admission_number = ?;", (admission_number.strip(),))
        row = cursor.fetchone()
        if not row:
            return None
        student_id = row["id"] if isinstance(row, sqlite3.Row) else row[0]
        return self.get_student_by_id(student_id)

    def transfer_or_withdraw_student(
        self,
        enrollment_id: int,
        new_status: str,
        note: Optional[str] = None
    ) -> None:
        """
        Updates enrollment status (e.g., 'Transferred', 'Withdrawn', 'Graduated').
        """
        valid_statuses = ("Active", "Transferred", "Withdrawn", "Graduated")
        if new_status not in valid_statuses:
            raise ValueError(f"Invalid status '{new_status}'. Allowed: {valid_statuses}")

        with self.conn:
            cursor = self.conn.cursor()
            cursor.execute("SELECT id FROM enrollments WHERE id = ?;", (enrollment_id,))
            if not cursor.fetchone():
                raise ValueError(f"Enrollment with id={enrollment_id} does not exist.")

            cursor.execute(
                "UPDATE enrollments SET status = ? WHERE id = ?;",
                (new_status, enrollment_id)
            )

    def update_student(self, student_data: StudentDTO) -> None:
        """Updates editable personal details of an existing student."""
        if not student_data.id:
            raise ValueError("Student ID must be provided to update profile.")

        if not student_data.first_name or not student_data.first_name.strip():
            raise ValueError("First name cannot be empty.")

        if not student_data.guardian_name or not student_data.guardian_name.strip():
            raise ValueError("Guardian name cannot be empty.")

        valid_phone = normalize_pakistan_phone(student_data.guardian_phone)
        valid_whatsapp = None
        if student_data.guardian_whatsapp and str(student_data.guardian_whatsapp).strip():
            valid_whatsapp = normalize_pakistan_phone(student_data.guardian_whatsapp)

        with self.conn:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                UPDATE students SET
                    first_name = ?,
                    last_name = ?,
                    urdu_name = ?,
                    gender = ?,
                    date_of_birth = ?,
                    b_form_number = ?,
                    guardian_name = ?,
                    guardian_urdu_name = ?,
                    guardian_relation = ?,
                    guardian_phone = ?,
                    guardian_whatsapp = ?,
                    guardian_cnic = ?,
                    residential_address = ?,
                    emergency_contact = ?,
                    is_active = ?,
                    updated_at = DATETIME('now')
                WHERE id = ?;
                """,
                (
                    student_data.first_name.strip(),
                    student_data.last_name.strip() if student_data.last_name else None,
                    student_data.urdu_name.strip() if student_data.urdu_name else None,
                    student_data.gender,
                    student_data.date_of_birth,
                    student_data.b_form_number,
                    student_data.guardian_name.strip(),
                    student_data.guardian_urdu_name.strip() if student_data.guardian_urdu_name else None,
                    student_data.guardian_relation or "Father",
                    valid_phone,
                    valid_whatsapp,
                    student_data.guardian_cnic,
                    student_data.residential_address,
                    student_data.emergency_contact,
                    1 if student_data.is_active else 0,
                    student_data.id
                )
            )
