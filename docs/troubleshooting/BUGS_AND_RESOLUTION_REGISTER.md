# ClassFellow - Bug Register & Troubleshooting Resolution Matrix

**Document Reference**: `docs/troubleshooting/BUGS_AND_RESOLUTION_REGISTER.md`  
**Tracking Cycle**: Phase 9 Gate 3 Finalization & Multi-Platform Testing Modernization  
**Current Status**: **ALL DEFECTS RESOLVED (REF-001 & REF-002 VERIFIED) | ARCHITECTURAL SHIFT: PARALLEL MULTI-PLATFORM TESTING MANDATED**  
**Associated Baseline**: Release `v1.1.0-enterprise` / Portable USB Build (Commit `e20cddd`)  
**Target Environments**: Windows 11 Desktop, Django Web Portal, Flutter Mobile, Distributed Cloud Sync  

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
│               PARALLEL MULTI-PLATFORM DEVELOPMENT & QUALITY PIPELINE                  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   ┌────────────────────────────────────────────────────────────────────────────────┐   │
│   │                 FAST-TRACK AUTOMATED TEST INFRASTRUCTURE (CI/CD)               │   │
│   │  • Desktop Unit & Logic (pytest 187/187 green)                                 │   │
│   │  • Desktop GUI Smoke & Windows Binary Execution (pywinauto / process probe)   │   │
│   │  • Web Application (Django tests + PostgreSQL + Playwright E2E)                │   │
│   │  • Mobile App (Flutter / Dart test suite in CI)                                │   │
│   │  • Distributed Cloud Sync (Multi-campus sync & reconciliation tests)           │   │
│   └───────────────────────────────────────┬────────────────────────────────────────┘   │
│                                           │                                            │
│                                           ▼                                            │
│                      [ Continuous Fast Engineering Velocity ]                          │
│                      • Repo AI & GEM AI proceed without blocking                       │
│                      • 4 Platform Tiers developed concurrently                         │
│                                           │                                            │
│                                           ▼                                            │
│                 [ Milestone Physical USB Inspection by Architect ]                     │
│                 • Visual UX & ergonomic validation on physical hardware                │
│                 • Asynchronous feedback logged without blocking development            │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Issue Catalog Index

| Defect ID | Severity | Affected Module | Short Summary | Status |
| :--- | :---: | :--- | :--- | :---: |
| **BUG-001** | **CRITICAL** | Core Kernel / Navigation | Unmigrated SQLite database on cold start crashes Student, Attendance, and Exam views; tabs appear dead/unclickable. | **RESOLVED** |
| **BUG-002** | **MEDIUM** | Shell UI / Sidebar | Sidebar navigation tabs exhibit jagged horizontal text misalignment due to multi-byte emoji font bounding boxes. | **RESOLVED** |
| **BUG-003** | **HIGH** | Settings Workspace | Settings page displays cosmetic "ENABLED" green pills from static JSON without verifying runtime database health ("Fake Indicators"). | **RESOLVED** |
| **BUG-004** | **HIGH** | Student Registration | Urdu Name field enforces LTR (Left-to-Right) typing instead of native RTL (Right-to-Left) BiDi flow in CustomTkinter input entry. | **RESOLVED** |
| **BUG-005** | **CRITICAL** | Student Registration | "Assign Class" dropdown displays unmapped "Default Class" on fresh database, triggering blocking "Validation Error" that prevents admissions. | **RESOLVED** |
| **BUG-002B**| **MEDIUM** | Shell UI / Sidebar | Compound Unicode ZWJ emoji (`👨‍🎓`) dissociates into dual glyphs (`👨` + `🎓`) on Windows DirectWrite Tkinter font fallback, expanding icon box width. | **RESOLVED** |
| **REF-001** | **ARCHITECTURAL**| Student Registration | Structured Two-Stage Admission Form, Sibling Discount Formula, Prior Arrears, and 3-Panel Fee Voucher Subsystem Overhaul. | **RESOLVED** |
| **REF-002** | **ARCHITECTURAL**| Settings / Admission / Ledger | First-Time Setup Guard ("Mother Form"), Regional Operating Surcharges (Generator/Paper/Guard/Refunds), Guardian Email & Persona Splitter. | **RESOLVED** |

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

      - Add a prominent button: **`🛠️ Run Schema Verification & Auto-Repair`**. Clicking it executes `init_database()`, repairs missing tables/indices, and refreshes the indicators with verified operational status.

---

## Defect Dossier 004: Urdu Text Entry LTR vs. RTL Input Flow

### 1. Error Reported by Chief Architect
- During test registration of a new student ("Abdullah Mohsen Butt") in the `New Student Admission` modal:
  - English fields (`First Name`, `Last Name`) functioned normally.
  - The **`Urdu Name`** field enforced Left-to-Right (LTR) typing instead of native Right-to-Left (RTL) input flow required for Urdu writing ("بٹ محسن عبداللہ").
  - The text cursor and characters flowed from left to right, creating awkward input behavior, reversing visual word order, and breaking expected Urdu script writing rules.
  - Mandated: Investigate and resolve across all Urdu-enabled input fields throughout the platform.

