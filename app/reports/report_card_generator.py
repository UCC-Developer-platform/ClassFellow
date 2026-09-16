"""
ClassFellow - ReportLab Bilingual A4 Terminal Report Card Generator
====================================================================
Renders a single-sheet A4 portrait (595.28 x 841.89 pt) terminal report card
with 36pt margins, institutional branding/header, student profile details,
subject-wise performance breakdown, scorecard summary metric blocks,
attendance statistics, teacher remarks with bidirectional Urdu ligature shaping,
and institutional sign-off footers as specified in CF-SRS-05.
"""

import os
from io import BytesIO
from decimal import Decimal
from typing import Union, Optional

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors

from app.reports.urdu_formatter import format_urdu
from models import StudentReportCardDTO

PAGE_WIDTH, PAGE_HEIGHT = A4  # 595.275 x 841.889 pt

# Color Palette (Slate/Indigo modern school design)
PRIMARY_COLOR = colors.HexColor("#1E3A8A")       # Deep Blue / Navy
SECONDARY_COLOR = colors.HexColor("#3B82F6")     # Accent Blue
HEADER_BG = colors.HexColor("#0F172A")           # Dark Slate
CARD_BG = colors.HexColor("#F8FAFC")             # Light Slate
CARD_BORDER = colors.HexColor("#CBD5E1")         # Border Slate
TEXT_DARK = colors.HexColor("#0F172A")           # Slate 900
TEXT_MUTED = colors.HexColor("#64748B")          # Slate 500
ROW_ALT = colors.HexColor("#F1F5F9")             # Alternating row
PASS_COLOR = colors.HexColor("#059669")          # Emerald 600
FAIL_COLOR = colors.HexColor("#DC2626")          # Red 600
GOLD_COLOR = colors.HexColor("#D97706")          # Amber 600

# Resolve Unicode / TTF font
_FONT_NORMAL = "Helvetica"
_FONT_BOLD = "Helvetica-Bold"


def _init_pdf_fonts() -> tuple[str, str]:
    """
    Attempts to register a TrueType font capable of Urdu/Unicode rendering.
    Falls back cleanly to standard Helvetica across Windows and Ubuntu CI environments.
    """
    global _FONT_NORMAL, _FONT_BOLD

    search_paths = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "fonts", "urdu.ttf"),
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]

    for path in search_paths:
        if os.path.exists(path):
            try:
                font_name = "CF_ReportFont"
                pdfmetrics.registerFont(TTFont(font_name, path))
                _FONT_NORMAL = font_name
                _FONT_BOLD = font_name
                return _FONT_NORMAL, _FONT_BOLD
            except Exception:
                continue

    return _FONT_NORMAL, _FONT_BOLD


_init_pdf_fonts()


