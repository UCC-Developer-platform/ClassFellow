"""
ClassFellow - 3-Tier Automated Backup Subsystem (services/backup_service.py)
============================================================================
Provides institutional data safety across 3 distinct tiers:
  - Tier 1 (BKP-01): Local daily rolling snapshots using SQLite's native online
                     backup API with 30-day automated retention pruning.
  - Tier 2 (BKP-02): Manual 1-click structured USB export/import with SHA-256
                     cryptographic checksums and atomic restore sequence.
  - Tier 3 (BKP-03): Asynchronous cloud sync worker interface with non-blocking
                     socket connectivity probe for Google Drive integration.
"""

import os
import time
import json
import socket
import shutil
import hashlib
import zipfile
import logging
import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Optional, Dict, List, Any, Callable

from database import create_backup_snapshot

logger = logging.getLogger(__name__)

DEFAULT_RETENTION_DAYS = 30
DEFAULT_CONNECTIVITY_HOST = "8.8.8.8"
DEFAULT_CONNECTIVITY_PORT = 53
DEFAULT_CONNECTIVITY_TIMEOUT = 2.0


def check_network_connectivity(
    host: str = DEFAULT_CONNECTIVITY_HOST,
    port: int = DEFAULT_CONNECTIVITY_PORT,
    timeout: float = DEFAULT_CONNECTIVITY_TIMEOUT,
) -> bool:
    """
    Non-blocking network probe to verify active internet connectivity.
    Attempts a lightweight TCP handshake against a dependable public DNS host.
    """
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, OSError):
        return False


# =============================================================================
# Tier 3 Cloud Provider Abstraction & Worker
# =============================================================================

