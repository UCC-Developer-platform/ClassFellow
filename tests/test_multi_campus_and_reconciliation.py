"""
ClassFellow - Category 12 Multi-Campus Scoping & Financial Reconciliation Test Suite
Verifies Campus model relationships, class group scoping, CashierReconciliationService
day-closing calculations, openpyxl monthly collection audit workbook generation,
and HTTP endpoints.
"""

import datetime
from decimal import Decimal
import io
import os
import sys
from pathlib import Path
import openpyxl
import pytest

# Ensure classfellow_web is on sys.path
WEB_DIR = Path(__file__).resolve().parent.parent / "classfellow_web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ["DJANGO_DB_ENGINE"] = "sqlite"

import django  # noqa: E402
django.setup()

from django.core.management import call_command  # noqa: E402
from django.test import Client  # noqa: E402

from apps.accounts.models import Role, User  # noqa: E402
from apps.core.models import AcademicSession, Campus, InstitutionProfile  # noqa: E402
from apps.fees.models import FeeHead, FeeInvoice, FeeInvoiceItem, Payment, PaymentMethod, PaymentStatus  # noqa: E402
from apps.fees.reports import FeeExcelExportService  # noqa: E402
from apps.fees.services import CashierReconciliationService  # noqa: E402
from apps.students.models import ClassGroup, Enrollment, EnrollmentStatus, Gender, GroupType, Student  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def setup_reconciliation_database():
    """Flushes and prepares fresh database environment for Category 12 testing."""
    call_command("migrate", interactive=False)
    call_command("flush", interactive=False)

    # 1. Institution & Academic Session
    InstitutionProfile.objects.create(
        name="Allama Iqbal Model College",
        campus_name="Central Complex",
    )
    session = AcademicSession.objects.create(
        name="2026-2027 Recon Session",
        start_date=datetime.date(2026, 4, 1),
        end_date=datetime.date(2027, 3, 31),
        is_active=True,
    )

    # 2. Campuses
    campus_main = Campus.objects.create(
        name="Main Boys Campus",
        code="MBC",
        address="Mall Road, Lahore",
        is_active=True,
    )
    campus_junior = Campus.objects.create(
        name="Junior Girls Wing",
        code="JGW",
        address="Gulberg III, Lahore",
        is_active=True,
    )

    # 3. Class Groups scoped to Campuses
    class_boys = ClassGroup.objects.create(
        session=session,
        campus=campus_main,
        name="Class 10-A",
        section_or_batch="Boys Section",
        group_type=GroupType.SCHOOL_CLASS,
        monthly_tuition_fee=Decimal("6000.00"),
    )
    class_girls = ClassGroup.objects.create(
        session=session,
        campus=campus_junior,
        name="Class 6-G",
        section_or_batch="Junior Section",
        group_type=GroupType.SCHOOL_CLASS,
        monthly_tuition_fee=Decimal("4000.00"),
    )

    # 4. Users
    User.objects.create_user(
        username="recon_admin",
        password="Password123!",
        role=Role.ADMIN,
    )
    cashier1 = User.objects.create_user(
        username="recon_cashier1",
        password="Password123!",
        role=Role.CASHIER,
        first_name="Tariq",
        last_name="Cashier",
    )
    cashier2 = User.objects.create_user(
        username="recon_cashier2",
        password="Password123!",
        role=Role.CASHIER,
        first_name="Salman",
        last_name="Cashier",
    )

    # 5. Students & Enrollments
    stu1 = Student.objects.create(
        admission_number="CF-2026-0501",
        first_name="Usman",
        last_name="Ghani",
        gender=Gender.MALE,
        guardian_name="Ghani Khan",
        guardian_phone="03001112222",
    )
    enr1 = Enrollment.objects.create(
        student=stu1,
        class_group=class_boys,
        session=session,
        roll_number="01",
        status=EnrollmentStatus.ACTIVE,
    )

    stu2 = Student.objects.create(
        admission_number="CF-2026-0502",
        first_name="Amina",
        last_name="Akram",
        gender=Gender.FEMALE,
        guardian_name="Muhammad Akram",
        guardian_phone="03123334444",
    )
    enr2 = Enrollment.objects.create(
        student=stu2,
        class_group=class_girls,
        session=session,
        roll_number="02",
        status=EnrollmentStatus.ACTIVE,
    )

    # 6. Fee Invoices
    head_tuition = FeeHead.objects.create(name="Tuition Fee", urdu_name="ٹیوشن فیس")
    inv1 = FeeInvoice.objects.create(
        enrollment=enr1,
        session=session,
        month_year="2026-06",
        issue_date=datetime.date(2026, 6, 1),
        due_date=datetime.date(2026, 6, 10),
        valid_until=datetime.date(2026, 6, 20),
        total_payable=Decimal("6000.00"),
        discount_amount=Decimal("0.00"),
        net_due=Decimal("6000.00"),
    )
    FeeInvoiceItem.objects.create(invoice=inv1, fee_head=head_tuition, amount=Decimal("6000.00"))

    inv2 = FeeInvoice.objects.create(
        enrollment=enr2,
        session=session,
        month_year="2026-06",
        issue_date=datetime.date(2026, 6, 1),
        due_date=datetime.date(2026, 6, 10),
        valid_until=datetime.date(2026, 6, 20),
        total_payable=Decimal("4000.00"),
        discount_amount=Decimal("500.00"),
        net_due=Decimal("3500.00"),
    )
    FeeInvoiceItem.objects.create(invoice=inv2, fee_head=head_tuition, amount=Decimal("4000.00"))

    # 7. Payments on Target Date (2026-06-05)
    recon_date = datetime.date(2026, 6, 5)

    # Payment 1: Cash (by cashier1, boys campus)
    Payment.objects.create(
        invoice=inv1,
        amount=Decimal("4000.00"),
        payment_date=recon_date,
        receipt_number="REC-2026-00010",
        payment_method=PaymentMethod.CASH,
        status=PaymentStatus.ISSUED,
        recorded_by_user=cashier1,
        note="Counter cash collection",
    )

    # Payment 2: Bank Transfer (by cashier1, boys campus)
    Payment.objects.create(
        invoice=inv1,
        amount=Decimal("2000.00"),
        payment_date=recon_date,
        receipt_number="REC-2026-00011",
        payment_method=PaymentMethod.BANK_TRANSFER,
        status=PaymentStatus.ISSUED,
        recorded_by_user=cashier1,
        note="HBL online transfer",
    )

    # Payment 3: Online Deposit (by cashier2, girls campus)
    Payment.objects.create(
        invoice=inv2,
        amount=Decimal("3500.00"),
        payment_date=recon_date,
        receipt_number="REC-2026-00012",
        payment_method=PaymentMethod.ONLINE_DEPOSIT,
        status=PaymentStatus.ISSUED,
        recorded_by_user=cashier2,
        note="Easypaisa branch collection",
    )

    # Payment 4: Reversed Cheque Payment on same date
    Payment.objects.create(
        invoice=inv1,
        amount=Decimal("1500.00"),
        payment_date=recon_date,
        receipt_number="REC-2026-00009",
        payment_method=PaymentMethod.CHEQUE,
        status=PaymentStatus.REVERSED,
        reversal_reason="Cheque dishonored / signature mismatch",
        recorded_by_user=cashier1,
    )


