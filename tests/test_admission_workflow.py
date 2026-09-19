"""
ClassFellow - Comprehensive Student Admission & Workflow Regression Tests
========================================================================
Validates Phase 9 Gate 3 specifications:
  1. Cold-boot database initialization and default seeding (Session, Class 1, Fee Heads).
  2. Extended Punjab admission schema persistence (B-Form, CNIC, raw Urdu UTF-8, SLC).
  3. Sibling concession formula (0% for 1st, 25% for 2nd, 50% for 3rd+ child).
  4. Prior arrears roll-forward aggregation across billing cycles.
  5. End-to-end walk-in admission atomic transaction and 3-panel A4 voucher generation.
  6. Inline class creation and dynamic availability.
"""

import os
from decimal import Decimal
import pytest

from database import init_database, get_schema_version
from models import StudentDTO
from services.student_service import StudentService
from services.fee_service import FeeService


@pytest.fixture
def cold_db_path(tmp_path):
    """Provides a path to a non-existent database file for cold-start testing."""
    return str(tmp_path / "cold_admission_boot.db")


@pytest.fixture
def migrated_db(tmp_path):
    """Provides an initialized, fully migrated database connection configured with initial school."""
    db_path = str(tmp_path / "migrated_admission.db")
    conn = init_database(db_path)
    from services.school_service import setup_initial_school
    setup_initial_school(
        conn,
        profile_data={"school_name": "ClassFellow Model School", "contact_number": "03001234567"},
        session_data={"name": "2026-2027 Academic Session", "start_date": "2026-04-01", "end_date": "2027-03-31"},
        classes_data=[{"name": "Class 1", "section_or_batch": "Section A", "monthly_tuition_fee": Decimal("3500.00")}]
    )
    yield conn
    conn.close()


# =============================================================================
# 1. Cold-Boot Database Initialization & Seeding Test
# =============================================================================

def test_cold_boot_seeding_and_schema_v5(cold_db_path):
    """
    Verifies that cold-boot initialization on a brand-new 0-byte file builds
    the full v5 schema, keeps production DB clean of mock classes, and seeds fee heads.
    """
    assert not os.path.exists(cold_db_path)

    from services.school_service import is_school_profile_configured, setup_initial_school

    conn = init_database(cold_db_path)
    try:
        assert os.path.exists(cold_db_path)
        assert get_schema_version(conn) == 5

        cur = conn.cursor()

        # 1. Clean zero-state database: no synthetic mock classes or sessions
        assert is_school_profile_configured(conn) is False
        cur.execute("SELECT COUNT(*) FROM class_groups;")
        assert cur.fetchone()[0] == 0

        # 2. Standard regional fee heads catalog seeded
        cur.execute("SELECT name, is_recurring FROM fee_heads;")
        heads = {row[0]: row[1] for row in cur.fetchall()}

        assert "Tuition Fee" in heads and heads["Tuition Fee"] == 1
        assert "Admission Fee" in heads and heads["Admission Fee"] == 0
        assert "Registration / Prospectus" in heads and heads["Registration / Prospectus"] == 0
        assert "Security Deposit" in heads and heads["Security Deposit"] == 0
        assert "Previous Arrears" in heads and heads["Previous Arrears"] == 1
        assert "Generator & Fuel Surcharge" in heads
        assert "Stationery & Exam Paper Fund" in heads

        # 3. Setup via Mother Form
        p_id, s_id = setup_initial_school(
            conn,
            profile_data={"school_name": "ClassFellow Grammar School", "contact_number": "03001234567"},
            session_data={"name": "2026-2027 Academic Session", "start_date": "2026-04-01", "end_date": "2027-03-31"},
            classes_data=[{"name": "Class 1", "section_or_batch": "Section A", "monthly_tuition_fee": Decimal("3500.00")}]
        )
        assert is_school_profile_configured(conn) is True

        cur.execute("SELECT COUNT(*) FROM class_groups;")
        assert cur.fetchone()[0] == 1
    finally:
        conn.close()


