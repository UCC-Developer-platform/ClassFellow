"""
Unit and integration tests for FeeService, Currency Words utility,
Payment Ledgers with ON DELETE RESTRICT, and 3-Panel A4 Voucher Generator.
"""

import io
import pytest
import sqlite3
from decimal import Decimal
from models import StudentDTO
from services.schema_service import migrate_to_latest
from services.student_service import StudentService
from services.fee_service import FeeService, generate_next_receipt_number
from reports.currency_words import amount_in_words_en
from app.reports.fee_voucher_generator import FeeVoucherGenerator, generate_fee_voucher_pdf


@pytest.fixture
def migrated_db(db_connection):
    """Provides a SQLite connection with all migrations applied."""
    migrate_to_latest(db_connection)
    return db_connection


@pytest.fixture
def student_service(migrated_db):
    return StudentService(migrated_db)


@pytest.fixture
def fee_service(migrated_db):
    return FeeService(migrated_db)


@pytest.fixture
def test_setup(student_service):
    """Sets up an academic session, class group, and two enrolled students."""
    session_id = student_service.create_academic_session(
        name="2025-2026",
        start_date="2025-04-01",
        end_date="2026-03-31"
    )
    class_group_id = student_service.create_class_group(
        session_id=session_id,
        name="Class 9",
        section_or_batch="Section Green",
        group_type="SchoolClass",
        monthly_tuition_fee=Decimal("5000.00")
    )

    # Student 1: Normal fee
    s1 = StudentDTO(
        first_name="Ahmed",
        last_name="Raza",
        urdu_name="احمد رضا",
        gender="Male",
        guardian_name="Tariq Raza",
        guardian_phone="03001234567"
    )
    st_id1, enr_id1 = student_service.register_student(
        s1, class_group_id, session_id, roll_number="R-01"
    )

    # Student 2: With approved permanent discount (Rs. 1000)
    s2 = StudentDTO(
        first_name="Ayesha",
        last_name="Khan",
        urdu_name="عائشہ خان",
        gender="Female",
        guardian_name="Imran Khan",
        guardian_phone="03019876543"
    )
    st_id2, enr_id2 = student_service.register_student(
        s2, class_group_id, session_id, roll_number="R-02",
        custom_discount_amount=Decimal("1000.00")
    )

    return {
        "session_id": session_id,
        "class_group_id": class_group_id,
        "student1": {"student_id": st_id1, "enrollment_id": enr_id1},
        "student2": {"student_id": st_id2, "enrollment_id": enr_id2},
    }


# --- Currency in Words Tests ---

def test_amount_in_words_english():
    """Verifies num2words conversion into standard Pakistani financial text."""
    assert amount_in_words_en(Decimal("0.00")) == "In Words: Zero Rupees Only"
    assert amount_in_words_en(Decimal("5000.00")) == "In Words: Five Thousand Rupees Only"
    assert amount_in_words_en(Decimal("4550.00")) == "In Words: Four Thousand Five Hundred And Fifty Rupees Only"
    assert amount_in_words_en(Decimal("1250.75")) == "In Words: One Thousand Two Hundred And Fifty Rupees and Seventy Five Paisas Only"



# --- Monthly Invoicing Engine Tests ---

def test_generate_monthly_invoices_and_itemized_lines(test_setup, fee_service):
    """
    Verifies batch generation of monthly invoices, itemized breakdown lines,
    discount deduction, and two-tier due dates.
    """
    session_id = test_setup["session_id"]
    count = fee_service.generate_monthly_invoices(
        session_id=session_id,
        month_year="2025-10",
        issue_date="2025-10-01",
        due_date="2025-10-10",
        valid_until="2025-10-20",
        late_fee_surcharge=Decimal("250.00")
    )
    assert count == 2

    # Idempotency check: Generating again for same cycle creates 0 new invoices
    second_run = fee_service.generate_monthly_invoices(
        session_id=session_id,
        month_year="2025-10",
        issue_date="2025-10-01",
        due_date="2025-10-10",
        valid_until="2025-10-20"
    )
    assert second_run == 0

    # Inspect Student 1 invoice (Full Fee: Rs. 5,000)
    enr_id1 = test_setup["student1"]["enrollment_id"]
    cursor = fee_service.conn.cursor()
    cursor.execute("SELECT id FROM fee_invoices WHERE enrollment_id = ? AND month_year = '2025-10';", (enr_id1,))
    inv1_id = cursor.fetchone()[0]

    inv1 = fee_service.get_invoice_details(inv1_id)
    assert inv1["net_due"] == "5000.00"
    assert inv1["discount_amount"] == "0.00"
    assert inv1["status"] == "Unpaid"
    assert len(inv1["items"]) == 1
    assert inv1["items"][0]["fee_head_name"] == "Tuition Fee"
    assert inv1["items"][0]["amount"] == "5000.00"

    # Inspect Student 2 invoice (Discounted Fee: Rs. 5,000 - 1,000 = Rs. 4,000)
    enr_id2 = test_setup["student2"]["enrollment_id"]
    cursor.execute("SELECT id FROM fee_invoices WHERE enrollment_id = ? AND month_year = '2025-10';", (enr_id2,))
    inv2_id = cursor.fetchone()[0]

    inv2 = fee_service.get_invoice_details(inv2_id)
    assert inv2["total_payable"] == "5000.00"
    assert inv2["discount_amount"] == "1000.00"
    assert inv2["net_due"] == "4000.00"
    assert inv2["status"] == "Unpaid"


