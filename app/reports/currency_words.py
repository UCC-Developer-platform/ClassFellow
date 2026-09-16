"""
ClassFellow - Currency in Words Utility
=======================================
Generates human-readable English text for financial voucher totals using num2words.
"""

from decimal import Decimal
from typing import Union
from num2words import num2words


def amount_in_words_en(amount: Union[Decimal, int, float, str]) -> str:
    """
    Converts a Decimal or numeric amount into standard English currency representation.
    E.g., Decimal("4500.00") -> "In Words: Four Thousand Five Hundred Rupees Only"
    """
    if amount is None:
        return "In Words: Zero Rupees Only"

    d = Decimal(str(amount))
    rupees = int(d)
    paisa = int(round((d - Decimal(rupees)) * 100))

    if rupees == 0 and paisa == 0:
        return "In Words: Zero Rupees Only"

    words = num2words(rupees, lang="en").replace("-", " ").replace(",", "").title()

    if paisa > 0:
        paisa_words = num2words(paisa, lang="en").replace("-", " ").title()
        return f"In Words: {words} Rupees and {paisa_words} Paisas Only"

    return f"In Words: {words} Rupees Only"
