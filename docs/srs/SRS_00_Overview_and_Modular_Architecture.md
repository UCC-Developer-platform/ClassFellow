# SRS 00: ClassFellow - System Overview & Modular Architecture Specification

## Document Information
- **Document Identifier**: `CF-SRS-00`
- **Project**: ClassFellow School and Academy Management Software
- **Version**: 1.0.0
- **Status**: APPROVED
- **Author**: Lead Architecture Team
- **Target Audience**: Core Developers, Database Engineers, UI/UX Designers, QA Engineers

---

## 1. Executive Summary & Vision

**ClassFellow** is a high-reliability, bilingual (English and Urdu), offline-first management platform designed specifically for private schools, tuition academies, coaching centers, and intermediate colleges across Punjab, Pakistan.

The software addresses the harsh ground realities of the local educational sector:
- **Intermittent Power & Connectivity**: Must run completely offline on local school desktop hardware.
- **Accurate Financial Records**: Zero-drift accounting using strict `Decimal` monetary representations and append-only ledgers.
- **Localized Administrative Workflows**: Direct Phonetic Urdu keyboard input with standard English/bilingual print layouts on standard A4 paper (specifically 3-panel fee vouchers).
- **Flexible Institutional Models**: Dual operational model supporting both full-time **Class/Section** private schools and subject-based **Batch** tuition academies.

---

## 2. Modular Commercial Packaging Architecture

To enable commercial flexibility where schools or academies can buy reduced packages or upgrade over time, ClassFellow is architected around a **Core Kernel + Plug-and-Play Domain Modules** design.

```text
                       ┌─────────────────────────────────────────┐
                       │               Core Kernel               │
                       │   (Database Engine, Migrations, Auth,   │
                       │    Async Runner, Logger, Theme Tokens)  │
                       └────────────────────┬────────────────────┘
                                            │
               ┌────────────────────────────┼────────────────────────────┐
               │                            │                            │
       ┌───────┴────────┐           ┌───────┴────────┐           ┌───────┴────────┐
       │ Module 1:      │           │ Module 2:      │           │ Module 3:      │
       │ Students &     │           │ Fees &         │           │ Attendance &   │
       │ Enrollments    │           │ Receipts       │           │ Notifications  │
       └────────────────┘           └────────────────┘           └────────────────┘
               │                            │                            │
               └────────────────────────────┼────────────────────────────┘
                                            │
                                    ┌───────┴────────┐
                                    │ Module 4:      │
                                    │ Examinations & │
                                    │ Report Cards   │
                                    └────────────────┘
```

### 2.1 Commercial Tiers & Feature Flags

The application manages active module entitlements via a configuration file (`config/modules.json`):

| Package Tier | Included Modules | Target Customer Profile |
|---|---|---|
| **Tier 1: Starter (Fee-Only Edition)** | Core Kernel + Students + Fees & Receipts | Small academies & coaching centers focused strictly on fee voucher generation, cashier payments, and defaulter tracking. |
| **Tier 2: Standard Edition** | Core Kernel + Students + Fees + Attendance | Medium schools & academies requiring daily student tracking, fee management, and absence notices. |
| **Tier 3: Professional Edition (Full Suite)** | All Modules (Students + Fees + Attendance + Examinations) | Comprehensive K-10/12 private schools and colleges needing end-to-end management, BISE-aligned grading, and A4 report cards. |

### 2.2 Dynamic UI Menu Injection Rule

During application boot, the UI Shell (`app/ui/shell.py`) reads `config/modules.json`:
- If `modules.fees == false`, the "Fees & Receipts" sidebar icon and navigation routes are omitted.
- If `modules.attendance == false`, the "Attendance" sidebar icon and background daily jobs are suppressed.
- Modules communicate exclusively through the database and Data Transfer Objects (DTOs), guaranteeing zero runtime crashes when an unpurchased module is disabled.

---

## 3. High-Level Subsystem Boundaries

1. **Kernel Subsystem**:
   - SQLite connection pool with WAL mode and `PRAGMA foreign_keys = ON;`.
   - Automated schema migrations via `PRAGMA user_version`.
   - Centralized logging (`logs/app.log`) and custom exception hierarchy (`DomainError`, `ValidationError`, `DatabaseError`).
   - Thread pool executor for UI responsiveness.

2. **Student & Enrollment Subsystem (`services/student_service.py`)**:
   - Manages student identity, guardians, and academic enrollments.
   - Dispatches enrollment data to both the Fee subsystem and Attendance subsystem.

3. **Fee & Receipt Subsystem (`services/fee_service.py`)**:
   - Itemized fee heads, master invoices, two-tier due dates, and append-only payment ledgers.
   - Generates 3-panel A4 vouchers using ReportLab with Arabic/Urdu ligature reshaping.

4. **Attendance Subsystem (`services/attendance_service.py`)**:
   - Enforces `Unique(enrollment_id, attendance_date)`.
   - Generates monthly percentages and WhatsApp notification payloads.

5. **Examination Subsystem (`services/exam_service.py`)**:
   - Configures subject maximum marks and pass thresholds.
   - Generates bilingual A4 report cards.

6. **Backup & Safety Subsystem (`services/backup_service.py`)**:
   - Executes 3-tier backup hierarchy: Local daily rolling snapshots (SQLite online backup API), manual USB snapshots, and Google Drive cloud sync.

---

## 4. Architectural Non-Goals for Desktop MVP

To preserve developmental velocity and operational stability, the desktop MVP explicitly excludes:
- Multi-user remote network database connections over SQLite (reserved for Django/PostgreSQL in Phase 5).
- Thermal POS printers (standard A4 desk printers only).
- Biometric hardware integrations.
- Online card payment gateways (cashier/bank vouchers only).
- Real-time GPS transport tracking.
