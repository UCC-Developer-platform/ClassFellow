# SRS 04: ClassFellow - Attendance & Notification Module Specification

## Document Information
- **Document Identifier**: `CF-SRS-04`
- **Project**: ClassFellow School and Academy Management Software
- **Version**: 1.0.0
- **Status**: APPROVED
- **Subsystem**: Daily Attendance Logging, Uniqueness Constraints, Analytics & Parent Notifications

---

## 1. Module Overview & Dual Operational Models

The Attendance & Notification module tracks daily and session-based student participation, enforces data integrity to eliminate duplicate submissions, computes attendance percentages for academic report cards, and generates zero-cost parent absence notifications.

### 1.1 Dual Operational Attendance Workflows

1. **Private School Model (Class & Section Daily Roster)**:
   - **Bulk Entry Workflow**: Selecting a date and class group loads the entire enrolled student roster with all students **pre-marked as 'Present' by default**.
   - **Exception Marking**: The school clerk or teacher only flags exceptions (**'Absent'**, **'Late'**, **'Leave'**) using high-speed keyboard shortcuts (`Spacebar` to cycle status, `Down Arrow` to move to the next row).
   - This reduces daily data entry time for a class of 45 students from 8 minutes to under 45 seconds.

2. **Tuition Academy Model (Subject & Batch Session)**:
   - Attendance is logged per scheduled lecture slot or course period (e.g., *9th Physics - 4:00 PM to 5:00 PM*).
   - Students attending multiple subjects per day have individual attendance records logged per lecture session.

---

## 2. Relational Database Schema Specification

### 2.1 Table DDL

```sql
-- Academy Lecture Sessions (Optional for Subject/Batch model)
CREATE TABLE batch_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_group_id INTEGER NOT NULL,
    session_date TEXT NOT NULL,         -- ISO-8601 YYYY-MM-DD
    start_time TEXT,                    -- e.g., '16:00'
    end_time TEXT,                      -- e.g., '17:00'
    topic_covered TEXT,
    created_at TEXT NOT NULL DEFAULT (DATETIME('now')),
    FOREIGN KEY (class_group_id) REFERENCES class_groups(id) ON DELETE RESTRICT
);

-- Core Attendance Record
CREATE TABLE attendance_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    enrollment_id INTEGER NOT NULL,
    attendance_date TEXT NOT NULL,      -- ISO-8601 YYYY-MM-DD
    status TEXT NOT NULL CHECK (status IN ('Present', 'Absent', 'Late', 'Leave')),
    batch_session_id INTEGER,           -- NULL for school model; FK for academy model
    reason_note TEXT,                   -- Reason for leave or absence
    recorded_by_user_id INTEGER,        -- User audit trail
    created_at TEXT NOT NULL DEFAULT (DATETIME('now')),
    updated_at TEXT NOT NULL DEFAULT (DATETIME('now')),
    FOREIGN KEY (enrollment_id) REFERENCES enrollments(id) ON DELETE RESTRICT,
    FOREIGN KEY (batch_session_id) REFERENCES batch_sessions(id) ON DELETE SET NULL,
    UNIQUE(enrollment_id, attendance_date)
);
```

### 2.2 Data Integrity & Index Specifications
- **Uniqueness Constraint**: `UNIQUE(enrollment_id, attendance_date)` strictly prevents duplicate entries for the same student on the same date. Re-saving or submitting attendance for a previously recorded date triggers an atomic SQLite `INSERT ... ON CONFLICT(enrollment_id, attendance_date) DO UPDATE SET status=excluded.status, updated_at=DATETIME('now')`.

```sql
-- High-performance query indexes for monthly attendance aggregation
CREATE INDEX idx_attendance_enrollment_date ON attendance_records(enrollment_id, attendance_date);
CREATE INDEX idx_attendance_date_status ON attendance_records(attendance_date, status);
CREATE INDEX idx_attendance_batch ON attendance_records(batch_session_id);
```

---

## 3. Attendance Analytics & Monthly Metric Calculations

For academic terms and report cards, attendance percentages are calculated using standardized formulas:

$$\text{Total Working Days} = \text{Count of unique institution working dates in period}$$
$$\text{Days Present} = \text{Count of records with status = 'Present'}$$
$$\text{Days Late} = \text{Count of records with status = 'Late'}$$
$$\text{Days Leave} = \text{Count of records with status = 'Leave'}$$

$$\text{Attendance Percentage} = \left( \frac{\text{Days Present} + \text{Days Leave} + (0.5 \times \text{Days Late})}{\text{Total Working Days}} \right) \times 100$$

*Note: Institutional policy can configure whether Approved Leaves count toward the numerator.*

---

## 4. Zero-Cost WhatsApp & SMS Notification Payloads

To eliminate reliance on expensive third-party SMS/WhatsApp API gateways during desktop operation, ClassFellow generates standardized, copy-ready clipboard strings and `wa.me` deep-links.

### 4.1 Localized Message Templates (English & Urdu)

#### Absence Notification Template
```text
محترم والدین،
اطلاع دی جاتی ہے کہ آپ کا بچہ {student_name} (رول نمبر: {roll_no}) آج مورخہ {date} کو {institution_name} سے غیر حاضر ہے۔
اگر چھٹی کی کوئی خاص وجہ ہے تو براہ کرم اسکول آفس {institution_phone} پر رابطہ کریں۔
شکریہ،
انتظامیہ {institution_name}

--------------------------------------------------
Dear Parent,
This is to inform you that your child {student_name} (Roll No: {roll_no}) is ABSENT today ({date}) from {institution_name}.
Please contact the school office at {institution_phone} if you have not submitted a leave application.
Regards,
{institution_name} Administration
```

### 4.2 Desktop WhatsApp Deep-Link Launcher
When an administrator clicks the **"WhatsApp Parent"** button next to an absent student:
1. The service generates an encoded URL string:  
   `https://wa.me/92{guardian_phone}?text={url_encoded_message}`
2. Launches the desktop's default browser or WhatsApp Desktop client directly without API subscription fees.

---

## 5. Data Transfer Objects (DTOs) & Service Contracts

### 5.1 DTO Models

```python
# models/attendance_dto.py
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class AttendanceEntryDTO:
    enrollment_id: int
    student_name: str
    roll_number: Optional[str]
    status: str  # 'Present', 'Absent', 'Late', 'Leave'
    reason_note: Optional[str] = None

@dataclass(frozen=True)
class AttendanceSummaryDTO:
    enrollment_id: int
    total_days: int
    present_days: int
    absent_days: int
    leave_days: int
    late_days: int
    percentage: float
```

### 5.2 Service Layer Contract (`services/attendance_service.py`)

1. `load_class_roster_for_attendance(class_group_id: int, date: str) -> list[AttendanceEntryDTO]`
   - Queries active enrollments for the class group.
   - Merges existing attendance records if already logged; otherwise defaults all students to `'Present'`.

2. `save_bulk_attendance(date: str, entries: list[AttendanceEntryDTO], user_id: int) -> int`
   - Executes an atomic SQLite transaction using `UPSERT` syntax.
   - Guarantees zero duplicate rows and updates modified statuses.

3. `get_monthly_attendance_summary(enrollment_id: int, start_date: str, end_date: str) -> AttendanceSummaryDTO`
   - Aggregates status counts and returns computed percentage.

4. `generate_absence_whatsapp_payload(enrollment_id: int, date: str) -> dict`
   - Extracts student, guardian mobile, and institution profile.
   - Generates formatted English/Urdu text and `wa.me` deep-link URL.
