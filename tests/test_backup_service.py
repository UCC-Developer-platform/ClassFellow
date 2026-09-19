"""
Automated Test Suite for 3-Tier Backup Architecture Subsystem
============================================================
Tests:
  - Tier 1: SQLite online snapshot creation, deterministic 30-day retention
            pruning using os.utime manipulation, startup/shutdown hooks.
  - Tier 2: 1-click USB export with SHA-256 hash and manifest.json,
            tamper detection, and atomic restore sequence with companion file purge.
  - Tier 3: Socket connectivity probe and asynchronous GoogleDriveSyncWorker.
"""

import os
import time
import json
import socket
import sqlite3
import zipfile
import pytest
from unittest.mock import patch, MagicMock

from database import init_database, get_connection
from services.backup_service import (
    BackupService,
    CloudSyncProvider,
    GoogleDriveSyncWorker,
    check_network_connectivity,
    DEFAULT_RETENTION_DAYS,
)


@pytest.fixture
def populated_db(tmp_path):
    """Creates a temporary migrated SQLite database with sample data."""
    db_path = str(tmp_path / "classfellow_test.db")
    conn = init_database(db_path)

    # Insert baseline test data
    conn.execute(
        "INSERT OR IGNORE INTO academic_sessions (name, start_date, end_date, is_active) "
        "VALUES ('2026-2027 Academic Session', '2026-04-01', '2027-03-31', 1);"
    )
    conn.execute(
        "INSERT INTO class_groups (session_id, name, section_or_batch, group_type, monthly_tuition_fee) "
        "VALUES (1, 'Class 10', 'A', 'SchoolClass', '2500.00');"
    )
    conn.execute(
        "INSERT INTO students (admission_number, first_name, last_name, gender, guardian_name, guardian_phone) "
        "VALUES ('CF-2026-0001', 'Ahmed', 'Khan', 'Male', 'Tariq Khan', '03001234567');"
    )
    return conn, db_path


@pytest.fixture
def backup_service(populated_db, tmp_path):
    """Initializes BackupService with isolated temporary backup directories."""
    conn, db_path = populated_db
    backup_base = str(tmp_path / "backups")
    return BackupService(conn=conn, db_path=db_path, backup_base_dir=backup_base)


# =============================================================================
# Tier 1 Tests (BKP-01): Daily Rolling Backup & Retention Pruning
# =============================================================================

def test_tier1_daily_backup_online_snapshot(backup_service):
    """Verifies that create_daily_backup captures an uncorrupted SQLite snapshot."""
    backup_path = backup_service.create_daily_backup(prefix="test_snap")

    assert os.path.exists(backup_path)
    assert backup_path.endswith(".db")
    assert "test_snap_" in os.path.basename(backup_path)

    # Validate snapshot can be opened and contains migrated schema and records
    snap_conn = sqlite3.connect(backup_path)
    try:
        cur = snap_conn.cursor()
        cur.execute("PRAGMA integrity_check;")
        assert cur.fetchone()[0] == "ok"

        cur.execute("PRAGMA user_version;")
        assert cur.fetchone()[0] == 4  # Schema version v4 (Punjab admission subsystem)

        cur.execute("SELECT COUNT(*) FROM students;")
        assert cur.fetchone()[0] == 1

        cur.execute("SELECT COUNT(*) FROM academic_sessions;")
        assert cur.fetchone()[0] == 1
    finally:
        snap_conn.close()


