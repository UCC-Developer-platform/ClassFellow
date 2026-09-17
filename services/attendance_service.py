"""
ClassFellow - Attendance & Notification Domain Service
======================================================
Governs daily class-roster attendance entry with default 'Present' status,
atomic UPSERT on attendance dates, uniqueness constraint enforcement,
monthly percentage metrics, and zero-cost WhatsApp absence notifications
as specified in CF-SRS-04.
"""

import re
import urllib.parse
import sqlite3
from typing import Optional, Any
from database import transaction
from models import AttendanceEntryDTO, AttendanceSummaryDTO, BatchSessionDTO


class AttendanceService:
    """Encapsulates daily attendance logging, metric calculations, and parent notifications."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # --- Academy Batch Sessions ---

    def create_batch_session(
        self,
        class_group_id: int,
        session_date: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        topic_covered: Optional[str] = None
    ) -> int:
        """Creates a lecture batch session (Academy Model)."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM class_groups WHERE id = ?;", (class_group_id,))
        if not cursor.fetchone():
            raise ValueError(f"Class group id={class_group_id} does not exist.")

        with transaction(self.conn):
            cursor.execute(
                """
                INSERT INTO batch_sessions (class_group_id, session_date, start_time, end_time, topic_covered)
                VALUES (?, ?, ?, ?, ?);
                """,
                (class_group_id, session_date.strip(), start_time, end_time, topic_covered)
            )
            return cursor.lastrowid

    # --- Attendance Roster Loading ---

    def load_class_roster_for_attendance(
        self,
        class_group_id: int,
        date: str
    ) -> list[dict[str, Any]]:
        """
        Loads the active student roster for a class group on a specific date.
        If attendance has already been recorded, existing statuses ('Absent', 'Late', 'Leave')
        are populated; otherwise, all students default to 'Present'.

        Args:
            class_group_id: Target class group / section.
            date: Attendance date in ISO format (YYYY-MM-DD).

        Returns:
            List of student roster dictionaries ready for high-speed exception marking.
        """
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
            raise ValueError(f"Invalid date format '{date}'. Must be 'YYYY-MM-DD'.")

        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT 
                e.id AS enrollment_id,
                e.student_id,
                e.roll_number,
                s.admission_number,
                s.first_name,
                s.last_name,
                TRIM(s.first_name || ' ' || COALESCE(s.last_name, '')) AS student_name,
                s.urdu_name AS student_urdu_name,
                s.guardian_name,
                s.guardian_phone,
                ar.id AS attendance_record_id,
                ar.status,
                ar.reason_note,
                ar.batch_session_id
            FROM enrollments e
            JOIN students s ON e.student_id = s.id
            LEFT JOIN attendance_records ar 
                ON e.id = ar.enrollment_id AND ar.attendance_date = ?
            WHERE e.class_group_id = ? AND e.status = 'Active' AND s.is_active = 1
            ORDER BY 
                CASE WHEN e.roll_number GLOB '[0-9]*' THEN CAST(e.roll_number AS INTEGER) ELSE 9999 END ASC,
                s.admission_number ASC;
            """,
            (date, class_group_id)
        )
        rows = cursor.fetchall()

        roster = []
        for r in rows:
            entry = {k: r[k] for k in r.keys()}
            # Default to 'Present' if not yet recorded
            if entry["status"] is None:
                entry["status"] = "Present"
                entry["is_previously_logged"] = False
            else:
                entry["is_previously_logged"] = True

            roster.append(entry)

        return roster

    # --- Bulk Attendance Entry with Atomic UPSERT ---

    def save_bulk_attendance(
        self,
        date: str,
        entries: list[dict[str, Any]],
        user_id: Optional[int] = None,
        batch_session_id: Optional[int] = None
    ) -> int:
        """
        Atomically saves attendance entries using SQLite UPSERT syntax.
        Enforces UNIQUE(enrollment_id, attendance_date) without duplicates.

        Args:
            date: Attendance date in ISO format (YYYY-MM-DD).
            entries: List of dictionaries or DTOs with 'enrollment_id', 'status', and optional 'reason_note'.
            user_id: Admin / teacher user ID.
            batch_session_id: Optional foreign key to batch_sessions.

        Returns:
            Count of successfully saved/updated attendance records.
        """
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
            raise ValueError(f"Invalid date format '{date}'. Must be 'YYYY-MM-DD'.")

        if not entries:
            return 0

        valid_statuses = ("Present", "Absent", "Late", "Leave")
        for idx, entry in enumerate(entries):
            st = entry.get("status", "Present")
            if st not in valid_statuses:
                raise ValueError(f"Invalid attendance status '{st}' at entry index {idx}. Allowed: {valid_statuses}")

        upsert_sql = """
        INSERT INTO attendance_records (
            enrollment_id, attendance_date, status, batch_session_id,
            reason_note, recorded_by_user_id, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, DATETIME('now'), DATETIME('now'))
        ON CONFLICT(enrollment_id, attendance_date) DO UPDATE SET
            status = excluded.status,
            batch_session_id = excluded.batch_session_id,
            reason_note = excluded.reason_note,
            recorded_by_user_id = excluded.recorded_by_user_id,
            updated_at = DATETIME('now');
        """

        saved_count = 0
        with transaction(self.conn):
            cursor = self.conn.cursor()
            for entry in entries:
                enr_id = entry.get("enrollment_id")
                status = entry.get("status", "Present")
                reason = entry.get("reason_note")
                b_sess_id = entry.get("batch_session_id", batch_session_id)

                cursor.execute(
                    upsert_sql,
                    (enr_id, date, status, b_sess_id, reason, user_id)
                )
                saved_count += 1

        return saved_count

    # --- Analytics & Metric Calculation ---

    def get_monthly_attendance_summary(
        self,
        enrollment_id: int,
        start_date: str,
        end_date: str
    ) -> AttendanceSummaryDTO:
        """
        Calculates attendance statistics and percentage for an enrolled student
        across a specified date range.

        Formula (CF-SRS-04 Section 3):
            Percentage = ((Present + Leave + 0.5 * Late) / Total_Working_Days) * 100
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT 
                COUNT(*) AS total_days,
                COALESCE(SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END), 0) AS present_days,
                COALESCE(SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END), 0) AS absent_days,
                COALESCE(SUM(CASE WHEN status = 'Leave' THEN 1 ELSE 0 END), 0) AS leave_days,
                COALESCE(SUM(CASE WHEN status = 'Late' THEN 1 ELSE 0 END), 0) AS late_days
            FROM attendance_records
            WHERE enrollment_id = ? AND attendance_date BETWEEN ? AND ?;
            """,
            (enrollment_id, start_date, end_date)
        )
        row = cursor.fetchone()

        total = row["total_days"] if row else 0
        present = row["present_days"] if row else 0
        absent = row["absent_days"] if row else 0
        leave = row["leave_days"] if row else 0
        late = row["late_days"] if row else 0

        if total > 0:
            numerator = present + leave + (0.5 * late)
            percentage = round((numerator / total) * 100.0, 2)
        else:
            percentage = 0.0

        return AttendanceSummaryDTO(
            enrollment_id=enrollment_id,
            total_days=total,
            present_days=present,
            absent_days=absent,
            leave_days=leave,
            late_days=late,
            percentage=percentage
        )

    # --- Zero-Cost Parent Absence Notification (WhatsApp & SMS) ---

    def generate_absence_whatsapp_payload(
        self,
        enrollment_id: int,
        date: str,
        institution_name: str = "ClassFellow High School & Academy",
        institution_phone: str = "0300-1234567"
    ) -> dict[str, str]:
        """
        Generates copy-ready standardized bilingual WhatsApp messages and deep-links
        without requiring external paid API gateways.

        Args:
            enrollment_id: Target enrollment ID.
            date: Date of absence (YYYY-MM-DD).
            institution_name: Official school title.
            institution_phone: Office contact number.

        Returns:
            Dictionary containing guardian phone, formatted message text, and wa.me URL.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT 
                s.first_name,
                s.last_name,
                TRIM(s.first_name || ' ' || COALESCE(s.last_name, '')) AS student_name,
                s.urdu_name,
                s.guardian_name,
                s.guardian_phone,
                e.roll_number
            FROM enrollments e
            JOIN students s ON e.student_id = s.id
            WHERE e.id = ?;
            """,
            (enrollment_id,)
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Enrollment id={enrollment_id} does not exist.")

        student_name = row["student_name"]
        roll_no = row["roll_number"] or "N/A"
        guardian_phone = row["guardian_phone"]

        # Localized Bilingual Absence Template (CF-SRS-04 Section 4.1)
        urdu_msg = (
            f"محترم والدین،\n"
            f"اطلاع دی جاتی ہے کہ آپ کا بچہ {student_name} (رول نمبر: {roll_no}) آج مورخہ {date} کو {institution_name} سے غیر حاضر ہے۔\n"
            f"اگر چھٹی کی کوئی خاص وجہ ہے تو براہ کرم اسکول آفس {institution_phone} پر رابطہ کریں۔\n"
            f"شکریہ،\n"
            f"انتظامیہ {institution_name}"
        )

        eng_msg = (
            f"Dear Parent,\n"
            f"This is to inform you that your child {student_name} (Roll No: {roll_no}) is ABSENT today ({date}) from {institution_name}.\n"
            f"Please contact the school office at {institution_phone} if you have not submitted a leave application.\n"
            f"Regards,\n"
            f"{institution_name} Administration"
        )

        full_message = f"{urdu_msg}\n\n--------------------------------------------------\n{eng_msg}"

        # Clean phone number for WhatsApp wa.me format (923XXXXXXXXX)
        clean_phone = re.sub(r"\D", "", guardian_phone)
        if clean_phone.startswith("03"):
            clean_phone = "92" + clean_phone[1:]
        elif clean_phone.startswith("0092"):
            clean_phone = clean_phone[2:]
        elif not clean_phone.startswith("92"):
            clean_phone = "92" + clean_phone

        encoded_text = urllib.parse.quote(full_message)
        whatsapp_url = f"https://wa.me/{clean_phone}?text={encoded_text}"

        return {
            "enrollment_id": str(enrollment_id),
            "student_name": student_name,
            "guardian_phone": guardian_phone,
            "message_text": full_message,
            "whatsapp_url": whatsapp_url
        }
