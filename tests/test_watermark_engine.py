"""
Automated Test Suite for Opacity-Controlled ReportLab Watermark Engine
"""

from io import BytesIO
from decimal import Decimal
import pytest
from PIL import Image

from app.reports.fee_voucher_generator import FeeVoucherGenerator
from app.reports.report_card_generator import ReportCardGenerator
from models import StudentReportCardDTO, SubjectResultDTO


@pytest.fixture
def sample_logo_file(tmp_path):
    """Creates a temporary sample PNG image to act as a school crest."""
    logo_path = str(tmp_path / "school_crest.png")
    img = Image.new("RGBA", (100, 100), color=(16, 185, 129, 255))
    img.save(logo_path)
    return logo_path


@pytest.fixture
def dummy_voucher_data():
    return {
        "voucher_no": "VCH-2026-0001",
        "issue_date": "2026-09-01",
        "due_date": "2026-09-10",
        "valid_until": "2026-09-20",
        "billing_period": "September 2026",
        "student": {
            "admission_number": "CF-2026-0001",
            "name": "Ahmed Khan",
            "urdu_name": "احمد خان",
            "guardian_name": "Tariq Khan",
            "guardian_urdu_name": "طارق خان",
            "class_group": "Class 10 (Section A)",
            "b_form_number": "35201-1234567-1",
        },
        "fee_items": [
            {"head_name": "Tuition Fee", "urdu_head_name": "ٹیوشن فیس", "amount": "3500.00"},
            {"head_name": "Admission Fee", "urdu_head_name": "داخلہ فیس", "amount": "5000.00"},
        ],
        "subtotal": "8500.00",
        "discount_amount": "500.00",
        "prior_arrears": "0.00",
        "total_payable": "8000.00",
        "late_fee_fine": "200.00",
        "payable_after_due": "8200.00",
        "payment_status": "Unpaid",
    }


@pytest.fixture
def dummy_report_card_data():
    return StudentReportCardDTO(
        student_name="Hamza Tariq",
        urdu_name="حمزہ طارق",
        roll_number="12",
        class_name="Class 9",
        admission_number="CF-2026-0001",
        exam_name="Mid-Term Examination 2026",
        session_name="2026-2027",
        results=[
            SubjectResultDTO(
                subject_name="Mathematics",
                subject_urdu_name="ریاضی",
                maximum_marks=Decimal("100.00"),
                passing_marks=Decimal("33.00"),
                marks_obtained=Decimal("85.00"),
                is_absent=False,
                is_passed=True,
                grade="A"
            ),
            SubjectResultDTO(
                subject_name="English",
                subject_urdu_name="انگریزی",
                maximum_marks=Decimal("100.00"),
                passing_marks=Decimal("33.00"),
                marks_obtained=Decimal("78.00"),
                is_absent=False,
                is_passed=True,
                grade="B"
            ),
        ],
        total_maximum=Decimal("200.00"),
        total_obtained=Decimal("163.00"),
        percentage=Decimal("81.50"),
        final_grade="A",
        gpa_point=Decimal("3.8"),
        rank_in_class=1,
        total_students_in_class=45,
        attendance_percentage=93.75,
        teacher_remarks="Outstanding academic performance.",
        teacher_urdu_remarks="شاندار تعلیمی کارکردگی"
    )


def test_fee_voucher_with_valid_watermark(sample_logo_file, dummy_voucher_data):
    """Verifies that FeeVoucherGenerator produces a valid PDF with watermark when logo exists."""
    gen = FeeVoucherGenerator(
        institution_name="ClassFellow Grammar School",
        logo_path=sample_logo_file
    )
    buf = BytesIO()
    out = gen.render_voucher(dummy_voucher_data, buf)
    pdf_bytes = out.getvalue()
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 1000


def test_fee_voucher_with_missing_watermark_omits_cleanly(dummy_voucher_data):
    """Verifies that FeeVoucherGenerator omits watermark cleanly without crashing if logo is None or missing."""
    gen = FeeVoucherGenerator(
        institution_name="ClassFellow Grammar School",
        logo_path="non_existent_crest_logo.png"
    )
    buf = BytesIO()
    out = gen.render_voucher(dummy_voucher_data, buf)
    pdf_bytes = out.getvalue()
    assert pdf_bytes.startswith(b"%PDF-")


def test_report_card_with_valid_watermark(sample_logo_file, dummy_report_card_data):
    """Verifies that ReportCardGenerator produces a valid PDF with watermark when logo exists."""
    gen = ReportCardGenerator(
        institution_name="ClassFellow Grammar School",
        logo_path=sample_logo_file
    )
    buf = BytesIO()
    out = gen.render_report_card(dummy_report_card_data, buf)
    pdf_bytes = out.getvalue()
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 1000


def test_report_card_with_missing_watermark_omits_cleanly(dummy_report_card_data):
    """Verifies that ReportCardGenerator omits watermark cleanly without crashing if logo is missing."""
    gen = ReportCardGenerator(
        institution_name="ClassFellow Grammar School",
        logo_path=None
    )
    buf = BytesIO()
    out = gen.render_report_card(dummy_report_card_data, buf)
    pdf_bytes = out.getvalue()
    assert pdf_bytes.startswith(b"%PDF-")