def test_tier1_retention_pruning_30_days(backup_service):
    """
    Verifies rolling retention pruning using os.utime to simulate file age:
      - Files older than 30 days are purged.
      - Files within the 30-day window are preserved.
    """
    now = time.time()
    daily_dir = backup_service.daily_dir

    # 1. Create simulated test backup files with varied ages
    files_to_create = [
        ("classfellow_backup_old_40d.db", now - (40 * 86400)),
        ("classfellow_backup_old_31d.db", now - (31 * 86400)),
        ("classfellow_backup_recent_25d.db", now - (25 * 86400)),
        ("classfellow_backup_recent_5d.db", now - (5 * 86400)),
        ("classfellow_backup_today.db", now),
    ]

    for fname, timestamp in files_to_create:
        fpath = os.path.join(daily_dir, fname)
        with open(fpath, "w") as f:
            f.write("mock sqlite content")
        os.utime(fpath, (timestamp, timestamp))

    # 2. Execute retention pruning
    pruned = backup_service.prune_old_backups(retention_days=DEFAULT_RETENTION_DAYS)

    # 3. Assertions: 40-day and 31-day backups removed, others retained
    assert len(pruned) == 2
    assert any("old_40d" in p for p in pruned)
    assert any("old_31d" in p for p in pruned)

    remaining_files = os.listdir(daily_dir)
    assert "classfellow_backup_old_40d.db" not in remaining_files
    assert "classfellow_backup_old_31d.db" not in remaining_files
    assert "classfellow_backup_recent_25d.db" in remaining_files
    assert "classfellow_backup_recent_5d.db" in remaining_files
    assert "classfellow_backup_today.db" in remaining_files


def test_tier1_lifecycle_startup_and_shutdown_hooks(backup_service):
    """Verifies that startup and shutdown hooks execute cleanly without exceptions."""
    startup_path = backup_service.run_startup_backup()
    assert startup_path is not None
    assert os.path.exists(startup_path)

    shutdown_path = backup_service.run_shutdown_backup()
    assert shutdown_path is not None
    assert os.path.exists(shutdown_path)


# =============================================================================
# Tier 2 Tests (BKP-02): USB Export, Manifest, Tamper Detection & Restore
# =============================================================================

def test_tier2_usb_export_with_manifest_and_sha256(backup_service, tmp_path):
    """Verifies that USB export bundles snapshot, valid manifest, and SHA-256 hash."""
    usb_dir = str(tmp_path / "usb_drive")
    archive_path = backup_service.export_usb_backup(target_directory=usb_dir)

    assert os.path.exists(archive_path)
    assert zipfile.is_zipfile(archive_path)

    # Verify archive structure and contents
    verify_result = BackupService.verify_backup_archive(archive_path)
    assert verify_result["is_valid"] is True

    manifest = verify_result["manifest"]
    assert manifest["app_name"] == "ClassFellow"
    assert manifest["schema_version"] == 4
    assert manifest["db_file"] == "classfellow_snapshot.db"
    assert manifest["table_counts"]["students"] == 1
    assert "sha256" in manifest
    assert len(manifest["sha256"]) == 64  # Valid SHA-256 hex digest


def test_tier2_archive_tamper_detection(backup_service, tmp_path):
    """Verifies that verify_backup_archive rejects modified or corrupted archives."""
    usb_dir = str(tmp_path / "usb_drive")
    archive_path = backup_service.export_usb_backup(target_directory=usb_dir)

    # Create tampered archive by altering the database bytes while keeping manifest unchanged
    tampered_archive_path = str(tmp_path / "tampered_backup.zip")
    with zipfile.ZipFile(archive_path, "r") as src_zip:
        manifest_bytes = src_zip.read("manifest.json")

    with zipfile.ZipFile(tampered_archive_path, "w") as dst_zip:
        dst_zip.writestr("manifest.json", manifest_bytes)
        dst_zip.writestr("classfellow_snapshot.db", b"CORRUPTED_TAMPERED_DATABASE_PAYLOAD")

    with pytest.raises(ValueError, match="Integrity check failed: SHA-256 checksum mismatch"):
        BackupService.verify_backup_archive(tampered_archive_path)


