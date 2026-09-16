"""
Unit and integration tests for StudentService, Phone Validation,
Admission Number Auto-Generation, and Schema Migrations.
"""

import pytest
import sqlite3
from decimal import Decimal
from models import StudentDTO
from services.schema_service import migrate_to_latest
from services.student_service import (
    StudentService,
    normalize_pakistan_phone,
    generate_next_admission_number,
)


@pytest.fixture
def migrated_db(db_connection):
    """Provides a SQLite connection with all SRS_02 & SRS_03 migrations applied."""
    migrate_to_latest(db_connection)
    return db_connection


@pytest.fixture
def student_service(migrated_db):
    """Provides an initialized StudentService backed by a migrated database."""
    return StudentService(migrated_db)


@pytest.fixture
def test_setup(student_service):
    """Creates a sample academic session and class group for testing."""
    session_id = student_service.create_academic_session(
        name="2025-2026",
        start_date="2025-04-01",
        end_date="2026-03-31"
    )
    class_group_id = student_service.create_class_group(
        session_id=session_id,
        name="Class 9",
        section_or_batch="Section Blue",
        group_type="SchoolClass",
        monthly_tuition_fee=Decimal("4500.00")
    )
    return {"session_id": session_id, "class_group_id": class_group_id}


# --- Schema Migration Tests ---

def test_migration_creates_required_tables_and_indexes(db_connection):
    """Verifies that migration_v1 creates all tables and indexes from SRS_02 and SRS_03."""
    version = migrate_to_latest(db_connection)
    assert version == 1

    cursor = db_connection.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = {row[0] for row in cursor.fetchall()}

    expected_tables = {
        "academic_sessions", "students", "class_groups", "enrollments",
        "fee_heads", "fee_invoices", "fee_invoice_items", "payments"
    }
    assert expected_tables.issubset(tables)

    # Verify baseline fee heads seeded
    cursor.execute("SELECT name FROM fee_heads;")
    fee_heads = {row[0] for row in cursor.fetchall()}
    assert "Tuition Fee" in fee_heads
    assert "Admission Fee" in fee_heads


# --- Pakistani Phone Validation Tests ---

def test_phone_normalization_valid_formats():
    """Tests various valid formats of Pakistani phone numbers."""
    assert normalize_pakistan_phone("03001234567") == "03001234567"
    assert normalize_pakistan_phone("+923001234567") == "03001234567"
    assert normalize_pakistan_phone("923001234567") == "03001234567"
    assert normalize_pakistan_phone("0300-1234567") == "03001234567"
    assert normalize_pakistan_phone("0300 1234567") == "03001234567"
    assert normalize_pakistan_phone("(0345) 9876543") == "03459876543"


@pytest.mark.parametrize("invalid_phone", [
    "",
    "   ",
    "0421234567",       # Landline / wrong prefix
    "030012345",        # Too short
    "0300123456789",    # Too long
    "abcdefghijk",      # Non-numeric
    "12345678901",      # Invalid prefix
])
def test_phone_normalization_invalid_raises_error(invalid_phone):
    """Verifies that invalid phone numbers raise ValueError."""
    with pytest.raises(ValueError):
        normalize_pakistan_phone(invalid_phone)


# --- Admission Number Generation Tests ---

def test_admission_number_auto_increment(migrated_db, test_setup, student_service):
    """Verifies sequence auto-increment for admission numbers (CF-YYYY-0001, 0002)."""
    # 1. First student auto-generates 0001
    s1 = StudentDTO(
        first_name="Ali",
        last_name="Raza",
        gender="Male",
        guardian_name="Tariq Raza",
        guardian_phone="03001112233"
    )
    student_id1, _ = student_service.register_student(
        student_data=s1,
        class_group_id=test_setup["class_group_id"],
        session_id=test_setup["session_id"]
    )
    profile1 = student_service.get_student_by_id(student_id1)
    assert profile1["admission_number"].endswith("-0001")

    # 2. Second student auto-generates 0002
    s2 = StudentDTO(
        first_name="Zainab",
        last_name="Bibi",
        gender="Female",
        guardian_name="Muhammad Tariq",
        guardian_phone="03019998877"
    )
    student_id2, _ = student_service.register_student(
        student_data=s2,
        class_group_id=test_setup["class_group_id"],
        session_id=test_setup["session_id"]
    )
    profile2 = student_service.get_student_by_id(student_id2)
    assert profile2["admission_number"].endswith("-0002")


def test_admission_number_uniqueness_enforced(test_setup, student_service):
    """Verifies that manually passing an existing admission number raises ValueError."""
    s1 = StudentDTO(
        admission_number="CF-2025-MANUAL",
        first_name="Hamza",
        gender="Male",
        guardian_name="Farooq",
        guardian_phone="03001234567"
    )
    student_service.register_student(s1, test_setup["class_group_id"], test_setup["session_id"])

    # Duplicate attempt
    s2 = StudentDTO(
        admission_number="CF-2025-MANUAL",
        first_name="Danyal",
        gender="Male",
        guardian_name="Nadeem",
        guardian_phone="03215554433"
    )
    with pytest.raises(ValueError, match="already registered"):
        student_service.register_student(s2, test_setup["class_group_id"], test_setup["session_id"])


