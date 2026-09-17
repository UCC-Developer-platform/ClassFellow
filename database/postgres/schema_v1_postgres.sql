-- =============================================================================
-- ClassFellow - Production PostgreSQL 16 Schema Specification (Migration v1)
-- File: database/postgres/schema_v1_postgres.sql
-- =============================================================================
-- Translates the SQLite desktop schema into enterprise PostgreSQL 16 DDL:
--   1. Primary Keys: BIGINT GENERATED ALWAYS AS IDENTITY
--   2. Monetary Fields: NUMERIC(12, 2) NOT NULL
--   3. Native Booleans: BOOLEAN NOT NULL DEFAULT TRUE / FALSE
--   4. Timestamps: TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
--   5. Financial Integrity: ON DELETE RESTRICT on ledgers, enrollments, and payments
--   6. Performance Indexes: Explicit B-Tree indexes covering core foreign keys and lookup queries
-- =============================================================================

SET statement_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SET check_function_bodies = false;
SET client_min_messages = warning;

-- Optional update timestamp helper trigger function
CREATE OR REPLACE FUNCTION set_updated_at_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- =============================================================================
-- 1. Academic Sessions
-- =============================================================================
CREATE TABLE IF NOT EXISTS academic_sessions (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE academic_sessions IS 'Defines institutional academic calendars (e.g. 2026-2027).';


-- =============================================================================
-- 2. Student Registry & Guardian Metadata
-- =============================================================================
CREATE TABLE IF NOT EXISTS students (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    admission_number VARCHAR(50) NOT NULL UNIQUE,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100),
    urdu_name VARCHAR(150),
    gender VARCHAR(20) NOT NULL CHECK (gender IN ('Male', 'Female', 'Other')),
    date_of_birth DATE,
    b_form_number VARCHAR(30),
    guardian_name VARCHAR(100) NOT NULL,
    guardian_urdu_name VARCHAR(150),
    guardian_relation VARCHAR(50) NOT NULL DEFAULT 'Father',
    guardian_phone VARCHAR(20) NOT NULL,
    guardian_whatsapp VARCHAR(20),
    guardian_cnic VARCHAR(30),
    residential_address TEXT,
    emergency_contact VARCHAR(20),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER trg_students_updated_at
    BEFORE UPDATE ON students
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at_timestamp();

COMMENT ON TABLE students IS 'Student biological identities, legal names, and primary guardian emergency contacts.';


-- =============================================================================
-- 3. Class Groups & Academy Batches
-- =============================================================================
CREATE TABLE IF NOT EXISTS class_groups (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id BIGINT NOT NULL REFERENCES academic_sessions(id) ON DELETE RESTRICT,
    name VARCHAR(100) NOT NULL,
    section_or_batch VARCHAR(100) NOT NULL,
    group_type VARCHAR(50) NOT NULL CHECK (group_type IN ('SchoolClass', 'AcademyBatch')),
    monthly_tuition_fee NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_class_groups_session_name_section UNIQUE (session_id, name, section_or_batch)
);

COMMENT ON TABLE class_groups IS 'Academic containers supporting both Private School class/sections and Tuition Academy batches.';


-- =============================================================================
-- 4. Student Enrollments
-- =============================================================================
CREATE TABLE IF NOT EXISTS enrollments (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_id BIGINT NOT NULL REFERENCES students(id) ON DELETE RESTRICT,
    class_group_id BIGINT NOT NULL REFERENCES class_groups(id) ON DELETE RESTRICT,
    session_id BIGINT NOT NULL REFERENCES academic_sessions(id) ON DELETE RESTRICT,
    roll_number VARCHAR(30),
    enrollment_date DATE NOT NULL DEFAULT CURRENT_DATE,
    status VARCHAR(30) NOT NULL DEFAULT 'Active' CHECK (status IN ('Active', 'Transferred', 'Withdrawn', 'Graduated')),
    custom_discount_amount NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_enrollments_student_class_session UNIQUE (student_id, class_group_id, session_id)
);

COMMENT ON TABLE enrollments IS 'Links a student to an academic session and class group with custom recurring discounts.';


-- =============================================================================
-- 5. Fee Heads Catalog
-- =============================================================================
CREATE TABLE IF NOT EXISTS fee_heads (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    urdu_name VARCHAR(150),
    is_recurring BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE fee_heads IS 'Catalog of financial line item categories (Tuition, Lab, Exam, Admission).';


-- =============================================================================
-- 6. Fee Invoices (Master Vouchers)
-- =============================================================================
CREATE TABLE IF NOT EXISTS fee_invoices (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    enrollment_id BIGINT NOT NULL REFERENCES enrollments(id) ON DELETE RESTRICT,
    session_id BIGINT NOT NULL REFERENCES academic_sessions(id) ON DELETE RESTRICT,
    month_year VARCHAR(10) NOT NULL,
    issue_date DATE NOT NULL,
    due_date DATE NOT NULL,
    valid_until DATE NOT NULL,
    late_fee_surcharge NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    total_payable NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    discount_amount NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    net_due NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_fee_invoices_enrollment_month UNIQUE (enrollment_id, month_year)
);

COMMENT ON TABLE fee_invoices IS 'Master billing records for students per cycle with two-tier due date geometry.';


-- =============================================================================
-- 7. Fee Invoice Items (Breakdown Lines)
-- =============================================================================
CREATE TABLE IF NOT EXISTS fee_invoice_items (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    invoice_id BIGINT NOT NULL REFERENCES fee_invoices(id) ON DELETE CASCADE,
    fee_head_id BIGINT NOT NULL REFERENCES fee_heads(id) ON DELETE RESTRICT,
    amount NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE fee_invoice_items IS 'Itemized fee lines comprising each voucher.';


-- =============================================================================
-- 8. Payment Receipts Ledger (Immutable Audit Trail)
-- =============================================================================
CREATE TABLE IF NOT EXISTS payments (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    invoice_id BIGINT NOT NULL REFERENCES fee_invoices(id) ON DELETE RESTRICT,
    amount NUMERIC(12, 2) NOT NULL,
    payment_date DATE NOT NULL DEFAULT CURRENT_DATE,
    receipt_number VARCHAR(50) NOT NULL UNIQUE,
    payment_method VARCHAR(30) NOT NULL DEFAULT 'Cash' CHECK (payment_method IN ('Cash', 'BankTransfer', 'OnlineDeposit', 'Cheque')),
    status VARCHAR(30) NOT NULL DEFAULT 'Issued' CHECK (status IN ('Issued', 'Reversed', 'Cancelled')),
    reversal_reason TEXT,
    recorded_by_user_id BIGINT,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE payments IS 'Auditable transaction ledger. Enforces ON DELETE RESTRICT on fee_invoices.';


-- =============================================================================
-- 9. Batch Sessions (Academy Lecture Log)
-- =============================================================================
CREATE TABLE IF NOT EXISTS batch_sessions (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    class_group_id BIGINT NOT NULL REFERENCES class_groups(id) ON DELETE RESTRICT,
    session_date DATE NOT NULL,
    start_time TIME,
    end_time TIME,
    topic_covered TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE batch_sessions IS 'Chronological lecture sessions for academy batches.';


-- =============================================================================
-- 10. Daily Attendance Records
-- =============================================================================
CREATE TABLE IF NOT EXISTS attendance_records (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    enrollment_id BIGINT NOT NULL REFERENCES enrollments(id) ON DELETE RESTRICT,
    attendance_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('Present', 'Absent', 'Late', 'Leave')),
    batch_session_id BIGINT REFERENCES batch_sessions(id) ON DELETE SET NULL,
    reason_note TEXT,
    recorded_by_user_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_attendance_enrollment_date UNIQUE (enrollment_id, attendance_date)
);

CREATE TRIGGER trg_attendance_records_updated_at
    BEFORE UPDATE ON attendance_records
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at_timestamp();

COMMENT ON TABLE attendance_records IS 'Daily student attendance logs with strict unique enrollment and date constraints.';


-- =============================================================================
-- 11. Subjects Catalog
-- =============================================================================
CREATE TABLE IF NOT EXISTS subjects (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    urdu_name VARCHAR(150),
    code VARCHAR(20) UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE subjects IS 'Master subject definitions supporting bilingual curriculum.';


-- =============================================================================
-- 12. Examination Cycles
-- =============================================================================
CREATE TABLE IF NOT EXISTS exams (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id BIGINT NOT NULL REFERENCES academic_sessions(id) ON DELETE RESTRICT,
    name VARCHAR(100) NOT NULL,
    exam_type VARCHAR(50) NOT NULL CHECK (exam_type IN ('MonthlyTest', 'TermExam', 'AnnualExam', 'MockTest')),
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    is_published BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_exams_session_name UNIQUE (session_id, name)
);

COMMENT ON TABLE exams IS 'Academic examination terms and assessment cycles.';


-- =============================================================================
-- 13. Exam Subject Configuration
-- =============================================================================
CREATE TABLE IF NOT EXISTS exam_subjects (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_id BIGINT NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    class_group_id BIGINT NOT NULL REFERENCES class_groups(id) ON DELETE RESTRICT,
    subject_id BIGINT NOT NULL REFERENCES subjects(id) ON DELETE RESTRICT,
    maximum_marks NUMERIC(6, 2) NOT NULL DEFAULT 100.00,
    passing_marks NUMERIC(6, 2) NOT NULL DEFAULT 33.00,
    weightage_percent NUMERIC(5, 2) NOT NULL DEFAULT 100.00,
    exam_date DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_exam_class_subject UNIQUE (exam_id, class_group_id, subject_id)
);

COMMENT ON TABLE exam_subjects IS 'Subject-specific maximum marks and passing score thresholds per exam and class.';


-- =============================================================================
-- 14. Grading Tiers
-- =============================================================================
CREATE TABLE IF NOT EXISTS grading_tiers (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id BIGINT NOT NULL REFERENCES academic_sessions(id) ON DELETE RESTRICT,
    grade_name VARCHAR(20) NOT NULL,
    min_percentage NUMERIC(5, 2) NOT NULL,
    max_percentage NUMERIC(5, 2) NOT NULL,
    gpa_point NUMERIC(3, 2) NOT NULL DEFAULT 0.00,
    remarks_en VARCHAR(100),
    remarks_ur VARCHAR(150),
    is_passing BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_grading_tiers_session_grade UNIQUE (session_id, grade_name)
);

COMMENT ON TABLE grading_tiers IS 'Percentage grade boundaries and bilingual remarks (BISE Punjab grading rules).';


-- =============================================================================
-- 15. Marks Ledger
-- =============================================================================
CREATE TABLE IF NOT EXISTS marks (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_subject_id BIGINT NOT NULL REFERENCES exam_subjects(id) ON DELETE CASCADE,
    enrollment_id BIGINT NOT NULL REFERENCES enrollments(id) ON DELETE RESTRICT,
    marks_obtained NUMERIC(6, 2) NOT NULL,
    is_absent BOOLEAN NOT NULL DEFAULT FALSE,
    remarks TEXT,
    recorded_by_user_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_marks_exam_subject_enrollment UNIQUE (exam_subject_id, enrollment_id)
);

CREATE TRIGGER trg_marks_updated_at
    BEFORE UPDATE ON marks
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at_timestamp();

COMMENT ON TABLE marks IS 'Student assessment scores. Enforces strict marks_obtained bounds and uniqueness per subject.';


-- =============================================================================
-- 16. B-Tree Performance & Covering Indexes
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_students_admission_no ON students USING btree (admission_number);
CREATE INDEX IF NOT EXISTS idx_students_names ON students USING btree (first_name, last_name);
CREATE INDEX IF NOT EXISTS idx_students_guardian_phone ON students USING btree (guardian_phone);

CREATE INDEX IF NOT EXISTS idx_enrollments_student ON enrollments USING btree (student_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_class_session ON enrollments USING btree (class_group_id, session_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_status ON enrollments USING btree (status);

CREATE INDEX IF NOT EXISTS idx_fee_invoices_enrollment ON fee_invoices USING btree (enrollment_id);
CREATE INDEX IF NOT EXISTS idx_fee_invoices_cycle ON fee_invoices USING btree (month_year, session_id);
CREATE INDEX IF NOT EXISTS idx_fee_invoices_valid_until ON fee_invoices USING btree (valid_until);
CREATE INDEX IF NOT EXISTS idx_fee_invoices_session_valid ON fee_invoices USING btree (session_id, valid_until);
CREATE INDEX IF NOT EXISTS idx_fee_invoice_items_invoice ON fee_invoice_items USING btree (invoice_id);

CREATE INDEX IF NOT EXISTS idx_payments_invoice ON payments USING btree (invoice_id);
CREATE INDEX IF NOT EXISTS idx_payments_invoice_status_amount ON payments USING btree (invoice_id, status, amount);
CREATE INDEX IF NOT EXISTS idx_payments_receipt_no ON payments USING btree (receipt_number);

CREATE INDEX IF NOT EXISTS idx_attendance_enrollment_date ON attendance_records USING btree (enrollment_id, attendance_date);
CREATE INDEX IF NOT EXISTS idx_attendance_date_status ON attendance_records USING btree (attendance_date, status);
CREATE INDEX IF NOT EXISTS idx_attendance_batch ON attendance_records USING btree (batch_session_id);

CREATE INDEX IF NOT EXISTS idx_exam_subjects_lookup ON exam_subjects USING btree (exam_id, class_group_id);
CREATE INDEX IF NOT EXISTS idx_marks_enrollment ON marks USING btree (enrollment_id);
CREATE INDEX IF NOT EXISTS idx_marks_lookup ON marks USING btree (exam_subject_id, enrollment_id);


-- =============================================================================
-- 17. Baseline Seed Data
-- =============================================================================
INSERT INTO fee_heads (name, urdu_name, is_recurring)
VALUES
    ('Tuition Fee', 'ٹیوشن فیس', TRUE),
    ('Admission Fee', 'داخلہ فیس', FALSE),
    ('Examination Fee', 'امتحانی فیس', FALSE),
    ('Computer Lab Fee', 'کمپیوٹر لیب فیس', TRUE),
    ('Generator / Utility Charges', 'جنریٹر و یوٹیلٹی چارجز', TRUE)
ON CONFLICT (name) DO NOTHING;

INSERT INTO subjects (name, urdu_name, code)
VALUES
    ('Mathematics', 'ریاضی', 'MATH'),
    ('English', 'انگریزی', 'ENG'),
    ('Urdu', 'اردو', 'URDU'),
    ('Science', 'جنرل سائنس', 'SCI'),
    ('Islamiat', 'اسلامیات', 'ISL'),
    ('Pakistan Studies', 'مطالعہ پاکستان', 'PST')
ON CONFLICT (name) DO NOTHING;