def test_tier2_restore_from_backup_archive_with_companion_purge(backup_service, tmp_path):
    """
    Verifies atomic restore sequence:
      - Validates SHA-256 first.
      - Purges target DB along with any lingering -wal and -shm files.
      - Extracts and verifies restored SQLite database integrity.
    """
    usb_dir = str(tmp_path / "usb_drive")
    archive_path = backup_service.export_usb_backup(target_directory=usb_dir)

    # Prepare a mock target location with lingering companion WAL and SHM files
    restore_target = str(tmp_path / "restored_classfellow.db")
    wal_file = f"{restore_target}-wal"
    shm_file = f"{restore_target}-shm"

    with open(restore_target, "w") as f:
        f.write("old corrupted db")
    with open(wal_file, "w") as f:
        f.write("old uncommitted wal logs")
    with open(shm_file, "w") as f:
        f.write("old shm index")

    # Execute atomic restore
    success = BackupService.restore_from_backup_archive(archive_path, restore_target)
    assert success is True

    # Confirm companion WAL/SHM files were safely purged
    assert not os.path.exists(wal_file)
    assert not os.path.exists(shm_file)

    # Verify restored database content and integrity
    res_conn = sqlite3.connect(restore_target)
    try:
        cur = res_conn.cursor()
        cur.execute("PRAGMA integrity_check;")
        assert cur.fetchone()[0] == "ok"

        cur.execute("SELECT first_name, last_name FROM students WHERE admission_number='CF-2026-0001';")
        assert cur.fetchone() == ("Ahmed", "Khan")
    finally:
        res_conn.close()


# =============================================================================
# Tier 3 Tests (BKP-03): Connectivity Probe & Cloud Sync Worker
# =============================================================================

def test_tier3_network_connectivity_probe():
    """Verifies that check_network_connectivity properly detects socket states."""
    # Test successful socket connection (mocked)
    with patch("socket.create_connection") as mock_conn:
        mock_conn.return_value = MagicMock()
        assert check_network_connectivity() is True

    # Test socket timeout / failure
    with patch("socket.create_connection", side_effect=socket.timeout):
        assert check_network_connectivity() is False

    with patch("socket.create_connection", side_effect=OSError("Network unreachable")):
        assert check_network_connectivity() is False


def test_tier3_cloud_sync_worker_online_flow(tmp_path):
    """Verifies that GoogleDriveSyncWorker successfully dispatches cloud uploads when online."""
    dummy_file = str(tmp_path / "dummy_backup.db")
    with open(dummy_file, "w") as f:
        f.write("test db")

    # Create mock cloud provider
    mock_provider = MagicMock(spec=CloudSyncProvider)
    mock_provider.authenticate.return_value = True
    mock_provider.upload_backup.return_value = {
        "file_id": "gdrive_12345",
        "web_link": "https://drive.google.com/file/d/12345",
    }

    worker = GoogleDriveSyncWorker(provider=mock_provider)

    callback_called = []
    def on_complete(res):
        callback_called.append(res)

    with patch("services.backup_service.check_network_connectivity", return_value=True):
        future = worker.sync_snapshot_async(
            local_path=dummy_file,
            remote_filename="cloud_backup.db",
            on_complete=on_complete,
        )
        result = future.result(timeout=3.0)

    assert result["status"] == "success"
    assert result["synced"] is True
    assert result["details"]["file_id"] == "gdrive_12345"
    assert len(callback_called) == 1

    worker.shutdown(wait=True)


def test_tier3_cloud_sync_worker_offline_fallback(tmp_path):
    """Verifies that GoogleDriveSyncWorker gracefully defers when offline without exceptions."""
    dummy_file = str(tmp_path / "dummy_backup.db")
    with open(dummy_file, "w") as f:
        f.write("test db")

    mock_provider = MagicMock(spec=CloudSyncProvider)
    worker = GoogleDriveSyncWorker(provider=mock_provider)

    with patch("services.backup_service.check_network_connectivity", return_value=False):
        future = worker.sync_snapshot_async(local_path=dummy_file)
        result = future.result(timeout=3.0)

    assert result["status"] == "offline"
    assert result["synced"] is False
    assert "No internet connectivity" in result["error"]
    mock_provider.upload_backup.assert_not_called()

    worker.shutdown(wait=True)