# =============================================================================
# 2. Extended Punjab Student Schema & Raw Urdu UTF-8 Persistence Test
# =============================================================================

def test_extended_student_schema_persistence(migrated_db):
    """
    Verifies that all Punjab specification fields (B-Form, CNIC, raw Urdu UTF-8,
    previous SLC, WhatsApp) persist losslessly and indexes are created.
    """
    student_svc = StudentService(migrated_db)

    cur = migrated_db.cursor()
    cur.execute("SELECT id, session_id FROM class_groups LIMIT 1;")
    cg_row = cur.fetchone()
    class_id, session_id = cg_row[0], cg_row[1]

    dto = StudentDTO(
        first_name="محمد حارث",
        last_name="خان",
        urdu_name="محمد حارث خان",
        gender="Male",
        date_of_birth="2014-08-22",
        b_form_number="35201-9876543-1",
        guardian_name="طارق محمود",
        guardian_urdu_name="طارق محمود خان",
        guardian_relation="Father",
        guardian_phone="0300-1122334",
        guardian_whatsapp="+923001122334",
        guardian_cnic="35201-1234567-3",
        guardian_email="haris.guardian@example.com",
        residential_address="House 45, Street 9, Sector G, Lahore",
        previous_school_slc="SLC-2026-5542 (Crescent Model School)",
        emergency_contact="03009988776"
    )

    student_id, enrollment_id = student_svc.register_student(
        student_data=dto,
        class_group_id=class_id,
        session_id=session_id
    )

    student = student_svc.get_student_by_id(student_id)
    assert student is not None
    assert student["first_name"] == "محمد حارث"
    assert student["last_name"] == "خان"
    assert student["urdu_name"] == "محمد حارث خان"
    assert student["b_form_number"] == "35201-9876543-1"
    assert student["guardian_name"] == "طارق محمود"
    assert student["guardian_urdu_name"] == "طارق محمود خان"
    assert student["guardian_relation"] == "Father"
    assert student["guardian_phone"] == "03001122334"
    assert student["guardian_whatsapp"] == "03001122334"
    assert student["guardian_cnic"] == "35201-1234567-3"
    assert student["guardian_email"] == "haris.guardian@example.com"
    assert student["residential_address"] == "House 45, Street 9, Sector G, Lahore"
    assert student["previous_school_slc"] == "SLC-2026-5542 (Crescent Model School)"

    # Verify indices
    cur.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='students';")
    indices = {row[0] for row in cur.fetchall()}
    assert "idx_students_admission_no" in indices
    assert "idx_students_names" in indices
    assert "idx_students_guardian_phone" in indices


# =============================================================================
# 3. Sibling Concession Discount Calculations Test
# =============================================================================