# --- Student Registration & Atomic Enrollment Tests ---

def test_register_student_success_with_urdu_and_discount(test_setup, student_service):
    """Verifies complete student registration with Urdu script and recurring discount."""
    student_dto = StudentDTO(
        first_name="Usman",
        last_name="Ghani",
        urdu_name="عثمان غنی",
        gender="Male",
        guardian_name="Abdul Ghani",
        guardian_urdu_name="عبدالغنی",
        guardian_relation="Father",
        guardian_phone="+92-300-7654321",
        residential_address="Gulberg III, Lahore",
        date_of_birth="2010-05-15"
    )

    student_id, enrollment_id = student_service.register_student(
        student_data=student_dto,
        class_group_id=test_setup["class_group_id"],
        session_id=test_setup["session_id"],
        roll_number="Roll-12",
        custom_discount_amount=Decimal("500.00")
    )

    assert student_id > 0
    assert enrollment_id > 0

    student = student_service.get_student_by_id(student_id)
    assert student["first_name"] == "Usman"
    assert student["last_name"] == "Ghani"
    assert student["full_name"] == "Usman Ghani"
    assert student["urdu_name"] == "عثمان غنی"
    assert student["guardian_phone"] == "03007654321"
    assert student["class_name"] == "Class 9"
    assert student["roll_number"] == "Roll-12"
    assert student["custom_discount_amount"] == "500.00"
    assert student["enrollment_status"] == "Active"


def test_register_student_validation_errors(test_setup, student_service):
    """Tests validation guards on missing mandatory fields or invalid foreign keys."""
    # 1. Missing first name
    with pytest.raises(ValueError, match="first name"):
        student_service.register_student(
            StudentDTO(first_name="", guardian_name="Father", guardian_phone="03001234567"),
            test_setup["class_group_id"],
            test_setup["session_id"]
        )

    # 2. Missing guardian name
    with pytest.raises(ValueError, match="Guardian name"):
        student_service.register_student(
            StudentDTO(first_name="Ahmad", guardian_name="", guardian_phone="03001234567"),
            test_setup["class_group_id"],
            test_setup["session_id"]
        )

    # 3. Invalid foreign key (non-existent class_group)
    with pytest.raises(ValueError, match="Class group"):
        student_service.register_student(
            StudentDTO(first_name="Ahmad", guardian_name="Father", guardian_phone="03001234567"),
            class_group_id=9999,
            session_id=test_setup["session_id"]
        )


# --- Multi-Field Search Tests ---

def test_search_students(test_setup, student_service):
    """Verifies multi-field search across admission number, names, and guardian phone."""
    s1 = StudentDTO(
        first_name="Bilal",
        last_name="Akram",
        urdu_name="بلال اکرم",
        gender="Male",
        guardian_name="Muhammad Akram",
        guardian_phone="03123456789"
    )
    s2 = StudentDTO(
        first_name="Fatima",
        last_name="Noor",
        urdu_name="فاطمہ نور",
        gender="Female",
        guardian_name="Noor Muhammad",
        guardian_phone="03339876543"
    )
    id1, _ = student_service.register_student(s1, test_setup["class_group_id"], test_setup["session_id"], roll_number="R-01")
    id2, _ = student_service.register_student(s2, test_setup["class_group_id"], test_setup["session_id"], roll_number="R-02")

    # Search by first name
    res = student_service.search_students("Bilal")
    assert len(res) == 1
    assert res[0]["student_id"] == id1

    # Search by Urdu name
    res_urdu = student_service.search_students("فاطمہ")
    assert len(res_urdu) == 1
    assert res_urdu[0]["student_id"] == id2

    # Search by phone substring
    res_phone = student_service.search_students("9876543")
    assert len(res_phone) == 1
    assert res_phone[0]["student_id"] == id2

    # Search by roll number
    res_roll = student_service.search_students("R-01")
    assert len(res_roll) == 1
    assert res_roll[0]["student_id"] == id1


# --- Transfer & Withdrawal Tests ---

def test_transfer_or_withdraw_student(test_setup, student_service):
    """Verifies updating enrollment status to Withdrawn or Transferred."""
    s = StudentDTO(
        first_name="Saad",
        gender="Male",
        guardian_name="Rashid",
        guardian_phone="03005556677"
    )
    student_id, enrollment_id = student_service.register_student(
        s, test_setup["class_group_id"], test_setup["session_id"]
    )

    student_service.transfer_or_withdraw_student(enrollment_id, "Withdrawn")
    updated = student_service.get_student_by_id(student_id)
    assert updated["enrollment_status"] == "Withdrawn"

    with pytest.raises(ValueError, match="Invalid status"):
        student_service.transfer_or_withdraw_student(enrollment_id, "NonExistentStatus")


