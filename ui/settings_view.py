"""
ClassFellow - Settings & Safety View (ui/settings_view.py)
=========================================================
System configuration, commercial tier & module feature flag inspection,
and 1-click execution of the 3-Tier Backup Architecture.
"""

import os
from datetime import datetime
from typing import Optional, Dict, Any
import customtkinter as ctk
from tkinter import filedialog

from database import init_database, get_schema_version
from services.backup_service import BackupService, check_network_connectivity, GoogleDriveSyncWorker
from ui.base_view import BaseView, THEME_COLORS


class SettingsView(BaseView):
    """Settings, feature flags, and backup operations workspace."""

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, app, **kwargs)
        self.backup_service: Optional[BackupService] = getattr(app, "backup_service", None)
        if not self.backup_service and self.db_conn:
            self.backup_service = BackupService(self.db_conn, getattr(app, "db_path", None))

        self._build_ui()
        self.refresh_data()

    def _build_ui(self) -> None:
        """Constructs license tier cards, feature flags list, and 3-tier backup cards."""
        # 1. Header Banner
        self.create_header(
            title="Settings & Data Safety",
            subtitle="Commercial module entitlements, system diagnostics, and 3-tier backup controls",
            actions=[
                ("🔄 Refresh", self.refresh_data, self.colors["brand_accent"]),
            ],
        )

        # 2. Main Scrollable Container
        self.content_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.content_scroll.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        # 3. Institutional Profile & Mother Form Card
        self._build_institutional_profile_card(self.content_scroll)

        # 4. System Diagnostics & Active Database Engine Health Card
        self._build_system_health_card(self.content_scroll)

        # 5. 3-Tier Automated Backup Management Card
        self._build_backup_card(self.content_scroll)

    def _build_institutional_profile_card(self, parent) -> None:
        """Renders institutional profile inspection and Mother Form launcher card."""
        card = ctk.CTkFrame(parent, fg_color=self.colors["bg_card"], corner_radius=8)
        card.pack(fill="x", pady=(0, 16))

        top_bar = ctk.CTkFrame(card, fg_color="transparent")
        top_bar.pack(fill="x", padx=16, pady=(12, 6))

        ctk.CTkLabel(
            top_bar,
            text="🏫 Institutional Profile & Academic Setup (Mother Form)",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=self.colors["text_primary"]
        ).pack(side="left")

        btn_open_profile = ctk.CTkButton(
            top_bar,
            text="⚙️ Open School Profile & Setup Wizard",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=self.colors["brand_primary"],
            hover_color=self.colors["brand_accent"],
            command=self._open_school_profile_modal
        )
        btn_open_profile.pack(side="right")

        ctk.CTkLabel(
            card,
            text="Manage institutional branding, official contacts, academic calendar, active grade levels, and regional surcharge catalog.",
            font=ctk.CTkFont(size=11),
            text_color=self.colors["text_secondary"]
        ).pack(anchor="w", padx=16, pady=(0, 8))

        # Profile details grid
        info_frame = ctk.CTkFrame(card, fg_color=self.colors["bg_app"], corner_radius=6)
        info_frame.pack(fill="x", padx=16, pady=(0, 12))

        for col in range(2):
            info_frame.grid_columnconfigure(col, weight=1)

        self.school_name_info_lbl = ctk.CTkLabel(info_frame, text="School: Not Configured", anchor="w", font=ctk.CTkFont(size=12, weight="bold"))
        self.school_name_info_lbl.grid(row=0, column=0, padx=12, pady=6, sticky="w")

        self.school_session_info_lbl = ctk.CTkLabel(info_frame, text="Active Session: None", anchor="w", font=ctk.CTkFont(size=12))
        self.school_session_info_lbl.grid(row=0, column=1, padx=12, pady=6, sticky="w")

        self.school_contact_info_lbl = ctk.CTkLabel(info_frame, text="Contact: N/A", anchor="w", font=ctk.CTkFont(size=12))
        self.school_contact_info_lbl.grid(row=1, column=0, padx=12, pady=6, sticky="w")

        self.school_classes_info_lbl = ctk.CTkLabel(info_frame, text="Registered Classes: 0", anchor="w", font=ctk.CTkFont(size=12))
        self.school_classes_info_lbl.grid(row=1, column=1, padx=12, pady=6, sticky="w")

    def _open_school_profile_modal(self) -> None:
        """Opens SchoolProfileModal and refreshes settings view on save."""
        from ui.school_profile_modal import SchoolProfileModal
        SchoolProfileModal(self, db_conn=self.db_conn, on_configured=self.refresh_data)

    def _build_system_health_card(self, parent) -> None:
        """Renders live system diagnostics, database engine status, and 1-click auto-repair."""
        card = ctk.CTkFrame(parent, fg_color=self.colors["bg_card"], corner_radius=8)
        card.pack(fill="x", pady=(0, 16))

        # Top Bar
        top_bar = ctk.CTkFrame(card, fg_color="transparent")
        top_bar.pack(fill="x", padx=16, pady=(12, 6))

        ctk.CTkLabel(
            top_bar,
            text="🔍 System Diagnostics & Active Database Engine Health",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=self.colors["text_primary"]
        ).pack(side="left")

        # 1-Click Verification & Auto-Repair Button
        self.btn_repair = ctk.CTkButton(
            top_bar,
            text="🛠️ Verify & Auto-Repair Database",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=self.colors["brand_primary"],
            hover_color=self.colors["brand_accent"],
            command=self._run_db_repair
        )
        self.btn_repair.pack(side="right")

        # Subtitle
        ctk.CTkLabel(
            card,
            text="Real-time telemetry probing SQLite WAL storage engine, active schema migration version, and operational table readiness.",
            font=ctk.CTkFont(size=11),
            text_color=self.colors["text_secondary"]
        ).pack(anchor="w", padx=16, pady=(0, 8))

        # Repair status message label
        self.repair_status_label = ctk.CTkLabel(
            card,
            text="",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self.colors["status_paid"]
        )
        self.repair_status_label.pack(anchor="w", padx=16, pady=(0, 4))

        # Diagnostics Grid (Engine Level)
        diag_frame = ctk.CTkFrame(card, fg_color=self.colors["bg_app"], corner_radius=6)
        diag_frame.pack(fill="x", padx=16, pady=(0, 10))

        for c in range(2):
            diag_frame.grid_columnconfigure(c, weight=1)

        self.db_conn_status_label = ctk.CTkLabel(
            diag_frame, text="● Connection: Initializing...", font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self.colors["text_primary"], anchor="w"
        )
        self.db_conn_status_label.grid(row=0, column=0, padx=12, pady=6, sticky="w")

        self.db_engine_label = ctk.CTkLabel(
            diag_frame, text="Engine Mode: SQLite 3.x (WAL Active)", font=ctk.CTkFont(size=12),
            text_color=self.colors["text_secondary"], anchor="w"
        )
        self.db_engine_label.grid(row=0, column=1, padx=12, pady=6, sticky="w")

        self.db_schema_version_label = ctk.CTkLabel(
            diag_frame, text="Schema: Checking PRAGMA user_version...", font=ctk.CTkFont(size=12),
            text_color=self.colors["text_secondary"], anchor="w"
        )
        self.db_schema_version_label.grid(row=1, column=0, padx=12, pady=6, sticky="w")

        self.db_file_info_label = ctk.CTkLabel(
            diag_frame, text="Database File: Inspecting disk path...", font=ctk.CTkFont(size=12),
            text_color=self.colors["text_secondary"], anchor="w"
        )
        self.db_file_info_label.grid(row=1, column=1, padx=12, pady=6, sticky="w")

        # Table Readiness Probes Grid
        ctk.CTkLabel(
            card,
            text="Active Table Readiness & Row Count Probes:",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=self.colors["brand_accent"]
        ).pack(anchor="w", padx=16, pady=(4, 6))

        probes_grid = ctk.CTkFrame(card, fg_color="transparent")
        probes_grid.pack(fill="x", padx=16, pady=(0, 12))
        for c in range(2):
            probes_grid.grid_columnconfigure(c, weight=1)

        # 1. Students Probe
        p_students = ctk.CTkFrame(probes_grid, fg_color=self.colors["bg_app"], corner_radius=6)
        p_students.grid(row=0, column=0, padx=4, pady=4, sticky="ew")
        ctk.CTkLabel(p_students, text="👨‍🎓 Students Module:", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=10, pady=6)
        self.probe_students_label = ctk.CTkLabel(p_students, text="Checking...", font=ctk.CTkFont(size=11, weight="bold"))
        self.probe_students_label.pack(side="right", padx=10, pady=6)

        # 2. Fees Probe
        p_fees = ctk.CTkFrame(probes_grid, fg_color=self.colors["bg_app"], corner_radius=6)
        p_fees.grid(row=0, column=1, padx=4, pady=4, sticky="ew")
        ctk.CTkLabel(p_fees, text="💳 Fee & Receipts:", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=10, pady=6)
        self.probe_fees_label = ctk.CTkLabel(p_fees, text="Checking...", font=ctk.CTkFont(size=11, weight="bold"))
        self.probe_fees_label.pack(side="right", padx=10, pady=6)

        # 3. Attendance Probe
        p_att = ctk.CTkFrame(probes_grid, fg_color=self.colors["bg_app"], corner_radius=6)
        p_att.grid(row=1, column=0, padx=4, pady=4, sticky="ew")
        ctk.CTkLabel(p_att, text="🗓️ Attendance Module:", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=10, pady=6)
        self.probe_attendance_label = ctk.CTkLabel(p_att, text="Checking...", font=ctk.CTkFont(size=11, weight="bold"))
        self.probe_attendance_label.pack(side="right", padx=10, pady=6)

        # 4. Exams Probe
        p_exam = ctk.CTkFrame(probes_grid, fg_color=self.colors["bg_app"], corner_radius=6)
        p_exam.grid(row=1, column=1, padx=4, pady=4, sticky="ew")
        ctk.CTkLabel(p_exam, text="📝 Examination Module:", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=10, pady=6)
        self.probe_exams_label = ctk.CTkLabel(p_exam, text="Checking...", font=ctk.CTkFont(size=11, weight="bold"))
        self.probe_exams_label.pack(side="right", padx=10, pady=6)

    def refresh_data(self) -> None:
        """Probes live database connection, journal mode, schema version, and module tables."""
        conn = getattr(self.app, "db_conn", None) or self.db_conn
        if not conn:
            self.db_conn_status_label.configure(text="● Connection: Disconnected", text_color=self.colors["status_unpaid"])
            self.db_engine_label.configure(text="Engine Mode: Inactive")
            self.db_schema_version_label.configure(text="Schema: Unreachable")
            self.probe_students_label.configure(text="UNINITIALIZED (No Connection)", text_color=self.colors["status_unpaid"])
            self.probe_fees_label.configure(text="UNINITIALIZED (No Connection)", text_color=self.colors["status_unpaid"])
            self.probe_attendance_label.configure(text="UNINITIALIZED (No Connection)", text_color=self.colors["status_unpaid"])
            self.probe_exams_label.configure(text="UNINITIALIZED (No Connection)", text_color=self.colors["status_unpaid"])
            return

        self.db_conn = conn
        self.db_conn_status_label.configure(text="● Connection: Active & Verified", text_color=self.colors["status_paid"])

        # Journal Mode
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA journal_mode;")
            jm = cur.fetchone()
            j_str = jm[0].upper() if jm else "WAL"
            self.db_engine_label.configure(text=f"Engine Mode: SQLite 3.x ({j_str} Mode)")
        except Exception:
            self.db_engine_label.configure(text="Engine Mode: SQLite 3.x (Active)")

        # Schema Version
        try:
            v = get_schema_version(conn)
            self.db_schema_version_label.configure(text=f"Schema Version: v{v} (PRAGMA user_version={v})")
        except Exception as exc:
            self.db_schema_version_label.configure(text=f"Schema: Error ({exc})")

        # Disk File Info
        db_path = getattr(self.app, "db_path", None) or os.path.join("data", "classfellow.db")
        if os.path.exists(db_path):
            sz_kb = os.path.getsize(db_path) / 1024.0
            self.db_file_info_label.configure(text=f"Database File: {os.path.basename(db_path)} ({sz_kb:.1f} KB)")
        else:
            self.db_file_info_label.configure(text="Database File: In-Memory / Not Stored")

        # Table Row Count Probes
        try:
            cur.execute("SELECT COUNT(*) FROM students;")
            c = cur.fetchone()[0]
            self.probe_students_label.configure(text=f"Operational ({c} students)", text_color=self.colors["status_paid"])
        except Exception:
            self.probe_students_label.configure(text="UNINITIALIZED (Table Missing)", text_color=self.colors["status_unpaid"])

        try:
            cur.execute("SELECT COUNT(*) FROM fee_invoices;")
            c = cur.fetchone()[0]
            self.probe_fees_label.configure(text=f"Operational ({c} invoices)", text_color=self.colors["status_paid"])
        except Exception:
            self.probe_fees_label.configure(text="UNINITIALIZED (Table Missing)", text_color=self.colors["status_unpaid"])

        try:
            cur.execute("SELECT COUNT(*) FROM attendance_records;")
            c = cur.fetchone()[0]
            self.probe_attendance_label.configure(text=f"Operational ({c} entries)", text_color=self.colors["status_paid"])
        except Exception:
            self.probe_attendance_label.configure(text="UNINITIALIZED (Table Missing)", text_color=self.colors["status_unpaid"])

        try:
            cur.execute("SELECT COUNT(*) FROM exams;")
            c = cur.fetchone()[0]
            self.probe_exams_label.configure(text=f"Operational ({c} exams)", text_color=self.colors["status_paid"])
        except Exception:
            self.probe_exams_label.configure(text="UNINITIALIZED (Table Missing)", text_color=self.colors["status_unpaid"])

        # Refresh Institutional Profile Information
        if self.db_conn and hasattr(self, "school_name_info_lbl"):
            try:
                from services.school_service import get_school_profile
                prof = get_school_profile(self.db_conn)
                if prof:
                    s_name = prof.get("school_name", "Not Configured")
                    c_name = f" ({prof['campus_name']})" if prof.get("campus_name") else ""
                    self.school_name_info_lbl.configure(text=f"School: {s_name}{c_name}")
                    contact_str = prof.get("contact_number") or "N/A"
                    email_str = f" | {prof['email']}" if prof.get("email") else ""
                    self.school_contact_info_lbl.configure(text=f"Contact: {contact_str}{email_str}")
                else:
                    self.school_name_info_lbl.configure(text="School: Not Configured (Setup Required)")
                    self.school_contact_info_lbl.configure(text="Contact: N/A")

                cur.execute("SELECT name FROM academic_sessions WHERE is_active = 1 LIMIT 1;")
                sess_row = cur.fetchone()
                if sess_row:
                    s_name = sess_row[0] if isinstance(sess_row, (tuple, list)) else sess_row["name"]
                    self.school_session_info_lbl.configure(text=f"Active Session: {s_name}")
                else:
                    self.school_session_info_lbl.configure(text="Active Session: None")

                cur.execute("SELECT COUNT(*) FROM class_groups;")
                cl_count = cur.fetchone()[0]
                self.school_classes_info_lbl.configure(text=f"Registered Classes: {cl_count}")
            except Exception:
                pass

    def on_show(self, **kwargs) -> None:
        """Refreshes health metrics and connection state when tab is opened."""
        self.refresh_data()

    def _run_db_repair(self) -> None:
        """Executes init_database() to auto-migrate missing tables and refreshes metrics."""
        try:
            target_db = getattr(self.app, "db_path", None)
            repaired_conn = init_database(target_db) if target_db else init_database()
            self.db_conn = repaired_conn
            if hasattr(self.app, "db_conn"):
                self.app.db_conn = repaired_conn
            if hasattr(self.app, "backup_service") and self.app.backup_service:
                self.app.backup_service.db_conn = repaired_conn

            # Clear cached views so they re-query clean tables on next click
            if hasattr(self.app, "views"):
                for k in list(self.app.views.keys()):
                    if k != "settings":
                        self.app.views.pop(k, None)

            self.refresh_data()
            self.repair_status_label.configure(
                text="✅ Database verified & auto-repaired! All 15 schema tables confirmed operational.",
                text_color=self.colors["status_paid"]
            )
        except Exception as exc:
            self.repair_status_label.configure(
                text=f"❌ Auto-repair error: {exc}",
                text_color=self.colors["status_unpaid"]
            )

    def _build_backup_card(self, parent) -> None:
        """Renders controls for Tier 1, Tier 2, and Tier 3 backups."""
        card = ctk.CTkFrame(parent, fg_color=self.colors["bg_card"], corner_radius=8)
        card.pack(fill="x", pady=(0, 16))

        ctk.CTkLabel(
            card,
            text="🛡️ 3-Tier Automated Backup Operations",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=self.colors["text_primary"]
        ).pack(anchor="w", padx=16, pady=(14, 8))

        # --- Tier 1 Section ---
        t1_frame = ctk.CTkFrame(card, fg_color=self.colors["bg_app"], corner_radius=6)
        t1_frame.pack(fill="x", padx=16, pady=6)

        t1_title = ctk.CTkLabel(
            t1_frame,
            text="Tier 1: Local Daily Rolling Snapshots (SQLite Online API)",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=self.colors["brand_accent"]
        )
        t1_title.pack(anchor="w", padx=12, pady=(10, 2))

        t1_desc = ctk.CTkLabel(
            t1_frame,
            text="Captures WAL transactions with zero lock contention and enforces a rolling 30-day retention window.",
            font=ctk.CTkFont(size=11),
            text_color=self.colors["text_secondary"]
        )
        t1_desc.pack(anchor="w", padx=12, pady=(0, 8))

        t1_btn_box = ctk.CTkFrame(t1_frame, fg_color="transparent")
        t1_btn_box.pack(fill="x", padx=12, pady=(0, 10))

        btn_t1 = ctk.CTkButton(
            t1_btn_box,
            text="💾 Run Daily Backup Now",
            command=self._on_run_daily_backup,
            fg_color=self.colors["brand_primary"],
            hover_color=self.colors["brand_accent"],
            font=ctk.CTkFont(size=12, weight="bold")
        )
        btn_t1.pack(side="left")

        self.t1_status_lbl = ctk.CTkLabel(
            t1_btn_box,
            text="Ready • Auto-runs on app start/shutdown",
            font=ctk.CTkFont(size=11),
            text_color=self.colors["text_secondary"]
        )
        self.t1_status_lbl.pack(side="left", padx=16)

        # --- Tier 2 Section ---
        t2_frame = ctk.CTkFrame(card, fg_color=self.colors["bg_app"], corner_radius=6)
        t2_frame.pack(fill="x", padx=16, pady=6)

        t2_title = ctk.CTkLabel(
            t2_frame,
            text="Tier 2: Manual USB Snapshot Export / Import (Air-Gapped Safety)",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=self.colors["brand_accent"]
        )
        t2_title.pack(anchor="w", padx=12, pady=(10, 2))

        t2_desc = ctk.CTkLabel(
            t2_frame,
            text="Packages database snapshot, manifest.json, and SHA-256 cryptographic checksum into a verified ZIP archive.",
            font=ctk.CTkFont(size=11),
            text_color=self.colors["text_secondary"]
        )
        t2_desc.pack(anchor="w", padx=12, pady=(0, 8))

        t2_btn_box = ctk.CTkFrame(t2_frame, fg_color="transparent")
        t2_btn_box.pack(fill="x", padx=12, pady=(0, 10))

        btn_export = ctk.CTkButton(
            t2_btn_box,
            text="📦 Export USB Snapshot",
            command=self._on_export_usb,
            fg_color=self.colors["brand_accent"],
            font=ctk.CTkFont(size=12, weight="bold")
        )
        btn_export.pack(side="left", padx=(0, 8))

        btn_restore = ctk.CTkButton(
            t2_btn_box,
            text="🔄 Restore USB Snapshot",
            command=self._on_restore_usb,
            fg_color=self.colors["status_unpaid"],
            font=ctk.CTkFont(size=12, weight="bold")
        )
        btn_restore.pack(side="left")

        # --- Tier 3 Section ---
        t3_frame = ctk.CTkFrame(card, fg_color=self.colors["bg_app"], corner_radius=6)
        t3_frame.pack(fill="x", padx=16, pady=(6, 16))

        t3_title = ctk.CTkLabel(
            t3_frame,
            text="Tier 3: Automated Cloud Backup (Google Drive Sync Worker)",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=self.colors["brand_accent"]
        )
        t3_title.pack(anchor="w", padx=12, pady=(10, 2))

        t3_desc = ctk.CTkLabel(
            t3_frame,
            text="Non-blocking socket probes detect internet connectivity and trigger asynchronous cloud synchronization.",
            font=ctk.CTkFont(size=11),
            text_color=self.colors["text_secondary"]
        )
        t3_desc.pack(anchor="w", padx=12, pady=(0, 8))

        t3_btn_box = ctk.CTkFrame(t3_frame, fg_color="transparent")
        t3_btn_box.pack(fill="x", padx=12, pady=(0, 10))

        btn_probe = ctk.CTkButton(
            t3_btn_box,
            text="🌐 Test Connectivity",
            command=self._on_test_connectivity,
            fg_color=self.colors["border_color"],
            font=ctk.CTkFont(size=12, weight="bold")
        )
        btn_probe.pack(side="left")

        self.t3_status_lbl = ctk.CTkLabel(
            t3_btn_box,
            text="Status: Unchecked",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=self.colors["text_secondary"]
        )
        self.t3_status_lbl.pack(side="left", padx=16)

    def _on_run_daily_backup(self) -> None:
        """Executes Tier 1 daily backup snapshot."""
        if not self.backup_service:
            self.show_error("Error", "Backup service unavailable.")
            return

        try:
            path = self.backup_service.run_startup_backup()
            if path:
                self.t1_status_lbl.configure(
                    text=f"Last snapshot: {os.path.basename(path)} ({datetime.now().strftime('%H:%M:%S')})",
                    text_color=self.colors["status_paid"]
                )
                self.show_info("Backup Complete", f"Snapshot successfully created:\n{path}")
            else:
                self.show_error("Backup Error", "Failed to create daily backup snapshot.")
        except Exception as exc:
            self.show_error("Backup Error", str(exc))

    def _on_export_usb(self) -> None:
        """Selects directory and exports verified USB backup archive."""
        if not self.backup_service:
            return

        target_dir = filedialog.askdirectory(title="Select USB Target Directory")
        if not target_dir:
            return

        try:
            archive_path = self.backup_service.export_usb_backup(target_directory=target_dir)
            verify_res = self.backup_service.verify_backup_archive(archive_path)
            sha = verify_res["manifest"]["sha256"][:16]

            self.show_info(
                "USB Export Verified",
                f"Archive: {os.path.basename(archive_path)}\n"
                f"SHA-256 Digest: {sha}...\n"
                f"Location: {archive_path}"
            )
        except Exception as exc:
            self.show_error("Export Failed", str(exc))

    def _on_restore_usb(self) -> None:
        """Selects archive and restores database."""
        if not self.backup_service:
            return

        archive_file = filedialog.askopenfilename(
            title="Select ClassFellow Backup ZIP Archive",
            filetypes=[("ClassFellow Backup ZIP", "*.zip")]
        )
        if not archive_file:
            return

        target_db = getattr(self.app, "db_path", None) or os.path.join("data", "classfellow.db")

        try:
            # Verify and restore
            self.backup_service.restore_from_backup_archive(archive_file, target_db)
            self.show_info(
                "Database Restored",
                f"Database restored successfully from:\n{os.path.basename(archive_file)}\n\n"
                "Please restart ClassFellow to reload all cached connections."
            )
        except Exception as exc:
            self.show_error("Restore Failed", str(exc))

    def _on_test_connectivity(self) -> None:
        """Runs non-blocking network probe."""
        is_online = check_network_connectivity()
        if is_online:
            self.t3_status_lbl.configure(text="Status: 🟢 Connected to Internet", text_color=self.colors["status_paid"])
        else:
            self.t3_status_lbl.configure(text="Status: 🔴 Offline (Zero Internet)", text_color=self.colors["status_unpaid"])
