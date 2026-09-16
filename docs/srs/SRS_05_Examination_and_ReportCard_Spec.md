# SRS 05: ClassFellow - Examination & Report Card Module Specification

## Document Information
- **Document Identifier**: `CF-SRS-05`
- **Project**: ClassFellow School and Academy Management Software
- **Version**: 1.0.0
- **Status**: APPROVED
- **Subsystem**: Examination Sessions, Marks Entry, Grade Calculations & Bilingual A4 Report Cards

---

## 1. Module Overview & Educational Standards

The Examination & Report Card module manages institutional testing cycles (Monthly Tests, Mid-Term Exams, Terminal / Annual Board Examinations), records student scores, evaluates pass/fail and grade boundaries against configurable scales, and generates professional, printable bilingual A4 Terminal Report Cards.

### 1.1 Core Engineering Principles
1. **Dynamic Contextual Mark Limits (`exam_subjects`)**: Reject static global maximum marks. Subject limits and passing thresholds are bound to the specific examination, class group, and academic session.
2. **Database-Driven Grading Rules (`grading_tiers`)**: Grade boundaries (A+, A, B, C, D, F) are stored as configurable database records rather than hardcoded in application logic, enabling schools to customize BISE board standards or institutional thresholds.
3. **Bilingual A4 Print Engine**: Generates ready-to-print single-sheet A4 terminal report cards formatted with clean typography, student ranking, attendance statistics, and pre-shaped Urdu remarks.

---

## 2. Relational Database Schema Specification

### 2.1 Table DDL

```sql
-- Master Subject Definitions
CREATE TABLE subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,             -- e.g., 'Mathematics', 'Urdu', 'Physics'
    urdu_name TEXT,                        -- e.g., 'ریاضی', 'اردو', 'طبیعیات'
    code TEXT UNIQUE,                      -- e.g., 'MATH-10', 'PHY-09'
    created_at TEXT NOT NULL DEFAULT (DATETIME('now'))
);

-- Master Examination Cycle
CREATE TABLE exams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    name TEXT NOT NULL,                    -- e.g., 'Mid-Term Examination 2025'
    exam_type TEXT NOT NULL CHECK (exam_type IN ('MonthlyTest', 'TermExam', 'AnnualExam', 'MockTest')),
    start_date TEXT NOT NULL,              -- ISO-8601 YYYY-MM-DD
    end_date TEXT NOT NULL,                -- ISO-8601 YYYY-MM-DD
    is_published INTEGER NOT NULL DEFAULT 0 CHECK (is_published IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (DATETIME('now')),
    FOREIGN KEY (session_id) REFERENCES academic_sessions(id) ON DELETE RESTRICT
);

-- Dynamic Class-Specific Subject Examination Configuration
CREATE TABLE exam_subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id INTEGER NOT NULL,
    class_group_id INTEGER NOT NULL,
    subject_id INTEGER NOT NULL,
    maximum_marks TEXT NOT NULL,           -- Stored as TEXT Decimal (e.g., '100.00', '75.00')
    passing_marks TEXT NOT NULL,           -- Stored as TEXT Decimal (e.g., '33.00', '40.00')
    weightage_percent TEXT NOT NULL DEFAULT '100.00',
    exam_date TEXT,                        -- Date of specific paper
    created_at TEXT NOT NULL DEFAULT (DATETIME('now')),
    FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE,
    FOREIGN KEY (class_group_id) REFERENCES class_groups(id) ON DELETE RESTRICT,
    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE RESTRICT,
    UNIQUE(exam_id, class_group_id, subject_id)
);

-- Configurable Grading Scales
CREATE TABLE grading_tiers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    grade_name TEXT NOT NULL,              -- e.g., 'A+', 'A', 'B', 'C', 'D', 'F'
    min_percentage TEXT NOT NULL,          -- e.g., '80.00'
    max_percentage TEXT NOT NULL,          -- e.g., '100.00'
    gpa_point TEXT NOT NULL DEFAULT '0.0', -- e.g., '4.0'
    remarks_en TEXT,                       -- 'Exceptional', 'Excellent'
    remarks_ur TEXT,                       -- 'بہترین کارکردگی'
    is_passing INTEGER NOT NULL DEFAULT 1 CHECK (is_passing IN (0, 1)),
    FOREIGN KEY (session_id) REFERENCES academic_sessions(id) ON DELETE CASCADE,
    UNIQUE(session_id, grade_name)
);

-- Individual Student Marks Entry Ledger
CREATE TABLE marks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_subject_id INTEGER NOT NULL,
    enrollment_id INTEGER NOT NULL,
    marks_obtained TEXT NOT NULL,          -- Stored as TEXT Decimal (e.g., '84.50')
    is_absent INTEGER NOT NULL DEFAULT 0 CHECK (is_absent IN (0, 1)),
    teacher_remarks TEXT,
    recorded_by_user_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (DATETIME('now')),
    updated_at TEXT NOT NULL DEFAULT (DATETIME('now')),
    FOREIGN KEY (exam_subject_id) REFERENCES exam_subjects(id) ON DELETE CASCADE,
    FOREIGN KEY (enrollment_id) REFERENCES enrollments(id) ON DELETE RESTRICT,
    UNIQUE(exam_subject_id, enrollment_id)
);
```

