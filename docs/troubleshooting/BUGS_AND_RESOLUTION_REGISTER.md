# ClassFellow - Bug Register & Troubleshooting Resolution Matrix

**Document Reference**: `docs/troubleshooting/BUGS_AND_RESOLUTION_REGISTER.md`  
**Tracking Cycle**: Phase 9 Desktop Physical Auditing & Field Validation  
**Current Status**: **ACTIVE ISSUE REGISTER — PENDING ARCHITECTURAL SIGN-OFF**  
**Associated Baseline**: Release `v1.0.0-enterprise` / MVP Portable USB Build (Commit `62df58c`)  
**Target Environments**: Windows 11 (64-bit Desktop), SQLite WAL Engine, CustomTkinter Runtime  

---

## Executive Overview & Quality Assurance Mandate

During initial hands-on physical testing of the portable USB executable on Windows 11 by the Chief Architect, critical functional and visual discrepancies were identified. 

While all 177 automated unit tests passed in the CI test runner, physical execution on a fresh machine exposed fundamental gaps between automated test mocks and cold-start production realities.

This document serves as the permanent, authoritative **Bug Register & Troubleshooting Matrix** for ClassFellow. Every defect discovered must be cataloged here with:
1. **The Exact Error Reported**: Physical observations and operational failure modes.
2. **Repository Existing State**: Specific files, lines, and mechanics currently implemented.
3. **Root Cause Analysis (Why the Codebase Was Wrong)**: Detailed technical post-mortem.
4. **Comparative Solution Methodology**: Multi-option analysis with trade-offs and recommended architectural fixes.

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                          DEFECT ESCALATION & LIFECYCLE FLOW                            │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   [ Physical Windows 11 Audit ] ──► [ Defect Identified & Logged Here ]               │
│                                                     │                                  │
│                                                     ▼                                  │
│   [ Code Execution Held ] ◄──────── [ Multi-Option Solution Trade-Off Analysis ]      │
│            │                                                                           │
│            ▼                                                                           │
│   [ Chief Architect & GEM Review ] ──► [ Authorized Implementation & Verification ]    │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Issue Catalog Index

| Defect ID | Severity | Affected Module | Short Summary | Status |
| :--- | :---: | :--- | :--- | :---: |
| **BUG-001** | **CRITICAL** | Core Kernel / Navigation | Unmigrated SQLite database on cold start crashes Student, Attendance, and Exam views; tabs appear dead/unclickable. | **ANALYZED** |
| **BUG-002** | **MEDIUM** | Shell UI / Sidebar | Sidebar navigation tabs exhibit jagged horizontal text misalignment due to multi-byte emoji font bounding boxes. | **ANALYZED** |
| **BUG-003** | **HIGH** | Settings Workspace | Settings page displays cosmetic "ENABLED" green pills from static JSON without verifying runtime database health ("Fake Indicators"). | **ANALYZED** |

---

## Defect Dossier 001: Unmigrated SQLite Database on Cold Boot (Silent Tab Freeze)

### 1. Error Reported by Chief Architect
- After launching `ClassFellow.exe` from the USB drive on a clean Windows 11 machine, the Dashboard interface loaded cleanly.
- The user attempted to click the sidebar tabs:
  - **Dashboard**, **Fee & Receipts**, and **Settings** were active and responded to clicks.
  - **Students**, **Attendance**, and **Examinations** tabs were completely unresponsive and appeared unclickable.

---

### 2. Repository Existing State
- **File**: `app/app.py` (Lines 95–99)
  ```python
  # app/app.py line 97
  self.db_path = db_path
  self.db_conn = get_connection(db_path) if db_path else get_connection()
  self.backup_service = BackupService(self.db_conn, self.db_path)
  ```
- **File**: `database.py` (Lines 41–74 & 111–121)
  ```python
  def get_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
      # Connects and sets PRAGMAs (foreign_keys, WAL, synchronous)
      # DOES NOT RUN SCHEMA MIGRATIONS!
      ...
      return conn

  def init_database(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
      # Fully initializes connection AND executes schema migrations:
      from services.schema_service import migrate_to_latest
      conn = get_connection(db_path)
      migrate_to_latest(conn)
      return conn
  ```

---

### 3. Root Cause Analysis (Why the Codebase Was Wrong)
1. **The Cold-Start Omission**: `app/app.py` invoked `get_connection()` instead of `init_database()`. On a fresh computer or USB drive with no preexisting database, SQLite automatically created an empty `data\classfellow.db` file (0 bytes, `PRAGMA user_version = 0`). No tables were constructed.
2. **Why the Automated Test Matrix Missed It**: In `tests/conftest.py`, automated test fixtures explicitly invoked `migrate_to_latest()` and Django migration commands before running tests. Therefore, all 177 unit tests ran against pre-migrated databases, masking the cold-start failure.
3. **The Asymmetric View Failure Cascade**:
   - `DashboardView` contains an internal `try...except` block in `refresh_data()`; upon encountering `sqlite3.OperationalError: no such table: students`, it logged a warning and safely rendered zeroes.
   - `FeeView` contains an internal `try...except` block in `refresh_data()`; upon encountering `sqlite3.OperationalError: no such table: fee_invoices`, it logged a warning and safely rendered an empty table.
   - `SettingsView` does not query the database for its cards; it only read `config/modules.json`.
   - `StudentView.__init__`, `AttendanceView.__init__`, and `ExamView.__init__` invoked queries without exception handlers during construction:
     ```python
     # StudentView line 32 -> refresh_data() -> student_service.search_students()
     # Threw: sqlite3.OperationalError: no such table: students
     ```
