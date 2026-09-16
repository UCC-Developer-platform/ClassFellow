"""
Unit tests for database.py connection harness, pragmas, and Decimal serialization.
"""

import os
import sqlite3
from decimal import Decimal
import pytest

from database import get_connection, create_backup_snapshot, get_schema_version, set_schema_version


def test_sqlite_pragmas_enabled(db_connection):
    """Verifies that foreign keys, WAL mode, and synchronous normal are set."""
    cursor = db_connection.cursor()

    # Foreign keys must be ON (1)
    cursor.execute("PRAGMA foreign_keys;")
    assert cursor.fetchone()[0] == 1

    # Journal mode must be WAL
    cursor.execute("PRAGMA journal_mode;")
    assert cursor.fetchone()[0].upper() == "WAL"

    # Synchronous mode must be NORMAL (1)
    cursor.execute("PRAGMA synchronous;")
    assert cursor.fetchone()[0] == 1


def test_decimal_adapter_and_converter(db_connection):
    """Verifies that Decimal values are serialized as TEXT and deserialized as Decimal."""
    cursor = db_connection.cursor()
    cursor.execute("CREATE TABLE test_ledger (id INTEGER PRIMARY KEY, amount DECIMAL);")

    # Insert Python Decimal
    test_amount = Decimal("3450.75")
    cursor.execute("INSERT INTO test_ledger (amount) VALUES (?);", (test_amount,))

    # Retrieve and verify type
    cursor.execute("SELECT amount FROM test_ledger WHERE id = 1;")
    retrieved_amount = cursor.fetchone()[0]

    assert isinstance(retrieved_amount, Decimal)
    assert retrieved_amount == test_amount


def test_foreign_key_constraint_enforcement(db_connection):
    """Verifies that foreign key violations raise sqlite3.IntegrityError."""
    cursor = db_connection.cursor()
    cursor.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY);")
    cursor.execute("CREATE TABLE child (id INTEGER PRIMARY KEY, parent_id INTEGER REFERENCES parent(id) ON DELETE RESTRICT);")

    cursor.execute("INSERT INTO parent (id) VALUES (1);")
    cursor.execute("INSERT INTO child (id, parent_id) VALUES (10, 1);")

    # Deleting parent must raise IntegrityError due to ON DELETE RESTRICT
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute("DELETE FROM parent WHERE id = 1;")


def test_schema_version_tracking(db_connection):
    """Verifies reading and updating PRAGMA user_version."""
    assert get_schema_version(db_connection) == 0

    set_schema_version(db_connection, 4)
    assert get_schema_version(db_connection) == 4


def test_online_backup_api(db_connection, tmp_path):
    """Verifies native SQLite backup creates a clean snapshot without error."""
    cursor = db_connection.cursor()
    cursor.execute("CREATE TABLE sample (name TEXT);")
    cursor.execute("INSERT INTO sample (name) VALUES ('ClassFellow');")

    backup_file = str(tmp_path / "snapshot.db")
    create_backup_snapshot(db_connection, backup_file)

    assert os.path.exists(backup_file)

    # Verify backup content
    verify_conn = sqlite3.connect(backup_file)
    cur = verify_conn.cursor()
    cur.execute("SELECT name FROM sample;")
    assert cur.fetchone()[0] == "ClassFellow"
    verify_conn.close()


def test_memory_fixture_decimal_and_foreign_keys(memory_db_connection):
    """Verifies that the in-memory fixture properly enforces foreign keys and handles Decimals."""
    cursor = memory_db_connection.cursor()
    
    # Check foreign keys pragma
    cursor.execute("PRAGMA foreign_keys;")
    assert cursor.fetchone()[0] == 1

    # Verify Decimal serialization
    cursor.execute("CREATE TABLE fee_test (id INTEGER PRIMARY KEY, fee DECIMAL);")
    test_fee = Decimal("12500.50")
    cursor.execute("INSERT INTO fee_test (fee) VALUES (?);", (test_fee,))
    
    cursor.execute("SELECT fee FROM fee_test WHERE id = 1;")
    retrieved = cursor.fetchone()[0]
    assert isinstance(retrieved, Decimal)
    assert retrieved == test_fee

