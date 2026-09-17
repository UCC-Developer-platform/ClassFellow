"""
Unit and integration tests for AttendanceService, Migration v2,
Atomic UPSERT, Uniqueness Constraints, Analytics, and WhatsApp Payloads.
"""

import pytest
import sqlite3
from decimal import Decimal
from models import StudentDTO
from services.schema_service import migrate_to_latest
from services.student_service import StudentService
from services.attendance_service import AttendanceService


@pytest.fixture
def migrated_db(db_connection):
    """Provides a SQLite connection with all migrations (v1 and v2) applied."""
    migrate_to_latest(db_connection)
    return db_connection


@pytest.fixture
def student_service(migrated_db):
    return StudentService(migrated_db)


@pytest.fixture
def attendance_service(migrated_db):
    return AttendanceService(migrated_db)


@pytest.fixture
def test_setup(student_service):
    """Sets up an academic session, class group, and three enrolled students."""
    session_id = student_service.create_academic_session(
        name="2025-2026",
        start_date="2025-04-01",
        end_date="2026-03-31"
    )
    class_group_id = student_service.create_class_group(
        session_id=session_id,
        name="Class 10",
        section_or_batch="Section Alpha",
        group_type="SchoolClass",
        monthly_tuition_fee=Decimal("6000.00")
    )

    s1 = StudentDTO(
        first_name="Haris",
        last_name="Rauf",
        urdu_name="حارث رؤف",
        gender="Male",
        guardian_name="Rauf Ahmed",
        guardian_phone="03001112233"
    )
    st_id1, enr_id1 = student_service.register_student(s1, class_group_id, session_id, roll_number="1")

    s2 = StudentDTO(
        first_name="Babar",
        last_name="Azam",
        urdu_name="بابر اعظم",
        gender="Male",
        guardian_name="Azam Siddique",
        guardian_phone="03215556677"
    )
    st_id2, enr_id2 = student_service.register_student(s2, class_group_id, session_id, roll_number="2")

    s3 = StudentDTO(
        first_name="Shaheen",
        last_name="Afridi",
        urdu_name="شاہین آفریدی",
        gender="Male",
        guardian_name="Ayaz Afridi",
        guardian_phone="03339998877"
    )
    st_id3, enr_id3 = student_service.register_student(s3, class_group_id, session_id, roll_number="3")

    return {
        "session_id": session_id,
        "class_group_id": class_group_id,
        "students": [
            {"student_id": st_id1, "enrollment_id": enr_id1, "name": "Haris Rauf"},
            {"student_id": st_id2, "enrollment_id": enr_id2, "name": "Babar Azam"},
            {"student_id": st_id3, "enrollment_id": enr_id3, "name": "Shaheen Afridi"},
        ]
    }


# --- Migration v2 Schema Verification ---

def test_migration_v2_creates_attendance_and_batch_tables(db_connection):
    """Verifies that migration v2 creates batch_sessions and attendance_records."""
    version = migrate_to_latest(db_connection)
    assert version >= 2


    cursor = db_connection.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = {row[0] for row in cursor.fetchall()}

    assert "batch_sessions" in tables
    assert "attendance_records" in tables

    # Verify uniqueness index/constraint
    cursor.execute("PRAGMA index_list('attendance_records');")
    indexes = cursor.fetchall()
    has_unique = any(idx["unique"] == 1 for idx in indexes)
    assert has_unique


# --- Roster Loading with Default 'Present' Tests ---

def test_load_class_roster_defaults_to_present(test_setup, attendance_service):
    """
    Verifies that loading an unrecorded class roster sets status='Present'
    by default for all enrolled students.
    """
    class_group_id = test_setup["class_group_id"]
    roster = attendance_service.load_class_roster_for_attendance(class_group_id, "2025-10-15")

    assert len(roster) == 3
    for entry in roster:
        assert entry["status"] == "Present"
        assert entry["is_previously_logged"] is False
        assert entry["attendance_record_id"] is None


# --- Bulk Attendance Save & Atomic UPSERT Tests ---

def test_save_bulk_attendance_and_upsert_on_conflict(test_setup, attendance_service, migrated_db):
    """
    Verifies saving bulk attendance and modifying statuses using atomic UPSERT
    without creating duplicate records.
    """
    class_group_id = test_setup["class_group_id"]
    date = "2025-10-16"
    st = test_setup["students"]

    # Initial submission: Haris=Present, Babar=Absent, Shaheen=Late
    entries = [
        {"enrollment_id": st[0]["enrollment_id"], "status": "Present"},
        {"enrollment_id": st[1]["enrollment_id"], "status": "Absent", "reason_note": "Fever"},
        {"enrollment_id": st[2]["enrollment_id"], "status": "Late", "reason_note": "Traffic delay"},
    ]
    saved = attendance_service.save_bulk_attendance(date, entries, user_id=1)
    assert saved == 3

    # Verify database count
    cursor = migrated_db.cursor()
    cursor.execute("SELECT COUNT(*) FROM attendance_records WHERE attendance_date = ?;", (date,))
    assert cursor.fetchone()[0] == 3

    # Verify loaded roster reflects the recorded statuses
    roster = attendance_service.load_class_roster_for_attendance(class_group_id, date)
    status_map = {r["enrollment_id"]: r["status"] for r in roster}
    assert status_map[st[0]["enrollment_id"]] == "Present"
    assert status_map[st[1]["enrollment_id"]] == "Absent"
    assert status_map[st[2]["enrollment_id"]] == "Late"

    # Modification / Correction: Babar's parent submitted leave -> update to 'Leave'
    updated_entries = [
        {"enrollment_id": st[1]["enrollment_id"], "status": "Leave", "reason_note": "Approved medical leave"}
    ]
    attendance_service.save_bulk_attendance(date, updated_entries, user_id=1)

    # Database count must still be 3 (zero duplicates)
    cursor.execute("SELECT COUNT(*) FROM attendance_records WHERE attendance_date = ?;", (date,))
    assert cursor.fetchone()[0] == 3

    # Status must be updated to Leave
    cursor.execute(
        "SELECT status, reason_note FROM attendance_records WHERE enrollment_id = ? AND attendance_date = ?;",
        (st[1]["enrollment_id"], date)
    )
    row = cursor.fetchone()
    assert row["status"] == "Leave"
    assert row["reason_note"] == "Approved medical leave"