4. **The Silent Failure in CustomTkinter**: When an exception occurs inside a Tkinter/CustomTkinter button callback (`command=lambda: self._on_navigate(k)`), Tkinter prints a traceback to `sys.stderr` and silently aborts the callback. Because `ClassFellow.exe` was packaged with `--windowed` (`console=False`), `stderr` was hidden. The UI did not crash with an error dialog—it simply did nothing, giving the appearance that the buttons were dead.

---

### 4. Comparative Solution Methodology

#### Option A: External First-Run Setup Wizard (Rejected)
- *Concept*: Prompt the user on first launch to run a setup wizard or click a manual "Initialize Database" button.
- *Trade-Off*: Fails the core product value proposition of a seamless, zero-config desktop application for non-technical school clerks.

#### Option B: Automated Self-Healing Bootstrapping (Recommended)
- *Concept*:
  1. In `app/app.py`, replace `get_connection()` with `init_database(self.db_path)`. At application launch, verify `PRAGMA user_version`. If `user_version < 3`, automatically execute `migrate_to_latest()` inside an immediate transaction, building all 15 relational tables and seeding baseline fee heads.
  2. In `app/app.py` `navigate_to()`, wrap `view_cls(self.workspace_frame, self)` inside a guarded `try...except Exception` block. If a view fails to initialize, display a clear, non-modal error card in the workspace with a "Repair Database" button instead of silently swallowing the error.
  3. In `StudentView`, `AttendanceView`, and `ExamView`, wrap initial database reads in `refresh_data()` in `try...except OperationalError` blocks, displaying clean empty-state banners.

---

## Defect Dossier 002: Sidebar Tab Visual Misalignment

### 1. Error Reported by Chief Architect
- The navigation buttons in the left-hand sidebar are visually unaligned.
- Text labels do not line up on a clean vertical axis (neither left-aligned nor right-aligned).

---

### 2. Repository Existing State
- **File**: `app/app.py` (Lines 137–163)
  ```python
  nav_items = [
      ("📊 Dashboard", "dashboard"),
      ("👨‍🎓 Students", "students"),
      ("💳 Fees & Receipts", "fees"),
      ("🗓️ Attendance", "attendance"),
      ("📝 Examinations", "examinations"),
      ("⚙️ Settings", "settings"),
  ]
  for label, mod_key in nav_items:
      btn = ctk.CTkButton(
          self.sidebar_frame,
          text=label,
          anchor="w",
          fg_color="transparent",
          text_color="#F8FAFC",
          hover_color="#1E293B",
          font=ctk.CTkFont(size=13),
          command=lambda k=mod_key: self._on_navigate(k)
      )
      btn.pack(fill="x", padx=10, pady=5)
  ```

---

### 3. Root Cause Analysis (Why the Codebase Was Wrong)
1. **Unicode Glyph Width Disparity**: The button text strings combine Unicode emojis with alphanumeric English labels:
   - `📊` (Bar Chart): Standard single-codepoint emoji (Width: ~1.0 em).
   - `👨‍🎓` (Student): Multi-codepoint Zero-Width-Joiner (ZWJ) sequence: `U+1F468` (Man) + `U+200D` (ZWJ) + `U+1F393` (Graduation Cap). Windows DirectWrite font fallback renders this glyph significantly wider (~2.4 em).
   - `🗓️` (Calendar): Standard emoji with `U+FE0F` variation selector.
   - `⚙️` (Gear): Text symbol font fallback.
2. **CustomTkinter Button Text Anchoring**: While `anchor="w"` anchors the start of the text string to the west (left) margin of the button, the *text label following the emoji* begins immediately after the variable-width emoji character. Because the emojis have varying widths, the text labels (`Dashboard`, `Students`, `Fees & Receipts`) start at varying pixel positions, creating an irregular, unaligned appearance.

---

### 4. Comparative Solution Methodology

#### Option A: Strip All Emojis (Plain Text Only) (Rejected)
- *Concept*: Change buttons to `Dashboard`, `Students`, `Fees`, `Attendance`, `Examinations`, `Settings`.
- *Trade-Off*: Resolves the alignment issue instantly, but removes visual cues and results in an unappealing, utilitarian appearance.

