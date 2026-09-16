# SRS 02: ClassFellow - Student & Enrollment Module Specification

## Document Information
- **Document Identifier**: `CF-SRS-02`
- **Project**: ClassFellow School and Academy Management Software
- **Version**: 1.0.0
- **Status**: APPROVED
- **Subsystem**: Student Identity, Guardian Profiling & Academic Enrollment

---

## 1. Module Overview & Operational Models

The Student & Enrollment module is the foundational entity provider for the ClassFellow ecosystem. It establishes student identity, captures parent/guardian contact and demographic information, and records academic enrollments.

To address the local Punjab educational landscape, the data model supports **two distinct operational modes**:

### 1.1 Model Comparison

| Dimension | Private School Model (Class & Section) | Tuition Academy / Coaching Model (Subject & Batch) |
|---|---|---|
| **Academic Grouping** | Fixed grade/class and section (e.g., *Class 9 - Green*, *Class 10 - A*) | Subject-specific batches by teacher & time (e.g., *9th Physics @ 4:00 PM - Sir Ali*) |
| **Enrollment Term** | Full academic session (e.g., *April 2025 – March 2026*) | Flexible / rolling enrollment per subject or course batch |
| **Fee Association** | Class-wide flat tuition fee (all subjects bundled) | Fee charged per subject/batch (e.g., Rs. 1,500/subject) |
| **Daily Attendance** | Logged **once per day** for the entire section group | Logged **per batch session** / subject lecture |

The database abstracts both structures under a unified `class_groups` table linked to `enrollments`.

---

## 2. Relational Database Schema Specification

### 2.1 Table DDL

```sql
-- Academic Sessions (e.g., 2025-2026)
CREATE TABLE academic_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,          -- e.g., '2025-2026'
    start_date TEXT NOT NULL,           -- ISO-8601 YYYY-MM-DD
    end_date TEXT NOT NULL,             -- ISO-8601 YYYY-MM-DD
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
);

-- Core Student Identity
CREATE TABLE students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admission_number TEXT NOT NULL UNIQUE, -- e.g., 'CF-2025-0104'
    first_name TEXT NOT NULL,
    last_name TEXT,
    urdu_name TEXT,                        -- UTF-8 Urdu name for bilingual vouchers
    gender TEXT NOT NULL CHECK (gender IN ('Male', 'Female', 'Other')),
    date_of_birth TEXT,                    -- ISO-8601 YYYY-MM-DD (Optional)
    b_form_number TEXT,                    -- National B-Form / CNIC (Optional)
    guardian_name TEXT NOT NULL,
    guardian_urdu_name TEXT,               -- UTF-8 Guardian Urdu name
    guardian_relation TEXT NOT NULL DEFAULT 'Father',
    guardian_phone TEXT NOT NULL,          -- Primary mobile for WhatsApp/SMS
    guardian_whatsapp TEXT,                -- Secondary WhatsApp contact
    guardian_cnic TEXT,                    -- National ID (Optional)
    residential_address TEXT,
    emergency_contact TEXT,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (DATETIME('now')),
    updated_at TEXT NOT NULL DEFAULT (DATETIME('now'))
);

-- Class Groups and Subject Batches
CREATE TABLE class_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    name TEXT NOT NULL,                    -- e.g., 'Class 9', '9th Physics'
    section_or_batch TEXT NOT NULL,        -- e.g., 'Section A', 'Evening 4PM Batch'
    group_type TEXT NOT NULL CHECK (group_type IN ('SchoolClass', 'AcademyBatch')),
    monthly_tuition_fee TEXT NOT NULL DEFAULT '0.00', -- Base tuition fee
    created_at TEXT NOT NULL DEFAULT (DATETIME('now')),
    FOREIGN KEY (session_id) REFERENCES academic_sessions(id) ON DELETE RESTRICT,
    UNIQUE(session_id, name, section_or_batch)
);

-- Academic Enrollments
CREATE TABLE enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    class_group_id INTEGER NOT NULL,
    session_id INTEGER NOT NULL,
    roll_number TEXT,                      -- e.g., 'Roll 24'
    enrollment_date TEXT NOT NULL,         -- ISO-8601 YYYY-MM-DD
    status TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active', 'Transferred', 'Withdrawn', 'Graduated')),
    custom_discount_amount TEXT NOT NULL DEFAULT '0.00', -- Approved permanent monthly discount
    created_at TEXT NOT NULL DEFAULT (DATETIME('now')),
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE RESTRICT,
    FOREIGN KEY (class_group_id) REFERENCES class_groups(id) ON DELETE RESTRICT,
    FOREIGN KEY (session_id) REFERENCES academic_sessions(id) ON DELETE RESTRICT,
    UNIQUE(student_id, class_group_id, session_id)
);
```

