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

        # 3. Commercial Licensing & Feature Flags Card
        self._build_license_card(self.content_scroll)

        # 4. 3-Tier Automated Backup Management Card
        self._build_backup_card(self.content_scroll)

    def _build_license_card(self, parent) -> None:
        """Renders license package tier and module feature flags."""
        card = ctk.CTkFrame(parent, fg_color=self.colors["bg_card"], corner_radius=8)
        card.pack(fill="x", pady=(0, 16))

        # Card Title
        top_bar = ctk.CTkFrame(card, fg_color="transparent")
        top_bar.pack(fill="x", padx=16, pady=(12, 6))

        ctk.CTkLabel(
            top_bar,
            text="🏷️ Commercial License & Feature Flags",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=self.colors["text_primary"]
        ).pack(side="left")

        tier_name = self.app.config.get("system", {}).get(
            "licensed_tier", "Tier 3: Professional Suite"
        )
        self.tier_badge = ctk.CTkLabel(
            top_bar,
            text=f"Active: {tier_name}",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self.colors["brand_primary"],
            fg_color=self.colors["bg_app"],
            corner_radius=4,
            padx=10,
            pady=4
        )
        self.tier_badge.pack(side="right")

        # Module Flags Grid
        modules = self.app.config.get("modules", {})
        self.flags_frame = ctk.CTkFrame(card, fg_color="transparent")
        self.flags_frame.pack(fill="x", padx=16, pady=(0, 12))

        for idx, (mod_key, is_enabled) in enumerate(modules.items()):
            col = idx % 3
            row = idx // 3
            pill_color = self.colors["status_paid"] if is_enabled else self.colors["status_unpaid"]
            status_text = "ENABLED" if is_enabled else "DISABLED"

            pill = ctk.CTkFrame(self.flags_frame, fg_color=self.colors["bg_app"], corner_radius=6)
            pill.grid(row=row, column=col, padx=6, pady=4, sticky="ew")
            self.flags_frame.grid_columnconfigure(col, weight=1)

            ctk.CTkLabel(
                pill,
                text=f"{mod_key.capitalize()}:",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=self.colors["text_primary"]
            ).pack(side="left", padx=10, pady=8)

            ctk.CTkLabel(
                pill,
                text=status_text,
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color=pill_color
            ).pack(side="right", padx=10, pady=8)

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

    def refresh_data(self) -> None:
        """Refreshes status labels."""
        pass

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
