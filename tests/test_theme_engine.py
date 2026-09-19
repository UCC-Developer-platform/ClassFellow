"""
Automated Test Suite for Institutional UI/UX Theme Engine & 4 Palettes
"""

import json
import os
from ui.base_view import (
    THEME_COLORS,
    get_available_theme_palettes,
    apply_theme_palette,
)


def test_theme_palettes_completeness():
    """Verifies all 4 official institutional palettes exist with complete color tokens."""
    expected_palettes = [
        "Emerald Classic",
        "Royal Navy",
        "Executive Burgundy",
        "Charcoal Modern",
    ]
    palettes = get_available_theme_palettes()
    for p in expected_palettes:
        assert p in palettes, f"Palette '{p}' missing from THEME_PALETTES!"
        pal = palettes[p]
        required_tokens = [
            "bg_app", "bg_card", "bg_row_alt", "bg_sidebar",
            "brand_primary", "brand_accent", "text_primary", "text_secondary",
            "status_paid", "status_partial", "status_unpaid", "border_color"
        ]
        for token in required_tokens:
            assert token in pal, f"Token '{token}' missing from palette '{p}'!"
            assert pal[token].startswith("#"), f"Token '{token}' in '{p}' must be a hex color!"


def test_apply_theme_palette_switching(tmp_path):
    """Verifies switching palettes updates THEME_COLORS in-place and persists to theme.json."""
    config_dir = str(tmp_path / "config")
    os.makedirs(config_dir, exist_ok=True)
    theme_json = os.path.join(config_dir, "theme.json")

    # Initial dummy theme.json
    with open(theme_json, "w", encoding="utf-8") as f:
        json.dump({"theme": "Dark", "active_palette": "Emerald Classic"}, f)

    # 1. Switch to Royal Navy
    updated = apply_theme_palette("Royal Navy", config_dir=config_dir)
    assert updated["brand_primary"] == "#2563EB"
    assert THEME_COLORS["brand_primary"] == "#2563EB"

    with open(theme_json, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["active_palette"] == "Royal Navy"

    # 2. Switch to Executive Burgundy
    updated = apply_theme_palette("Executive Burgundy", config_dir=config_dir)
    assert updated["brand_primary"] == "#991B1B"
    assert THEME_COLORS["brand_primary"] == "#991B1B"

    # 3. Switch to Charcoal Modern
    updated = apply_theme_palette("Charcoal Modern", config_dir=config_dir)
    assert updated["brand_primary"] == "#0284C7"
    assert THEME_COLORS["brand_primary"] == "#0284C7"

    # 4. Switch back to Emerald Classic
    updated = apply_theme_palette("Emerald Classic", config_dir=config_dir)
    assert updated["brand_primary"] == "#10B981"
    assert THEME_COLORS["brand_primary"] == "#10B981"
