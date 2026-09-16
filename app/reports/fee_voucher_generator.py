"""
ClassFellow - ReportLab 3-Panel A4 Fee Voucher Generator
=========================================================
Renders a standard portrait A4 page (595.28 x 841.89 pt) divided into three
horizontal voucher panels:
  1. School Copy    (Office record archived in accounts register)
  2. Accounts / Bank Copy (Surrendered to bank cashier upon deposit)
  3. Student Copy   (Retained by student / parent)

Panels are demarcated with dashed cut lines and scissors indicators.
All Urdu strings (student names, guardian names, fee titles) are shaped
and reordered via `format_urdu()` before canvas drawing.
"""

import os
import sys
from decimal import Decimal
from typing import Union, Optional, Any
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from app.reports.urdu_formatter import format_urdu
from app.reports.currency_words import amount_in_words_en

PAGE_WIDTH, PAGE_HEIGHT = A4  # 595.275 x 841.889 pt

# Resolve Font Name
_FONT_NORMAL = "Helvetica"
_FONT_BOLD = "Helvetica-Bold"

def _init_pdf_fonts() -> tuple[str, str]:
    """
    Attempts to register a TrueType font capable of Urdu/Unicode glyph rendering.
    Falls back cleanly to standard Helvetica across Windows and Ubuntu CI environments.
    """
    global _FONT_NORMAL, _FONT_BOLD

    # Candidates in order of preference
    search_paths = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "fonts", "urdu.ttf"),
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]

    for path in search_paths:
        if os.path.exists(path):
            try:
                font_name = "CF_UnicodeFont"
                pdfmetrics.registerFont(TTFont(font_name, path))
                _FONT_NORMAL = font_name
                _FONT_BOLD = font_name
                return _FONT_NORMAL, _FONT_BOLD
            except Exception:
                continue

    return _FONT_NORMAL, _FONT_BOLD

_init_pdf_fonts()