---

### 2. Repository Existing State
- **File**: `ui/student_view.py` (Line 311 & Lines 373–379)
  ```python
  # ui/student_view.py line 311
  self.urdu_name = self._add_entry(form_scroll, "Urdu Name:", "مثال: محمد علی")

  # ui/student_view.py line 373
  def _add_entry(self, parent, label: str, placeholder: str) -> ctk.CTkEntry:
      f = ctk.CTkFrame(parent, fg_color="transparent")
      f.pack(fill="x", pady=4)
      ctk.CTkLabel(f, text=label, width=140, anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
      e = ctk.CTkEntry(f, placeholder_text=placeholder, width=280)
      e.pack(side="left")
      return e
  ```

---

### 3. Root Cause Analysis (Why the Codebase Was Wrong)
1. **Tkinter Default Left-Justification**: CustomTkinter `CTkEntry` wraps standard Tkinter `Entry`, which defaults to `justify="left"`. When a user types Arabic/Urdu Unicode characters into a left-justified field, characters are anchored to the left margin. The cursor remains on the right as text expands left-to-right, reversing the natural Right-to-Left writing mechanics expected by native Urdu speakers.
2. **Conflating Storage with Live Typing**: While ReportLab PDF exports utilize `arabic_reshaper` and `python_bidi` (`format_urdu()` in `reports/urdu_formatter.py`) for connected ligatures on canvas, GUI text input fields were left in standard English LTR configuration with no explicit `justify="right"` or dedicated Urdu font specification.

---

### 4. Comparative Solution Methodology

#### Option A: Real-Time BiDi String Manipulation on Keystroke (Rejected)
- *Concept*: Bind a `<KeyRelease>` event to dynamically reshape and reverse the string via `python-bidi` while the user types.
- *Trade-Off*: Breaks cursor positioning on every keypress, breaks backspace/arrow navigation, and corrupts the raw Unicode stored in SQLite (preventing standard SQL `LIKE %محمد%` search queries from working).

#### Option B: Native Right-Justified RTL Entry with TrueType Font Support (Recommended)
- *Concept*:
  1. Add an explicit parameter `is_rtl: bool = False` to `_add_entry()` or configure `CTkEntry(justify="right")` specifically on `urdu_name` and all Urdu input fields.
  2. Bind a high-fidelity Arabic/Urdu TrueType font family (`assets/fonts/urdu.ttf` or `Segoe UI` / `Tahoma` font fallback).
  3. Keep the raw unshaped Unicode in SQLite for fast, native SQL indexing and search. Reshaping is applied strictly downstream at PDF rendering time.
  4. Include an inline tooltip or toggle explaining Windows Urdu phonetic keyboard switching (<kbd>Alt</kbd> + <kbd>Shift</kbd>).

---

## Defect Dossier 005: "Default Class" Dummy Dropdown & Missing Inline Class Provisioning (Admission Blocker)

### 1. Error Reported by Chief Architect
- In the `New Student Admission` modal, the `Assign Class *` dropdown displayed only one choice: **`Default Class`**.
- When the user attempted to save the student admission, an unhandled validation error modal appeared:
  > **Validation Error**: *Please select a valid class group.*
- The user was completely blocked from completing student admission:
  - No other class was available in the dropdown.
  - The form provided no way to add a new class or assign a valid class.
- The Chief Architect mandated:
  - Investigate why this validation error is triggered when "Default Class" is the only available choice.
  - Provide technical architecture for whether classes should be pre-fed, and implement an inline mechanism ("small slide / sub-menu entry") allowing the clerk to enter a new class directly at the admission point without leaving the form.

---

### 2. Repository Existing State
- **File**: `ui/student_view.py` (Lines 338–350 & Lines 389–405)
  ```python
  # ui/student_view.py line 338
  self.class_groups_map: Dict[str, int] = {}
  if self.parent_view.db_conn:
      cur = self.parent_view.db_conn.cursor()
      cur.execute("SELECT id, name, section_or_batch FROM class_groups ORDER BY name;")
      for row in cur.fetchall():
          display_name = f"{row[1]} ({row[2]})"
          self.class_groups_map[display_name] = row[0]

  # Line 346: If class_groups is empty, defaults visually to ["Default Class"]
  class_names = list(self.class_groups_map.keys()) or ["Default Class"]
  self.class_var = ctk.StringVar(value=class_names[0])
  self.class_menu = ctk.CTkOptionMenu(class_frame, values=class_names, variable=self.class_var, width=220)

  # Line 389: During submission:
  selected_class = self.class_var.get()
  class_id = self.class_groups_map.get(selected_class)
  ...
  # Line 403: "Default Class" is NOT in self.class_groups_map, so class_id is None!
  if not class_id:
      self.parent_view.show_error("Validation Error", "Please select a valid class group.")
      return
  ```