### 2.2 Performance Indexes
```sql
CREATE INDEX idx_exam_subjects_lookup ON exam_subjects(exam_id, class_group_id);
CREATE INDEX idx_marks_enrollment ON marks(enrollment_id);
CREATE INDEX idx_marks_exam_subject ON marks(exam_subject_id);
```

---

## 3. Evaluation Algorithms & Grade Determination

### 3.1 Subject-Level Evaluation
For each student enrollment in an exam subject:
- If `is_absent == 1`: Marks = 0, Status = `'Absent'`.
- Else: Check validation rule:
  $$0 \le \text{marks\_obtained} \le \text{exam\_subjects.maximum\_marks}$$
- Passing check: $\text{marks\_obtained} \ge \text{exam\_subjects.passing\_marks}$.

### 3.2 Term Aggregate & Grade Derivation
For all subjects evaluated in a student's terminal exam:

$$\text{Total Max Marks} = \sum (\text{exam\_subjects.maximum\_marks})$$
$$\text{Total Obtained Marks} = \sum (\text{marks.marks\_obtained})$$

$$\text{Aggregate Percentage} = \left( \frac{\text{Total Obtained Marks}}{\text{Total Max Marks}} \right) \times 100$$

The system queries `grading_tiers` where:
$$\text{min\_percentage} \le \text{Aggregate Percentage} \le \text{max\_percentage}$$
and assigns the associated `grade_name`, `gpa_point`, and remarks.

### 3.3 Class Ranking Algorithm
Class rank / position is calculated across all active students enrolled in the class group, ordered by:
1. `Total Obtained Marks DESC`
2. `Aggregate Percentage DESC`
3. Equal aggregates share rank (e.g., Joint 2nd Position).

---

## 4. ReportLab Bilingual A4 Terminal Report Card Specification

### 4.1 Page Geometry & Layout Architecture
- **Dimensions**: Single Sheet A4 Portrait ($595.27 \times 841.89$ points) with 36pt outer margins.
- **Header Section**:
  - School Crest / Logo (Left, 60x60pt).
  - Institution Name (Bold 18pt) and Urdu Name (Shaped Noto Naskh 16pt).
  - Examination Title and Academic Session (12pt Bold).
- **Student Profile Box**:
  - 2-column key-value grid: Student Name, Urdu Name, Roll No, Class/Section, Admission No.
- **Results Data Table**:
  - Columns: Subject, Maximum Marks, Passing Marks, Marks Obtained, Percentage, Grade, Status.
  - Alternating light-slate row shading (`#F8FAFC`).
- **Scorecard Summary Grid**:
  - 4 High-contrast summary blocks: Total Marks, Obtained Marks, Percentage (%), Grade / Rank.
- **Attendance & Remarks Section**:
  - Term Attendance Summary: "Attended {present}/{total_days} Days ({percentage}%)".
  - Teacher Remarks Box with bidirectional Urdu ligature reshaping (`arabic-reshaper` + `python-bidi`).
- **Institutional Sign-off Footer**:
  - 3 signature lines: Class Teacher, Examination Controller, Principal Stamp.

---

## 5. Data Transfer Objects (DTOs) & Service Contracts

### 5.1 DTO Models

```python
# models/exam_dto.py
from dataclasses import dataclass
from typing import Optional
from decimal import Decimal

@dataclass(frozen=True)
class SubjectResultDTO:
    subject_name: str
    subject_urdu_name: Optional[str]
    maximum_marks: Decimal
    passing_marks: Decimal
    marks_obtained: Decimal
    is_absent: bool
    is_passed: bool
    grade: str

@dataclass(frozen=True)
class StudentReportCardDTO:
    student_name: str
    urdu_name: Optional[str]
    roll_number: Optional[str]
    class_name: str
    admission_number: str
    results: list[SubjectResultDTO]
    total_maximum: Decimal
    total_obtained: Decimal
    percentage: Decimal
    final_grade: str
    rank_in_class: int
    attendance_percentage: float
    teacher_remarks: Optional[str]
```

### 5.2 Service Layer Contract (`services/exam_service.py`)

1. `configure_exam_subjects(exam_id: int, class_group_id: int, subject_configs: list[dict]) -> None`
   - Inserts or updates dynamic subject maximum and passing marks.

2. `record_student_marks(exam_subject_id: int, marks_data: list[dict], user_id: int) -> int`
   - Validates that obtained marks do not exceed `maximum_marks`.
   - Inserts/updates marks ledger atomically.

3. `calculate_class_results(exam_id: int, class_group_id: int) -> list[StudentReportCardDTO]`
   - Computes student totals, percentages, grade tiers, and class ranks.

4. `generate_report_card_pdf(report_data: StudentReportCardDTO, output_path: str) -> str`
   - Invokes ReportLab A4 rendering engine with Urdu font metrics and returns the generated PDF file path.