# --- Cashier Ledger, Receipts, & Status State Machine ---

def test_cashier_payment_recording_and_status_transitions(test_setup, fee_service):
    """
    Verifies status transitions (Unpaid -> Partially Paid -> Paid -> Overpaid)
    and receipt sequential numbering (REC-YYYY-XXXXX).
    """
    fee_service.generate_monthly_invoices(
        session_id=test_setup["session_id"],
        month_year="2025-11",
        issue_date="2025-11-01",
        due_date="2025-11-10",
        valid_until="2025-11-20"
    )

    enr_id = test_setup["student1"]["enrollment_id"]
    cursor = fee_service.conn.cursor()
    cursor.execute("SELECT id FROM fee_invoices WHERE enrollment_id = ? AND month_year = '2025-11';", (enr_id,))
    inv_id = cursor.fetchone()[0]

    # 1. Initial State: Unpaid
    state0 = fee_service.calculate_invoice_balance(inv_id)
    assert state0["status"] == "Unpaid"
    assert state0["current_balance"] == Decimal("5000.00")
    assert state0["total_paid"] == Decimal("0.00")

    # 2. First Payment: Partial (Rs. 2,000)
    rec1 = fee_service.record_payment(
        invoice_id=inv_id,
        amount=Decimal("2000.00"),
        payment_method="Cash",
        note="First installment"
    )
    assert rec1.startswith("REC-")
    assert rec1.endswith("-00001")

    state1 = fee_service.calculate_invoice_balance(inv_id)
    assert state1["status"] == "Partially Paid"
    assert state1["total_paid"] == Decimal("2000.00")
    assert state1["current_balance"] == Decimal("3000.00")

    # 3. Second Payment: Completing the Balance (Rs. 3,000)
    rec2 = fee_service.record_payment(
        invoice_id=inv_id,
        amount=Decimal("3000.00"),
        payment_method="BankTransfer"
    )
    assert rec2.endswith("-00002")

    state2 = fee_service.calculate_invoice_balance(inv_id)
    assert state2["status"] == "Paid"
    assert state2["total_paid"] == Decimal("5000.00")
    assert state2["current_balance"] == Decimal("0.00")

    # 4. Third Payment: Surplus / Advance (Rs. 500)
    fee_service.record_payment(inv_id, amount=Decimal("500.00"))
    state3 = fee_service.calculate_invoice_balance(inv_id)
    assert state3["status"] == "Overpaid"
    assert state3["current_balance"] == Decimal("-500.00")


def test_payment_reversal_restores_invoice_balance(test_setup, fee_service):
    """Verifies reversing a payment ledger record restores the unpaid balance."""
    fee_service.generate_monthly_invoices(
        session_id=test_setup["session_id"],
        month_year="2025-12",
        issue_date="2025-12-01",
        due_date="2025-12-10",
        valid_until="2025-12-20"
    )
    enr_id = test_setup["student1"]["enrollment_id"]
    cursor = fee_service.conn.cursor()
    cursor.execute("SELECT id FROM fee_invoices WHERE enrollment_id = ? AND month_year = '2025-12';", (enr_id,))
    inv_id = cursor.fetchone()[0]

    # Record full payment
    fee_service.record_payment(inv_id, Decimal("5000.00"))
    assert fee_service.calculate_invoice_balance(inv_id)["status"] == "Paid"

    # Get payment record ID
    cursor.execute("SELECT id FROM payments WHERE invoice_id = ?;", (inv_id,))
    payment_id = cursor.fetchone()[0]

    # Reverse payment
    fee_service.reverse_payment(payment_id, reason="Cheque bounced by bank")

    # Balance must return to Unpaid
    state = fee_service.calculate_invoice_balance(inv_id)
    assert state["status"] == "Unpaid"
    assert state["current_balance"] == Decimal("5000.00")
    assert state["total_paid"] == Decimal("0.00")