class ReportCardGenerator:
    """Generates print-ready single-sheet A4 terminal report cards."""

    def __init__(self, institution_name: str = "CLASSFELLOW HIGH SCHOOL & ACADEMY", urdu_institution_name: str = "کلاس فیلو ہائی سکول و اکیڈمی"):
        self.institution_name = institution_name
        self.urdu_institution_name = urdu_institution_name

    def render_report_card(
        self,
        report_data: StudentReportCardDTO,
        output: Union[str, BytesIO]
    ) -> Union[str, BytesIO]:
        """
        Renders the complete A4 terminal report card document.

        Args:
            report_data: StudentReportCardDTO containing academic marks and profile.
            output: Destination file path or BytesIO buffer.

        Returns:
            The destination file path or BytesIO buffer.
        """
        pdf = canvas.Canvas(output, pagesize=A4)
        pdf.setTitle(f"Report_Card_{report_data.admission_number}_{report_data.exam_name}")

        margin = 36.0
        content_width = PAGE_WIDTH - (2 * margin)

        # 1. Draw Page Outer Border
        pdf.setStrokeColor(CARD_BORDER)
        pdf.setLineWidth(1.0)
        pdf.rect(margin - 10, margin - 10, content_width + 20, PAGE_HEIGHT - (2 * margin) + 20)

        # 2. Header Section
        y = PAGE_HEIGHT - margin - 20
        y = self._draw_header(pdf, report_data, margin, content_width, y)

        # 3. Student Profile Box
        y -= 10
        y = self._draw_student_profile(pdf, report_data, margin, content_width, y)

        # 4. Results Data Table
        y -= 15
        y = self._draw_results_table(pdf, report_data, margin, content_width, y)

        # 5. Scorecard Metric Summary Grid
        y -= 15
        y = self._draw_summary_grid(pdf, report_data, margin, content_width, y)

        # 6. Attendance & Teacher Remarks Box
        y -= 15
        y = self._draw_remarks_section(pdf, report_data, margin, content_width, y)

        # 7. Institutional Sign-off Footer
        self._draw_footer(pdf, margin, content_width, margin + 25)

        pdf.showPage()
        pdf.save()

        if isinstance(output, BytesIO):
            output.seek(0)
        return output

    def _draw_header(self, pdf: canvas.Canvas, report_data: StudentReportCardDTO, x: float, width: float, y: float) -> float:
        """Renders school crest branding and title."""
        # Crest / Embellishment Box on Left
        crest_size = 50.0
        pdf.setFillColor(PRIMARY_COLOR)
        pdf.roundRect(x, y - crest_size + 10, crest_size, crest_size, 6, fill=1, stroke=0)
        pdf.setFillColor(colors.white)
        pdf.setFont(_FONT_BOLD, 18)
        pdf.drawCentredString(x + (crest_size / 2.0), y - (crest_size / 2.0) + 4, "CF")

        # School Name & Urdu Title
        pdf.setFillColor(PRIMARY_COLOR)
        pdf.setFont(_FONT_BOLD, 16)
        pdf.drawString(x + crest_size + 15, y + 2, self.institution_name)

        shaped_urdu_school = format_urdu(self.urdu_institution_name)
        pdf.setFont(_FONT_NORMAL, 12)
        pdf.setFillColor(TEXT_MUTED)
        pdf.drawRightString(x + width, y + 2, shaped_urdu_school)

        # Exam Name & Session Subheading
        y -= 22
        pdf.setFillColor(TEXT_DARK)
        pdf.setFont(_FONT_BOLD, 12)
        pdf.drawString(x + crest_size + 15, y, f"PROGRESS REPORT / TERMINAL RESULT CARD - {report_data.session_name.upper()}")

        exam_title_str = f"EXAMINATION: {report_data.exam_name.upper()}"
        pdf.setFont(_FONT_NORMAL, 10)
        pdf.setFillColor(TEXT_MUTED)
        pdf.drawString(x + crest_size + 15, y - 14, exam_title_str)

        y -= 25
        pdf.setStrokeColor(PRIMARY_COLOR)
        pdf.setLineWidth(2.0)
        pdf.line(x, y, x + width, y)

        return y

    def _draw_student_profile(self, pdf: canvas.Canvas, report_data: StudentReportCardDTO, x: float, width: float, y: float) -> float:
        """Renders the 2-column key-value student profile box."""
        box_height = 54.0
        box_y = y - box_height

        pdf.setFillColor(CARD_BG)
        pdf.setStrokeColor(CARD_BORDER)
        pdf.setLineWidth(0.75)
        pdf.roundRect(x, box_y, width, box_height, 4, fill=1, stroke=1)

        pdf.setFont(_FONT_BOLD, 9)
        pdf.setFillColor(TEXT_MUTED)

        # Column 1
        col1_x = x + 12
        col1_val_x = x + 105
        # Column 2
        col2_x = x + (width / 2.0) + 12
        col2_val_x = col2_x + 100

        # Row 1
        r1_y = box_y + 36
        pdf.drawString(col1_x, r1_y, "STUDENT NAME:")
        pdf.setFont(_FONT_BOLD, 9.5)
        pdf.setFillColor(TEXT_DARK)
        student_display = report_data.student_name
        if report_data.urdu_name:
            student_display += f" ({format_urdu(report_data.urdu_name)})"
        pdf.drawString(col1_val_x, r1_y, student_display)

        pdf.setFont(_FONT_BOLD, 9)
        pdf.setFillColor(TEXT_MUTED)
        pdf.drawString(col2_x, r1_y, "ADMISSION NO:")
        pdf.setFont(_FONT_BOLD, 9.5)
        pdf.setFillColor(TEXT_DARK)
        pdf.drawString(col2_val_x, r1_y, report_data.admission_number)

        # Row 2
        r2_y = box_y + 14
        pdf.setFont(_FONT_BOLD, 9)
        pdf.setFillColor(TEXT_MUTED)
        pdf.drawString(col1_x, r2_y, "CLASS & SECTION:")
        pdf.setFont(_FONT_BOLD, 9.5)
        pdf.setFillColor(TEXT_DARK)
        pdf.drawString(col1_val_x, r2_y, report_data.class_name)

        pdf.setFont(_FONT_BOLD, 9)
        pdf.setFillColor(TEXT_MUTED)
        pdf.drawString(col2_x, r2_y, "ROLL NUMBER:")
        pdf.setFont(_FONT_BOLD, 9.5)
        pdf.setFillColor(TEXT_DARK)
        pdf.drawString(col2_val_x, r2_y, report_data.roll_number or "N/A")

        return box_y

    def _draw_results_table(self, pdf: canvas.Canvas, report_data: StudentReportCardDTO, x: float, width: float, y: float) -> float:
        """Renders subject-wise marks table with alternating rows."""
        header_height = 22.0
        row_height = 20.0

        cols = [
            ("Sr #", 35.0, "center"),
            ("Subject Name", 170.0, "left"),
            ("Max Marks", 65.0, "center"),
            ("Pass Marks", 65.0, "center"),
            ("Obtained", 65.0, "center"),
            ("Percentage", 65.0, "center"),
            ("Grade", 58.0, "center"),
        ]

        # Table Header
        pdf.setFillColor(PRIMARY_COLOR)
        pdf.rect(x, y - header_height, width, header_height, fill=1, stroke=0)

        pdf.setFillColor(colors.white)
        pdf.setFont(_FONT_BOLD, 8.5)

        curr_x = x
        for title, col_w, align in cols:
            if align == "center":
                pdf.drawCentredString(curr_x + (col_w / 2.0), y - header_height + 7, title)
            elif align == "right":
                pdf.drawRightString(curr_x + col_w - 5, y - header_height + 7, title)
            else:
                pdf.drawString(curr_x + 8, y - header_height + 7, title)
            curr_x += col_w

        y -= header_height

        # Table Body
        for idx, res in enumerate(report_data.results, start=1):
            pdf.setFillColor(ROW_ALT if idx % 2 == 0 else colors.white)
            pdf.rect(x, y - row_height, width, row_height, fill=1, stroke=0)

            # Draw bottom separator
            pdf.setStrokeColor(CARD_BORDER)
            pdf.setLineWidth(0.5)
            pdf.line(x, y - row_height, x + width, y - row_height)

            curr_x = x
            pdf.setFont(_FONT_NORMAL, 8.5)
            pdf.setFillColor(TEXT_DARK)

            # 1. Sr #
            pdf.drawCentredString(curr_x + (cols[0][1] / 2.0), y - row_height + 6, str(idx))
            curr_x += cols[0][1]

            # 2. Subject Name
            sub_display = res.subject_name
            if res.subject_urdu_name:
                sub_display += f" - {format_urdu(res.subject_urdu_name)}"
            pdf.drawString(curr_x + 8, y - row_height + 6, sub_display)
            curr_x += cols[1][1]

            # 3. Max Marks
            pdf.drawCentredString(curr_x + (cols[2][1] / 2.0), y - row_height + 6, f"{res.maximum_marks:.1f}")
            curr_x += cols[2][1]

            # 4. Pass Marks
            pdf.drawCentredString(curr_x + (cols[3][1] / 2.0), y - row_height + 6, f"{res.passing_marks:.1f}")
            curr_x += cols[3][1]

            # 5. Obtained Marks
            pdf.setFont(_FONT_BOLD, 8.5)
            if res.is_absent:
                pdf.setFillColor(FAIL_COLOR)
                pdf.drawCentredString(curr_x + (cols[4][1] / 2.0), y - row_height + 6, "ABS")
            else:
                pdf.setFillColor(TEXT_DARK)
                pdf.drawCentredString(curr_x + (cols[4][1] / 2.0), y - row_height + 6, f"{res.marks_obtained:.1f}")
            curr_x += cols[4][1]

            # 6. Percentage
            if res.maximum_marks > 0 and not res.is_absent:
                sub_pct = (res.marks_obtained / res.maximum_marks) * Decimal("100.00")
                pdf.setFont(_FONT_NORMAL, 8.5)
                pdf.setFillColor(TEXT_DARK)
                pdf.drawCentredString(curr_x + (cols[5][1] / 2.0), y - row_height + 6, f"{sub_pct:.1f}%")
            else:
                pdf.drawCentredString(curr_x + (cols[5][1] / 2.0), y - row_height + 6, "0.0%")
            curr_x += cols[5][1]

            # 7. Grade
            pdf.setFont(_FONT_BOLD, 8.5)
            if not res.is_passed or res.is_absent:
                pdf.setFillColor(FAIL_COLOR)
            else:
                pdf.setFillColor(PASS_COLOR)
            pdf.drawCentredString(curr_x + (cols[6][1] / 2.0), y - row_height + 6, res.grade)

            y -= row_height

        return y

    def _draw_summary_grid(self, pdf: canvas.Canvas, report_data: StudentReportCardDTO, x: float, width: float, y: float) -> float:
        """Renders 4 high-contrast summary blocks: Total, Obtained, Percentage, Grade / Rank."""
        grid_height = 46.0
        card_y = y - grid_height
        num_cards = 4
        spacing = 8.0
        card_width = (width - (spacing * (num_cards - 1))) / num_cards

        metrics = [
            ("TOTAL MARKS", f"{report_data.total_maximum:.1f}", TEXT_DARK),
            ("OBTAINED MARKS", f"{report_data.total_obtained:.1f}", PRIMARY_COLOR),
            ("PERCENTAGE", f"{report_data.percentage:.2f}%", PRIMARY_COLOR),
            ("GRADE / POSITION", f"{report_data.final_grade} (Rank: {report_data.rank_in_class})", GOLD_COLOR if report_data.rank_in_class <= 3 else PRIMARY_COLOR),
        ]

        curr_x = x
        for label, val, val_color in metrics:
            pdf.setFillColor(CARD_BG)
            pdf.setStrokeColor(CARD_BORDER)
            pdf.setLineWidth(0.75)
            pdf.roundRect(curr_x, card_y, card_width, grid_height, 4, fill=1, stroke=1)

            # Label
            pdf.setFont(_FONT_BOLD, 7.5)
            pdf.setFillColor(TEXT_MUTED)
            pdf.drawCentredString(curr_x + (card_width / 2.0), card_y + 30, label)

            # Value
            pdf.setFont(_FONT_BOLD, 11)
            pdf.setFillColor(val_color)
            pdf.drawCentredString(curr_x + (card_width / 2.0), card_y + 12, val)

            curr_x += card_width + spacing

        return card_y

    def _draw_remarks_section(self, pdf: canvas.Canvas, report_data: StudentReportCardDTO, x: float, width: float, y: float) -> float:
        """Renders Term Attendance Summary and Teacher Remarks with Urdu formatting."""
        section_height = 68.0
        sec_y = y - section_height

        pdf.setFillColor(CARD_BG)
        pdf.setStrokeColor(CARD_BORDER)
        pdf.setLineWidth(0.75)
        pdf.roundRect(x, sec_y, width, section_height, 4, fill=1, stroke=1)

        # Attendance summary
        pdf.setFont(_FONT_BOLD, 8.5)
        pdf.setFillColor(PRIMARY_COLOR)
        pdf.drawString(x + 12, sec_y + section_height - 16, "ATTENDANCE METRIC:")

        att_text = f"Cumulative Term Attendance: {report_data.attendance_percentage:.1f}%"
        pdf.setFont(_FONT_NORMAL, 8.5)
        pdf.setFillColor(TEXT_DARK)
        pdf.drawString(x + 140, sec_y + section_height - 16, att_text)

        # Remarks
        pdf.setFont(_FONT_BOLD, 8.5)
        pdf.setFillColor(PRIMARY_COLOR)
        pdf.drawString(x + 12, sec_y + section_height - 36, "TEACHER REMARKS:")

        remarks_str = report_data.teacher_remarks or "Satisfactory performance. Consistent effort recommended."
        if report_data.teacher_urdu_remarks:
            remarks_str += f" | {format_urdu(report_data.teacher_urdu_remarks)}"

        pdf.setFont(_FONT_NORMAL, 8.5)
        pdf.setFillColor(TEXT_DARK)
        pdf.drawString(x + 140, sec_y + section_height - 36, remarks_str)

        # Board / Evaluation note
        pdf.setFont(_FONT_NORMAL, 7.5)
        pdf.setFillColor(TEXT_MUTED)
        pdf.drawString(x + 12, sec_y + 10, "* Note: This is an official institutional terminal evaluation based on school examination standards.")

        return sec_y

    def _draw_footer(self, pdf: canvas.Canvas, x: float, width: float, y: float) -> None:
        """Renders 3 sign-off signature slots."""
        col_w = width / 3.0
        line_w = 120.0

        pdf.setStrokeColor(TEXT_MUTED)
        pdf.setLineWidth(0.75)
        pdf.setFont(_FONT_BOLD, 8)
        pdf.setFillColor(TEXT_MUTED)

        # Slot 1: Class Teacher
        pdf.line(x + 10, y + 15, x + 10 + line_w, y + 15)
        pdf.drawCentredString(x + 10 + (line_w / 2.0), y + 2, "Class Teacher")

        # Slot 2: Controller of Examinations
        mid_x = x + col_w + (col_w - line_w) / 2.0
        pdf.line(mid_x, y + 15, mid_x + line_w, y + 15)
        pdf.drawCentredString(mid_x + (line_w / 2.0), y + 2, "Examination Controller")

        # Slot 3: Principal
        right_x = x + width - line_w - 10
        pdf.line(right_x, y + 15, right_x + line_w, y + 15)
        pdf.drawCentredString(right_x + (line_w / 2.0), y + 2, "Principal / Official Stamp")


def generate_report_card_pdf(
    report_data: StudentReportCardDTO,
    output: Optional[Union[str, BytesIO]] = None,
    institution_name: str = "CLASSFELLOW HIGH SCHOOL & ACADEMY"
) -> Union[str, BytesIO]:
    """Convenience helper to generate an A4 terminal report card PDF."""
    generator = ReportCardGenerator(institution_name=institution_name)
    if output is None:
        output = BytesIO()
    return generator.render_report_card(report_data, output)