# =============================================================================
# 1. Multi-Branch & Campus Scoping Tests (Task MC-01)
# =============================================================================

def test_campus_model_and_class_group_scoping():
    """Verifies Campus model attributes, reverse relations, and scoping."""
    mbc = Campus.objects.get(code="MBC")
    jgw = Campus.objects.get(code="JGW")

    assert str(mbc) == "Main Boys Campus (MBC)"
    assert str(jgw) == "Junior Girls Wing (JGW)"

    mbc_classes = list(mbc.classes.all())
    assert len(mbc_classes) == 1
    assert mbc_classes[0].name == "Class 10-A"

    jgw_classes = list(jgw.classes.all())
    assert len(jgw_classes) == 1
    assert jgw_classes[0].name == "Class 6-G"

    # Default campus migration verification
    default_camp = Campus.objects.filter(code="MBC").first()
    assert default_camp is not None


# =============================================================================
# 2. Cashier Day-Closing Reconciliation Engine Tests (Task MC-02)
# =============================================================================

def test_cashier_reconciliation_service_all_aggregates():
    """Verifies daily summary totals, payment method breakdown, and receipt boundaries."""
    recon_date = datetime.date(2026, 6, 5)
    summary = CashierReconciliationService.generate_daily_closing_summary(target_date=recon_date)

    # Total collected: 4000 (Cash) + 2000 (Bank) + 3500 (Online) = 9500.00
    assert summary["total_collected"] == Decimal("9500.00")
    assert summary["receipts_count"] == 3

    # Method Breakdown
    assert summary["method_breakdown"][PaymentMethod.CASH] == Decimal("4000.00")
    assert summary["method_breakdown"][PaymentMethod.BANK_TRANSFER] == Decimal("2000.00")
    assert summary["method_breakdown"][PaymentMethod.ONLINE_DEPOSIT] == Decimal("3500.00")
    assert summary["method_breakdown"][PaymentMethod.CHEQUE] == Decimal("0.00")

    # Receipt Sequence Range
    assert summary["receipt_range_start"] == "REC-2026-00010"
    assert summary["receipt_range_end"] == "REC-2026-00012"

    # Reversals
    assert summary["reversed_count"] == 1
    assert summary["reversed_amount"] == Decimal("1500.00")
    assert len(summary["reversed_transactions"]) == 1
    assert summary["reversed_transactions"][0]["receipt_number"] == "REC-2026-00009"
    assert "dishonored" in summary["reversed_transactions"][0]["reversal_reason"]


