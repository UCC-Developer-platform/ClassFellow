# SRS 01: ClassFellow - Core Kernel, Database Engine & Infrastructure Specification

## Document Information
- **Document Identifier**: `CF-SRS-01`
- **Project**: ClassFellow School and Academy Management Software
- **Version**: 1.0.0
- **Status**: APPROVED
- **Subsystem**: Core Engine, Storage Layer & Version Control

---

## 1. SQLite Database Engine Specification

The desktop application uses SQLite 3 as its embedded database engine. To achieve zero-loss concurrency, referential integrity, and crash resilience, all connections must execute through a centralized connection manager.

### 1.1 Connection Harness & Engine Pragmas

Every SQLite connection created by `database.py` must execute the following setup sequence:

```python
# database.py
import sqlite3
from decimal import Decimal

# Register Decimal adapters and converters
sqlite3.register_adapter(Decimal, lambda d: str(d))
sqlite3.register_converter("DECIMAL", lambda s: Decimal(s.decode("utf-8")))

def get_connection(db_path: str = "data/classfellow.db") -> sqlite3.Connection:
    conn = sqlite3.connect(
        db_path,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        timeout=10.0,
        isolation_level=None  # Explicit autocommit management via transactions
    )
    # Enable essential engine pragmas
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.row_factory = sqlite3.Row
    return conn
```

### 1.2 Mandatory Engineering Constraints
1. **Foreign Key Enforcement**: SQLite disables foreign keys by default. Executing `PRAGMA foreign_keys = ON;` is strictly enforced on every connection to protect relational constraints (specifically `ON DELETE RESTRICT` on financial payment ledgers).
2. **Write-Ahead Logging (WAL)**: `PRAGMA journal_mode = WAL;` allows concurrent readers to query the database (e.g., generating A4 fee vouchers in a background thread) while an office clerk performs write operations, preventing desktop UI lockups.
3. **Synchronous Normal**: `PRAGMA synchronous = NORMAL;` provides optimal write performance while maintaining database integrity across sudden power outages.

---

## 2. Monetary Precision & Type Converters

SQLite lacks an internal `DECIMAL` data type. Storing currency as `REAL` or Python `float` introduces catastrophic rounding discrepancies.

### 2.1 Currency Storage Convention
- All monetary fields in SQL table DDL must be defined explicitly as `TEXT NOT NULL` (e.g., `amount TEXT NOT NULL`).
- Python domain services must process monetary values strictly using the standard library `decimal.Decimal` module.
- The `sqlite3.register_adapter` and `sqlite3.register_converter` hooks serialize and deserialize `Decimal` instances to and from strings transparently without numeric distortion.

---

## 3. Offline Schema Migration Mechanism

Because ClassFellow runs as an offline desktop application without continuous internet access or external database administration tools, database schema updates must execute automatically upon executable launch.

### 3.1 `PRAGMA user_version` Migration Pipeline

1. **Version Tracking**: The SQLite database engine stores an integer version number via `PRAGMA user_version`.
2. **Startup Check**: During boot, `database.py` checks `PRAGMA user_version;`:
   ```python
   def apply_migrations(conn: sqlite3.Connection):
       cursor = conn.cursor()
       cursor.execute("PRAGMA user_version;")
       current_version = cursor.fetchone()[0]
       
       # Sequential migration dictionary
       migrations = {
           1: migration_v1_initial_schema,
           2: migration_v2_add_itemized_fees,
       }
       
       for version, migration_func in sorted(migrations.items()):
           if version > current_version:
               with conn:
                   migration_func(conn)
                   conn.execute(f"PRAGMA user_version = {version};")
   ```
3. **Atomicity**: Each migration executes inside a single database transaction (`with conn:`). If any DDL or data alteration fails, the transaction rolls back cleanly, preserving the prior database state.

---

## 4. 3-Tier Backup Architecture Specification

Data safety is the highest operational requirement for private institutions. ClassFellow establishes a 3-tier backup hierarchy:

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        3-TIER BACKUP ARCHITECTURE                      │
├────────────────────────────────────────────────────────────────────────┤
│ Tier 1: Local Daily Rolling Snapshots (Automated)                     │
│   • Trigger: Automated on app startup and clean exit.                  │
│   • Mechanism: Native SQLite Online Backup API (zero WAL corruption).  │
│   • Path: `data/backups/daily/classfellow_backup_YYYYMMDD_HHMMSS.db`   │
│   • Retention: Rolling 30-day window; automated pruning of old files.  │
├────────────────────────────────────────────────────────────────────────┤
│ Tier 2: Manual USB Snapshot Export / Import                           │
│   • Trigger: Admin initiates 1-click button in Settings.               │
│   • Mechanism: Encrypted .zip archive written to removable USB drive.  │
├────────────────────────────────────────────────────────────────────────┤
│ Tier 3: Automated Cloud Backup (Google Drive Sync)                     │
│   • Trigger: Asynchronous background worker checks connectivity.       │
│   • Mechanism: Uploads encrypted database snapshot to Google Drive.    │
└────────────────────────────────────────────────────────────────────────┘
```

### 4.1 Native SQLite Online Backup Implementation (Tier 1 & 2)

Copying active SQLite databases via filesystem file copies (`shutil.copy2`) while WAL mode is active risks creating corrupted snapshots. All backups must use the native SQLite online backup API:

```python
def create_backup_snapshot(src_conn: sqlite3.Connection, dest_path: str):
    dest_conn = sqlite3.connect(dest_path)
    with dest_conn:
        src_conn.backup(dest_conn)
    dest_conn.close()
```

---

## 5. UI Threading & Windows High-DPI Scaling Standards

### 5.1 Asynchronous Worker Pool (`ThreadPoolExecutor` + `root.after`)
To maintain complete UI responsiveness and prevent Windows *"Not Responding"* hangs during long-running batch operations (such as generating 500 A4 vouchers or syncing to Google Drive):
- Long tasks execute in a `ThreadPoolExecutor(max_workers=4)`.
- UI updates, loading spinners, and completion modals are dispatched back to the main thread exclusively via `root.after(0, callback)`.

### 5.2 Windows High-DPI Scaling Guard (`app.py`)
To prevent blurry text on 1080p, 2K, and 4K laptop displays, `app.py` declares per-monitor DPI awareness v2 wrapped in an exception guard:

```python
import sys, ctypes

def init_windows_dpi():
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass  # Fall back gracefully to CustomTkinter's internal scaling
```

---

## 6. Version Control & CI/CD Pipeline Specification

### 6.1 Git Repository Conventions
- **Production Branch (`main`)**: Protected. Contains only stable, tagged commercial releases.
- **Development Branch (`develop`)**: Primary integration branch for verified feature merges.
- **Feature Branches (`feature/module-name`)**: Scoped branches for individual modules and tasks.

### 6.2 `.gitignore` Exclusions
The repository `.gitignore` must strictly exclude:
- Virtual environments (`.venv/`, `env/`)
- Compiled Python artifacts (`__pycache__/`, `*.pyc`, `*.pyo`)
- Local databases and backups (`data/*.db`, `data/backups/`)
- Application logs (`logs/*.log`)
- Environment secrets (`.env`, `credentials.json`)
- OS files (`Thumbs.db`, `.DS_Store`)

### 6.3 GitHub Actions CI/CD (`.github/workflows/ci.yml`)
Automated workflow executing on every push and pull request:
- Installs pinned dependencies from `requirements.txt`.
- Runs test suite via `pytest --cov=services --cov=database`.
- Verifies code formatting and linting via `flake8`.
- Ensures zero regressions across database pragmas and monetary calculations.