class FeeVoucherGenerator:
    """Generates print-ready 3-panel A4 fee vouchers."""

    def __init__(self, institution_name: str = "CLASSFELLOW HIGH SCHOOL & ACADEMY"):
        self.institution_name = institution_name

    def render_voucher(
        self,
        invoice_data: dict[str, Any],
        output: Union[str, BytesIO]
    ) -> Union[str, BytesIO]:
        """
        Renders the complete 3-panel A4 voucher PDF document.

        Args:
            invoice_data: Dictionary containing invoice details, student profile,
                          items list, and balance information.
            output: Destination file path or BytesIO buffer.

        Returns:
            The output destination.
        """
        c = canvas.Canvas(output, pagesize=A4)

        # Panel geometry:
        # Usable Height: 842 pt
        # Panel Height: ~260 pt each
        # Margins: Left=24, Right=24 (Width = 547 pt)
        margin_x = 24.0
        width = PAGE_WIDTH - (2 * margin_x)
        panel_height = 260.0

        # Panel 1: Top (School Copy) -> y = 565
        # Panel 2: Middle (Bank / Accounts Copy) -> y = 295
        # Panel 3: Bottom (Student Copy) -> y = 25
        panels = [
            ("SCHOOL COPY (دفتر ریکارڈ)", 565.0),
            ("ACCOUNTS / BANK COPY (بینک / کیش کاپی)", 295.0),
            ("STUDENT / PARENT COPY (طالب علم کاپی)", 25.0),
        ]

        for i, (copy_label, origin_y) in enumerate(panels):
            self._draw_panel(c, invoice_data, margin_x, origin_y, width, panel_height, copy_label)

            # Draw dashed separator cut line between panels
            if i < len(panels) - 1:
                cut_y = origin_y - 12.0
                self._draw_cut_line(c, margin_x, cut_y, width)

        c.showPage()
        c.save()
        return output

    def _draw_panel(
        self,
        c: canvas.Canvas,
        data: dict[str, Any],
        x: float,
        y: float,
        w: float,
        h: float,
        copy_label: str
    ) -> None:
        """Draws a single self-contained voucher panel."""
        # 1. Outer Panel Border
        c.setStrokeColorRGB(0.2, 0.25, 0.35)
        c.setLineWidth(0.8)
        c.rect(x, y, w, h, stroke=1, fill=0)

        # 2. Header Banner
        c.setFillColorRGB(0.08, 0.15, 0.28)  # Deep Navy / Slate
        c.rect(x, y + h - 28, w, 28, stroke=0, fill=1)

        c.setFillColorRGB(1.0, 1.0, 1.0)
        c.setFont(_FONT_BOLD, 10)
        c.drawString(x + 10, y + h - 18, self.institution_name.upper())

        # Copy Label Badge (Right Aligned in Banner)
        c.setFont(_FONT_BOLD, 9)
        c.drawRightString(x + w - 10, y + h - 18, copy_label)

        # Subheader info row
        c.setFillColorRGB(0.95, 0.96, 0.98)
        c.rect(x, y + h - 46, w, 18, stroke=0, fill=1)
        c.setFillColorRGB(0.1, 0.15, 0.25)
        c.setFont(_FONT_BOLD, 8)

        inv_num = f"VCH-{data.get('month_year', '2025-00')}-{data.get('id', 0):05d}"
        c.drawString(x + 10, y + h - 39, f"Voucher No: {inv_num}")
        c.drawString(x + 160, y + h - 39, f"Billing Cycle: {data.get('month_year', 'N/A')}")
        c.drawString(x + 300, y + h - 39, f"Issue Date: {data.get('issue_date', 'N/A')}")
        c.drawRightString(x + w - 10, y + h - 39, f"Due Date: {data.get('due_date', 'N/A')}")

        # 3. Student Identity Grid (2 Columns)
        c.setFont(_FONT_NORMAL, 8)
        c.setFillColorRGB(0.1, 0.1, 0.1)

        col1_x = x + 10
        col2_x = x + 280
        info_y = y + h - 58

        # Student Name (Bilingual)
        eng_name = data.get("full_name") or data.get("first_name", "Student")
        urdu_name = data.get("student_urdu_name")
        shaped_urdu = f"({format_urdu(urdu_name)})" if urdu_name else ""
        student_display = f"{eng_name} {shaped_urdu}".strip()

        c.drawString(col1_x, info_y, f"Student Name: {student_display}")
        c.drawString(col2_x, info_y, f"Admission No: {data.get('admission_number', 'N/A')}")

        info_y -= 12
        guardian_name = data.get("guardian_name", "N/A")
        c.drawString(col1_x, info_y, f"Father / Guardian: {guardian_name}")
        c.drawString(col2_x, info_y, f"Class / Section: {data.get('class_name', 'N/A')} - {data.get('section_or_batch', '')}")

        info_y -= 12
        c.drawString(col1_x, info_y, f"Contact: {data.get('guardian_phone', 'N/A')}")
        c.drawString(col2_x, info_y, f"Roll Number: {data.get('roll_number') or 'N/A'}")

        # 4. Itemized Fee Breakdown Table
        tbl_y = y + h - 94
        tbl_h = 75.0
        c.setStrokeColorRGB(0.7, 0.75, 0.8)
        c.setLineWidth(0.5)
        c.rect(x + 10, tbl_y - tbl_h, w - 20, tbl_h, stroke=1, fill=0)

        # Table Header
        c.setFillColorRGB(0.9, 0.93, 0.96)
        c.rect(x + 10, tbl_y - 15, w - 20, 15, stroke=1, fill=1)
        c.setFillColorRGB(0.1, 0.15, 0.25)
        c.setFont(_FONT_BOLD, 7.5)
        c.drawString(x + 16, tbl_y - 11, "Sr #")
        c.drawString(x + 40, tbl_y - 11, "Fee Head / Description (تفصیل فیس)")
        c.drawRightString(x + w - 20, tbl_y - 11, "Amount (PKR)")

        # Table Items
        items = data.get("items", [])
        item_cursor_y = tbl_y - 25
        c.setFont(_FONT_NORMAL, 7.5)
        c.setFillColorRGB(0.1, 0.1, 0.1)

        total_heads_amount = Decimal("0.00")
        for idx, item in enumerate(items[:4], start=1):  # Display up to 4 line items
            h_name = item.get("fee_head_name", "Fee")
            h_urdu = item.get("urdu_name")
            h_display = f"{h_name} ({format_urdu(h_urdu)})" if h_urdu else h_name
            amt = Decimal(str(item.get("amount", "0.00")))
            total_heads_amount += amt

            c.drawString(x + 16, item_cursor_y, str(idx))
            c.drawString(x + 40, item_cursor_y, h_display)
            c.drawRightString(x + w - 20, item_cursor_y, f"{amt:,.2f}")
            item_cursor_y -= 11

        # Summary Sub-Block
        sum_box_y = tbl_y - tbl_h - 26
        c.setFillColorRGB(0.97, 0.98, 0.99)
        c.rect(x + 10, sum_box_y, w - 20, 24, stroke=1, fill=1)

        net_due = Decimal(str(data.get("net_due", "0.00")))
        discount = Decimal(str(data.get("discount_amount", "0.00")))
        late_fee = Decimal(str(data.get("late_fee_surcharge", "200.00")))
        net_after_due = net_due + late_fee

        c.setFont(_FONT_BOLD, 8)
        c.setFillColorRGB(0.1, 0.15, 0.25)
        c.drawString(x + 16, sum_box_y + 14, f"Total: Rs. {total_heads_amount:,.2f}")
        c.drawString(x + 130, sum_box_y + 14, f"Discount: -Rs. {discount:,.2f}")
        c.drawString(x + 250, sum_box_y + 14, f"NET DUE (By Due Date): Rs. {net_due:,.2f}")
        c.drawRightString(x + w - 16, sum_box_y + 14, f"AFTER DUE DATE: Rs. {net_after_due:,.2f}")

        # Amount in words
        words_str = amount_in_words_en(net_due)
        c.setFont(_FONT_NORMAL, 7)
        c.setFillColorRGB(0.25, 0.3, 0.4)
        c.drawString(x + 16, sum_box_y + 4, words_str)
        c.drawRightString(x + w - 16, sum_box_y + 4, f"Late Surcharge: +Rs. {late_fee:,.2f}")

        # 5. Bank / Cashier Notes & Signatures
        note_y = sum_box_y - 12
        c.setFont(_FONT_NORMAL, 6.5)
        c.setFillColorRGB(0.4, 0.45, 0.5)
        c.drawString(x + 10, note_y, "Notice: Bank validity ends on cutoff date. Fee is non-refundable. Paid status is validated by official stamp.")

        sig_y = y + 14
        c.setStrokeColorRGB(0.6, 0.65, 0.7)
        c.setLineWidth(0.5)
        # Cashier Signature Line
        c.line(x + 30, sig_y + 14, x + 160, sig_y + 14)
        c.drawString(x + 40, sig_y + 4, "Cashier / Authorized Signature")

        # Bank Stamp Line
        c.line(x + w - 160, sig_y + 14, x + w - 30, sig_y + 14)
        c.drawString(x + w - 150, sig_y + 4, "Bank Officer / Depositor Stamp")

    def _draw_cut_line(self, c: canvas.Canvas, x: float, y: float, w: float) -> None:
        """Draws a dashed horizontal cut line with scissors indicator."""
        c.setStrokeColorRGB(0.5, 0.55, 0.6)
        c.setLineWidth(0.6)
        c.setDash(4, 3)
        c.line(x, y, x + w, y)
        c.setDash()  # Reset dash

        # Cut text badge in middle
        badge_text = "- - - ✂ Cut Here (یہاں سے کاٹیں) - - -"
        c.setFont(_FONT_NORMAL, 6.5)
        c.setFillColorRGB(0.45, 0.5, 0.55)
        c.drawCentredString(x + (w / 2.0), y - 2.5, badge_text)


def generate_fee_voucher_pdf(
    invoice_data: dict[str, Any],
    output: Union[str, BytesIO],
    institution_name: str = "CLASSFELLOW HIGH SCHOOL & ACADEMY"
) -> Union[str, BytesIO]:
    """
    Convenience function to generate a 3-panel A4 fee voucher PDF.
    """
    generator = FeeVoucherGenerator(institution_name=institution_name)
    return generator.render_voucher(invoice_data, output)
