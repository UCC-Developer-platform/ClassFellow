# -*- mode: python ; coding: utf-8 -*-
"""
ClassFellow - PyInstaller Build Specification (classfellow.spec)
===============================================================
Configures standalone executable release packaging for Windows 64-bit (.exe).
Bundles:
  - assets/fonts/ (Urdu ligature & Unicode TrueType fonts)
  - config/ (theme.json and commercial modules.json)
  - CustomTkinter themes and assets
Includes hidden imports for all dynamic dependencies:
  - customtkinter, reportlab, arabic_reshaper, bidi, num2words, sqlite3
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect CustomTkinter package assets (theme json definitions, icons, fonts)
ctk_datas = collect_data_files("customtkinter")

datas = [
    ("assets", "assets"),
    ("config", "config"),
] + ctk_datas

hiddenimports = [
    "customtkinter",
    "reportlab",
    "arabic_reshaper",
    "bidi",
    "bidi.algorithm",
    "num2words",
    "sqlite3",
    "openpyxl",
    "database",
    "models",
    "services",
    "services.student_service",
    "services.fee_service",
    "services.attendance_service",
    "services.exam_service",
    "services.backup_service",
    "services.schema_service",
    "services.importer_service",
    "ui",
    "ui.base_view",
    "ui.dashboard_view",
    "ui.student_view",
    "ui.fee_view",
    "ui.attendance_view",
    "ui.exam_view",
    "ui.settings_view",
    "app.reports.fee_voucher_generator",
    "app.reports.report_card_generator",
    "app.reports.urdu_formatter",
    "app.reports.currency_words",
]

a = Analysis(
    ["app/app.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter.test",
        "unittest",
        "pytest",
        "pytest_cov",
        "_pytest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ClassFellow",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Windowed GUI application (no trailing console pop-up)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="ClassFellow",
)
