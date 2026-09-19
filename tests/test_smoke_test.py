"""
Unit and Integration Tests for Standalone Executable Smoke Test Flag
"""

import sys
import subprocess
from app.app import handle_smoke_test


def test_handle_smoke_test_function():
    """Verifies that handle_smoke_test executes all engine checks and returns 0."""
    result = handle_smoke_test()
    assert result == 0


def test_smoke_test_cli_flag():
    """Verifies that invoking python app/app.py --smoke-test exits cleanly with code 0."""
    proc = subprocess.run(
        [sys.executable, "app/app.py", "--smoke-test"],
        capture_output=True,
        text=True,
        timeout=15
    )
    assert proc.returncode == 0
    assert "SUCCESS: Standalone executable components verified. Exit 0." in proc.stdout