def test_cashier_reconciliation_service_filtered_by_cashier():
    """Verifies day-closing summary filtered by specific cashier."""
    recon_date = datetime.date(2026, 6, 5)
    cashier1 = User.objects.get(username="recon_cashier1")

    summary = CashierReconciliationService.generate_daily_closing_summary(
        target_date=recon_date,
        user_id=cashier1.id,
    )

    # Cashier 1: 4000 + 2000 = 6000.00 (2 receipts)
    assert summary["total_collected"] == Decimal("6000.00")
    assert summary["receipts_count"] == 2
    assert summary["cashier_name"] == "Tariq Cashier"
    assert summary["receipt_range_start"] == "REC-2026-00010"
    assert summary["receipt_range_end"] == "REC-2026-00011"


def test_cashier_reconciliation_service_filtered_by_campus():
    """Verifies day-closing summary filtered by specific campus."""
    recon_date = datetime.date(2026, 6, 5)
    jgw = Campus.objects.get(code="JGW")

    summary = CashierReconciliationService.generate_daily_closing_summary(
        target_date=recon_date,
        campus_id=jgw.id,
    )

    # Junior Girls Wing: 3500.00 (1 receipt)
    assert summary["total_collected"] == Decimal("3500.00")
    assert summary["receipts_count"] == 1
    assert summary["campus_name"] == "Junior Girls Wing"
    assert summary["receipt_range_start"] == "REC-2026-00012"


# =============================================================================
# 3. Financial Audit Excel Export Engine Tests (Task MC-03)
# =============================================================================

def test_fee_excel_export_service_workbook_generation():
    """Verifies generating a styled openpyxl Excel spreadsheet for monthly fee collections."""
    session = AcademicSession.objects.filter(name="2026-2027 Recon Session").first()

    excel_buffer = FeeExcelExportService.export_monthly_collection_workbook(
        session_id=session.id,
        month_year="2026-06",
    )

    assert isinstance(excel_buffer, io.BytesIO)
    bytes_data = excel_buffer.getvalue()
    assert len(bytes_data) > 2000
    # OpenXML spreadsheets are zip archives starting with 'PK\x03\x04'
    assert bytes_data.startswith(b"PK\x03\x04")

    # Inspect worksheet contents using openpyxl
    wb = openpyxl.load_workbook(excel_buffer)
    assert "Collection 2026-06" in wb.sheetnames

    ws = wb["Collection 2026-06"]
    # Header title check
    assert "MONTHLY FEE COLLECTION AUDIT" in str(ws["A1"].value)
    # Column headers in row 4
    headers = [cell.value for cell in ws[4]]
    assert headers[0] == "Admission #"
    assert headers[1] == "Student Name"
    assert headers[4] == "Tuition Fee"
    assert headers[5] == "Total Billed"
    assert headers[7] == "Total Paid"
    assert headers[8] == "Balance"

    # Data row check (row 5)
    assert ws.cell(row=5, column=1).value in ("CF-2026-0501", "CF-2026-0502")
    # Summary row exists
    last_row = ws.max_row
    assert ws.cell(row=last_row, column=1).value == "TOTAL"


# =============================================================================
# 4. Web View & Streaming HTTP Endpoint Tests (Tasks MC-02 & MC-03)
# =============================================================================

def test_reconciliation_web_view_returns_200():
    """Verifies GET /fees/reconciliation/ displays printable audit certificate."""
    client = Client()
    client.login(username="recon_admin", password="Password123!")

    resp = client.get("/fees/reconciliation/?date=2026-06-05")
    assert resp.status_code == 200
    assert b"Financial Day-Closing Reconciliation" in resp.content
    assert b"DAILY CASHIER RECONCILIATION & CLOSING AUDIT" in resp.content
    assert b"REC-2026-00010" in resp.content
    assert b"REC-2026-00012" in resp.content
    assert b"Rs. 9500.00" in resp.content


def test_monthly_collection_xlsx_streaming_endpoint():
    """Verifies GET /fees/reports/monthly-collection/xlsx/ returns valid spreadsheet."""
    client = Client()
    client.login(username="recon_admin", password="Password123!")

    resp = client.get("/fees/reports/monthly-collection/xlsx/?month_year=2026-06")
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "attachment" in resp["Content-Disposition"]
    assert "Monthly_Collection_2026-06.xlsx" in resp["Content-Disposition"]

    content = resp.content
    assert len(content) > 1000
    assert content.startswith(b"PK\x03\x04")
