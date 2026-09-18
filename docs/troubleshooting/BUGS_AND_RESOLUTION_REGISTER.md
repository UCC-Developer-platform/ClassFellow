# ClassFellow - Bug Register & Troubleshooting Resolution Matrix

**Document Reference**: `docs/troubleshooting/BUGS_AND_RESOLUTION_REGISTER.md`  
**Tracking Cycle**: Phase 9 Desktop Physical Auditing & Field Validation  
**Current Status**: **DEFECTS RESOLVED & VERIFIED (OPTION B IMPLEMENTED & COMPILED)**  
**Associated Baseline**: Release `v1.0.0-enterprise` / MVP Portable USB Build (Commit `2acc34d` $\rightarrow$ Option B Fixes)  
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
│            │                                        │                                  │
│            ▼                                        ▼                                  │
│   [ Chief Architect & GEM Review ] ──► [ Option B Authorized & Implemented ]          │
│                                                     │                                  │
│                                                     ▼                                  │
│   [ Standalone USB Recompiled ] ◄─── [ Automated Cold-Boot Regression Passed ]         │
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
| **BUG-004** | **HIGH** | Student Registration | Urdu Name field enforces LTR (Left-to-Right) typing instead of native RTL (Right-to-Left) BiDi flow in CustomTkinter input entry. | **ANALYZED** |
| **BUG-005** | **CRITICAL** | Student Registration | "Assign Class" dropdown displays unmapped "Default Class" on fresh database, triggering blocking "Validation Error" that prevents admissions. | **ANALYZED** |
| **BUG-002B**| **MEDIUM** | Shell UI / Sidebar | Compound Unicode ZWJ emoji (`👨‍🎓`) dissociates into dual glyphs (`👨` + `🎓`) on Windows DirectWrite Tkinter font fallback, expanding icon box width. | **ANALYZED** |
| **REF-001** | **ARCHITECTURAL**| Student Registration | Admission Modal fee charges section redesign & discount semantics (Awaiting physical competitor registration form samples from Chief Architect). | **HELD PENDING SAMPLES** |

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
2. **Current Governance Status**:
   - In accordance with the Chief Architect's directive, code implementation of this section is **HELD PENDING PHYSICAL COMPETITOR FORM SAMPLES**.

---

## Action Plan & Architectural Implementation Register

| Defect / Item ID | Severity | Target Files | Implementation Summary | Status |
| :--- | :---: | :--- | :--- | :---: |
| **BUG-001** | **CRITICAL** | `app/app.py`, `ui/student_view.py`, `ui/attendance_view.py`, `ui/exam_view.py` | App launch calls `init_database()` triggering `migrate_to_latest()`; `navigate_to()` wraps view creation in error recovery card; all views guard table queries with empty states. | **RESOLVED** |
| **BUG-002** | **MEDIUM** | `app/app.py` (`SidebarNavButton`) | Two-column compound layout with centered 36px icon container and uniform text starting at identical horizontal pixel coordinates. | **RESOLVED** |
| **BUG-003** | **HIGH** | `ui/settings_view.py` | Replaced cosmetic badges with live engine metrics (connection, WAL, PRAGMA user_version=3, file size), live row-count table probes, and a 1-click `🛠️ Verify & Auto-Repair Database` button. | **RESOLVED** |
| **BUG-004** | **HIGH** | `ui/student_view.py` | Configure `justify="right"` on `urdu_name` and bind Urdu font family; maintain unshaped raw Unicode in database for clean SQL queries. | **ANALYZED (Option B Ready)** |
| **BUG-005** | **CRITICAL** | `services/schema_service.py`, `ui/student_view.py` | Auto-seed baseline default class and session on startup; add inline `➕ New Class` sub-modal button directly adjacent to `Assign Class` dropdown. | **ANALYZED (Option B Ready)** |
| **BUG-002B**| **MEDIUM** | `app/app.py` | Replace multi-codepoint emoji `👨‍🎓` with single-codepoint `🎓` and enforce strict 2-column grid geometry to prevent font fallback width expansion. | **ANALYZED (Option A Ready)** |
| **REF-001** | **ARCHITECTURAL** | `ui/student_view.py`, `models/dto.py` | Redesign New Student Admission modal into a structured collapsible form with full fee schedule and net payable calculations. | **HELD PENDING SAMPLES** |

---

## Verification & Validation Evidence

1. **Automated Cold-Start Regression Suite**:
   - Authored `tests/test_cold_boot.py`:
     - `test_init_database_on_empty_file`: Verified on brand-new 0-byte SQLite database that `init_database()` builds all 15 relational tables and sets `user_version = 3`.
     - `test_app_cold_start_and_workspace_navigation`: Verified `ClassFellowApp` starts against unmigrated database, navigates through all 6 workspaces without errors, verifies two-column button alignment, and tests Settings live health telemetry and auto-repair utility.
2. **Full Test Suite Execution**:
   - `pytest -q`: **179/179 PASSED** (0 failures, 100% green across all 25 test suites in 31.94s).
3. **Standalone Production Binary Recompilation**:
   - Recompiled via PyInstaller: `dist\ClassFellow\ClassFellow.exe`.
   - Verified process launch without crash (PID 33408).
   - SHA-256 Digest: `B61BE4BBA7CD34BC586E29E1CB44D7CF1672A7DAD4BD23FB5EA68CBA2E8938E9`.
4. **USB Flash Drive Distribution Payload Updated**:
   - Synced fresh executable and runtime assets to `dist\ClassFellow_Portable_USB\ClassFellow\`.
   - Updated `dist\ClassFellow_Portable_USB\04_Verification_Tools\checksums.sha256`.
   - Ready for physical re-testing by Chief Architect on Windows 11.
