# ClassFellow - School & Academy Management Software

[![CI/CD Pipeline](https://github.com/UCC-Developer-platform/ClassFellow/actions/workflows/ci.yml/badge.svg)](https://github.com/UCC-Developer-platform/ClassFellow/actions)
[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: Proprietary](https://img.shields.io/badge/license-Proprietary-red.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Desktop-lightgrey.svg)](https://microsoft.com)

**ClassFellow** is a high-reliability, bilingual (English and Urdu), offline-friendly school and academy management software engineered specifically for small and medium private schools, intermediate colleges, and tuition coaching centers in Punjab, Pakistan.

---

## 🌟 Core Highlights

- **Offline-First Resilience**: Runs 100% locally on standard office computers with automated background sync when internet is connected.
- **Zero-Drift Financial Integrity**: All monetary values computed using Python's `Decimal` module and stored as `TEXT` in SQLite with custom type adapters.
- **Auditable Financial Ledger**: Payments are recorded as immutable financial events with strict `ON DELETE RESTRICT` constraints on fee invoices.
- **Dual Institutional Models**: Supports both **Class/Section** (Schools) and **Subject/Batch** (Tuition Academies) operational structures.
- **3-Panel A4 Fee Vouchers**: ReportLab PDF generator rendering standardized 3-panel vouchers (*School Copy*, *Accounts Copy*, *Student Copy*) on single A4 portrait sheets.
- **Bilingual & Urdu Text Shaping**: Direct UTF-8 phonetic Urdu keyboard entry with complex ligature reshaping via `arabic-reshaper` and `python-bidi`.
- **3-Tier Backup Architecture**: Local daily rolling 30-day backups (SQLite native online backup API), manual USB encrypted snapshots, and automated Google Drive cloud sync.
- **Modular Packaging**: Feature-flagged architecture (`config/modules.json`) enabling flexible commercial editions (Fee-Only, Standard, Professional Suite).

---

## 📁 Repository Directory Structure

```text
classfellow/
├── app/                        # Application runtime, UI shell & entry point
│   └── app.py
├── assets/                     # Application assets & bundled fonts
│   └── fonts/                  # NotoNaskhArabic-Regular.ttf
├── database.py                 # SQLite connection manager, pragmas & migrations
├── models.py                   # Data models & Data Transfer Objects (DTOs)
├── services/                   # Plain Python domain business logic
│   ├── student_service.py
│   ├── fee_service.py
│   ├── attendance_service.py
│   ├── exam_service.py
│   └── backup_service.py
├── ui/                         # CustomTkinter GUI screens, forms & modal dialogs
├── reports/                    # ReportLab A4 PDF voucher & report generators
│   └── urdu_formatter.py       # Arabic/Urdu ligature reshaper pipeline
├── scripts/                    # Utility & database seeding scripts
│   └── seed_demo_data.py
├── tests/                      # Automated pytest unit & integration tests
├── config/                     # Settings, JSON theme tokens & module flags
├── data/                       # Local SQLite database & daily backups
│   └── backups/
├── docs/srs/                   # Formal Software Requirements Specifications
├── .github/workflows/          # Automated GitHub Actions CI/CD pipeline
├── classfellow.spec            # PyInstaller Windows 64-bit build specification
├── installer.iss               # Inno Setup 6 Windows installer compiler script
├── requirements.txt            # Pinned production & development dependencies
└── README.md
```

---

## 📚 Software Requirements Specifications (SRS)

Formal specifications are documented in [`docs/srs/`](docs/srs/):

| Specification | Subsystem / Focus |
|---|---|
| [**SRS 00**](docs/srs/SRS_00_Overview_and_Modular_Architecture.md) | Modular Commercial Architecture, Packaging Tiers & Feature Flags |
| [**SRS 01**](docs/srs/SRS_01_Core_Kernel_and_Database_Spec.md) | Database Pragmas, `Decimal` Adapters, Auto-Migrations, 3-Tier Backups |
| [**SRS 02**](docs/srs/SRS_02_Student_and_Enrollment_Spec.md) | School vs. Academy Models, Student Identity, Guardian Metadata & Search Indexes |
| [**SRS 03**](docs/srs/SRS_03_Fee_and_Receipt_Module_Spec.md) | Itemized Fees, Ledger `RESTRICT`, 2-Tier Due Dates, 3-Panel A4 Vouchers |
| [**SRS 04**](docs/srs/SRS_04_Attendance_and_Notification_Spec.md) | Daily Roster Exceptions, `UNIQUE` Constraint, Free WhatsApp Payloads |
| [**SRS 05**](docs/srs/SRS_05_Examination_and_ReportCard_Spec.md) | Dynamic Subject Marks, Database Grade Tiers, Bilingual A4 Report Cards |

---

## 🚀 Getting Started

### Prerequisites
- **Python**: 3.11 or higher
- **OS**: Windows 10 / 11 (Supports Windows 7 SP1 with Python 3.8+)

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/UCC-Developer-platform/ClassFellow.git
   cd ClassFellow
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # Windows PowerShell:
   .venv\Scripts\Activate.ps1
   ```

3. Install pinned dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run automated tests:
   ```bash
   pytest
   ```

5. Launch application:
   ```bash
   python app/app.py
   ```

---

## 🧪 Demo Pilot Data Seeding

ClassFellow includes a self-contained CLI utility to seed a realistic Punjab educational institution pilot dataset:
- **1 Academic Session**: 2026-2027 (active)
- **3 Class Groups**: Class 9 - Green (`SchoolClass`), Class 10 - Gold (`SchoolClass`), Tuition Batch - 9th Physics (`AcademyBatch`)
- **15 Enrolled Students**: Bilingual English/Urdu names and normalized mobile numbers (`0300...`)
- **Monthly Billing Cycle**: 15 invoices for `2026-04` (5 Paid, 5 Partially Paid, 5 Unpaid Defaulters)
- **5-Day Class Attendance**: Roster exception logs (Present, Absent, Late, Leave)
- **Examination Subsystem**: First Term Exam 2026 with BISE Punjab grading tiers and class ranks

```bash
# Seed default database (data/classfellow.db)
python scripts/seed_demo_data.py --reset

# Seed custom database location
python scripts/seed_demo_data.py --db-path data/pilot_school.db --reset
```

---

## 📦 Standalone Windows Executable Build (.exe)

Package ClassFellow into a standalone Windows 64-bit distribution folder using PyInstaller:

```bash
# Build standalone distribution directory from classfellow.spec
pyinstaller classfellow.spec --clean
```

The resulting standalone distribution is generated in `dist/ClassFellow/`:
- `dist/ClassFellow/ClassFellow.exe` (Main windowed GUI executable)
- `dist/ClassFellow/_internal/` (Bundled Python 3.12 runtime, dependencies, SQLite, ReportLab, and CustomTkinter)
- Bundled `assets/` and `config/` data trees

---

## 💿 Windows Setup Wizard Installer (Inno Setup 6)

Create a single-file Windows setup wizard (`ClassFellow_v1.0.0_Setup.exe`) configured for institutional deployment:

### Prerequisites
- Download and install [Inno Setup 6](https://jrsoftware.org/isdl.php).

### Compilation
1. Ensure the PyInstaller build is compiled in `dist/ClassFellow/`:
   ```bash
   pyinstaller classfellow.spec --clean
   ```

2. Compile `installer.iss` using the Inno Setup Command Line Compiler (`ISCC.exe`):
   ```powershell
   # Windows 64-bit Inno Setup path:
   & "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
   # Or if installed in 64-bit Program Files:
   & "C:\Program Files\Inno Setup 6\ISCC.exe" installer.iss
   ```

3. The generated installer will be saved to:
   - `dist/ClassFellow_v1.0.0_Setup.exe`

### Installer Highlights:
- Default installation directory: `{autopf}\ClassFellow` (Program Files) or `{userappdata}\ClassFellow` (Per-user).
- Automated Desktop and Start Menu shortcut creation.
- Clean uninstallation directives that safely preserve institutional student databases and backups (`data/` and `data/backups/`).

---

## 🛡️ License
Proprietary software. Developed for private educational institutions under the **ClassFellow** platform.