---

### 3. Root Cause Analysis (Why the Codebase Was Wrong)
1. **The Phantom Default Catch-22**: When a school first installs ClassFellow, the `class_groups` table is empty. Line 346 assigned `["Default Class"]` as a cosmetic fallback string for the dropdown, but **never inserted a default class into `self.class_groups_map` or into SQLite**. When the clerk submitted the form, `self.class_groups_map.get("Default Class")` returned `None`, triggering the validation error.
2. **Missing Inline Class Creation Workflow**: School administrative workflows in Punjab require clerks to create new classes (e.g. `Class 9`, Section `A`, or `Matric Bio Morning Batch`) on the fly during admissions. The existing UI forced a strict dependency on pre-existing database rows without providing an inline class creator.

---

### 4. Comparative Solution Methodology

#### Option A: Pre-Flight Academic Configuration Wizard Only (Rejected)
- *Concept*: Block admission and force the user to navigate to a separate Classes & Sessions screen before allowing student admissions.
- *Trade-Off*: Frustrating and clunky for clerks; forces abandonment of partially filled admission forms.

#### Option B: Dual-Track Provisioning: Baseline Auto-Seeding + Inline "➕ Quick Add Class" Sub-Modal (Recommended)
- *Concept*:
  1. **Baseline Cold-Boot Seeding**: During `init_database()`, if `academic_sessions` or `class_groups` are empty, automatically seed an active academic session (`2026-2027`) and a baseline class group (`Class 1 (Section A)`). This guarantees that even a brand-new machine always has a valid, selectable class.
  2. **Inline "➕ New Class" Sub-Dialog**: Add a small, prominent `➕` button directly adjacent to the `Assign Class` dropdown in `StudentAdmissionModal`. Clicking it opens a lightweight modal (`QuickAddClassModal`) that allows the clerk to enter `Class Name` (e.g., `Class 9`) and `Section` (e.g., `Rose`), saves it to SQLite, refreshes `self.class_groups_map`, and automatically selects the newly created class in the dropdown without losing any student data already entered!

---

## Defect Dossier 002B: Multi-Codepoint Emoji Dissociation in Windows DirectWrite Font Fallback

### 1. Error Reported by Chief Architect
- Despite previous alignment adjustments, sidebar buttons remain misaligned.
- Icons are not properly centered or justified with their text buttons.
- In the physical screenshot, the **"Students"** tab icon visibly renders as **two separate glyphs side-by-side** (`👨` and `🎓`).
- The doubled icon width pushes the text label `Students` further to the right than `Dashboard` and `Fees & Receipts`.

---

### 2. Repository Existing State
- **File**: `app/app.py` (Lines 83–108 & Line 140)
  ```python
  # Line 90
  self.icon_label = ctk.CTkLabel(
      self, text=icon, width=36, font=ctk.CTkFont(size=15), anchor="center", text_color="#F8FAFC"
  )
  self.icon_label.pack(side="left", padx=(8, 2), pady=3)

  # Line 140
  nav_items = [
      ("📊", "Dashboard", "dashboard"),
      ("👨‍🎓", "Students", "students"),  # <-- Compound ZWJ sequence!
      ...
  ]
  ```

---

### 3. Root Cause Analysis (Why the Codebase Was Wrong)
1. **Unicode ZWJ Dissociation**: `👨‍🎓` is not a single character; it is a compound sequence: `U+1F468` (Man) + `U+200D` (Zero-Width Joiner) + `U+1F393` (Graduation Cap).
2. **Tkinter GDI/DirectWrite Font Fallback Failure**: Tkinter on Windows does not support complex OpenType ZWJ ligature shaping. Instead of drawing a single merged student glyph, DirectWrite falls back to drawing two distinct emojis side-by-side: `👨` and `🎓`.
3. **Pack Geometry Auto-Expansion**: `CTkLabel.pack(side="left")` auto-expands when its content exceeds `width=36`. When the dual glyphs render at ~48px wide, `title_label` is pushed horizontally to the right, causing `Students` to visibly step out of vertical alignment with `Dashboard`.

---

### 4. Comparative Solution Methodology

#### Option A: Single-Codepoint Monolithic Unicode Symbols + Rigid Grid Constraints (Recommended - Immediate)
- *Concept*:
  1. Replace compound ZWJ sequences with universal single-codepoint symbols that never dissociate on Windows:
     - `Dashboard`: `📊` (`U+1F4CA` - Single codepoint)
     - `Students`: `🎓` (`U+1F393` - Graduation Cap, single codepoint, universal)
     - `Fees & Receipts`: `💳` (`U+1F4B3` - Single codepoint)
     - `Attendance`: `📅` (`U+1F4C5` - Single codepoint calendar)
     - `Examinations`: `📝` (`U+1F4DD` - Single codepoint pencil/memo)
     - `Settings`: `⚙️` (`U+2699` - Standard gear)
  2. Replace `pack(side="left")` inside `SidebarNavButton` with strict `grid(row=0, column=0)` layout where Column 0 is pinned to an immutable width of 40px and Column 1 starts at an exact horizontal coordinate `x = 48px`.