def test_sibling_discount_calculations(migrated_db):
    """
    Tests the Punjab sibling discount rule across sequential enrollments:
      - 1st child: 0% discount
      - 2nd child: 25% discount
      - 3rd+ child: 50% discount
    """
    student_svc = StudentService(migrated_db)
    fee_svc = FeeService(migrated_db)

    cur = migrated_db.cursor()
    cur.execute("SELECT id, session_id FROM class_groups LIMIT 1;")
    cg_row = cur.fetchone()
    class_id, session_id = cg_row[0], cg_row[1]

    guardian_phone = "0321-4455667"
    base_tuition = Decimal("4000.00")

    # Step A: Pre-admission check for 1st child -> 0%
    disc_1 = fee_svc.calculate_sibling_discount(guardian_phone, base_tuition)
    assert disc_1 == Decimal("0.00")

    # Admit 1st child
    c1_dto = StudentDTO(
        first_name="Ahmed",
        last_name="Raza",
        guardian_name="Raza Ali",
        guardian_phone=guardian_phone,
        gender="Male"
    )
    s1_id, e1_id = student_svc.register_student(
        student_data=c1_dto,
        class_group_id=class_id,
        session_id=session_id,
        custom_discount_amount=disc_1,
        enrollment_date="2026-04-01"
    )

    # Step B: Pre-admission check for 2nd child -> 25% of 4000 = 1000.00
    disc_2 = fee_svc.calculate_sibling_discount(guardian_phone, base_tuition)
    assert disc_2 == Decimal("1000.00")

    # Admit 2nd child
    c2_dto = StudentDTO(
        first_name="Bilal",
        last_name="Raza",
        guardian_name="Raza Ali",
        guardian_phone=guardian_phone,
        gender="Male"
    )
    s2_id, e2_id = student_svc.register_student(
        student_data=c2_dto,
        class_group_id=class_id,
        session_id=session_id,
        custom_discount_amount=disc_2,
        enrollment_date="2026-04-05"
    )

    # Step C: Pre-admission check for 3rd child -> 50% of 4000 = 2000.00
    disc_3 = fee_svc.calculate_sibling_discount(guardian_phone, base_tuition)
    assert disc_3 == Decimal("2000.00")

    # Admit 3rd child
    c3_dto = StudentDTO(
        first_name="Zainab",
        last_name="Raza",
        guardian_name="Raza Ali",
        guardian_phone=guardian_phone,
        gender="Female"
    )
    s3_id, e3_id = student_svc.register_student(
        student_data=c3_dto,
        class_group_id=class_id,
        session_id=session_id,
        custom_discount_amount=disc_3,
        enrollment_date="2026-04-10"
    )

    # Step D: Pre-admission check for 4th child -> 50%
    disc_4 = fee_svc.calculate_sibling_discount(guardian_phone, base_tuition)
    assert disc_4 == Decimal("2000.00")

    # Step E: Post-admission evaluation for existing enrolled students
    assert fee_svc.calculate_sibling_discount(guardian_phone, base_tuition, student_id=s1_id) == Decimal("0.00")
    assert fee_svc.calculate_sibling_discount(guardian_phone, base_tuition, student_id=s2_id) == Decimal("1000.00")
    assert fee_svc.calculate_sibling_discount(guardian_phone, base_tuition, student_id=s3_id) == Decimal("2000.00")


# =============================================================================
# 4. Prior Arrears Roll-Forward Calculation Test
# =============================================================================

def test_prior_arrears_calculation(migrated_db):
    """
    Tests rolling-forward unpaid balances from earlier billing cycles.
    """
    student_svc = StudentService(migrated_db)
    fee_svc = FeeService(migrated_db)

    cur = migrated_db.cursor()
    cur.execute("SELECT id, session_id FROM class_groups LIMIT 1;")
    cg_row = cur.fetchone()
    class_id, session_id = cg_row[0], cg_row[1]

    dto = StudentDTO(
        first_name="Usman",
        last_name="Tariq",
        guardian_name="Tariq Mehmood",
        guardian_phone="0333-5556677",
        gender="Male"
    )
    student_id, enrollment_id = student_svc.register_student(
        student_data=dto,
        class_group_id=class_id,
        session_id=session_id
    )

    # Invoice 1: 2026-01 (net_due = 3500.00, paid = 2000.00 -> balance = 1500.00)
    cur.execute(
        """
        INSERT INTO fee_invoices (
            enrollment_id, session_id, month_year, issue_date, due_date, valid_until,
            total_payable, discount_amount, net_due
        ) VALUES (?, ?, '2026-01', '2026-01-01', '2026-01-10', '2026-01-20', '3500.00', '0.00', '3500.00');
        """,
        (enrollment_id, session_id)
    )
    inv1_id = cur.lastrowid
    fee_svc.record_payment(invoice_id=inv1_id, amount=Decimal("2000.00"), payment_method="Cash")

    # Invoice 2: 2026-02 (net_due = 3500.00, paid = 0.00 -> balance = 3500.00)
    cur.execute(
        """
        INSERT INTO fee_invoices (
            enrollment_id, session_id, month_year, issue_date, due_date, valid_until,
            total_payable, discount_amount, net_due
        ) VALUES (?, ?, '2026-02', '2026-02-01', '2026-02-10', '2026-02-20', '3500.00', '0.00', '3500.00');
        """,
        (enrollment_id, session_id)
    )

    # Invoice 3: 2026-03 (Current cycle under evaluation, net_due = 3500.00)
    cur.execute(
        """
        INSERT INTO fee_invoices (
            enrollment_id, session_id, month_year, issue_date, due_date, valid_until,
            total_payable, discount_amount, net_due
        ) VALUES (?, ?, '2026-03', '2026-03-01', '2026-03-10', '2026-03-20', '3500.00', '0.00', '3500.00');
        """,
        (enrollment_id, session_id)
    )

    # Arrears prior to 2026-03 should sum 2026-01 (1500) + 2026-02 (3500) = 5000.00
    arrears_for_march = fee_svc.get_prior_arrears(enrollment_id=enrollment_id, current_month_year="2026-03")
    assert arrears_for_march == Decimal("5000.00")

    # Arrears prior to 2026-02 should be 2026-01 balance = 1500.00
    arrears_for_feb = fee_svc.get_prior_arrears(enrollment_id=enrollment_id, current_month_year="2026-02")
    assert arrears_for_feb == Decimal("1500.00")

    # Arrears prior to 2026-01 should be 0.00
    arrears_for_jan = fee_svc.get_prior_arrears(enrollment_id=enrollment_id, current_month_year="2026-01")
    assert arrears_for_jan == Decimal("0.00")