# --- Relational Integrity & ON DELETE RESTRICT Enforcement ---

def test_on_delete_restrict_prevents_invoice_deletion_with_payments(test_setup, fee_service):
    """
    Verifies that SQLite enforces ON DELETE RESTRICT: an invoice with payment
    receipts cannot be deleted, raising sqlite3.IntegrityError.
    """
    fee_service.generate_monthly_invoices(
        session_id=test_setup["session_id"],
        month_year="2026-01",
        issue_date="2026-01-01",
        due_date="2026-01-10",
        valid_until="2026-01-20"
    )
    enr_id = test_setup["student1"]["enrollment_id"]
    cursor = fee_service.conn.cursor()
    cursor.execute("SELECT id FROM fee_invoices WHERE enrollment_id = ? AND month_year = '2026-01';", (enr_id,))
    inv_id = cursor.fetchone()[0]

    # Record a payment
    fee_service.record_payment(inv_id, Decimal("1000.00"))

    # Attempting to delete the invoice must raise IntegrityError
    with pytest.raises(sqlite3.IntegrityError):
        fee_service.delete_invoice(inv_id)


def test_invoice_without_payments_can_be_deleted(test_setup, fee_service):
    """Verifies that an unpaid invoice without payments can be cleanly deleted."""
    fee_service.generate_monthly_invoices(
        session_id=test_setup["session_id"],
        month_year="2026-02",
        issue_date="2026-02-01",
        due_date="2026-02-10",
        valid_until="2026-02-20"
    )
    enr_id = test_setup["student2"]["enrollment_id"]
    cursor = fee_service.conn.cursor()
    cursor.execute("SELECT id FROM fee_invoices WHERE enrollment_id = ? AND month_year = '2026-02';", (enr_id,))
    inv_id = cursor.fetchone()[0]

    fee_service.delete_invoice(inv_id)

    # Verify deleted
    cursor.execute("SELECT id FROM fee_invoices WHERE id = ?;", (inv_id,))
    assert cursor.fetchone() is None


# --- Defaulters Reporting Tests ---

def test_get_defaulters_list(test_setup, fee_service):
    """Verifies querying students with outstanding balances."""
    fee_service.generate_monthly_invoices(
        session_id=test_setup["session_id"],
        month_year="2026-03",
        issue_date="2026-03-01",
        due_date="2026-03-10",
        valid_until="2026-03-20"
    )

    # Both students are initially defaulters
    defaulters = fee_service.get_defaulters_list(test_setup["session_id"], "2026-03")
    assert len(defaulters) == 2

    # Pay off student 1 completely
    inv1_id = defaulters[0]["id"]
    fee_service.record_payment(inv1_id, Decimal("5000.00"))

    # Now only 1 student remains in defaulters
    remaining = fee_service.get_defaulters_list(test_setup["session_id"], "2026-03")
    assert len(remaining) == 1
    assert remaining[0]["first_name"] == "Ayesha"


# --- ReportLab 3-Panel A4 Voucher PDF Tests ---

def test_generate_3_panel_a4_fee_voucher_pdf(test_setup, fee_service):
    """Verifies generating a valid 3-panel A4 PDF voucher buffer with ReportLab."""
    fee_service.generate_monthly_invoices(
        session_id=test_setup["session_id"],
        month_year="2025-10",
        issue_date="2025-10-01",
        due_date="2025-10-10",
        valid_until="2025-10-20"
    )
    enr_id1 = test_setup["student1"]["enrollment_id"]
    cursor = fee_service.conn.cursor()
    cursor.execute("SELECT id FROM fee_invoices WHERE enrollment_id = ? AND month_year = '2025-10';", (enr_id1,))
    inv_id = cursor.fetchone()[0]

    invoice_data = fee_service.get_invoice_details(inv_id)

    pdf_buffer = io.BytesIO()
    generate_fee_voucher_pdf(
        invoice_data=invoice_data,
        output=pdf_buffer,
        institution_name="CLASSFELLOW GRAMMAR SCHOOL"
    )

    pdf_bytes = pdf_buffer.getvalue()
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF-")  # Valid PDF header signature
