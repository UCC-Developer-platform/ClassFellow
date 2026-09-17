"""
ClassFellow - Urdu & Arabic Ligature Reshaping Pipeline
========================================================
ReportLab lacks native OpenType glyph substitution and bidirectional script
reordering. Passing raw Urdu strings creates disconnected and reversed letters.

This module provides `format_urdu()` to prepare text for ReportLab PDF canvases
and paragraph flows using arabic-reshaper and python-bidi.
"""

from typing import Optional
import arabic_reshaper
from bidi.algorithm import get_display


def format_urdu(text: Optional[str]) -> str:
    """
    Reshapes cursive ligatures and applies bidirectional reordering for Urdu text.

    Args:
        text: Raw UTF-8 Urdu or bilingual string.

    Returns:
        Properly shaped, RTL-reordered string ready for ReportLab rendering.
    """
    if not text or not str(text).strip():
        return ""

    # Step 1: Reshape disconnected characters into contextual cursive forms
    reshaped_text = arabic_reshaper.reshape(str(text))

    # Step 2: Apply Unicode bidirectional algorithm for visual RTL presentation
    visual_bidi_text = get_display(reshaped_text)

    return visual_bidi_text