# =============================================================================
# 5. Walk-in Admission Atomic Transaction & 3-Panel Fee Voucher Test
# =============================================================================

def test_walkin_admission_atomic_transaction_and_voucher(migrated_db, tmp_path):
    """
    Validates end-to-end execution of process_walkin_admission:
      - Student & active enrollment creation
      - Itemized invoice creation (Tuition, Admission, Prospectus, Security minus Concession)
      - Non-empty 3-panel A4 fee voucher PDF output on disk
    """
    fee_svc = FeeService(migrated_db)

    cur = migrated_db.cursor()
    cur.execute("SELECT id, session_id FROM class_groups LIMIT 1;")
    cg_row = cur.fetchone()
    class_id, session_id = cg_row[0], cg_row[1]

    student_dto = StudentDTO(
        admission_number="CF-2026-9901",
        first_name="Hassan",
        last_name="Nawaz",
        urdu_name="حسن نواز",
        gender="Male",
        date_of_birth="2013-11-14",
        b_form_number="35201-1122334-5",
        guardian_name="Nawaz Sharif",
        guardian_urdu_name="نواز شریف",
        guardian_relation="Father",
        guardian_phone="03009988112",
        guardian_cnic="35201-9988776-1",
        residential_address="Model Town, Lahore",
        previous_school_slc="SLC-7711 (Lahore Grammar School)"
    )

    voucher_dir = str(tmp_path / "vouchers")

    pdf_path = fee_svc.process_walkin_admission(
        student_data=student_dto,
        class_group_id=class_id,
        session_id=session_id,
        concession_discount=Decimal("500.00"),
        admission_fee=Decimal("2500.00"),
        prospectus_fee=Decimal("1000.00"),
        security_deposit=Decimal("1500.00"),
        prior_arrears=Decimal("0.00"),
        voucher_output_dir=voucher_dir,
        generate_voucher=True
    )

    # 1. Verify PDF was generated
    assert pdf_path is not None
    assert os.path.exists(pdf_path)
    assert os.path.getsize(pdf_path) > 1000  # Non-empty valid PDF

    # 2. Verify database records
    cur.execute("SELECT id FROM students WHERE admission_number = 'CF-2026-9901';")
    s_row = cur.fetchone()
    assert s_row is not None
    st_id = s_row[0]

    cur.execute("SELECT id, custom_discount_amount FROM enrollments WHERE student_id = ?;", (st_id,))
    enr_row = cur.fetchone()
    assert enr_row is not None
    enr_id = enr_row[0]
    assert Decimal(str(enr_row[1])) == Decimal("500.00")

    # 3. Verify Invoice and Items
    cur.execute("SELECT id, total_payable, discount_amount, net_due FROM fee_invoices WHERE enrollment_id = ?;", (enr_id,))
    inv_row = cur.fetchone()
    assert inv_row is not None
    inv_id = inv_row[0]

    # Total: Base Tuition (3500) + Admission (2500) + Prospectus (1000) + Security (1500) = 8500
    # Discount: 500
    # Net: 8000
    assert Decimal(str(inv_row[1])) == Decimal("8500.00")
    assert Decimal(str(inv_row[2])) == Decimal("500.00")
    assert Decimal(str(inv_row[3])) == Decimal("8000.00")

    cur.execute(
        """
        SELECT fh.name, fii.amount
        FROM fee_invoice_items fii
        JOIN fee_heads fh ON fii.fee_head_id = fh.id
        WHERE fii.invoice_id = ?
        ORDER BY fii.id ASC;
        """,
        (inv_id,)
    )
    items = {r[0]: Decimal(str(r[1])) for r in cur.fetchall()}
    assert items["Tuition Fee"] == Decimal("3500.00")
    assert items["Admission Fee"] == Decimal("2500.00")
    assert items["Registration / Prospectus"] == Decimal("1000.00")
    assert items["Security Deposit"] == Decimal("1500.00")


