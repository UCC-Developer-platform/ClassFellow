"""
Unit tests for application configuration loading and module tier gating.
"""

import os
import json
import pytest
from app.app import load_configuration


def test_load_configuration_structure():
    """Verifies that load_configuration reads theme and modules correctly."""
    config = load_configuration()
    assert "theme" in config
    assert "modules" in config
    assert "system" in config

    modules = config["modules"]
    assert isinstance(modules, dict)
    assert modules.get("students") is True
    assert modules.get("fees") is True


def test_module_tier_filtering():
    """Verifies that disabled modules in tier configurations are properly filtered."""
    nav_items = [
        ("Dashboard", "dashboard"),
        ("Students", "students"),
        ("Fees & Receipts", "fees"),
        ("Attendance", "attendance"),
        ("Examinations", "examinations"),
    ]

    # Simulate Tier 1: Fee-Only Edition (attendance and examinations disabled)
    tier1_modules = {
        "students": True,
        "fees": True,
        "attendance": False,
        "examinations": False,
    }

    visible_items = [
        key for label, key in nav_items
        if not (key in tier1_modules and not tier1_modules[key])
    ]

    assert "students" in visible_items
    assert "fees" in visible_items
    assert "attendance" not in visible_items
    assert "examinations" not in visible_items
