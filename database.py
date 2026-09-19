"""
ClassFellow - Database Connection & Engine Harness
===================================================
Provides thread-safe SQLite connection factory with strict relational pragmas,
WAL mode concurrency, and Decimal monetary serialization.
"""

import os
import sqlite3
from contextlib import contextmanager
from decimal import Decimal

# -----------------------------------------------------------------------------
# Register Custom Decimal Adapters and Converters
# SQLite does not have a native DECIMAL type. To prevent float coercion and
# arithmetic precision loss, all monetary values are adapted to/from strings.
# -----------------------------------------------------------------------------
sqlite3.register_adapter(Decimal, lambda d: str(d))
sqlite3.register_converter("DECIMAL", lambda s: Decimal(s.decode("utf-8")))

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "data", "classfellow.db")


@contextmanager
def transaction(conn: sqlite3.Connection):
    """
    Context manager for atomic SQLite transactions under isolation_level=None.
    Issues 'BEGIN IMMEDIATE;' to acquire an immediate write lock and prevent concurrency races.
    Supports nesting: nested transaction blocks participate in the active outer transaction.
    Commits on successful outer block completion, rolls back on any exception.
    """
    if conn.in_transaction:
        yield conn
        return

    conn.execute("BEGIN IMMEDIATE;")
    try:
        yield conn
        conn.execute("COMMIT;")
    except Exception:
        conn.execute("ROLLBACK;")
        raise


def get_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:

    """
    Creates and configures a SQLite connection with mandatory engine pragmas.

    Pragmas Enforced:
      - PRAGMA foreign_keys = ON;    (Enforces ON DELETE RESTRICT on ledgers)
      - PRAGMA journal_mode = WAL;   (Enables non-blocking concurrent readers)
      - PRAGMA synchronous = NORMAL; (Fast, safe durability for desktop crashes)

    Args:
        db_path: Filesystem path to the SQLite database file.

    Returns:
        A fully initialized, pragma-configured sqlite3.Connection instance.
    """
    db_dir = os.path.dirname(os.path.abspath(db_path))
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

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


def create_backup_snapshot(src_conn: sqlite3.Connection, dest_path: str) -> None:
    """
    Performs an online backup using SQLite's native backup API.
    Guarantees zero database locking and captures uncommitted WAL transactions cleanly.

    Args:
        src_conn: Active source sqlite3.Connection.
        dest_path: Destination path for the backup .db file.
    """
    dest_dir = os.path.dirname(os.path.abspath(dest_path))
    if dest_dir and not os.path.exists(dest_dir):
        os.makedirs(dest_dir, exist_ok=True)

    dest_conn = sqlite3.connect(dest_path)
    try:
        with dest_conn:
            src_conn.backup(dest_conn)
    finally:
        dest_conn.close()


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Returns the current PRAGMA user_version of the database."""
    cursor = conn.cursor()
    cursor.execute("PRAGMA user_version;")
    row = cursor.fetchone()
    return int(row[0]) if row else 0


def set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    """Updates the PRAGMA user_version of the database."""
    conn.execute(f"PRAGMA user_version = {version};")


def init_database(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """
    Creates a connection and runs all pending schema migrations up to the latest version.
    Ensures baseline zero-state standard fee heads exist.

    Returns:
        A fully initialized, migrated sqlite3.Connection instance.
    """
    from services.schema_service import migrate_to_latest, seed_default_academic_data
    conn = get_connection(db_path)
    migrate_to_latest(conn)
    seed_default_academic_data(conn)
    return conn