# =============================================================================
# 6. Inline Class Creation Workflow Test
# =============================================================================

def test_inline_class_creation_workflow(migrated_db):
    """
    Tests registering a class group on the fly and verifying it is selectable.
    """
    student_svc = StudentService(migrated_db)

    cur = migrated_db.cursor()
    cur.execute("SELECT id FROM academic_sessions WHERE is_active = 1 LIMIT 1;")
    session_id = cur.fetchone()[0]

    # Create new class
    new_class_id = student_svc.create_class_group(
        session_id=session_id,
        name="Class 5",
        section_or_batch="Blue",
        group_type="SchoolClass",
        monthly_tuition_fee=Decimal("3200.00")
    )
    assert new_class_id > 0

    # Verify retrievable
    classes = student_svc.get_class_groups(session_id=session_id)
    class_names = [f"{c['name']} ({c['section_or_batch']})" for c in classes]
    assert "Class 5 (Blue)" in class_names


# =============================================================================
# 7. Route Guard & Dynamic Surcharges Verification (REF-002)
# =============================================================================

def test_route_guard_and_mother_form_setup(cold_db_path):
    """
    Verifies that is_school_profile_configured safely guards unconfigured databases
    and transitions to True after complete Mother Form setup.
    """
    from services.school_service import (
        is_school_profile_configured,
        setup_initial_school,
        get_active_fee_heads
    )

    conn = init_database(cold_db_path)
    try:
        # Route guard must block on fresh database
        assert is_school_profile_configured(conn) is False

        # Execute Mother Form setup
        p_id, s_id = setup_initial_school(
            conn,
            profile_data={
                "school_name": "Punjab Stars Grammar School",
                "school_urdu_name": "پنجاب اسٹارز گرائمر اسکول",
                "campus_name": "City Campus",
                "contact_number": "03009988776",
                "email": "info@punjabstars.edu.pk",
                "city": "Faisalabad"
            },
            session_data={"name": "2026-2027 Academic Session", "start_date": "2026-04-01", "end_date": "2027-03-31"},
            classes_data=[
                {"name": "Class 1", "section_or_batch": "Rose", "monthly_tuition_fee": Decimal("3000.00")},
                {"name": "Class 2", "section_or_batch": "Tulip", "monthly_tuition_fee": Decimal("3200.00")}
            ],
            fee_heads_data=[
                {"id": None, "name": "Generator & Fuel Surcharge", "urdu_name": "جنریٹر چارجز", "is_recurring": 1, "default_amount": Decimal("600.00"), "is_active": 1},
                {"id": None, "name": "Stationery & Exam Paper Fund", "urdu_name": "امتحان فنڈ", "is_recurring": 0, "default_amount": Decimal("1200.00"), "is_active": 1}
            ]
        )
        assert p_id is not None
        assert s_id is not None

        # Route guard must now approve
        assert is_school_profile_configured(conn) is True

        # Verify active fee heads retrieved
        active_heads = get_active_fee_heads(conn)
        active_names = [h["name"] for h in active_heads]
        assert "Generator & Fuel Surcharge" in active_names
        assert "Stationery & Exam Paper Fund" in active_names
    finally:
        conn.close()


