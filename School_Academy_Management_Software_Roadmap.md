# ClassFellow - School and Academy Management Software Roadmap

## Product vision

Build **ClassFellow**, a practical, bilingual (English and Urdu), offline-friendly school and academy management system for small and medium private schools, colleges, and tuition academies in Punjab, Pakistan.

The product should begin as a modular local application and grow through validated stages into a maintainable commercial product platform under the **ClassFellow** brand. Each stage must be useful on its own, tested before expansion, and reviewed with real teachers, administrators, and a senior developer.

> This roadmap is a development guide, not a final business or regulatory specification. Confirm rules, workflows, privacy expectations, grading schemes, and pricing with local institutions before implementation.

## 1. Why this product is worth exploring

Private schools and academies repeatedly manage:

- Student registration and admission records
- Classes, sections, batches, and academic sessions
- Daily attendance
- Monthly or quarterly fees
- Receipts, discounts, arrears, and defaulters
- Tests, examinations, marks, grades, and report cards
- Teacher and staff records
- Parent and student notices
- Expenses, inventory, and basic administration
- Printed reports for parents, management, and inspection

Public-school reporting already includes government systems such as Punjab's School Information System (SIS). The first product should therefore serve private schools, colleges, academies, and tuition centers rather than attempting to replace government reporting platforms.

Useful research starting points:

- [Punjab School Information System](https://sis.pesrp.edu.pk/)
- [Punjab School Education Department](https://schools.punjab.gov.pk/)
- [BISE Lahore E-Services](https://www.biselahore.com/)

## 2. Product goals

### Primary goals

1. Reduce repetitive manual work for school and academy staff.
2. Reduce calculation mistakes in fees, marks, grades, totals, and percentages.
3. Produce professional receipts and reports quickly.
4. Work reliably for institutions with limited or unreliable internet.
5. Support English and Urdu labels and printable documents.
6. Protect student, parent, teacher, and financial data.
7. Provide a product that can be installed, demonstrated, supported, and sold locally.
8. Create one connected learning journey through Python, databases, web development, testing, and mobile development.

### Non-goals for the first release

Do not initially attempt to build:

- A replacement for government SIS or board systems
- A full enterprise ERP for every type of institution
- Online payments before the accounting workflow is reliable
- Biometric hardware integration
- GPS transport tracking
- Artificial intelligence features
- A complete parent mobile application
- Complex multi-country tax and education support
- Automatic claims of compliance with government requirements

These can be considered only after the core product has real users and documented requirements.

## 3. Target customers

### Primary customer groups

1. Small private schools
2. Medium private schools with multiple classes or sections
3. Tuition academies
4. Coaching centers
5. Colleges with simple internal administration needs
6. Schools with one or more branches

### Buyer and user roles

The person who pays may not be the person who uses the software. Design for these roles:

- Owner or director: business overview, revenue, expenses, branches
- Principal or head: attendance, academic progress, reports, notices
- Accountant: fees, receipts, arrears, discounts, collection reports
- Teacher: attendance, marks, lesson plans, homework
- Receptionist or office clerk: admissions, student records, certificates
- Parent or guardian: notices, attendance, fees, results
- Student: timetable, homework, results, notices
- System administrator: users, permissions, backups, configuration

The first version should support only the roles required by the pilot institution.

## 4. Product options considered

### 4.1 Fee and receipt system

A focused first commercial product.

Core features:

- Student fee profile
- Monthly or quarterly fee invoices
- Paid, unpaid, partially paid, and overdue status
- Late fees
- Discounts and sibling discounts
- Printable receipts
- Defaulter list
- Daily and monthly collection reports
- Excel or CSV export
- Manual backup and restore

Why start here:

- Every private institution collects fees.
- The value is easy to demonstrate.
- The first version is smaller than a full ERP.
- It can operate offline on one computer.
- It gives a clear path to paid installation and support.

### 4.2 Attendance and parent notification system

Core features:

- Student and teacher attendance
- Daily, monthly, and session reports
- Late and absent status
- Absence notes
- Parent notification workflow
- Exportable attendance summaries

The first version may generate a WhatsApp-ready message instead of integrating directly with WhatsApp. Direct messaging integrations require additional provider, privacy, and operational decisions.

### 4.3 Examination and report-card system

Core features:

- Academic sessions and examinations
- Subjects and maximum marks
- Marks entry
- Total, percentage, grade, and pass/fail rules
- Position or ranking rules if the institution uses them
- Printable report cards
- Result summaries by class and subject
- Urdu and English output

### 4.4 Academy management system

Core features:

- Batches and timings
- Student attendance
- Monthly fees
- Teacher salary calculation
- Tests and results
- Notices
- Batch-level reports

This may be a good pilot market because smaller academies may make purchasing decisions faster than larger formal schools.

### 4.5 School inventory and expense system

Core features:

- Furniture, computers, books, stationery, and other assets
- Stock received and stock issued
- Suppliers
- Expense categories
- Purchase records
- Low-stock alerts
- Monthly expense reports

### 4.6 College admission and document tracker

Core features:

- Applicant registration
- Document checklist
- Admission status
- Merit or selection list
- Fee status
- Migration, correction, or certificate workflow notes
- Searchable student history

### 4.7 Teacher lesson planner and homework system

Core features:

- Syllabus and lesson-plan progress
- Homework assignments
- Class notes
- Teacher comments
- Parent or student visibility
- Completion tracking

### 4.8 School transport and pickup tracker

Core features:

- Vehicles and routes
- Drivers and attendants
- Student route assignment
- Transport fee
- Pickup list
- Vehicle maintenance notes

This is a later feature because it introduces operational, safety, and potentially location-related requirements.

### 4.9 Student result and grade calculator

Core features:

- Marks and grades
- Percentage and GPA/CGPA where appropriate
- Session and examination configuration
- Printable results
- Board-specific rules only after validation

### 4.10 Complete school and academy management system

The complete product can eventually combine the validated modules:

- Admissions
- Students and guardians
- Classes and batches
- Attendance
- Fees and receipts
- Exams and report cards
- Teachers and staff
- Lesson planning and homework
- Notices
- Expenses and inventory
- Transport
- Dashboards and reports
- Parent, teacher, and student access

Do not build this entire scope before testing a smaller product with real users.

## 4A. Approved technical refinements and architecture decisions

These technical recommendations were reviewed and accepted as part of the product direction. They should be treated as design rules for the implementation journey, even during the first learning prototype.

### 1. Use `Decimal` for fee amounts

Money should never be stored or calculated using Python `float` in a school fee system. `float` is not a safe choice for monetary values because it can create rounding errors and inconsistent totals.

Use `Decimal` for all fee, discount, late-fee, and payment calculations. Convert incoming values from strings or correctly formatted numeric input into `Decimal` before doing arithmetic.

```python
from decimal import Decimal

monthly_fee = Decimal("2500.00")
discount = Decimal("100.00")
amount_due = monthly_fee - discount
```

This rule applies to any module that deals with fee generation, receipt issues, scholarships, waived fees, or balances.

### 2. Treat payments as an auditable ledger

Payments are not simple editable text values. They are financial events and must be auditable. A generated payment or receipt must not be silently edited or deleted. Any correction must be represented as a separate, traceable transaction or reversal.

Use these ideas as the baseline:

- Receipt number
- Student or invoice reference
- Payment date
- Amount
- Payment method
- Recorded by user
- Recorded timestamp
- Status: issued, reversed, cancelled, disputed, corrected
- Correction or reversal reason
- User or administrator responsible

This protects the financial integrity of the school system and supports trust in the product.

### 3. Connect attendance to `Enrollment`

Attendance must not be stored in a way that loses the context of which class or section a student belonged to during the attendance period. A student can transfer, leave, or move between sections, so the most reliable design is to connect attendance records to the enrollment record for that specific academic session and class group.

The system should treat attendance as a student record for a specific enrollment, not just a student record in isolation.

### 4. Enforce one attendance record per enrolled student per date

To maintain integrity, the system should prevent duplicate attendance entries for the same student enrollment on the same date.

Recommended constraint concept:

```text
Unique(enrollment_id, attendance_date)
```

This prevents accidental double-submissions and multiple edits created by repeated user actions or retries.

### 5. Calculate fee status from financial facts

Fee status should normally be derived from underlying financial data rather than stored as a manually editable label. This keeps the system consistent and reduces the chance of impossible states such as:

- `Paid` while there is still an unpaid balance
- `Partially paid` while the payment record exceeds the amount due
- `Unpaid` where a valid receipt exists

Use the following approach:

```text
invoice_amount
minus discount
plus late_fee
minus total_valid_payments
= current_balance
```

Then derive the status:

- `Unpaid` when current balance is still due
- `Partially paid` when some amount has been received but the balance remains
- `Paid` when the balance is fully settled
- `Overpaid` when the paid amount exceeds the amount due
- `Waived`, `Scholarship`, or `Exempted` only via explicit approved rules or adjustments

This is essential because fee management is a financial subsystem and must remain auditable and consistent.

### 6. Connect marks to exam-specific subject configuration

A simple global `Subject.maximum_marks` will become too limiting as the software matures. Marks should eventually be tied to class/session-specific subject setup and exam setup, not just a generic subject record.

The model should support:

- exam definition
- academic session
- subject assignment
- class/class group association
- subject maximum marks
- pass marks
- weight or score contribution if required

This allows for proper validation such as:

```text
marks <= exam_subject.maximum_marks
```

and supports different mark rules between different examinations and institutions.

### 7. Decide the desktop scope before implementation

The first desktop version should clearly define whether it is for:

- a single office computer only, or
- multiple staff accessing the same data from different machines

SQLite is an excellent choice for a local desktop prototype or one-office installation. It is not a good substitute for a shared multi-user network database when the product needs simultaneous users and network concurrency.

The roadmap should therefore explicitly choose one of the following for the desktop MVP:

- One institution, one primary office computer, offline-first
- Or a later multi-user web version with Django/PostgreSQL

### 8. Keep business rules in reusable Python services

Reusable logic should live in plain Python services instead of being tightly embedded inside Tkinter button handlers or future Django view functions. This keeps the logic consistent across the desktop MVP and the later web version.

Examples of service modules:

- `fee_service.py`
- `attendance_service.py`
- `grading_service.py`
- `validation_service.py`
- `report_service.py`

This reduces duplicate logic, improves testing, and makes future migrations easier.

### 9. Add lightweight architecture-decision records

Whenever the product chooses an important direction, add a short decision record. This is not a heavy process; a simple markdown note is enough.

Example structure:

```text
Decision: Use SQLite for the first desktop prototype
Date: 2026-09-15
Status: Accepted
Context: One institution, one office computer, offline-first
Decision: Use SQLite for the MVP
Consequences: Easy local setup, but no multi-user network database support
Revisit when: the pilot requires multiple simultaneous users
```

These records help preserve design reasoning as the project grows and as different stakeholders review the project.

### 10. Test bilingual output and local printing early

For Punjab schools, bilingual support is not a final cosmetic step. It must be tested with real-use examples early.

The system should be validated with:

- Urdu student names and guardian names
- Mixed Urdu/English text
- Right-to-left layouts
- A4 report-card printing
- The actual school printer
- Receipt formatting
- Statement/card generation
- PDF or print output with fonts that work reliably

This should be part of the prototype validation stage before the product is considered polished enough for a pilot school.

### 11. Standard A4 printers & 3-panel fee vouchers (No thermal printers)

In Punjab's private school and academy ecosystem, standard desk printers using A4 paper are universally present. Thermal POS receipt printers are unnecessary for this market.

All document rendering and fee voucher layouts must target standard A4 paper:
- Monthly Fee Vouchers should render as standard **3-panel A4 vouchers** (*School Copy*, *Bank/Accounts Copy*, *Student Copy*) side-by-side or stacked on a single sheet.
- Examination Report Cards and Registers should be formatted for standard A4 portrait/landscape printing.

### 12. Direct Urdu keyboard input & English/bilingual voucher focus

School clerks will input Urdu student, guardian, and institution names directly using standard Phonetic Urdu desktop keyboards. 

Key strategic decision:
- Storage must fully support UTF-8 encoding for Urdu input fields.
- Printed fee vouchers, receipts, and administrative reports will use standard **English / Bilingual headers and field labels** on A4 paper. Pure Urdu receipt templates are not required for the initial MVP.

### 13. Dual hybrid desktop backup strategy

Because the desktop MVP operates on a single office computer with intermittent connectivity, data safety requires two complementary backup channels:

1. **Manual USB Export/Import**: Simple one-click `.db` database export / encrypted ZIP archive to external USB storage drives for offline safety.
2. **Automated Google Drive Cloud Sync**: Background service that detects active internet connectivity and automatically uploads encrypted database snapshots to a designated Google Drive account.

### 14. Support both Class/Section and Subject/Batch operational models

The core domain model must cleanly handle the operational difference between the two primary customer types:
- **Private School Model**: Class & Section based (e.g. Class 9 - Section A). Students enroll for an entire academic session, pay flat/class-level monthly fees, and attendance is marked once per day per class group.
- **Tuition Academy Model**: Subject & Batch based (e.g. 9th Physics @ 4 PM). Students enroll per subject/teacher, pay fee per subject/course batch, and attendance is logged per batch session.

The schema abstraction (`ClassGroup` / `Batch` linked to `Enrollment`) must support both workflows without code modification.

### 15. Enforce mandatory SQLite Pragmas & Decimal Type Adapters

SQLite has foreign key checks disabled by default. The database connection manager (`database.py`) must register `Decimal` type adapters and execute essential PRAGMA directives immediately upon opening any connection:

```python
# app/database.py
import sqlite3
from decimal import Decimal

# Register Decimal adapters and converters to prevent float coercion
sqlite3.register_adapter(Decimal, lambda d: str(d))
sqlite3.register_converter("DECIMAL", lambda s: Decimal(s.decode("utf-8")))

def get_connection(db_path: str = "data/school.db") -> sqlite3.Connection:
    conn = sqlite3.connect(
        db_path,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        timeout=10.0,
        isolation_level=None  # Explicit autocommit management via transactions
    )
    # Enable essential SQLite engine pragmas
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.row_factory = sqlite3.Row
    return conn
```

This guarantees relational integrity (e.g., `ON DELETE RESTRICT` for payment ledgers) and prevents database locking during background report generation.

### 16. Store monetary values as `TEXT` in SQLite

Because SQLite lacks a native `DECIMAL` column type, store all currency fields as `TEXT` (`amount TEXT NOT NULL`). The `sqlite3` type adapters registered in `database.py` convert Python `Decimal` objects to/from text automatically, avoiding float coercion errors.

### 17. Use pure-Python `ReportLab` for desktop PDF generation

For the desktop MVP packaged via PyInstaller, use **`ReportLab`** for A4 PDF voucher and report generation. A single portrait A4 sheet (595.27 x 841.89 points) divides cleanly into three horizontal panels (~280 points high) or three vertical columns (~198 points wide) separated by dashed scissor cut lines for the 3-panel voucher (*School*, *Bank*, *Student* copies). 

Avoid `WeasyPrint` during desktop phases because its C-library dependencies (Cairo, Pango, GDK-PixBuf) create DLL bundling issues on legacy Windows machines. `WeasyPrint` can be introduced in Phase 5 web hosting.

### 18. Package bundled Urdu fonts in `assets/fonts/`

To ensure Urdu text renders correctly across all Windows machines, bundle an open-source Naskh/Nastaliq font (e.g., *Noto Naskh Arabic* or *Jameel Noori Nastaliq*) in `assets/fonts/` and register it inside ReportLab's `pdfmetrics` during application startup:

```python
# app/reports/font_manager.py
import os
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

def register_app_fonts(assets_path: str):
    font_path = os.path.join(assets_path, "fonts", "NotoNaskhArabic-Regular.ttf")
    if os.path.exists(font_path):
        pdfmetrics.registerFont(TTFont("UrduFont", font_path))
```

### 19. Desktop UI grid strategy (Read-only grids + Modal forms)

To maintain a fast, clean UI in `customtkinter`, keep multi-column table views read-only. Perform all additions, edits, and fee payment actions inside dedicated modal dialog forms rather than inline grid cell editing.

### 20. ReportLab Arabic/Urdu Script Shaping Pipeline (`arabic-reshaper` + `python-bidi`)

Registering TTF fonts with ReportLab `pdfmetrics` is insufficient on its own because ReportLab does not perform native OpenType glyph substitution or complex bidirectional script reordering. Passing raw Urdu strings (e.g., `"عاصم خان"` or `"داخلہ فیس"`) prints individual letters disconnected and reversed (`"ن ا خ م ص ا ع"`).

Wrap all ReportLab Urdu string variables in an explicit reshaping pipeline:

```python
# app/reports/urdu_formatter.py
import arabic_reshaper
from bidi.algorithm import get_display

def format_urdu(text: str) -> str:
    """Reshapes cursive ligatures and applies bidirectional reordering for ReportLab PDF rendering."""
    if not text:
        return ""
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)
```

Include `arabic-reshaper` and `python-bidi` in `requirements.txt`.

### 21. Field-Verified Pakistani Fee Schema (`fee_heads`, `fee_invoices`, `fee_invoice_items`) & `num2words`

Real-world Pakistani fee vouchers (e.g., KIPS, Punjab private schools) require:
1. **Itemized Charge Breakdown**: *Admission Fee*, *Tuition Fee*, *Lab Fee*, *Library Fee* instead of a single flat amount.
2. **Two-Tier Due Dates**: **Due Date** (e.g., 10th of month) and **Valid Until / Expiry Date** (e.g., 20th of month), after which banks and offices reject vouchers without late surcharge.
3. **Currency Totals in Words**: Voucher footers mandate *Amount in Words* (`"Two Thousand Nine Hundred Rupees Only"` / `"کل روپے: دو ہزار نو سو روپے صرف"`). Include `num2words` in `requirements.txt`.

#### Relational Fee Schema & Strict Financial Ledger Foreign Key Rule

```sql
-- Dynamic fee categories (Tuition, Lab, Transport, Admission)
CREATE TABLE fee_heads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    urdu_name TEXT,
    is_recurring INTEGER DEFAULT 1
);

-- Master invoice record
CREATE TABLE fee_invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    enrollment_id INTEGER NOT NULL,
    session_id INTEGER NOT NULL,
    month_year TEXT NOT NULL,       -- Format: YYYY-MM
    issue_date TEXT NOT NULL,       -- ISO-8601 YYYY-MM-DD
    due_date TEXT NOT NULL,
    valid_until TEXT NOT NULL,
    late_fee_amount TEXT DEFAULT '0.00',
    total_payable TEXT NOT NULL,
    discount_amount TEXT DEFAULT '0.00',
    net_due TEXT NOT NULL,
    FOREIGN KEY (enrollment_id) REFERENCES enrollments(id) ON DELETE RESTRICT
);

-- Itemized breakdowns on vouchers (Safe cascade on invoice deletion)
CREATE TABLE fee_invoice_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL,
    fee_head_id INTEGER NOT NULL,
    amount TEXT NOT NULL,
    FOREIGN KEY (invoice_id) REFERENCES fee_invoices(id) ON DELETE CASCADE,
    FOREIGN KEY (fee_head_id) REFERENCES fee_heads(id)
);

-- Financial payment receipts (MANDATORY RESTRICT: prevents deleting invoices with issued receipts!)
CREATE TABLE payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL,
    amount TEXT NOT NULL,
    payment_date TEXT NOT NULL,
    receipt_number TEXT NOT NULL UNIQUE,
    payment_method TEXT NOT NULL,
    recorded_by_user_id INTEGER,
    note TEXT,
    FOREIGN KEY (invoice_id) REFERENCES fee_invoices(id) ON DELETE RESTRICT
);
```

### 22. Thread Pool Executor for UI Freeze Prevention (`ThreadPoolExecutor` + `root.after`)

In CustomTkinter, running long operations synchronously in button callbacks (e.g. generating batch vouchers for 500 students or syncing Google Drive backups) locks the main GUI thread, triggering Windows *"Not Responding"* dialogs.

All long tasks must execute in a background `ThreadPoolExecutor` worker pool and safely post UI updates back to the main thread via `root.after(0, callback)`:

```python
# app/ui/async_runner.py
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=4)

def run_async(root, background_func, on_complete_func):
    def worker():
        result = background_func()
        root.after(0, lambda: on_complete_func(result))
    executor.submit(worker)
```

### 23. Windows High-DPI Scaling Awareness (`SetProcessDpiAwareness`)

Modern Windows laptops (1080p to 4K displays) use 125%, 150%, or 200% OS display scaling. Without explicit DPI awareness declarations, CustomTkinter windows appear blurry or suffer from misaligned grid borders.

The main application entry point (`app.py`) must declare per-monitor DPI awareness before creating UI widgets:

```python
# app.py
import sys
import ctypes

def init_windows_dpi():
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI awareness (v2)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
```

### 24. Pinned Core Dependencies (`requirements.txt`)

The official Phase 1 `requirements.txt` specifies all required libraries:

```text
customtkinter>=5.2.0
reportlab>=4.1.0
arabic-reshaper>=3.0.0
python-bidi>=0.4.2
num2words>=0.5.13
openpyxl>=3.1.2
pytest>=8.0.0
pytest-cov>=4.1.0
```

---

## 4B. Comprehensive Technology Stack Matrix (MVP to Enterprise)

The following matrix defines the end-to-end technology stack evolution across all product growth phases. This specification serves as an authoritative reference for software architecture reviews, database modeling, and technical evaluation by database and system architecture experts.

| Architectural Layer | Phase 1–4: Offline Desktop MVP | Phase 5–6: Multi-User Web Application | Phase 7: Mobile Ecosystem | Phase 8: Enterprise & Multi-Branch | Strategic / Technical Rationale |
|---|---|---|---|---|---|
| **Primary Language / Runtime** | Python 3.11+ | Python 3.11+ | Dart (Flutter 3.x) | Python 3.11+ / Go (Optional Services) | Single primary language (Python) across desktop & web backend maximizes code reuse. |
| **Database Engine** | SQLite 3 (WAL Mode Enabled) | PostgreSQL 16+ | SQLite / Isar (Mobile Local Cache) | PostgreSQL 16+ (Primary + Read Replicas) | SQLite for zero-config offline desktop; PostgreSQL for robust multi-user concurrency and ACID safety. |
| **Data Access & Abstraction** | Python `sqlite3` + Parameterized SQL & Repository Pattern | Django ORM + Migrations | Mobile Local Repositories + REST API Client | Django ORM / SQLAlchemy + Connection Pooling (pgBouncer) | Repository abstraction in MVP isolates SQL, allowing smooth migration to Django ORM in Phase 5. |
| **Monetary & Financial Math** | Python `Decimal` module | Python `Decimal` / Django `DecimalField` | String/Decimal handling in Dart | PostgreSQL `NUMERIC` / `DECIMAL` types | Strictly forbids floating-point arithmetic to prevent rounding errors on fees and balances. |
| **User Interface (UI)** | Python Tkinter / `customtkinter` | HTML5, CSS3, Vanilla JS / HTMX + Django Templates | Flutter Cross-Platform (Android & iOS) | Web Dashboard (Responsive CSS) | Lightweight native desktop UI in MVP; SSR HTML/HTMX for fast web rendering without SPA overhead. |
| **Business Logic Layer** | Reusable Domain Services (`services/*.py`) | Shared Domain Services (`apps/*/services.py`) | Mobile View Models / BLoC / Provider | Microservices / Domain-Driven Services | Decoupled domain services insulate business rules from UI frameworks across all platforms. |
| **Reporting & Voucher Print** | `ReportLab` / HTML-to-PDF (`WeasyPrint`) on A4 | `WeasyPrint` / `ReportLab` + CSS `@media print` | In-App PDF Viewer + Native OS Print Service | Headless PDF Generator Cluster + Storage | Native A4 3-panel fee voucher generation (*School*, *Bank*, *Student* copies) and print optimization. |
| **Data Export / Exchange** | `csv` module, `openpyxl` (Excel) | `openpyxl`, `pandas`, CSV streams | PDF export & share via OS Intent | Automated Data Warehousing Exports (Parquet/CSV) | Enables school administrators to export reports for local analysis or external accounting. |
| **Localization & Fonts** | UTF-8 Phonetic Urdu Input + English/Bilingual A4 Prints | UTF-8, i18n (`gettext`), Urdu Naskh Fonts | Flutter i18n + Arabic/Urdu RTL layout | Multi-language tenant customization | Full support for typing Urdu student/guardian names with clean bilingual printed document templates. |
| **Backup & Data Protection** | USB 1-Click Snapshot (`.zip`/`.db`) + Google Drive Sync API | Automated `pg_dump`, S3/GCS backups, Point-in-time recovery | Encrypted Device Storage (Keychain/Keystore) | Automated Multi-Region Database Snapshots + Disaster Recovery | Ensures total data safety even under computer hardware failure or local power loss. |
| **Task Queue & Async Work** | Background Python Threads (`threading`) | Celery + Redis | Async Dart Future/Streams | Celery Cluster / Redis Queue | Offloads PDF generation, cloud backups, and notifications from the main execution thread. |
| **Testing & Quality** | `pytest`, `pytest-cov`, `unittest.mock` | `pytest-django`, `coverage.py`, Playwright E2E | `flutter_test`, Integration Tests | CI/CD Automated Test Matrix (GitHub Actions) | Ensures high test coverage for financial calculations, grading logic, and data constraints. |
| **Packaging & Deployment** | `PyInstaller` / `Inno Setup` (Windows `.exe`) | Gunicorn + Nginx on Linux VPS / Managed Cloud | Google Play Store / Apple App Store (`.apk`/`.aab`/`.ipa`) | Docker, Docker Compose, Kubernetes / Managed Cloud | One-click Windows desktop installer for non-technical school staff; containerized cloud web deployment. |

---

## 4C. Final Architectural Sign-off

The core architecture, database design, localized print layout, code patterns, and technical stack matrix have received final technical sign-off across all evaluation categories:

| Evaluation Check | Status | Verification Detail |
|---|---|---|
| **Data Integrity** | **APPROVED** | `Decimal` monetary storage via `TEXT` type adapters, derived payment statuses, and append-only financial ledger. |
| **Engine Safety** | **APPROVED** | WAL mode, synchronous normal, and runtime foreign-key enforcement on SQLite connections. |
| **Bilingual Workflow** | **APPROVED** | UTF-8 DB columns, phonetic input, bilingual A4 headers, and bundled Urdu TrueType fonts. |
| **Maintainability** | **APPROVED** | Clear boundary separation (`ui/` -> `services/` -> `database.py`) providing a smooth migration to Django ORM in Phase 5. |

With this sign-off complete, the project is cleared to proceed directly to **Phase 1: Repository architecture, testing harness & foundation codebase setup**.

---

## 4D. UI/UX Architecture, Visual Design System & Backend Technical Specifications

This section defines the visual design system, typography hierarchy, screen wireframe architecture, layout patterns, visual mockup demonstrations, and backend software engineering contracts across the entire application lifecycle.

### 1. Visual Design System & Theme Token Architecture

The application uses a modern, high-contrast visual design system. In `customtkinter` (Desktop Phase 1–4) and Django/Tailwind CSS (Web Phase 5+), styles are driven by central JSON theme tokens (`config/theme.json`).

#### Color Palette Tokens

| Token Name | Dark Mode HSL / Hex | Light Mode HSL / Hex | Usage / UI Purpose |
|---|---|---|---|
| `color.bg.app` | `#0F172A` (Slate 900) | `#F8FAFC` (Slate 50) | Main window background |
| `color.bg.card` | `#1E293B` (Slate 800) | `#FFFFFF` (Pure White) | KPI cards, data tables, modals |
| `color.bg.sidebar` | `#020617` (Slate 950) | `#1E293B` (Slate 800) | Navigation sidebar |
| `color.brand.primary` | `#10B981` (Emerald 500) | `#059669` (Emerald 600) | Primary buttons, active states |
| `color.brand.accent` | `#3B82F6` (Blue 500) | `#2563EB` (Blue 600) | Highlights, links, badge borders |
| `color.text.primary` | `#F8FAFC` (Slate 50) | `#0F172A` (Slate 900) | Headings, grid text, field values |
| `color.text.secondary` | `#94A3B8` (Slate 400) | `#64748B` (Slate 500) | Subtitles, labels, table headers |
| `color.status.paid` | `#10B981` (Emerald) | `#059669` (Emerald) | Paid status badges & indicators |
| `color.status.partial` | `#F59E0B` (Amber) | `#D97706` (Amber) | Partial payment status badges |
| `color.status.unpaid` | `#EF4444` (Red) | `#DC2626` (Red) | Overdue & unpaid status badges |

#### Layout & Radius Tokens
- `radius.card`: `8px` rounded corners for containers & modal dialogs.
- `radius.button`: `6px` rounded corners for interactive buttons.
- `radius.input`: `4px` rounded corners for text inputs and dropdowns.
- `spacing.padding`: `16px` inner padding for cards; `24px` for main view containers.

---

### 2. Typography & Font Management Hierarchy

#### English Typography (UI & Reports)
- **Primary Font Stack**: `Inter`, `Segoe UI`, `SF Pro Display`, `sans-serif`.
- **H1 Page Title**: 24pt Bold (Tracking -0.02em).
- **H2 Section Header**: 18pt Semi-Bold.
- **Data Grid / Form Labels**: 11pt Medium / Regular.
- **Small Badges & Captions**: 9pt Medium (Uppercase tracking).

#### Urdu Typography & Font Rendering
- **Bundled TrueType Font**: `Noto Naskh Arabic` (`assets/fonts/NotoNaskhArabic-Regular.ttf`).
- **Storage & Input**: Full UTF-8 string support for direct Phonetic Urdu keyboard typing.
- **ReportLab Registration**: Loaded during app boot via `pdfmetrics.registerFont(TTFont("UrduFont", path))`.
- **Direction**: Right-to-Left (RTL) text alignment for Urdu student/guardian name fields on A4 vouchers and report cards.

---

### 3. Screen Layout & Wireframe Architecture

#### App Shell Layout Structure (Desktop & Web)
```text
┌──────────────────────────────────────────────────────────────────────────┐
│  BRAND LOGO   │ 🔍 Search student, receipt...          🔔  ⚙️ Admin User │ [Header Bar]
├───────────────┼──────────────────────────────────────────────────────────┤
│ 📊 Dashboard  │  ┌──────────────────┐  ┌──────────────────┐              │
│ 👨‍🎓 Students   │  │ Total Students   │  │ Monthly Fees     │ [KPI Cards]  │
│ 🗓️ Attendance │  │      450         │  │   Rs 245,000     │              │
│ 💳 Fees & Pay  │  └──────────────────┘  └──────────────────┘              │
│ 📝 Exams      │  ┌────────────────────────────────────────────────────┐  │
│ 📄 Reports    │  │ Student Name   Class   Receipt ID  Amount  Status  │  │ [Data Grid]
│ ⚙️ Settings   │  │ Aryan Sharma   10-A    #REC1124   Rs 3,500 [PAID] │  │
└───────────────┴──┴────────────────────────────────────────────────────┴──┘
 [Left Sidebar]                         [Main Workspace Area]
```

#### 3-Panel A4 Fee Voucher Wireframe Geometry
- **Dimensions**: Single Portrait A4 sheet ($595.27 \times 841.89$ points).
- **Structure**: Divided into 3 horizontal panels (~280 points tall each):
  1. **Top Panel**: *School Copy* (Archived in office register).
  2. **Middle Panel**: *Accounts / Bank Copy* (Kept by cashier/bank).
  3. **Bottom Panel**: *Student / Parent Copy* (Handed to parent).
- **Cut Lines**: Separated by dashed lines `- - - ✂ Cut Here - - -`.

---

### 4. Visual Demonstration Screen Mockups

Below are visual design mockups demonstrating the target user interface aesthetic and document print layout:

#### A. Desktop Dashboard UI Demonstration
![Desktop UI Dashboard Mockup](C:\Users\abdul\.gemini\antigravity-ide\brain\193739a1-e3f0-4d7d-8637-32b6bceca6ac\desktop_dashboard_ui_mockup_1789508476758.jpg)

#### B. 3-Panel A4 Fee Voucher Print Layout Demonstration
![3-Panel A4 Fee Voucher Mockup](C:\Users\abdul\.gemini\antigravity-ide\brain\193739a1-e3f0-4d7d-8637-32b6bceca6ac\fee_voucher_a4_mockup_1789508495919.jpg)

---

### 5. End-to-End Backend Requirements & Data Flow Specifications

#### Data Access Contracts (`database.py`)
- Thread-safe SQLite connection factory with explicit `Decimal` adapters/converters.
- Connection Pragmas: `PRAGMA foreign_keys = ON;`, `PRAGMA journal_mode = WAL;`, `PRAGMA synchronous = NORMAL;`.

#### Service Layer State Machines
1. **`fee_service.py`**:
   - `generate_monthly_invoices(session_id, month_year)` -> Calculates base tuition and fee heads, adds late fees, applies discounts, creates `FeeInvoice` and `FeeInvoiceItem` records.
   - `record_payment(invoice_id, amount, payment_method, user_id)` -> Appends financial ledger transaction (`payments` table), recalculates balance, updates invoice status (`Paid`, `Partially Paid`).
2. **`attendance_service.py`**:
   - `mark_daily_attendance(enrollment_ids, date, status_map)` -> Validates `Unique(enrollment_id, date)` constraint, saves daily records.
3. **`backup_service.py`**:
   - `perform_local_daily_backup()` -> Saves timestamped database snapshots to `data/backups/daily/`.
   - `sync_to_google_drive()` -> Background sync to Google Drive API when internet is active.

---

## 5A. Approved product direction summary

The software should follow this validated direction:

1. Start with a focused local product for schools and academies in Punjab.
2. Use Python as the learning and product foundation, starting directly with proper repository setup, testing harnesses, and service architecture.
3. Target standard A4 printers (3-panel fee vouchers) and dual USB + Google Drive backups.
4. Support phonetic Urdu keyboard entry while maintaining clean English/bilingual print layouts.
5. Flexible schema supporting both Private School (Class/Section) and Tuition Academy (Subject/Batch) models.
6. Keep the system offline-friendly with automated cloud sync when connected.
7. Focus on daily administrative pain points where schools repeatedly lose time and make errors.
8. Build using reusable business logic services (`fee_service.py`, `attendance_service.py`) and a clean data model.
9. Move to the web version (Django + PostgreSQL) only after the desktop workflows are proven useful.
10. Add mobile access (Flutter) only after backend stability and real usage are confirmed.

This keeps the project realistic, learnable, and commercially relevant.

## 5. Recommended product direction

Build an English/Urdu, offline-friendly fee, attendance, and examination management system for small private schools and tuition academies in Punjab.

### Recommended first commercial package

Start with these modules:

1. Students
2. Classes, sections, and batches
3. Attendance
4. Fees
5. Receipts
6. Tests and marks
7. Reports

Then add the remaining modules according to verified customer demand.

## 6. Development principles

### Build in vertical slices

Each milestone should produce a small feature that works from input to stored data to output. For example:

```text
Register student -> Save student -> Search student -> Print student summary
```

This is better than building every database table first and delaying a usable result.

### Keep business logic separate

Use a layered design:

```text
Presentation layer  -> screens, forms, buttons, web pages
Application layer   -> workflows and permissions
Domain layer        -> fees, attendance, marks, grading rules
Data layer          -> database queries, migrations, backups
Testing layer       -> unit, integration, and end-to-end tests
```

Maintain strict separation between UI screens, service workflows, and data access. Reuse this layered architectural pattern across the desktop MVP and future web version.

### Prefer configuration over hard-coding

School rules vary. Store configurable values for:

- Academic session
- Fee types
- Discount rules
- Late-fee policy
- Subjects
- Maximum marks
- Grade boundaries
- Pass marks
- Attendance statuses
- Receipt numbering
- Institution name and logo

### Protect data from the beginning

Student and financial data are sensitive. Plan for:

- Authentication
- Role-based permissions
- Strong passwords
- Backups
- Restore testing
- Audit logs for important changes
- Minimum necessary personal data
- Safe error messages
- Secure deployment
- Clear data ownership and deletion procedures

Do not collect CNIC numbers or other sensitive information unless a real requirement has been confirmed and the data protection process is understood.

## 7. Complete learning and development sequence

### Phase 0: Discovery and validation before coding

#### Learning objectives

- Understand the difference between a user problem and a software feature.
- Learn how to interview users without leading them to a preferred answer.
- Learn to write a small requirements document.

#### Activities

Speak with at least:

- One school owner or director
- One principal or head teacher
- One accountant or office clerk
- One teacher
- One parent or student, if appropriate
- One senior developer

Ask:

- How are students currently registered?
- How are attendance records stored?
- How are fees generated and collected?
- How are discounts and arrears handled?
- How are results calculated?
- What reports are printed each month?
- Which tasks cause the most errors?
- What software is already being used?
- What happens when the internet is unavailable?
- What data must remain private?
- Who approves a correction to a fee or mark?
- What would make staff willing to change systems?
- What would they pay for installation, training, and support?

#### Deliverables

Create:

- Problem statement
- Target customer description
- Current workflow notes
- Feature priority list
- First pilot institution profile
- Risks and open questions
- Written confirmation of the first MVP scope

#### Exit criteria

Do not proceed to a large build until at least one real institution agrees to review a prototype or pilot.

### Phase 1: Repository architecture, testing harness & foundation codebase setup

#### Objectives & Skills

Focus directly on professional project scaffolding, developer tooling, and automated testing setups before writing domain code:

- Repository directory structure design (`app/`, `services/`, `models/`, `ui/`, `tests/`, `config/`)
- Virtual environment setup (`venv`) and dependency management (`requirements.txt`)
- Python type hints (`typing`), docstrings, and clean code principles
- Automated testing harness setup with `pytest` / `unittest`
- Application configuration management (environment variables & settings files)
- Structured logging, exception handling, and custom error classes
- Git repository setup, `.gitignore`, and clean commit conventions

#### Scaffold Activities

1. **Initialize Project Repository**: Establish project layout, `.gitignore`, virtual environment, and initial dependencies.
2. **Build Core Logging & Exception Layer**: Implement central logger and custom domain exceptions (`ValidationError`, `DomainError`, `DatabaseError`).
3. **Configure Testing Infrastructure**: Set up `pytest` / `unittest` runner, test fixtures, and sample data generators.
4. **Define Base Service Interfaces**: Create stubbed service modules (`fee_service.py`, `student_service.py`, `attendance_service.py`) with type annotations and docstrings.
5. **Database Connection Harness**: Create SQLite connection manager with thread safety and basic schema initialization hooks.

#### Exit criteria

The codebase structure is initialized, automated tests run cleanly, logging and exception mechanisms are verified, and base service modules are ready for database layer implementation in Phase 2.

### Phase 2: Data modeling and SQLite

#### Why this phase matters

A school system needs persistent records. Lists and text files are useful for learning but are not enough for reliable searching, relationships, reporting, and concurrent workflows.

#### Skills

- Relational database concepts
- Tables, rows, columns, and primary keys
- Foreign keys and relationships
- SQL `SELECT`, `INSERT`, `UPDATE`, and `DELETE`
- Constraints and indexes
- Transactions
- SQLite with Python
- Database migrations or schema versioning
- Backup and restore

#### Initial data model

Begin with a small schema:

```text
Institution
  - id
  - name
  - address
  - phone
  - language preference

AcademicSession
  - id
  - name
  - start_date
  - end_date

Student
  - id
  - admission_number
  - full_name
  - guardian_name
  - guardian_phone
  - date_of_birth (optional)
  - active status

ClassGroup
  - id
  - name
  - section or batch
  - session_id

Enrollment
  - id
  - student_id
  - class_group_id
  - session_id
  - enrollment_date
  - status

AttendanceRecord
  - id
  - student_id
  - date
  - status
  - note

FeeHead
  - id
  - name (e.g. Tuition, Lab, Admission, Library)
  - urdu_name
  - is_recurring

FeeInvoice
  - id
  - enrollment_id
  - session_id
  - month_year (YYYY-MM)
  - issue_date
  - due_date (e.g. 10th of month)
  - valid_until (e.g. 20th of month)
  - late_fee_amount
  - total_payable
  - discount_amount
  - net_due
  - status (Unpaid, Partially Paid, Paid)

FeeInvoiceItem
  - id
  - invoice_id
  - fee_head_id
  - amount

Payment (Auditable Ledger Transaction)
  - id
  - invoice_id
  - amount
  - payment_date
  - receipt_number
  - payment_method
  - recorded_by_user_id
  - note

Subject
  - id
  - name
  - maximum_marks

Exam
  - id
  - name
  - session_id
  - date

Mark
  - id
  - exam_id
  - student_id
  - subject_id
  - marks
```

This is a starting model. Review it with a senior developer before implementing production data storage.

#### Deliverables

- Database schema diagram
- SQLite prototype
- Seed data for development
- Backup command or screen
- Restore procedure
- Tests for database operations

#### Exit criteria

You can create, search, update, and delete test records and can restore a backup successfully.
### Phase 3: Desktop MVP with Tkinter

#### Purpose

Build an offline desktop prototype for a single institution or office computer.

#### Technology

```text
Python + Tkinter + SQLite + unittest
```

#### Screens

1. Dashboard
2. Student registration
3. Student search and profile
4. Class and batch management
5. Daily attendance
6. Fee generation
7. Payment and receipt entry
8. Defaulter report
9. Subject and exam setup
10. Marks entry
11. Report card preview and print
12. Backup and restore
13. Settings and institution profile

#### MVP workflow

##### Student registration

```text
Open registration -> Enter required fields -> Validate -> Save -> Show admission number
```

##### Attendance

```text
Choose date and class -> Load enrolled students -> Mark present/absent/late -> Save -> Print summary
```

##### Fees

```text
Choose session and month -> Generate fee records -> Apply discount or late fee -> Receive payment -> Print receipt
```

##### Results

```text
Choose exam and class -> Enter marks -> Validate limits -> Calculate totals and grades -> Preview -> Print report
```

#### Desktop quality requirements

- Clear labels and form validation
- Keyboard-friendly navigation where practical
- Helpful error messages
- No data loss when a form is incomplete
- Confirmation before destructive actions
- Search by admission number and name
- Print-friendly output
- Manual backup and restore
- Installation instructions
- Test data reset for demonstrations

#### Packaging

Investigate packaging only after the application works:

- PyInstaller or an equivalent packaging tool
- Windows installer
- Application icon
- Version number
- Upgrade procedure
- Backup before upgrade
- Uninstall behavior

#### Exit criteria

One pilot institution can complete a real weekly workflow using the desktop MVP with guidance, and all critical calculations have automated tests.

### Phase 4: Testing and quality discipline

#### Test pyramid

Use a balanced approach:

- Unit tests for fee, attendance, grading, and validation functions
- Integration tests for database and service workflows
- End-to-end tests for critical user journeys
- Manual usability checks with a teacher or administrator

#### Required test areas

##### Fees

- Correct monthly amount
- Discount calculation
- Sibling discount
- Late fee
- Partial payment
- Overpayment handling
- Duplicate payment prevention
- Receipt numbering
- Defaulter status

##### Attendance

- One record per student per date
- Present, absent, late, and excused statuses
- Editing a record
- Monthly percentage
- Duplicate prevention
- Empty class handling

##### Results

- Marks cannot exceed maximum marks
- Missing marks are handled explicitly
- Total and percentage are correct
- Grade boundaries are configurable
- Pass/fail rules are clear
- Ranking rules are approved by the institution

##### Security and permissions

- Users can access only permitted areas
- Sensitive records are not exposed in error messages
- Backups do not contain unnecessary secrets
- Logout works
- Password changes work

#### Development workflow

```text
Write requirement -> Write test -> Run test -> Implement -> Run tests -> Refactor -> Review with user
```

Test-driven development is optional, but useful for calculations and rules:

```text
RED: write a failing test
GREEN: write the smallest code that passes
REFACTOR: improve the design while keeping tests green
```

#### Exit criteria

The test suite is repeatable, important business rules are covered, and a teacher has tested the workflows using realistic examples.

### Phase 5: Web application for multi-user access

#### When to start

Start this phase after the desktop or prototype workflows have been validated. Do not rewrite the product for the web before confirming that users actually need multi-user or remote access.

#### Recommended technology direction

```text
Frontend: HTML, CSS, JavaScript
Backend: Python with Django
Database: PostgreSQL
Reports: PDF generation and print styles
Deployment: managed cloud hosting
```

Django is a practical choice for this product because it provides a mature structure for models, forms, authentication, administration, URLs, and permissions.

#### Web architecture

```text
Browser
  -> Web pages and forms
  -> Django views or service layer
  -> Domain rules
  -> PostgreSQL database
  -> Reports, email, or notification services
```

#### Web modules

- Institution and branch setup
- User accounts and roles
- Students and guardians
- Classes, sections, and sessions
- Attendance
- Fees and payments
- Exams and marks
- Reports and exports
- Notices
- Audit history
- Backups and administration

#### Multi-tenant decision

Decide with a senior developer whether the first web version supports:

- One institution per deployment, or
- Multiple institutions in one hosted system

Multi-tenant software requires careful data isolation, billing, support, backups, and security. A single-institution deployment may be simpler for the first commercial pilot.

#### Web security requirements

- HTTPS
- Secure password hashing
- Role-based authorization
- CSRF protection
- Input validation
- Database constraints
- Rate limiting where needed
- Secure session settings
- Audit logs
- Regular backups
- Restore testing
- Access review
- Privacy policy and terms of service

#### Exit criteria

At least one institution can use the web system with multiple user roles, and the deployment has tested backup, restore, security, and monitoring procedures.

### Phase 6: Reports, exports, and communication

#### Reports

Build and validate:

- Student list
- Class register
- Daily attendance
- Monthly attendance percentage
- Fee collection summary
- Defaulter list
- Individual receipt
- Monthly fee statement
- Exam marks sheet
- Class result summary
- Individual report card
- Teacher allocation
- Expense summary
- Inventory report

#### Export formats

Support according to verified customer need:

- PDF for printing and sharing
- CSV for simple data exchange
- Excel-compatible output for school offices
- Print-optimized HTML

#### Communication

Start with safe, low-dependency options:

- Printable notices
- Copyable WhatsApp-ready messages
- Exportable contact lists
- In-app notices

Later evaluate:

- SMS provider integration
- Email
- WhatsApp Business provider integration
- Push notifications

Confirm consent, costs, provider rules, and privacy requirements before sending messages automatically.
### Phase 7: Mobile applications

#### Do not start mobile development too early

A mobile application is not a replacement for a backend. It requires authentication, APIs, database rules, notifications, app maintenance, and support.

Build mobile access after the web workflows and API are stable.

#### Suggested technology

Consider Flutter for a cross-platform mobile application after validating the product.

#### Teacher app

- Login
- Assigned classes
- Attendance entry
- Marks entry
- Homework
- Notices
- Offline draft and later synchronization, if required

#### Parent app

- Child profile
- Attendance
- Fees and receipts
- Results
- Homework
- Notices
- Support contact

#### Student app

- Timetable
- Homework
- Results
- Attendance
- Notices

#### Mobile requirements

- Secure token handling
- Device logout
- Minimal personal data on the device
- Offline behavior defined clearly
- Synchronization conflict rules
- Notification consent
- Accessibility and readable Urdu text
- App-store policies
- Crash reporting and support

#### Exit criteria

The mobile app solves a validated user problem, uses a stable backend API, and has tested authentication, permissions, offline behavior, and notification consent.

### Phase 8: Advanced modules

Add only when customer demand and operational capacity justify them.

#### Admissions and document tracker

- Applicant pipeline
- Document checklist
- Merit or selection list
- Admission fee
- Enrollment conversion
- Correction history

#### Teacher and staff management

- Staff profiles
- Attendance
- Leave requests
- Salary calculations
- Role assignments
- Employment documents

#### Lesson planning and homework

- Syllabus setup
- Lesson progress
- Homework assignments
- Parent visibility
- Completion reports

#### Inventory and expenses

- Suppliers
- Purchase orders
- Stock receipts
- Stock issues
- Asset register
- Expense approvals
- Monthly reports

#### Transport

- Vehicles
- Routes
- Drivers
- Student assignment
- Transport fees
- Maintenance records
- Emergency contacts

#### Branches and franchises

- Branch-level permissions
- Central reporting
- Shared configuration
- Branch billing
- Data isolation

#### Analytics

- Enrollment trends
- Attendance trends
- Fee collection trends
- Subject performance
- At-risk student indicators

Analytics must be explainable and used as support for staff decisions, not as an automatic judgment of a student or teacher.

## 8. Local Punjab requirements to validate

Confirm these items with each pilot institution because practices vary:

- Academic year or session naming
- Class and section structure
- Matric, intermediate, or institution-specific grading
- Subject names and maximum marks
- Pass marks and grade boundaries
- Position and ranking policy
- Monthly, quarterly, or annual fee structure
- Admission and registration numbers
- Sibling and need-based discounts
- Late-fee rules
- Refunds and withdrawals
- Urdu and English spelling requirements
- Receipt and report-card formats
- Parent communication preferences
- Offline requirements
- Data retention and archive policy
- Staff permissions
- Board-related information, if used
- Local currency and date formats

Never assume that one school's rules apply to every school.

## 9. Product validation and sales plan

### Before building the commercial version

1. Interview at least ten schools or academies.
2. Document their current tools and workflows.
3. Identify the most expensive or frustrating repeated problem.
4. Show a clickable mockup or small working prototype.
5. Ask one institution to run a time-limited pilot.
6. Measure time saved and errors avoided.
7. Record feature requests but do not accept all requests immediately.
8. Ask for a paid pilot, installation fee, or support agreement when appropriate.

### Questions that reveal real demand

- What do you use today?
- What does it cost in money or staff time?
- Which report takes the longest to prepare?
- What errors occur most often?
- Who approves corrections?
- What happens when the internet is down?
- What data must be printed?
- What would make you change software?
- Can I observe the workflow?
- Would you run a pilot for one class or branch?

### Sales channels

- Direct visits to local schools and academies
- Demonstrations through teacher and administrator networks
- Local computer and education service providers
- Facebook and WhatsApp business communities
- Referrals from accountants or school consultants
- Local software resellers
- A simple website with screenshots and contact details

### Pricing approaches to evaluate

- One-time installation plus training
- Monthly subscription
- Annual subscription
- Per-branch pricing
- Free pilot with paid support
- Basic, standard, and professional packages

Validate willingness to pay before selecting the final model. Include support, backups, updates, and training in the commercial discussion.

## 10. Operational and legal considerations

Before selling widely, obtain appropriate professional advice about:

- Business registration
- Tax and invoicing obligations
- Software licensing
- Open-source license compliance
- Privacy policy
- Terms of service
- Data ownership
- Data deletion and export
- Support responsibilities
- Service availability commitments
- Payment collection
- App-store requirements
- Use of school logos, student photographs, and personal data

Do not promise government approval, official board integration, or regulatory compliance without written confirmation.

## 11. Project management system for learning

Use a simple progress board with these columns:

```text
Backlog -> Ready -> In progress -> Review -> Tested -> Done
```

Every task should contain:

- User problem
- Acceptance criteria
- Files or module area
- Test cases
- Review questions
- Notes from the teacher or developer

Example task:

```text
Task: Record a student's monthly fee payment
Acceptance criteria:
- Select an enrolled student.
- Show the current fee and outstanding balance.
- Accept a valid payment amount.
- Reject negative or excessive values according to the approved rule.
- Generate a unique receipt number.
- Save the payment.
- Show the updated balance.
- Add unit and integration tests.
```

### Review rhythm

- Weekly: review learning and coding progress
- At the end of each module: test with realistic sample data
- At each milestone: review with a senior developer
- Before product decisions: review with a teacher or administrator
- Before deployment: conduct a security and backup review
## 12. Recommended repository structure as the project grows

### Early desktop version

```text
classfellow/
├── app/                        # Application runtime & entry point
│   └── app.py
├── assets/                     # Application assets & fonts
│   └── fonts/                  # NotoNaskhArabic-Regular.ttf
├── database.py                 # SQLite connection manager & migrations
├── models.py                   # Data models / DTOs
├── services/                   # Plain Python domain business logic
│   ├── student_service.py
│   ├── fee_service.py
│   ├── attendance_service.py
│   └── backup_service.py
├── ui/                         # CustomTkinter GUI screens & dialogs
├── reports/                    # ReportLab A4 PDF voucher & report generators
│   └── urdu_formatter.py       # Arabic/Urdu ligature reshaper pipeline
├── tests/                      # Automated pytest unit & integration tests
├── config/                     # Settings & JSON theme tokens
├── data/                       # Local SQLite database & daily backups
│   └── backups/
├── docs/srs/                   # Formal SRS Specifications
├── requirements.txt            # Pinned dependencies
└── README.md
```

### Later web version

```text
classfellow_web/
├── manage.py
├── config/
├── apps/
│   ├── accounts/
│   ├── institutions/
│   ├── students/
│   ├── attendance/
│   ├── fees/
│   ├── examinations/
│   ├── reports/
│   └── notices/
├── templates/
├── static/
├── tests/
├── requirements.txt
└── README.md
```

The exact structure should be reviewed with a senior developer before it becomes large.

## 13. Definition of done for a feature

A feature is not complete merely because it appears on screen. It is complete when:

- The workflow is understood by a real user.
- Inputs are validated.
- The data model is correct.
- Permissions are considered.
- Errors are visible and helpful.
- Unit tests cover business rules.
- Integration tests cover data persistence where needed.
- Reports and exports are checked.
- Backup and restore implications are understood.
- Documentation is updated.
- A teacher or administrator has reviewed the result.
- The feature does not break existing tests.

## 14. Success measurements

Measure outcomes rather than only counting features.

### User outcomes

- Time required to register a student
- Time required to prepare a monthly fee report
- Time required to create report cards
- Number of calculation errors
- Number of duplicate or missing records
- Staff adoption rate
- Parent response to notices

### Product outcomes

- Number of active institutions
- Number of active users
- Monthly retention
- Support requests per institution
- Backup success rate
- Report generation success rate
- Paid conversion after pilot
- Revenue compared with support cost

### Learning outcomes

- Can explain the architecture
- Can write and run tests
- Can design a database table and relationship
- Can debug a failed workflow
- Can deploy and restore a test instance
- Can discuss trade-offs with a senior developer

## 15. Risks and mitigations

| Risk | Possible impact | Mitigation |
|---|---|---|
| Building too many features before validation | Months of wasted work | Start with a small paid or supervised pilot |
| Incorrect local grading or fee rules | Wrong reports and loss of trust | Confirm rules with multiple institutions |
| Data loss | Serious operational damage | Automated and manual backups; test restore |
| Poor permissions | Unauthorized data access | Roles, least privilege, and access tests |
| Internet failure | Staff cannot work | Offline desktop mode or documented offline workflow |
| Scope expansion | Delayed release | Maintain an MVP and reject unvalidated requests |
| Weak support process | Unhappy customers | Document installation, training, and issue handling |
| Language and printing problems | Reports unusable | Test Urdu, fonts, A4 printing, and real printers |
| Over-reliance on one developer | Maintenance difficulty | Documentation, tests, code review, backups |
| Direct messaging costs or policy issues | Unexpected expense or blocked service | Start with manual notices; validate providers |
| Security vulnerabilities | Privacy and legal risk | Security review before public deployment |

## 16. Questions for the professional review meeting

### Questions for a school teacher or administrator

- Which three tasks consume the most time each week?
- Which reports must be printed?
- What fields are required at admission?
- How do you handle transfers and withdrawals?
- How are corrections approved?
- Which attendance statuses do you use?
- How are fees discounted or refunded?
- How are exams and grades calculated?
- Which users need access to which information?
- Would offline operation be necessary?
- Would you test an early version with real but safe sample data?

### Questions for a senior developer

- Is the proposed data model normalized enough for the expected scope?
- Should the first product be single-institution or multi-tenant?
- Should the desktop prototype share domain logic with the future web version?
- Which Django architecture and testing strategy should be used?
- How should backups and migrations work?
- How should Urdu text, fonts, and right-to-left layouts be supported?
- How should roles and permissions be modeled?
- Which reports require a PDF library or print CSS?
- What security review is required before deployment?
- What deployment and monitoring setup is appropriate?
- Which features should explicitly be rejected from the first release?

### Decisions to record after the meeting

- Product name: **ClassFellow** (Target customers: Private Schools & Tuition Academies in Punjab)
- First pilot institution
- MVP modules
- Supported languages
- Offline or online behavior
- Fee rules
- Grading rules
- User roles
- Database choice
- Technology sequence
- Deployment approach
- Backup and support policy
- Pricing experiment
- Review date

## 17. Immediate next actions

1. Set up the project repository directory structure, virtual environment, and `.gitignore`.
2. Configure the automated testing framework (`pytest` / `unittest`) and logging setup.
3. Define base business service interfaces (`fee_service.py`, `student_service.py`, `attendance_service.py`).
4. Interview at least three local education professionals (school/academy administrators).
5. Write and validate the confirmed fee collection and attendance workflows.
6. Create the SQLite database schema and connection manager for students, enrollments, fees, and attendance.
7. Implement student registration workflow with validation.
8. Implement daily class/batch attendance workflow.
9. Implement fee generation and 3-panel A4 receipt printing module.
10. Add unit and integration tests for every fee calculation and validation rule.
11. Implement USB export and Google Drive automated backup sync.
12. Demonstrate the prototype to the pilot institution director and senior developer.

Do not skip the interviews and review steps. They prevent building a technically interesting product that does not match the real school workflow.

## 18. Final strategy

The full journey is:

```text
Repository & Testing Scaffold Setup
    -> SQLite Data Modeling & Service Layer
    -> Tkinter Offline Desktop MVP (Single Computer)
    -> Dual Backup (USB + Google Drive Sync) & A4 Printing Validation
    -> Pilot with a small academy or school
    -> Quality, reports, and support process
    -> Django Web Application (Multi-user / Multi-branch)
    -> Secure Hosted System with PostgreSQL
    -> Teacher and Parent Mobile Access (Flutter)
    -> Validated Advanced Modules (Inventory, Transport, Payroll)
    -> Sustainable local education software business
```

The best starting product is not the largest one. It is the smallest product that solves a real problem, can be tested with a real institution, and can grow without discarding the learning and code that came before it.

Use this document as a discussion draft. Finalize every business rule with a school professional and every architecture decision with a senior developer before treating it as a production specification.