def test_get_by_admission_number_and_update_student(test_setup, student_service):
    """Verifies fetching student by admission number and updating their profile."""
    s = StudentDTO(
        first_name="Hassan",
        last_name="Ali",
        gender="Male",
        guardian_name="Ali Asghar",
        guardian_phone="03001239876",
        residential_address="Model Town, Lahore"
    )
    student_id, _ = student_service.register_student(
        s, test_setup["class_group_id"], test_setup["session_id"]
    )
    student = student_service.get_student_by_id(student_id)
    adm_no = student["admission_number"]

    # Fetch by admission number
    fetched = student_service.get_student_by_admission_number(adm_no)
    assert fetched is not None
    assert fetched["student_id"] == student_id
    assert fetched["first_name"] == "Hassan"

    # Non-existent admission number returns None
    assert student_service.get_student_by_admission_number("NON_EXISTENT_ADM") is None

    # Update profile
    updated_dto = StudentDTO(
        id=student_id,
        admission_number=adm_no,
        first_name="Hassan",
        last_name="Raza",
        urdu_name="حسن رضا",
        gender="Male",
        guardian_name="Ali Asghar",
        guardian_phone="03009998877",
        residential_address="DHA Phase 5, Lahore"
    )
    student_service.update_student(updated_dto)

    refetched = student_service.get_student_by_id(student_id)
    assert refetched["last_name"] == "Raza"
    assert refetched["urdu_name"] == "حسن رضا"
    assert refetched["guardian_phone"] == "03009998877"
    assert refetched["residential_address"] == "DHA Phase 5, Lahore"


# --- Architectural Guardrail Tests ---

def test_guardrail_phone_normalization_0092_prefix():
    """Guardrail 3: Verifies stripping leading 0092 international prefix."""
    assert normalize_pakistan_phone("00923001234567") == "03001234567"
    assert normalize_pakistan_phone("0092-300-1234567") == "03001234567"


def test_guardrail_auto_admission_uses_active_session_year(migrated_db, student_service):
    """Guardrail 2: Verifies formatting sequential admission numbers using active session name (e.g. CF-2027-0001)."""
    sess_id = student_service.create_academic_session(
        name="2027-2028",
        start_date="2027-04-01",
        end_date="2028-03-31"
    )
    grp_id = student_service.create_class_group(
        session_id=sess_id,
        name="Class 10",
        section_or_batch="Section Gold",
        group_type="SchoolClass"
    )
    s = StudentDTO(
        first_name="Qasim",
        gender="Male",
        guardian_name="Tahir",
        guardian_phone="03004443322"
    )
    st_id, _ = student_service.register_student(s, grp_id, sess_id)
    profile = student_service.get_student_by_id(st_id)
    assert profile["admission_number"] == "CF-2027-0001"


def test_guardrail_atomic_composite_transaction_rollback(test_setup, student_service, migrated_db):
    """
    Guardrail 1: Verifies that if enrollment fails inside register_student(),
    the inserted student record is completely rolled back from the database.
    """
    cursor = migrated_db.cursor()
    cursor.execute("SELECT COUNT(*) FROM students;")
    initial_count = cursor.fetchone()[0]

    # Create a temporary trigger to abort on specific roll number
    cursor.execute("""
    CREATE TRIGGER test_rollback_enrollment_failure
    BEFORE INSERT ON enrollments
    WHEN NEW.roll_number = 'FORCE_FAIL_ENROLLMENT'
    BEGIN
        SELECT RAISE(ABORT, 'Simulated enrollment constraint failure');
    END;
    """)

    s = StudentDTO(
        first_name="RollbackCandidate",
        gender="Male",
        guardian_name="FatherName",
        guardian_phone="03001239999"
    )

    with pytest.raises(sqlite3.DatabaseError, match="Simulated enrollment constraint failure"):
        student_service.register_student(
            s,
            test_setup["class_group_id"],
            test_setup["session_id"],
            roll_number="FORCE_FAIL_ENROLLMENT"
        )

    # Verify rollback: student record was NOT persisted in students table
    cursor.execute("SELECT COUNT(*) FROM students;")
    current_count = cursor.fetchone()[0]
    assert current_count == initial_count

    cursor.execute("SELECT id FROM students WHERE first_name = 'RollbackCandidate';")
    assert cursor.fetchone() is None

    # Cleanup trigger
    cursor.execute("DROP TRIGGER IF EXISTS test_rollback_enrollment_failure;")



def test_guardrail_case_insensitive_search_with_whitespace(test_setup, student_service):
    """
    Guardrail 4: Verifies case-insensitive search with leading/trailing whitespace normalization.
    """
    s = StudentDTO(
        first_name="Zubair",
        last_name="Khan",
        gender="Male",
        guardian_name="Sultan Khan",
        guardian_phone="03217778899"
    )
    student_service.register_student(s, test_setup["class_group_id"], test_setup["session_id"])

    # Search with whitespace and mixed cases
    res1 = student_service.search_students("   zubair   ")
    assert len(res1) == 1
    assert res1[0]["first_name"] == "Zubair"

    res2 = student_service.search_students("ZUBAIR")
    assert len(res2) == 1
    assert res2[0]["first_name"] == "Zubair"

    res3 = student_service.search_students("khan")
    assert len(res3) >= 1
    assert any(r["last_name"] == "Khan" for r in res3)