### 2.2 Performance Search Indexes

To ensure high-speed search across thousands of student records in CustomTkinter UI search bars:

```sql
-- Fast student search by admission number, name, and guardian mobile
CREATE INDEX idx_students_admission_no ON students(admission_number);
CREATE INDEX idx_students_names ON students(first_name, last_name);
CREATE INDEX idx_students_guardian_phone ON students(guardian_phone);

-- Enrollment lookup indexes
CREATE INDEX idx_enrollments_student ON enrollments(student_id);
CREATE INDEX idx_enrollments_class_session ON enrollments(class_group_id, session_id);
```

---

## 3. Data Transfer Objects (DTOs)

The service layer exchanges typed Python `dataclasses` with the UI and database repositories:

```python
# models/student_dto.py
from dataclasses import dataclass
from typing import Optional
from decimal import Decimal

@dataclass(frozen=True)
class StudentDTO:
    id: Optional[int]
    admission_number: str
    first_name: str
    last_name: Optional[str]
    urdu_name: Optional[str]
    gender: str
    guardian_name: str
    guardian_urdu_name: Optional[str]
    guardian_phone: str
    residential_address: Optional[str]
    is_active: bool = True

@dataclass(frozen=True)
class EnrollmentDTO:
    id: Optional[int]
    student_id: int
    class_group_id: int
    session_id: int
    roll_number: Optional[str]
    enrollment_date: str
    status: str
    custom_discount_amount: Decimal = Decimal("0.00")
```

---

## 4. Service Layer Contracts (`services/student_service.py`)

The business logic is encapsulated in `StudentService`:

### 4.1 Core Methods

1. `register_student(student_data: StudentDTO, class_group_id: int, session_id: int, roll_no: str) -> int`
   - Validates unique admission number (auto-generates next sequence if blank).
   - Validates Pakistani phone format (`03XXXXXXXXX` / 11 digits).
   - Enforces UTF-8 encoding on Urdu names.
   - Creates `Student` record and initial `Enrollment` inside a single atomic transaction.

2. `search_students(query: str, active_only: bool = True) -> list[StudentDTO]`
   - Multi-field search matching admission number, student name, or guardian mobile with `LIKE %query%`.

3. `transfer_or_withdraw_student(enrollment_id: int, new_status: str, note: str) -> None`
   - Updates enrollment status (`Transferred`, `Withdrawn`).
   - Dispatches status change to fee service to halt future fee invoice generation.

---

## 5. UI Interaction & Form Validation Rules

1. **Focus & Keyboard Navigation**:
   - Tab sequence: First Name -> Last Name -> Urdu Name -> Gender -> Guardian Name -> Guardian Phone -> Class Group -> Save Button.
   - Enter key on the final field triggers validation and submission.
2. **Pakistani Phone Validation**:
   - Must match regex: `^03[0-9]{9}$` (11 digits starting with `03`).
3. **Modal Operation**:
   - Student profile additions and edits occur strictly inside modal dialogs. The main student list remains a high-performance read-only grid.