def test_walkin_admission_with_dynamic_surcharges(migrated_db, tmp_path):
    """
    Tests end-to-end walk-in admission with dynamic operational surcharges
    (Generator Fuel, Paper Fund) recorded on the invoice and branded with school title.
    """
    fee_svc = FeeService(migrated_db)
    cur = migrated_db.cursor()

    cur.execute("SELECT id, session_id FROM class_groups LIMIT 1;")
    cg_row = cur.fetchone()
    class_id, session_id = cg_row[0], cg_row[1]

    student_dto = StudentDTO(
        admission_number="CF-2026-8801",
        first_name="Bilal",
        last_name="Ahmed",
        urdu_name="بلال احمد",
        gender="Male",
        guardian_name="Ahmed Raza",
        guardian_phone="03007654321",
        guardian_email="ahmed.raza@example.com",
        residential_address="Gulberg, Lahore"
    )

    additional_surcharges = [
        ("Generator & Fuel Surcharge", Decimal("500.00"), "جنریٹر ایندھن فنڈ", 1),
        ("Stationery & Exam Paper Fund", Decimal("1000.00"), "کاغذ فنڈ", 0),
    ]

    voucher_dir = str(tmp_path / "dynamic_vouchers")
    pdf_path = fee_svc.process_walkin_admission(
        student_data=student_dto,
        class_group_id=class_id,
        session_id=session_id,
        concession_discount=Decimal("200.00"),
        admission_fee=Decimal("2000.00"),
        prospectus_fee=Decimal("500.00"),
        security_deposit=Decimal("1000.00"),
        additional_fee_items=additional_surcharges,
        voucher_output_dir=voucher_dir,
        generate_voucher=True
    )

    assert os.path.exists(pdf_path)
    assert os.path.getsize(pdf_path) > 1000

    # Verify student record has guardian_email
    cur.execute("SELECT guardian_email FROM students WHERE admission_number = 'CF-2026-8801';")
    assert cur.fetchone()[0] == "ahmed.raza@example.com"

    # Verify invoice total:
    # Tuition (3500) + Admission (2000) + Prospectus (500) + Security (1000) + Generator (500) + Paper (1000) = 8500
    # Discount: 200 -> Net Due: 8300
    cur.execute(
        """
        SELECT fi.total_payable, fi.discount_amount, fi.net_due
        FROM fee_invoices fi
        JOIN enrollments e ON fi.enrollment_id = e.id
        JOIN students s ON e.student_id = s.id
        WHERE s.admission_number = 'CF-2026-8801';
        """
    )
    inv_row = cur.fetchone()
    assert inv_row is not None
    assert Decimal(str(inv_row[0])) == Decimal("8500.00")
    assert Decimal(str(inv_row[1])) == Decimal("200.00")
    assert Decimal(str(inv_row[2])) == Decimal("8300.00")

    # Verify dynamic invoice items recorded in SQLite
    cur.execute(
        """
        SELECT fh.name, fii.amount
        FROM fee_invoice_items fii
        JOIN fee_heads fh ON fii.fee_head_id = fh.id
        JOIN fee_invoices fi ON fii.invoice_id = fi.id
        JOIN enrollments e ON fi.enrollment_id = e.id
        JOIN students s ON e.student_id = s.id
        WHERE s.admission_number = 'CF-2026-8801';
        """
    )
    items_map = {r[0]: Decimal(str(r[1])) for r in cur.fetchall()}
    assert items_map["Tuition Fee"] == Decimal("3500.00")
    assert items_map["Admission Fee"] == Decimal("2000.00")
    assert items_map["Registration / Prospectus"] == Decimal("500.00")
    assert items_map["Security Deposit"] == Decimal("1000.00")
    assert items_map["Generator & Fuel Surcharge"] == Decimal("500.00")
    assert items_map["Stationery & Exam Paper Fund"] == Decimal("1000.00")
