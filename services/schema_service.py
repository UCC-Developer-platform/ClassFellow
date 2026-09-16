"""
ClassFellow - Database Schema Migration Service
================================================
Tracks and executes offline schema migrations using SQLite's PRAGMA user_version.
Implements Migration v1 establishing tables for SRS_02 (Students & Enrollments)
and SRS_03 (Fee Structures, Invoices, Items, and Payment Ledgers).
"""

import sqlite3
from typing import Callable
from database import get_schema_version, set_schema_version

SCHEMA_VERSION_CURRENT = 3


def migration_v1_initial_schema(conn: sqlite3.Connection) -> None:
    """
    Executes Migration v1: Establishes initial relational schema for SRS_02 and SRS_03.
    """
    with conn:
        # 1. Academic Sessions
        conn.execute("""
        CREATE TABLE IF NOT EXISTS academic_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
        );
        """)

        # 2. Students Identity & Guardian Metadata
        conn.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admission_number TEXT NOT NULL UNIQUE,
            first_name TEXT NOT NULL,
            last_name TEXT,
            urdu_name TEXT,
            gender TEXT NOT NULL CHECK (gender IN ('Male', 'Female', 'Other')),
            date_of_birth TEXT,
            b_form_number TEXT,
            guardian_name TEXT NOT NULL,
            guardian_urdu_name TEXT,
            guardian_relation TEXT NOT NULL DEFAULT 'Father',
            guardian_phone TEXT NOT NULL,
            guardian_whatsapp TEXT,
            guardian_cnic TEXT,
            residential_address TEXT,
            emergency_contact TEXT,
            is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
            created_at TEXT NOT NULL DEFAULT (DATETIME('now')),
            updated_at TEXT NOT NULL DEFAULT (DATETIME('now'))
        );
        """)

        # 3. Class Groups & Subject Batches
        conn.execute("""
        CREATE TABLE IF NOT EXISTS class_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            section_or_batch TEXT NOT NULL,
            group_type TEXT NOT NULL CHECK (group_type IN ('SchoolClass', 'AcademyBatch')),
            monthly_tuition_fee TEXT NOT NULL DEFAULT '0.00',
            created_at TEXT NOT NULL DEFAULT (DATETIME('now')),
            FOREIGN KEY (session_id) REFERENCES academic_sessions(id) ON DELETE RESTRICT,
            UNIQUE(session_id, name, section_or_batch)
        );
        """)

        # 4. Academic Enrollments
        conn.execute("""
        CREATE TABLE IF NOT EXISTS enrollments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            class_group_id INTEGER NOT NULL,
            session_id INTEGER NOT NULL,
            roll_number TEXT,
            enrollment_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active', 'Transferred', 'Withdrawn', 'Graduated')),
            custom_discount_amount TEXT NOT NULL DEFAULT '0.00',
            created_at TEXT NOT NULL DEFAULT (DATETIME('now')),
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE RESTRICT,
            FOREIGN KEY (class_group_id) REFERENCES class_groups(id) ON DELETE RESTRICT,
            FOREIGN KEY (session_id) REFERENCES academic_sessions(id) ON DELETE RESTRICT,
            UNIQUE(student_id, class_group_id, session_id)
        );
        """)

        # 5. Fee Heads (Categories)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS fee_heads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            urdu_name TEXT,
            is_recurring INTEGER NOT NULL DEFAULT 1 CHECK (is_recurring IN (0, 1)),
            created_at TEXT NOT NULL DEFAULT (DATETIME('now'))
        );
        """)

        # 6. Fee Invoices
        conn.execute("""
        CREATE TABLE IF NOT EXISTS fee_invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            enrollment_id INTEGER NOT NULL,
            session_id INTEGER NOT NULL,
            month_year TEXT NOT NULL,
            issue_date TEXT NOT NULL,
            due_date TEXT NOT NULL,
            valid_until TEXT NOT NULL,
            late_fee_surcharge TEXT NOT NULL DEFAULT '0.00',
            total_payable TEXT NOT NULL DEFAULT '0.00',
            discount_amount TEXT NOT NULL DEFAULT '0.00',
            net_due TEXT NOT NULL DEFAULT '0.00',
            created_at TEXT NOT NULL DEFAULT (DATETIME('now')),
            FOREIGN KEY (enrollment_id) REFERENCES enrollments(id) ON DELETE RESTRICT,
            FOREIGN KEY (session_id) REFERENCES academic_sessions(id) ON DELETE RESTRICT,
            UNIQUE(enrollment_id, month_year)
        );
        """)

        # 7. Fee Invoice Items (Breakdown)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS fee_invoice_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            fee_head_id INTEGER NOT NULL,
            amount TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (DATETIME('now')),
            FOREIGN KEY (invoice_id) REFERENCES fee_invoices(id) ON DELETE CASCADE,
            FOREIGN KEY (fee_head_id) REFERENCES fee_heads(id) ON DELETE RESTRICT
        );
        """)

        # 8. Payments Ledger (Audit Trail)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            amount TEXT NOT NULL,
            payment_date TEXT NOT NULL,
            receipt_number TEXT NOT NULL UNIQUE,
            payment_method TEXT NOT NULL DEFAULT 'Cash' CHECK (payment_method IN ('Cash', 'BankTransfer', 'OnlineDeposit', 'Cheque')),
            status TEXT NOT NULL DEFAULT 'Issued' CHECK (status IN ('Issued', 'Reversed', 'Cancelled')),
            reversal_reason TEXT,
            recorded_by_user_id INTEGER,
            note TEXT,
            created_at TEXT NOT NULL DEFAULT (DATETIME('now')),
            FOREIGN KEY (invoice_id) REFERENCES fee_invoices(id) ON DELETE RESTRICT
        );
        """)

        # --- Indexes for High-Speed Querying ---
        conn.execute("CREATE INDEX IF NOT EXISTS idx_students_admission_no ON students(admission_number);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_students_names ON students(first_name, last_name);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_students_guardian_phone ON students(guardian_phone);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_enrollments_student ON enrollments(student_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_enrollments_class_session ON enrollments(class_group_id, session_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_fee_invoices_enrollment ON fee_invoices(enrollment_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_fee_invoices_cycle ON fee_invoices(month_year, session_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_fee_invoice_items_invoice ON fee_invoice_items(invoice_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_payments_invoice ON payments(invoice_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_payments_receipt_no ON payments(receipt_number);")

        # Seed baseline Fee Heads if empty
        conn.execute("""
        INSERT OR IGNORE INTO fee_heads (name, urdu_name, is_recurring)
        VALUES 
            ('Tuition Fee', 'ٹیوشن فیس', 1),
            ('Admission Fee', 'داخلہ فیس', 0),
            ('Examination Fee', 'امتحانی فیس', 0),
            ('Computer Lab Fee', 'کمپیوٹر لیب فیس', 1),
            ('Generator / Utility Charges', 'جنریٹر و یوٹیلٹی چارجز', 1);
        """)

    set_schema_version(conn, 1)