#### Option B: Vector SVG / Bundled PNG Icon Strip (Future UI Enhancement)
- *Concept*: Bundle dedicated 24x24 anti-aliased PNG icons in `assets/icons/` loaded via `ctk.CTkImage`. Completely independent of OS emoji fonts.

---

## Architectural Refinement REF-001: Student Admission Form Fee Redesign & Competitor Analysis Strategy

### 1. Observation & Directive from Chief Architect
- The "Monthly Discount (PKR)" field in the admission form creates confusion regarding its business and accounting semantics:
  - Is it a flat concession on tuition fees?
  - Is it negotiated during parental bargaining at admission?
  - What will be the accumulated total monthly fee after discount?
- The Chief Architect noted:
  > *"We are missing a complete fee charges form here. I prefer to add separators or a collapsible method and redesign this New Student Admission form in a reasonable way like competitor schools are using. I suggest that you wait for me to bring few registration form samples for other schools and collect more data on this point, but meanwhile note the above points to correct in future registration form design work."*

---

### 2. Architectural Analysis & Proposed Design Blueprint
1. **Separation of Student Identity vs. Fee Schedule**:
   - The current form combines personal bio data with a single raw discount input.
   - Competitor software in Punjab (PakSchool, SkoolSys) divides the admission flow into two clear stages:
     - **Stage 1: Student & Guardian Identity** (Admission #, Names in English/Urdu, B-Form, DOB, Guardian CNIC & Phone, Residential Address).
     - **Stage 2: Institutional Fee Enrollment Schedule** (Collapsible / Tabbed panel):
       - Base Monthly Tuition Fee for Selected Class (Read-only, auto-filled from class structure).
       - One-Time Admission Charges (Admission Fee, Registration/Prospectus Charges, Security Deposit).
       - Concession / Discount Category (Sibling Concession 20%, Kinship / Staff Child 50%, Discretionary Scholarship, or Custom Flat PKR Discount).
       - Net Monthly Payable Balance (Auto-computed dynamically: $\text{Base Tuition} - \text{Discount} = \text{Net Monthly Payable}$).
2. **Resolution & Implementation (Phase 9 Gate 3)**:
   - Upgraded SQLite schema to **Migration Version 4** (`migration_v4_punjab_admission_spec`):
     - Extended `students` table: `b_form_number`, `guardian_urdu_name`, `guardian_relation`, `guardian_whatsapp`, `guardian_cnic`, `previous_school_slc`, `updated_at`.
     - Created compound lookup indexes: `idx_students_admission_no`, `idx_students_names`, `idx_students_guardian_phone`.
   - Seeded baseline academic session `'2026-2027 Academic Session'`, standard class group `'Class 1 (Section A)'` at base tuition fee `PKR 3,500.00`, and standard fee heads (Tuition, Admission, Prospectus, Security, Arrears).
   - Refactored `StudentAdmissionModal` into a structured two-stage registration layout:
     - **Stage 1 (Identity & Demographics)**: English & Urdu names (`justify="right"` RTL with `Segoe UI`), B-Form, Guardian CNIC, Relation, Phone with blur-time `<FocusOut>` normalization, WhatsApp, residential address, previous school SLC.
     - **Stage 2 (Academic & Fee Enrollment)**: Dynamic class selection with inline `➕` button (`QuickAddClassModal`), base fee display, upfront one-time heads (Admission, Prospectus, Security), concession engine with Sibling Auto-Detection (0% 1st, 25% 2nd, 50% 3rd+ active child), and live calculated summary cards.
     - Action bar with dual execution paths: `💾 Save Only` vs. `🖨️ Submit & Print Voucher [Ctrl+P]` with printer spooler fallback to default PDF viewer.
   - Built atomic transaction in `fee_service.process_walkin_admission` issuing student registration, active enrollment, admission invoice, payment receipt, and generating a professional 3-Panel A4 Fee Voucher PDF.

---

## Architectural Refinement REF-002: School Profile Mother Form, First-Time Onboarding Guard, Regional Operating Surcharges, and Persona Splitter

### 1. Directives & Physical Observations from Chief Architect
Following the Phase 9 Gate 3 review, the Chief Architect conducted an architectural evaluation of the cold-boot seeding strategy, real-world fee economics, and communication logistics:

1. **Auto-Seeding vs. Enterprise First-Time Onboarding ("Mother Form")**:
   - Automatic seeding of hard-coded sessions (`2026-2027`) and classes (`Class 1 (Section A)`) in `schema_service.py` is an engineer's cold-start patch, not sound enterprise architecture.
   - When commercial school clients purchase ClassFellow, forcing synthetic classes or dates corrupts their administrative reality.
   - **Architectural Directive**: Implement a **Hidden First-Time Setup Guard** triggered whenever a fresh installation attempts its first admission. If no academic session exists, the clerk/administrator is intercepted and guided to a **School Profile Mother Form** (accessible permanently in Settings).
   - In this Mother Form, school management officially establishes:
     - **Admission Year** (e.g. `2026-2027`)
     - **Academic Session Period** (e.g. `2026-04-01` to `2027-03-31`)
     - **Class & Batch Structure** with baseline monthly tuition rates
     - **Annual Institutional Fee Policy** (decided once per year, adjustable anytime via Settings).

2. **Real-World Regional Fee Heads (Punjab Private School Realities)**:
   - Schools in Punjab do not operate solely on tuition and admission fees. Operational realities require localized surcharges:
     - **Tuition Fee**: Core monthly instructional fee.
     - **Admission Fee & Prospectus / Registration**: One-time upfront enrollment charges.
     - **Stationery & Exam Paper Fund**: Terminal test sheets, annual examination printing, and classroom activity materials.
     - **Generator & Fuel Surcharge**: Continuous power grid (WAPDA) outages in Pakistan make generator diesel fuel a mandatory monthly operational surcharge.
     - **Gate Security Guard Fund**: Mandatory private security deployments for school campus protection.
     - **Refundable Security Deposit & Refund Tracking**: Caution deposit logged at admission; upon withdrawal/SLC issuance, the refund amount and auditable explanatory notes must be recorded.

3. **Guardian Communication & Persona Splitter in Admission UI**:
   - **Guardian Email**: Add `guardian_email` to the database schema and admission UI. Phone calls and WhatsApp are insufficient for official circulars, 10-page fee policies, and legal documentation.
   - **Visual Persona Splitter**: In Stage 1 (Identity & Demographics), insert an explicit visual separator card/line demarcating **Student Identity** from **Guardian Identity** to prevent clerks from conflating individual personas during high-pressure walk-ins.

---

### 2. Financial & Ledger Services: Human Storytelling Architecture (Day 1 Walk-in to Month 12 Annual Cycle)

To enable school administrators, principals, and accountants to grasp the system's ledger mechanics, the financial subsystem is architected around an intuitive, auditable narrative:

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│               THE 12-MONTH FINANCIAL LEDGER LIFECYCLE (A HUMAN STORY)                  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   [ DAY 1: WALK-IN ADMISSION ]                                                         │
│     Father brings Hamza (Class 1) & Ali (Class 5).                                    │
│     • Ledger Inception: Sibling Auto-Detect queries Father's mobile.                   │
│     • Child 1 (Hamza): 0% discount. Initial Invoice: Admission (5,000) +               │
│       Prospectus (1,000) + Security Deposit (3,000) + Tuition (3,500) +               │
│       Paper Fund (500) + Generator Fund (500) = Total Rs. 13,500.                     │
│     • Child 2 (Ali): Auto-detected 2nd child -> 25% Tuition Concession.                │
│     • Three-Panel A4 Voucher generated (Bank / School / Student).                      │
│     • Cashier collects Rs. 13,500 -> Receipt issued -> Ledger Balance = Rs. 0.        │
│                                                                                        │
│   [ MONTH 2: FIRST RECURRING BILLING CYCLE (MAY 1) ]                                   │
│     • System batch-generates May monthly fee bills.                                    │
│     • Hamza: Tuition (3,500) + Generator Fuel (500) = Rs. 4,000.                      │
│     • Father pays full on May 8 (Before Due Date Rs. 4,000 / After Due Date Rs. 4,300).│
│     • Balance = Rs. 0.                                                                 │
│                                                                                        │
│   [ MONTH 4: PARTIAL PAYMENT & ARREARS ROLL-FORWARD (JULY) ]                           │
│     • Monthly bill: Rs. 4,000. Father pays only Rs. 2,500 due to financial strain.     │
│     • Ledger records Credit: Rs. 2,500. Remaining Unpaid = Rs. 1,500.                 │
│     • August 1 Bill Generation: Tuition (3,500) + Generator (500) +                   │
│       Arrears Carried Forward (1,500) = Total Rs. 5,500.                               │
│     • Zero manual arithmetic: Previous debt automatically rolls forward.               │
│                                                                                        │
│   [ MONTH 8: TERMINAL EXAMS & SEASONAL SURCHARGES (NOVEMBER) ]                         │
│     • School activates "Exam Paper Fund" (Rs. 800) for Mid-Term printing.              │
│     • Invoice dynamically itemizes standard tuition + paper fund.                      │
│                                                                                        │
│   [ MONTH 12: SESSION CLOSE & SLC REFUND SETTLEMENT (MARCH) ]                          │
│     • Family relocates; Father applies for School Leaving Certificate (SLC).           │
│     • Final Ledger Audit: Unpaid Arrears = Rs. 1,000.                                  │
│     • Refundable Caution Deposit held from Day 1 = Rs. 3,000.                          │
│     • Net Settlement: Rs. 3,000 - Rs. 1,000 arrears = Net Refund Rs. 2,000.            │
│     • Refund voucher issued with explanatory notes; Student status set to 'Withdrawn'; │
│       Ledger fully closed and reconciled.                                              │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

### 3. Repo AI Engineering Opinion & Trade-Off Matrix (For GEM AI & Gemini Notebook AI Review)

#### Analysis Point 1: Elimination of Static Cold-Boot Seeding
- **Engineering Verdict**: **STRONGLY ENDORSE CHIEF ARCHITECT'S POSITION**.
- *Rationale*: Static seeding (`insert into academic_sessions values ('2026-2027 Academic Session')`) was introduced in Phase 9 Gate 2 to silence `test_cold_boot.py` from crashing on unmigrated tables. While it passed automated unit tests, it hard-codes calendar dates and a single mock class (`Class 1 (Section A)`) that a real school principal would immediately have to delete or rename.
- *Recommended Architecture*:
  1. Maintain clean schema creation without hardcoded tenant data.
  2. Implement an application-level route guard:
     ```python
     if not school_service.is_school_profile_configured():
         # Open First-Time School Profile Setup Modal
         FirstTimeSetupWizard(self)
     ```
  3. Keep the seeding routine exclusively inside `tests/conftest.py` and `scripts/seed_demo_data.py` for CI runners and demo presentations, leaving clean production installations unpolluted.

#### Analysis Point 2: Dynamic Regional Fee Heads vs. Fixed GUI Entry Fields
- **Engineering Verdict**: **ADOPT DYNAMIC FEE HEAD ARCHITECTURE**.
- *Rationale*: Hard-coding entry boxes (`adm_fee_entry`, `prospectus_fee_entry`, `security_entry`, `generator_entry`, `paper_fund_entry`) inside `StudentAdmissionModal` creates brittle GUI code. If another school needs a "Computer Lab Fund" or "AC Surcharge", developers must modify the form.
- *Recommended Architecture*:
  - Back the admission form with a dynamic SQLite query: `SELECT id, name, default_amount, is_recurring FROM fee_heads WHERE is_active = 1`.
  - Render these dynamically in Stage 2 as editable grid items.
  - Allows school management to add, deactivate, or adjust Generator, Security, Paper Fund, or Transport heads at any time via the Settings Mother Form without code edits.

#### Analysis Point 3: Guardian Email & Migration v5
- **Engineering Verdict**: **HIGH PRIORITY EXTENSION**.
- *Rationale*: In modern Pakistani urban academies and private schools (Beaconhouse, City School, Punjab Group), email is the primary vector for formal fee circulars, tax certificates, and legal transcripts. Adding `guardian_email TEXT` to `students` table via Migration v5 is a zero-risk, high-value addition.

#### Analysis Point 4: Stage 1 Persona Splitter
- **Engineering Verdict**: **IMMEDIATE UX REFINEMENT**.
- *Rationale*: In busy admissions, clerks frequently confuse the child's B-Form with the father's CNIC, or the father's name with the student's name. Dividing Stage 1 into two nested sub-frames (`👤 Student Persona` and `👨‍👧 Guardian Persona`) with a distinct border and icon provides immediate visual cognitive clarity.

---

## Action Plan & Architectural Implementation Register

| Defect / Item ID | Severity | Target Files | Implementation Summary | Status |
| :--- | :---: | :--- | :--- | :---: |
| **BUG-001** | **CRITICAL** | `app/app.py`, `ui/student_view.py`, `ui/attendance_view.py`, `ui/exam_view.py` | App launch calls `init_database()` triggering `migrate_to_latest()`; `navigate_to()` wraps view creation in error recovery card; all views guard table queries with empty states. | **RESOLVED** |
| **BUG-002** | **MEDIUM** | `app/app.py` (`SidebarNavButton`) | Two-column compound layout with centered 36px icon container and uniform text starting at identical horizontal pixel coordinates. | **RESOLVED** |
| **BUG-003** | **HIGH** | `ui/settings_view.py` | Replaced cosmetic badges with live engine metrics (connection, WAL, PRAGMA user_version=4, file size), live row-count table probes, and a 1-click `🛠️ Verify & Auto-Repair Database` button. | **RESOLVED** |
| **BUG-004** | **HIGH** | `ui/student_view.py` | Configured `justify="right"` on `urdu_name` and `guardian_urdu_name` with `Segoe UI` Urdu TrueType font family; maintained unshaped raw Unicode in SQLite for fast SQL search. | **RESOLVED** |
| **BUG-005** | **CRITICAL** | `services/schema_service.py`, `database.py`, `ui/student_view.py` | Cold-boot auto-seeding of session `2026-2027 Academic Session` and baseline class group `Class 1 (Section A)` (PKR 3500.00); added inline `➕ New Class` sub-dialog (`QuickAddClassModal`) allowing on-the-fly class creation without leaving form. | **RESOLVED** |
| **BUG-002B**| **MEDIUM** | `app/app.py` | Replaced multi-codepoint compound emoji `👨‍🎓` with universal single-codepoint `🎓`, `💳` for fees, and `📅` for attendance; enforced rigid 40px width `grid(row=0, column=0)` layout in `SidebarNavButton`. | **RESOLVED** |
| **REF-001** | **ARCHITECTURAL** | `services/fee_service.py`, `services/schema_service.py`, `ui/student_view.py`, `ui/quick_add_class_modal.py` | Overhauled New Student Admission modal into a structured Two-Stage Punjab form with sibling auto-detection, prior arrears calculation, ReportLab 3-panel voucher generation, and keyboard accelerators. | **RESOLVED** |
| **REF-002** | **ARCHITECTURAL** | `ui/settings_view.py`, `ui/student_view.py`, `ui/school_profile_modal.py`, `services/schema_service.py`, `services/school_service.py`, `models.py` | School Profile Mother Form Wizard, First-Time Setup Guard, Dynamic Regional Surcharges Grid (Generator/Paper/Lab), Guardian Email & Persona Splitter. | **RESOLVED** |

---

## Verification & Validation Evidence

1. **Automated Cold-Start & Admission Regression Suite**:
   - Authored `tests/test_cold_boot.py`:
     - `test_init_database_on_empty_file`: Verified on brand-new 0-byte SQLite database that `init_database()` builds relational tables, sets `user_version = 4`, and auto-seeds baseline session, fee heads, and class.
     - `test_app_cold_start_and_workspace_navigation`: Verified `ClassFellowApp` starts against unmigrated database, navigates through all 6 workspaces without errors, tests inline `QuickAddClassModal`, admits student, and tests Settings live health telemetry and auto-repair utility.
   - Authored `tests/test_admission_workflow.py`:
     - `test_cold_boot_seeding_and_schema_v4`: Verified migration v4 and default academic seeding.
     - `test_extended_student_schema_persistence`: Verified B-Form, guardian CNIC, raw Urdu UTF-8, and previous school SLC fields.
     - `test_sibling_discount_calculations`: Verified sibling discount formula (0%, 25%, 50%).
     - `test_prior_arrears_calculation`: Verified prior arrears roll-forward across multiple billing cycles.
     - `test_walkin_admission_atomic_transaction_and_voucher`: Verified atomic enrollment + invoice + receipt + 3-panel A4 voucher PDF generation.
     - `test_inline_class_creation_workflow`: Verified `QuickAddClassModal` inline class creation and automatic dropdown selection.
2. **Full Test Suite Execution**:
   - `pytest -q`: **187/187 PASSED** (0 failures, 100% green across all 26 test suites in 32.84s).
3. **Standalone Production Binary Recompilation**:
   - Recompiled via PyInstaller: `dist\ClassFellow\ClassFellow.exe`.
   - SHA-256 Digest: `751D11FF4EBDB97F919BD7732304E5424A3AEA26DD46DFD8D5BE6CBF758DA3F3`.
4. **USB Flash Drive Distribution Payload Updated**:
   - Synced fresh executable and runtime assets to `dist\ClassFellow_Portable_USB\ClassFellow\`.
   - Updated `dist\ClassFellow_Portable_USB\04_Verification_Tools\checksums.sha256`.
5. **Phase 9 Gate 3 Finalization (REF-002 Verification)**:
   - **Migration v5 Idempotency**: `PRAGMA table_info(students)` adds `guardian_email` and `previous_school_slc` without error if columns pre-exist; `fee_heads` extended with `default_amount` and `is_active`; `school_profiles` table established; `PRAGMA user_version` advanced to `5`.
   - **Clean Zero-State DB**: Production cold-boot database contains 0 mock classes and 0 mock sessions, strictly seeding the regional fee head catalog.
   - **Route Guard Interception**: Unconfigured databases intercept "➕ New Admission" and divert clerk directly into `SchoolProfileModal` ("Mother Form") before admitting any students.
   - **Persona Splitter**: Stage 1 admission form physically isolates `Student Identity` and `Guardian Identity` into bordered cards with seamless keyboard `<Tab>` navigation.
   - **Dynamic Surcharge Grid**: Stage 2 admission surcharges are dynamically populated from active fee heads in SQLite with strict `Decimal` validation.
   - **Institutional Branding & Voucher Crest**: Single school profile drives header title and logo across ReportLab 3-panel fee vouchers with file-existence safeguards.
   - **Full Regression**: **187/187 PASSED** (100% green across all 26 test suites).
   - Ready for physical inspection #3 by Chief Architect on Windows 11.

---

## Strategic Architectural Pivot: Parallel Multi-Platform Testing & Engineering Velocity

### 1. The Bottleneck: Sequential USB Testing vs. Modern Multi-Platform Scale
Until Phase 9 Gate 3, ClassFellow adhered to a strictly sequential, single-threaded audit model: all engineering development paused while the standalone executable was compiled, copied to a physical USB flash drive, and manually click-tested on physical Windows 11 hardware.

While this verified real-world hardware behavior (such as DirectWrite font fallback and DirectPrint spooler states), it created three severe strategic bottlenecks:
1. **Engineering Stall (Development Bottleneck)**: Both **Repo AI** and **GEM AI** were placed on indefinite hold between inspection rounds, artificially depressing project velocity.
2. **Platform Imbalance (Desktop Monoculture)**: Focusing test execution solely on the desktop client left the **Web App** (`classfellow_web`), **Mobile App** (`classfellow_mobile`), and **Cloud Sync** subsystems trailing behind without equal quality assurance or architectural parity.
3. **Automated Test Blindspots**: In-memory `pytest` runs (187 tests) validated Python logic and database schemas, but could not catch OS-level window rendering issues, native mobile Dart regressions, or real browser template breakage.

### 2. Chief Architect Directive: The Dual-Track Parallel Testing Mandate
Under formal authorization from the Chief Architect, ClassFellow is abandoning the sequential single-threaded USB halt model in favor of an **Enterprise Dual-Track Strategy**:

- **Track A (Continuous Fast Development & Automated Test Engine)**:
  - Development proceeds across all four architectural tiers simultaneously without waiting for physical USB cycles.
  - Test infrastructure is upgraded from single-engine `pytest` into a multi-tier automated test matrix covering Desktop, Web, Mobile, and Cloud Sync.
- **Track B (Asynchronous Milestone Physical Validation)**:
  - The Chief Architect receives standalone USB packages at designated **Major Release Milestones** for visual, tactile, and administrative validation on physical Windows 11 hardware.
  - Observations and refinements are logged into this register asynchronously as new feature requirements or non-blocking enhancements, without stalling engineering progress.

### 3. Multi-Platform Testing Architecture Blueprint

| Platform Tier | Current Test State | Upgraded Target Engine | Execution Environment |
| :--- | :--- | :--- | :--- |
| **1. Desktop Suite** | `pytest` (187 unit/migration tests) + Manual USB click testing | `pytest` + `pywinauto` / OS-level executable smoke test | Local `.venv` & GitHub Actions `windows-latest` |
| **2. Web Application** | Python HTTP mock tests (`test_django_web_views.py`) | `pytest-django` + PostgreSQL service container + Playwright browser E2E | Local Django dev server & CI Ubuntu container |
| **3. Mobile App** | Untracked Dart test files in `classfellow_mobile/test/` | Native `flutter test` / `dart test` integrated directly into root CI | GitHub Actions `ubuntu-latest` / Flutter SDK |
| **4. Cloud Sync & Reconciliation** | Unit tests for backup retention & SHA-256 manifests | Simulated offline/online network partition & dual-campus conflict tests | Pytest network mock harness |
| **5. CI/CD Pipeline** | Single-job Python `pytest` run in `.github/workflows/ci.yml` | Multi-job matrix pipeline (Desktop Build + Django Postgres + Flutter + Binary Smoke) | GitHub Actions CI/CD matrix |

### 4. Summary of Recently Completed Baseline (Phase 9 Gate 3 Finalization)
Before initiating this testing modernization, all Phase 9 Gate 3 objectives have been completed, verified, and committed to `develop`:
- **REF-001 (Two-Stage Punjab Admission Subsystem)**: Complete with sibling auto-discount math, prior arrears roll-forward, ReportLab 3-panel A4 fee vouchers, and keyboard shortcuts.
- **REF-002 (Mother Form, Dynamic Surcharges & Persona Splitter)**:
  - **Migration v5**: Added `guardian_email` and `previous_school_slc` to `students`; established `school_profiles` table; advanced `PRAGMA user_version` to `5`.
  - **Zero-State DB Cleanliness**: Production databases on cold boot contain 0 mock classes and 0 mock sessions, keeping databases pristine for the onboarding wizard.
  - **Route Guard Interception**: Blocks unconfigured admission attempts and launches the 4-tab `SchoolProfileModal` setup wizard.
  - **Persona Splitter**: Separate bordered cards for `Student Identity` and `Guardian Persona` with full RTL Urdu and `<Tab>` progression.
  - **Dynamic Surcharges**: Database-driven fee head grid (Generator Fuel, Paper Fund, Guard Fund, Lab Fee) with strict `Decimal` error handling.
  - **Single Branding**: Institutional name and crest logo dynamically branded on fee vouchers with `os.path.exists()` crash guards.
- **Test Suite Health**: **187/187 tests passing (100% green)**.
- **Binary Distribution**: Recompiled `ClassFellow.exe` (SHA-256: `751D11FF4EBDB97F919BD7732304E5424A3AEA26DD46DFD8D5BE6CBF758DA3F3`) mirrored to `dist/ClassFellow_Portable_USB/ClassFellow/`.
- **Git Baseline**: Synced on `origin/develop` at commit `e20cddd`.