#### Option B: Fixed-Width Two-Column Button Layout (Recommended)
- *Concept*:
  - Structure each navigation item as a compound CustomTkinter widget or configure `CTkButton` with explicit compound layout:
    1. Allocate a fixed-width icon column (e.g., exactly 32 pixels wide, centered) for the emoji/icon.
    2. Place the text label in an adjacent left-aligned container starting at an exact fixed horizontal coordinate (e.g., `x = 44px`).
  - All text labels (`Dashboard`, `Students`, `Fees & Receipts`, `Attendance`, `Examinations`, `Settings`) will align on a vertical line.

---

## Defect Dossier 003: Cosmetic "Fake Indicator" Status on Settings Page

### 1. Error Reported by Chief Architect
- In the Settings workspace under "Commercial Licensing & Feature Flags", all six modules are displayed with green badges marked **"ENABLED"**.
- This indicator was discovered to be superficial ("fake") because the Students, Attendance, and Examination modules were inoperative, yet the settings page reported them as active and enabled.
- The Chief Architect mandated that software indicators must reflect actual system operational status rather than artificial values.

---

### 2. Repository Existing State
- **File**: `ui/settings_view.py` (Lines 83–105)
  ```python
  # ui/settings_view.py line 83
  modules = self.app.config.get("modules", {})
  ...
  for idx, (mod_key, is_enabled) in enumerate(modules.items()):
      pill_color = self.colors["status_paid"] if is_enabled else self.colors["status_unpaid"]
      status_text = "ENABLED" if is_enabled else "DISABLED"
      ...
      ctk.CTkLabel(pill, text=f"{mod_key.capitalize()}:", ...)
      ctk.CTkLabel(pill, text=status_text, text_color=pill_color, ...)
  ```

---

### 3. Root Cause Analysis (Why the Codebase Was Wrong)
1. **Conflating Static Configuration with Runtime Health**: `settings_view.py` directly read the static JSON file `config/modules.json`. If `modules.json` contained `"students": true`, the UI rendered a green `ENABLED` pill regardless of whether:
   - The database file was present or accessible.
   - The `students` SQL table existed.
   - The `StudentService` could execute queries without throwing exceptions.
2. **Absence of a System Diagnostics Layer**: The settings workspace was designed solely as an entitlement viewer rather than an operational diagnostics monitor. For a desktop application running in low-resource school environments, an operator requires actionable operational status (e.g., database connection, table integrity, record counts, schema version), not cosmetic badges.

---

### 4. Comparative Solution Methodology

#### Option A: Rename to "Licensed Entitlements" (Rejected)
- *Concept*: Change the label from "Feature Flags" to "Commercial License Entitlements (config/modules.json)" to clarify that it reflects license status rather than runtime health.
- *Trade-Off*: Partially clarifies intent, but leaves the core issue unresolved: operators still lack visibility into actual software health.

#### Option B: Live System Health & Operational Diagnostic Monitor (Recommended)
- *Concept*: Replace the static flag card with a **Live System Diagnostic Monitor**:
  1. **Database Engine Status**:
     - Status: `Connected` (Green) or `Disconnected` (Red).
     - Engine Mode: `SQLite 3.x (WAL Mode Concurrency)`.
     - Schema Migration Version: `PRAGMA user_version = 3 (15/15 Tables Verified)`.
     - Database File Location & Size: `C:\...\data\classfellow.db (64 KB)`.
  2. **Operational Module Readiness**:
     - For each module, perform an active runtime probe:
       - `Students`: Checks `SELECT COUNT(*) FROM students` $\rightarrow$ Displays `Operational (0 Students Registered)`.
       - `Fees`: Checks `SELECT COUNT(*) FROM fee_invoices` $\rightarrow$ Displays `Operational (0 Active Invoices)`.
       - `Attendance`: Checks `SELECT COUNT(*) FROM attendance_records` $\rightarrow$ Displays `Operational (0 Records)`.
       - `Examinations`: Checks `SELECT COUNT(*) FROM exams` $\rightarrow$ Displays `Operational (0 Exam Sessions)`.
     - If a table is missing, display: `UNINITIALIZED (Action Required)` in red.
  3. **Actionable Operator Controls**:
     - Add a prominent button: **`🛠️ Run Schema Verification & Auto-Repair`**. Clicking it executes `init_database()`, repairs missing tables/indices, and refreshes the indicators with verified operational status.

---

## Action Plan & Architectural Next Steps

| Action Item | Target Files | Objective |
| :--- | :--- | :--- |
| **Fix 1: Cold-Start Bootstrapping** | `app/app.py`, `database.py` | Call `init_database()` on startup; auto-migrate missing tables; add view instantiation exception guards. |
| **Fix 2: Pixel-Perfect Sidebar Alignment** | `app/app.py` | Implement fixed-width icon column and uniform text margin for sidebar navigation. |
| **Fix 3: Live Health Monitor in Settings** | `ui/settings_view.py` | Replace static JSON badges with live database table checks, record counts, and a 1-click database repair utility. |
| **Fix 4: Recompile & Repackage** | PyInstaller build | Rebuild `dist\ClassFellow\ClassFellow.exe` and update `dist\ClassFellow_Portable_USB\`. |

*Note: In accordance with project governance, all code changes remain on hold pending Chief Architect and GEM AI review.*