class CloudSyncProvider(ABC):
    """Abstract contract for cloud backup sync providers (e.g. Google Drive)."""

    @abstractmethod
    def authenticate(self) -> bool:
        """Authenticates with remote cloud service credentials."""
        pass

    @abstractmethod
    def upload_backup(
        self, local_path: str, remote_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Uploads a local backup file to cloud destination."""
        pass


class GoogleDriveSyncWorker:
    """
    Asynchronous background worker handling cloud backup synchronization
    without blocking desktop UI responsiveness or locking SQLite files.
    """

    def __init__(
        self,
        provider: Optional[CloudSyncProvider] = None,
        max_workers: int = 1,
    ):
        self.provider = provider
        self.executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="CloudSyncWorker"
        )

    def sync_snapshot_async(
        self,
        local_path: str,
        remote_filename: Optional[str] = None,
        on_complete: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Future:
        """
        Dispatches backup upload asynchronously. Performs live connectivity
        check before invoking provider upload.
        """
        def _task() -> Dict[str, Any]:
            if not os.path.exists(local_path):
                res = {
                    "status": "error",
                    "synced": False,
                    "error": f"Local file not found: {local_path}",
                }
                if on_complete:
                    on_complete(res)
                return res

            if not check_network_connectivity():
                res = {
                    "status": "offline",
                    "synced": False,
                    "error": "No internet connectivity detected. Deferred sync.",
                }
                if on_complete:
                    on_complete(res)
                return res

            if not self.provider or not self.provider.authenticate():
                res = {
                    "status": "unauthenticated",
                    "synced": False,
                    "error": "Cloud provider not configured or authentication failed.",
                }
                if on_complete:
                    on_complete(res)
                return res

            try:
                upload_res = self.provider.upload_backup(local_path, remote_filename)
                res = {
                    "status": "success",
                    "synced": True,
                    "details": upload_res,
                }
            except Exception as exc:
                logger.error(f"Cloud backup upload failed: {exc}")
                res = {
                    "status": "error",
                    "synced": False,
                    "error": str(exc),
                }

            if on_complete:
                on_complete(res)
            return res

        return self.executor.submit(_task)

    def shutdown(self, wait: bool = False) -> None:
        """Terminates background worker threads."""
        self.executor.shutdown(wait=wait)


# =============================================================================
# Core Backup Service Orchestrator
# =============================================================================

class BackupService:
    """
    Unified backup service orchestrating Tier 1 (daily rolling snapshots),
    Tier 2 (manual USB archive exports/restores), and Tier 3 (cloud sync).
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        db_path: Optional[str] = None,
        backup_base_dir: Optional[str] = None,
    ):
        self.conn = conn
        self.db_path = db_path

        if backup_base_dir:
            self.base_dir = os.path.abspath(backup_base_dir)
        else:
            root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.base_dir = os.path.join(root_dir, "data", "backups")

        self.daily_dir = os.path.join(self.base_dir, "daily")
        self.exports_dir = os.path.join(self.base_dir, "exports")

        os.makedirs(self.daily_dir, exist_ok=True)
        os.makedirs(self.exports_dir, exist_ok=True)

    # -------------------------------------------------------------------------
    # Tier 1: Local Daily Rolling Snapshots (BKP-01)
    # -------------------------------------------------------------------------

    def create_daily_backup(self, prefix: str = "classfellow_backup") -> str:
        """
        Creates an online SQLite backup snapshot in data/backups/daily/.
        Uses native src_conn.backup(dest_conn) ensuring zero WAL file locking.
        """
        now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest_filename = f"{prefix}_{now_str}.db"
        dest_path = os.path.join(self.daily_dir, dest_filename)

        create_backup_snapshot(self.conn, dest_path)
        logger.info(f"Tier 1 daily backup created: {dest_path}")
        return dest_path

    def prune_old_backups(self, retention_days: int = DEFAULT_RETENTION_DAYS) -> List[str]:
        """
        Enforces rolling retention window in data/backups/daily/.
        Prunes files older than retention_days based on file modification time.
        """
        cutoff_seconds = time.time() - (retention_days * 86400)
        pruned_files: List[str] = []

        if not os.path.exists(self.daily_dir):
            return pruned_files

        for entry in os.listdir(self.daily_dir):
            if not entry.endswith(".db"):
                continue

            full_path = os.path.join(self.daily_dir, entry)
            if not os.path.isfile(full_path):
                continue

            file_mtime = os.path.getmtime(full_path)
            if file_mtime < cutoff_seconds:
                try:
                    os.remove(full_path)
                    pruned_files.append(full_path)
                    logger.info(f"Pruned expired backup file: {full_path}")
                except OSError as exc:
                    logger.warning(f"Failed to prune {full_path}: {exc}")

        return pruned_files

    def run_startup_backup(self) -> Optional[str]:
        """
        Startup lifecycle hook: generates a fresh daily snapshot and prunes
        expired snapshots older than 30 days. Suppresses exceptions to prevent
        application launch crashes.
        """
        try:
            backup_path = self.create_daily_backup()
            self.prune_old_backups(DEFAULT_RETENTION_DAYS)
            return backup_path
        except Exception as exc:
            logger.error(f"Startup backup encountered an error: {exc}", exc_info=True)
            return None

    def run_shutdown_backup(self) -> Optional[str]:
        """
        Shutdown lifecycle hook: safely snapshots database state on clean exit.
        """
        try:
            return self.create_daily_backup()
        except Exception as exc:
            logger.error(f"Shutdown backup encountered an error: {exc}", exc_info=True)
            return None

    # -------------------------------------------------------------------------
    # Tier 2: Manual USB Snapshot Export / Import (BKP-02)
    # -------------------------------------------------------------------------

    def export_usb_backup(
        self,
        target_directory: str,
        archive_name: Optional[str] = None,
    ) -> str:
        """
        Packages an atomic online SQLite snapshot, SHA-256 integrity hash,
        and manifest.json into a portable ZIP archive for USB storage.
        """
        os.makedirs(target_directory, exist_ok=True)
        now = datetime.now()

        if not archive_name:
            archive_name = f"classfellow_usb_backup_{now.strftime('%Y%m%d_%H%M%S')}.zip"
        if not archive_name.endswith(".zip"):
            archive_name += ".zip"

        archive_path = os.path.join(target_directory, archive_name)

        # 1. Capture atomic online snapshot into temp file
        temp_snapshot_name = f"temp_usb_{now.strftime('%Y%m%d_%H%M%S_%f')}.db"
        temp_snapshot_path = os.path.join(self.exports_dir, temp_snapshot_name)
        create_backup_snapshot(self.conn, temp_snapshot_path)

        try:
            # 2. Compute cryptographic SHA-256 hash of snapshot
            hasher = hashlib.sha256()
            with open(temp_snapshot_path, "rb") as f:
                while chunk := f.read(65536):
                    hasher.update(chunk)
            sha256_digest = hasher.hexdigest()

            # 3. Extract schema version and table record counts for audit manifest
            temp_conn = sqlite3.connect(temp_snapshot_path)
            try:
                cur = temp_conn.cursor()
                cur.execute("PRAGMA user_version;")
                schema_version = cur.fetchone()[0]

                cur.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
                )
                tables = [row[0] for row in cur.fetchall()]
                table_counts = {}
                for tbl in tables:
                    try:
                        cur.execute(f"SELECT COUNT(*) FROM \"{tbl}\";")
                        table_counts[tbl] = cur.fetchone()[0]
                    except Exception:
                        table_counts[tbl] = 0
            finally:
                temp_conn.close()

            manifest_data = {
                "app_name": "ClassFellow",
                "app_version": "1.0.0",
                "backup_type": "usb_snapshot",
                "created_at": now.isoformat(),
                "db_file": "classfellow_snapshot.db",
                "sha256": sha256_digest,
                "schema_version": schema_version,
                "table_counts": table_counts,
            }

            # 4. Package into compressed ZIP archive
            with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.write(temp_snapshot_path, arcname="classfellow_snapshot.db")
                zf.writestr("manifest.json", json.dumps(manifest_data, indent=2))

            logger.info(f"Tier 2 USB backup archive exported: {archive_path}")
            return archive_path

        finally:
            if os.path.exists(temp_snapshot_path):
                try:
                    os.remove(temp_snapshot_path)
                except OSError:
                    pass

    @staticmethod
    def verify_backup_archive(archive_path: str) -> Dict[str, Any]:
        """
        Validates the integrity of a backup ZIP archive:
          1. Verifies ZIP archive structure.
          2. Parses manifest.json.
          3. Recalculates SHA-256 hash of packaged .db and verifies against manifest.
        Raises ValueError if corrupted or tampered.
        """
        if not os.path.exists(archive_path):
            raise FileNotFoundError(f"Backup archive not found: {archive_path}")

        if not zipfile.is_zipfile(archive_path):
            raise ValueError(f"File is not a valid ZIP archive: {archive_path}")

        with zipfile.ZipFile(archive_path, "r") as zf:
            namelist = zf.namelist()
            if "manifest.json" not in namelist:
                raise ValueError("Corrupt backup archive: Missing manifest.json.")

            try:
                manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
            except Exception as exc:
                raise ValueError(f"Corrupt backup archive: Invalid manifest JSON ({exc}).")

            db_filename = manifest.get("db_file", "classfellow_snapshot.db")
            if db_filename not in namelist:
                raise ValueError(f"Corrupt backup archive: Missing {db_filename}.")

            # Compute SHA-256 of internal database bytes
            hasher = hashlib.sha256()
            with zf.open(db_filename) as db_stream:
                while chunk := db_stream.read(65536):
                    hasher.update(chunk)
            computed_sha256 = hasher.hexdigest()

            expected_sha256 = manifest.get("sha256")
            if computed_sha256 != expected_sha256:
                raise ValueError(
                    f"Integrity check failed: SHA-256 checksum mismatch "
                    f"(expected {expected_sha256}, calculated {computed_sha256})."
                )

        return {
            "is_valid": True,
            "manifest": manifest,
            "sha256": computed_sha256,
            "archive_path": archive_path,
        }

    @classmethod
    def restore_from_backup_archive(
        cls,
        archive_path: str,
        target_db_path: str,
    ) -> bool:
        """
        Executes atomic database restore sequence per architecture rules:
          1. Verifies archive integrity (SHA-256 check) first.
          2. Purges target database and any companion WAL/SHM files to prevent journal mismatch.
          3. Extracts database snapshot to target location.
          4. Verifies restored SQLite file passes PRAGMA integrity_check.
        """
        # Step 1: Pre-restore integrity audit
        verify_result = cls.verify_backup_archive(archive_path)
        manifest = verify_result["manifest"]
        db_arcname = manifest.get("db_file", "classfellow_snapshot.db")

        target_dir = os.path.dirname(os.path.abspath(target_db_path))
        if target_dir and not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)

        # Step 2: Atomic cleanup of target and companion WAL/SHM files
        for ext in ("", "-wal", "-shm"):
            companion_path = f"{target_db_path}{ext}"
            if os.path.exists(companion_path):
                os.remove(companion_path)

        # Step 3: Extract database stream directly
        with zipfile.ZipFile(archive_path, "r") as zf:
            with zf.open(db_arcname) as src, open(target_db_path, "wb") as dst:
                shutil.copyfileobj(src, dst)

        # Step 4: Verification of restored database
        check_conn = sqlite3.connect(target_db_path)
        try:
            cur = check_conn.cursor()
            cur.execute("PRAGMA integrity_check;")
            row = cur.fetchone()
            if not row or row[0] != "ok":
                raise ValueError(f"Restored database integrity check failed: {row}")
        finally:
            check_conn.close()

        logger.info(f"Database successfully restored from {archive_path} to {target_db_path}")
        return True