def migration_v2_attendance_schema(conn: sqlite3.Connection) -> None:
    """
    Executes Migration v2: Establishes batch_sessions and attendance_records
    with UNIQUE(enrollment_id, attendance_date) constraint as specified in CF-SRS-04.
    """
    with conn:
        # 1. Academy Lecture Sessions (Optional for Subject/Batch model)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS batch_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_group_id INTEGER NOT NULL,
            session_date TEXT NOT NULL,
            start_time TEXT,
            end_time TEXT,
            topic_covered TEXT,
            created_at TEXT NOT NULL DEFAULT (DATETIME('now')),
            FOREIGN KEY (class_group_id) REFERENCES class_groups(id) ON DELETE RESTRICT
        );
        """)

        # 2. Core Attendance Records
        conn.execute("""
        CREATE TABLE IF NOT EXISTS attendance_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            enrollment_id INTEGER NOT NULL,
            attendance_date TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('Present', 'Absent', 'Late', 'Leave')),
            batch_session_id INTEGER,
            reason_note TEXT,
            recorded_by_user_id INTEGER,
            created_at TEXT NOT NULL DEFAULT (DATETIME('now')),
            updated_at TEXT NOT NULL DEFAULT (DATETIME('now')),
            FOREIGN KEY (enrollment_id) REFERENCES enrollments(id) ON DELETE RESTRICT,
            FOREIGN KEY (batch_session_id) REFERENCES batch_sessions(id) ON DELETE SET NULL,
            UNIQUE(enrollment_id, attendance_date)
        );
        """)

        # 3. High-Performance Lookup Indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_attendance_enrollment_date ON attendance_records(enrollment_id, attendance_date);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_attendance_date_status ON attendance_records(attendance_date, status);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_attendance_batch ON attendance_records(batch_session_id);")

    set_schema_version(conn, 2)


def migration_v3_exam_schema(conn: sqlite3.Connection) -> None:
    """
    Executes Migration v3: Establishes subjects, exams, exam_subjects,
    grading_tiers, and marks tables as specified in CF-SRS-05.
    """
    with conn:
        # 1. Master Subject Definitions
        conn.execute("""
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            urdu_name TEXT,
            code TEXT UNIQUE,
            created_at TEXT NOT NULL DEFAULT (DATETIME('now'))
        );
        """)

        # 2. Master Examination Cycles
        conn.execute("""
        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            exam_type TEXT NOT NULL CHECK (exam_type IN ('MonthlyTest', 'TermExam', 'AnnualExam', 'MockTest')),
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            is_published INTEGER NOT NULL DEFAULT 0 CHECK (is_published IN (0, 1)),
            created_at TEXT NOT NULL DEFAULT (DATETIME('now')),
            FOREIGN KEY (session_id) REFERENCES academic_sessions(id) ON DELETE RESTRICT
        );
        """)

        # 3. Dynamic Class-Specific Subject Examination Configuration
        conn.execute("""
        CREATE TABLE IF NOT EXISTS exam_subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER NOT NULL,
            class_group_id INTEGER NOT NULL,
            subject_id INTEGER NOT NULL,
            maximum_marks TEXT NOT NULL,
            passing_marks TEXT NOT NULL,
            weightage_percent TEXT NOT NULL DEFAULT '100.00',
            exam_date TEXT,
            created_at TEXT NOT NULL DEFAULT (DATETIME('now')),
            FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE,
            FOREIGN KEY (class_group_id) REFERENCES class_groups(id) ON DELETE RESTRICT,
            FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE RESTRICT,
            UNIQUE(exam_id, class_group_id, subject_id)
        );
        """)

        # 4. Configurable Grading Scales
        conn.execute("""
        CREATE TABLE IF NOT EXISTS grading_tiers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            grade_name TEXT NOT NULL,
            min_percentage TEXT NOT NULL,
            max_percentage TEXT NOT NULL,
            gpa_point TEXT NOT NULL DEFAULT '0.0',
            remarks_en TEXT,
            remarks_ur TEXT,
            is_passing INTEGER NOT NULL DEFAULT 1 CHECK (is_passing IN (0, 1)),
            FOREIGN KEY (session_id) REFERENCES academic_sessions(id) ON DELETE CASCADE,
            UNIQUE(session_id, grade_name)
        );
        """)

        # 5. Individual Student Marks Entry Ledger
        conn.execute("""
        CREATE TABLE IF NOT EXISTS marks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_subject_id INTEGER NOT NULL,
            enrollment_id INTEGER NOT NULL,
            marks_obtained TEXT NOT NULL,
            is_absent INTEGER NOT NULL DEFAULT 0 CHECK (is_absent IN (0, 1)),
            teacher_remarks TEXT,
            recorded_by_user_id INTEGER,
            created_at TEXT NOT NULL DEFAULT (DATETIME('now')),
            updated_at TEXT NOT NULL DEFAULT (DATETIME('now')),
            FOREIGN KEY (exam_subject_id) REFERENCES exam_subjects(id) ON DELETE CASCADE,
            FOREIGN KEY (enrollment_id) REFERENCES enrollments(id) ON DELETE RESTRICT,
            UNIQUE(exam_subject_id, enrollment_id)
        );
        """)

        # 6. Performance Indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_exam_subjects_lookup ON exam_subjects(exam_id, class_group_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_marks_enrollment ON marks(enrollment_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_marks_exam_subject ON marks(exam_subject_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_grading_tiers_session ON grading_tiers(session_id);")

        # Seed baseline subjects
        conn.execute("""
        INSERT OR IGNORE INTO subjects (name, urdu_name, code)
        VALUES
            ('Mathematics', 'ریاضی', 'MATH'),
            ('English', 'انگریزی', 'ENG'),
            ('Urdu', 'اردو', 'URDU'),
            ('Science', 'جنرل سائنس', 'SCI'),
            ('Islamiat', 'اسلامیات', 'ISL'),
            ('Pakistan Studies', 'مطالعہ پاکستان', 'PST');
        """)

    set_schema_version(conn, 3)


MIGRATIONS: dict[int, Callable[[sqlite3.Connection], None]] = {
    1: migration_v1_initial_schema,
    2: migration_v2_attendance_schema,
    3: migration_v3_exam_schema,
}


def migrate_to_latest(conn: sqlite3.Connection) -> int:
    """
    Inspects PRAGMA user_version and sequentially applies all pending migrations.

    Returns:
        The current updated schema version number.
    """
    current_version = get_schema_version(conn)
    for ver in range(current_version + 1, SCHEMA_VERSION_CURRENT + 1):
        if ver in MIGRATIONS:
            MIGRATIONS[ver](conn)
    return get_schema_version(conn)


