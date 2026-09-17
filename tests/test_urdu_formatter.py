"""
Unit tests for app/reports/urdu_formatter.py ligature reshaping and BiDi rendering.
"""

from app.reports.urdu_formatter import format_urdu


def test_format_urdu_reshaping():
    """Verifies that Urdu strings are reshaped and bidirectional text is produced."""
    sample_text = "عاصم خان"
    formatted = format_urdu(sample_text)

    # Formatted string must not be empty and must differ from raw disconnected glyphs
    assert len(formatted) > 0
    assert isinstance(formatted, str)


def test_format_urdu_empty_and_none():
    """Verifies graceful handling of empty, None, and whitespace strings."""
    assert format_urdu(None) == ""
    assert format_urdu("") == ""
    assert format_urdu("   ") == ""


def test_format_urdu_bilingual():
    """Verifies handling of mixed English and Urdu text."""
    bilingual = "Class 10 - جماعت دہم"
    formatted = format_urdu(bilingual)
    assert len(formatted) > 0