def test_unique_constraint_enforced_at_db_level(test_setup, attendance_service, migrated_db):
    """
    Verifies that raw duplicate insert for the same enrollment and date
    raises sqlite3.IntegrityError due to UNIQUE(enrollment_id, attendance_date).
    """
    enr_id = test_setup["students"][0]["enrollment_id"]
    date = "2025-10-17"

    cursor = migrated_db.cursor()
    cursor.execute(
        "INSERT INTO attendance_records (enrollment_id, attendance_date, status) VALUES (?, ?, 'Present');",
        (enr_id, date)
    )

    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute(
            "INSERT INTO attendance_records (enrollment_id, attendance_date, status) VALUES (?, ?, 'Absent');",
            (enr_id, date)
        )


# --- Attendance Metrics & Percentage Calculation Tests ---

def test_attendance_summary_percentage_calculation(test_setup, attendance_service):
    """
    Verifies metric aggregation:
      Total: 10 days
      Present: 7
      Leave: 1
      Late: 2
      Absent: 0
      Formula: ((7 + 1 + 0.5 * 2) / 10) * 100 = 90.0%
    """
    enr_id = test_setup["students"][0]["enrollment_id"]

    # Log 10 dates
    for day in range(1, 8):  # Days 1 to 7: Present
        attendance_service.save_bulk_attendance(f"2025-11-{day:02d}", [{"enrollment_id": enr_id, "status": "Present"}])

    attendance_service.save_bulk_attendance("2025-11-08", [{"enrollment_id": enr_id, "status": "Leave"}])
    attendance_service.save_bulk_attendance("2025-11-09", [{"enrollment_id": enr_id, "status": "Late"}])
    attendance_service.save_bulk_attendance("2025-11-10", [{"enrollment_id": enr_id, "status": "Late"}])

    summary = attendance_service.get_monthly_attendance_summary(enr_id, "2025-11-01", "2025-11-30")
    assert summary.total_days == 10
    assert summary.present_days == 7
    assert summary.leave_days == 1
    assert summary.late_days == 2
    assert summary.absent_days == 0
    assert summary.percentage == 90.0


def test_attendance_summary_zero_days_returns_zero_percent(test_setup, attendance_service):
    """Verifies that an empty range safely returns 0.0% without division by zero."""
    enr_id = test_setup["students"][0]["enrollment_id"]
    summary = attendance_service.get_monthly_attendance_summary(enr_id, "2024-01-01", "2024-01-31")
    assert summary.total_days == 0
    assert summary.percentage == 0.0


# --- Zero-Cost WhatsApp Absence Payload Tests ---

def test_generate_absence_whatsapp_payload(test_setup, attendance_service):
    """
    Verifies copy-ready bilingual message text and wa.me deep-link formatting
    with international dial code conversion.
    """
    babar_enr_id = test_setup["students"][1]["enrollment_id"]
    payload = attendance_service.generate_absence_whatsapp_payload(
        enrollment_id=babar_enr_id,
        date="2025-10-18",
        institution_name="CLASSFELLOW GRAMMAR SCHOOL",
        institution_phone="042-35889900"
    )

    assert payload["student_name"] == "Babar Azam"
    assert payload["guardian_phone"] == "03215556677"

    msg = payload["message_text"]
    assert "محترم والدین" in msg
    assert "Babar Azam" in msg
    assert "2025-10-18" in msg
    assert "CLASSFELLOW GRAMMAR SCHOOL" in msg
    assert "042-35889900" in msg

    # Verify wa.me URL formats to 923215556677
    url = payload["whatsapp_url"]
    assert url.startswith("https://wa.me/923215556677?text=")


# --- Academy Model Batch Session Tests ---

def test_academy_batch_session_creation(test_setup, attendance_service):
    """Verifies creating an academy lecture slot in batch_sessions."""
    grp_id = test_setup["class_group_id"]
    sess_id = attendance_service.create_batch_session(
        class_group_id=grp_id,
        session_date="2025-10-19",
        start_time="16:00",
        end_time="17:00",
        topic_covered="Newton's Laws of Motion"
    )
    assert sess_id > 0