def test_tier2_verify_archive_validation_errors(tmp_path):
    """Verifies that verify_backup_archive raises appropriate errors on invalid archives."""
    # 1. Non-existent file
    with pytest.raises(FileNotFoundError):
        BackupService.verify_backup_archive(str(tmp_path / "non_existent.zip"))

    # 2. Not a valid zip
    not_zip = str(tmp_path / "not_a_zip.zip")
    with open(not_zip, "w") as f:
        f.write("plain text")
    with pytest.raises(ValueError, match="not a valid ZIP archive"):
        BackupService.verify_backup_archive(not_zip)

    # 3. Missing manifest.json
    no_manifest = str(tmp_path / "no_manifest.zip")
    with zipfile.ZipFile(no_manifest, "w") as zf:
        zf.writestr("some_file.txt", "data")
    with pytest.raises(ValueError, match="Missing manifest.json"):
        BackupService.verify_backup_archive(no_manifest)

    # 4. Corrupt JSON manifest
    bad_json = str(tmp_path / "bad_json.zip")
    with zipfile.ZipFile(bad_json, "w") as zf:
        zf.writestr("manifest.json", "{invalid_json_format")
    with pytest.raises(ValueError, match="Invalid manifest JSON"):
        BackupService.verify_backup_archive(bad_json)

    # 5. Missing db file
    missing_db = str(tmp_path / "missing_db.zip")
    with zipfile.ZipFile(missing_db, "w") as zf:
        zf.writestr("manifest.json", json.dumps({"db_file": "missing.db", "sha256": "123"}))
    with pytest.raises(ValueError, match="Missing missing.db"):
        BackupService.verify_backup_archive(missing_db)


def test_tier2_restore_corrupt_db_integrity_fails(tmp_path):
    """Verifies that restore_from_backup_archive detects invalid SQLite file during integrity check."""
    import hashlib
    corrupt_zip = str(tmp_path / "corrupt_db.zip")
    bad_content = b"NOT_A_VALID_SQLITE_DATABASE"
    sha256_hash = hashlib.sha256(bad_content).hexdigest()

    with zipfile.ZipFile(corrupt_zip, "w") as zf:
        zf.writestr("classfellow_snapshot.db", bad_content)
        zf.writestr(
            "manifest.json",
            json.dumps({"db_file": "classfellow_snapshot.db", "sha256": sha256_hash}),
        )

    target_restore = str(tmp_path / "corrupt_restore.db")
    with pytest.raises(Exception):
        BackupService.restore_from_backup_archive(corrupt_zip, target_restore)


def test_tier3_cloud_sync_worker_error_branches(tmp_path):
    """Verifies cloud sync worker error branches: file not found, unauthenticated, and upload error."""
    mock_provider = MagicMock(spec=CloudSyncProvider)
    worker = GoogleDriveSyncWorker(provider=mock_provider)

    # 1. File not found
    future = worker.sync_snapshot_async(local_path=str(tmp_path / "does_not_exist.db"))
    res = future.result(timeout=2.0)
    assert res["status"] == "error"
    assert "not found" in res["error"]

    # 2. Unauthenticated provider
    dummy_file = str(tmp_path / "test_auth.db")
    with open(dummy_file, "w") as f:
        f.write("content")

    mock_provider.authenticate.return_value = False
    with patch("services.backup_service.check_network_connectivity", return_value=True):
        future = worker.sync_snapshot_async(local_path=dummy_file)
        res = future.result(timeout=2.0)
    assert res["status"] == "unauthenticated"

    # 3. Upload exception
    mock_provider.authenticate.return_value = True
    mock_provider.upload_backup.side_effect = RuntimeError("Google Drive API rate limit exceeded")
    with patch("services.backup_service.check_network_connectivity", return_value=True):
        future = worker.sync_snapshot_async(local_path=dummy_file)
        res = future.result(timeout=2.0)
    assert res["status"] == "error"
    assert "rate limit exceeded" in res["error"]

    worker.shutdown(wait=True)


def test_tier1_lifecycle_exception_guards(backup_service):
    """Verifies that startup and shutdown hooks suppress exceptions safely."""
    with patch.object(backup_service, "create_daily_backup", side_effect=RuntimeError("Disk full")):
        assert backup_service.run_startup_backup() is None
        assert backup_service.run_shutdown_backup() is None

