"""
ClassFellow - Realistic Punjab School Demo Data Seeder (scripts/seed_demo_data.py)
==================================================================================
CLI utility to populate a fresh or existing ClassFellow SQLite database with a
realistic Punjab educational institution pilot dataset:
  - 1 Academic Session (2026-2027)
  - 3 Class Groups (Class 9 - Green, Class 10 - Gold, Tuition Batch - 9th Physics)
  - 5 Core Subjects (English, Urdu, Mathematics, Physics, Chemistry)
  - 3 Dynamic Fee Heads (Tuition, Exam, Lab)
  - 15 Enrolled Students with bilingual English/Urdu profiles & normalized phones
  - 15 Fee Invoices for billing cycle 2026-04 (5 Paid, 5 Partially Paid, 5 Unpaid Defaulters)
  - 5 Daily Class Attendance Roll Calls (with Present, Absent, and Late exceptions)
  - 1 Terminal Examination with configured subject limits, marks entries, and BISE ranks
"""

import os
import sys
import argparse
import sqlite3
from decimal import Decimal

# Ensure project root is in sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from database import init_database, get_connection
from models import StudentDTO
from services.student_service import StudentService
from services.fee_service import FeeService
from services.attendance_service import AttendanceService
from services.exam_service import ExamService


# =============================================================================
# Demo Pilot Dataset Definition
# =============================================================================

DEMO_STUDENTS = [
    # --- Class 9 - Green (SchoolClass) ---
    {
        "first_name": "Muhammad Ali",
        "last_name": "Khan",
        "urdu_name": "محمد علی خان",
        "gender": "Male",
        "guardian_name": "Tariq Khan",
        "guardian_urdu_name": "طارق خان",
        "guardian_relation": "Father",
        "guardian_phone": "03001234567",
        "guardian_whatsapp": "03001234567",
        "class_index": 0,
        "roll_number": "101",
        "discount": Decimal("0.00"),
        "marks": [Decimal("92.00"), Decimal("88.00"), Decimal("95.00")],  # Eng, Math, Phy
    },
    {
        "first_name": "Fatima",
        "last_name": "Zahra",
        "urdu_name": "فاطمہ زہرا",
        "gender": "Female",
        "guardian_name": "Muhammad Aslam",
        "guardian_urdu_name": "محمد اسلم",
        "guardian_relation": "Father",
        "guardian_phone": "03017654321",
        "guardian_whatsapp": "03017654321",
        "class_index": 0,
        "roll_number": "102",
        "discount": Decimal("500.00"),
        "marks": [Decimal("85.00"), Decimal("91.00"), Decimal("89.00")],
    },
    {
        "first_name": "Usman",
        "last_name": "Tariq",
        "urdu_name": "عثمان طارق",
        "gender": "Male",
        "guardian_name": "Tariq Mehmood",
        "guardian_urdu_name": "طارق محمود",
        "guardian_relation": "Father",
        "guardian_phone": "03219876543",
        "guardian_whatsapp": "03219876543",
        "class_index": 0,
        "roll_number": "103",
        "discount": Decimal("0.00"),
        "marks": [Decimal("74.00"), Decimal("68.00"), Decimal("72.00")],
    },
    {
        "first_name": "Ayesha",
        "last_name": "Siddiqa",
        "urdu_name": "عائشہ صدیقہ",
        "gender": "Female",
        "guardian_name": "Abdul Rashid",
        "guardian_urdu_name": "عبدالرشید",
        "guardian_relation": "Father",
        "guardian_phone": "03335551234",
        "guardian_whatsapp": "03335551234",
        "class_index": 0,
        "roll_number": "104",
        "discount": Decimal("0.00"),
        "marks": [Decimal("78.00"), Decimal("82.00"), Decimal("80.00")],
    },
    {
        "first_name": "Bilal",
        "last_name": "Ahmed",
        "urdu_name": "بلال احمد",
        "gender": "Male",
        "guardian_name": "Ahmed Hassan",
        "guardian_urdu_name": "احمد حسن",
        "guardian_relation": "Father",
        "guardian_phone": "03456667890",
        "guardian_whatsapp": "03456667890",
        "class_index": 0,
        "roll_number": "105",
        "discount": Decimal("1000.00"),
        "marks": [Decimal("62.00"), Decimal("58.00"), Decimal("65.00")],
    },

    # --- Class 10 - Gold (SchoolClass) ---
    {
        "first_name": "Zainab",
        "last_name": "Bibi",
        "urdu_name": "زینب بی بی",
        "gender": "Female",
        "guardian_name": "Ghulam Nabi",
        "guardian_urdu_name": "غلام نبی",
        "guardian_relation": "Father",
        "guardian_phone": "03024445566",
        "guardian_whatsapp": "03024445566",
        "class_index": 1,
        "roll_number": "201",
        "discount": Decimal("0.00"),
        "marks": [Decimal("94.00"), Decimal("96.00"), Decimal("98.00")],
    },
    {
        "first_name": "Hamza",
        "last_name": "Farooq",
        "urdu_name": "حمزہ فاروق",
        "gender": "Male",
        "guardian_name": "Farooq Azam",
        "guardian_urdu_name": "فاروق اعظم",
        "guardian_relation": "Father",
        "guardian_phone": "03123332211",
        "guardian_whatsapp": "03123332211",
        "class_index": 1,
        "roll_number": "202",
        "discount": Decimal("0.00"),
        "marks": [Decimal("71.00"), Decimal("65.00"), Decimal("70.00")],
    },
    {
        "first_name": "Maryam",
        "last_name": "Noor",
        "urdu_name": "مریم نور",
        "gender": "Female",
        "guardian_name": "Noor Muhammad",
        "guardian_urdu_name": "نور محمد",
        "guardian_relation": "Father",
        "guardian_phone": "03228889900",
        "guardian_whatsapp": "03228889900",
        "class_index": 1,
        "roll_number": "203",
        "discount": Decimal("500.00"),
        "marks": [Decimal("88.00"), Decimal("85.00"), Decimal("90.00")],
    },
    {
        "first_name": "Abdullah",
        "last_name": "Rauf",
        "urdu_name": "عبداللہ رؤف",
        "gender": "Male",
        "guardian_name": "Abdul Rauf",
        "guardian_urdu_name": "عبدالرؤف",
        "guardian_relation": "Father",
        "guardian_phone": "03347778899",
        "guardian_whatsapp": "03347778899",
        "class_index": 1,
        "roll_number": "204",
        "discount": Decimal("0.00"),
        "marks": [Decimal("55.00"), Decimal("48.00"), Decimal("52.00")],
    },
    {
        "first_name": "Khadija",
        "last_name": "Tul Kubra",
        "urdu_name": "خدیجہ الکبریٰ",
        "gender": "Female",
        "guardian_name": "Zubair Ahmed",
        "guardian_urdu_name": "زبیر احمد",
        "guardian_relation": "Father",
        "guardian_phone": "03461112233",
        "guardian_whatsapp": "03461112233",
        "class_index": 1,
        "roll_number": "205",
        "discount": Decimal("0.00"),
        "marks": [Decimal("82.00"), Decimal("79.00"), Decimal("84.00")],
    },

    # --- Tuition Batch - 9th Physics (AcademyBatch) ---
    {
        "first_name": "Hassan",
        "last_name": "Raza",
        "urdu_name": "حسن رضا",
        "gender": "Male",
        "guardian_name": "Raza Hussain",
        "guardian_urdu_name": "رضا حسین",
        "guardian_relation": "Father",
        "guardian_phone": "03039998877",
        "guardian_whatsapp": "03039998877",
        "class_index": 2,
        "roll_number": "T-301",
        "discount": Decimal("0.00"),
        "marks": [Decimal("89.00"), Decimal("86.00"), Decimal("92.00")],
    },
    {
        "first_name": "Dua",
        "last_name": "Fatima",
        "urdu_name": "دعا فاطمہ",
        "gender": "Female",
        "guardian_name": "Imran Shah",
        "guardian_urdu_name": "عمران شاہ",
        "guardian_relation": "Father",
        "guardian_phone": "03136665544",
        "guardian_whatsapp": "03136665544",
        "class_index": 2,
        "roll_number": "T-302",
        "discount": Decimal("200.00"),
        "marks": [Decimal("76.00"), Decimal("80.00"), Decimal("78.00")],
    },
    {
        "first_name": "Saad",
        "last_name": "Murtaza",
        "urdu_name": "سعد مرتضیٰ",
        "gender": "Male",
        "guardian_name": "Murtaza Ali",
        "guardian_urdu_name": "مرتضیٰ علی",
        "guardian_relation": "Father",
        "guardian_phone": "03235554433",
        "guardian_whatsapp": "03235554433",
        "class_index": 2,
        "roll_number": "T-303",
        "discount": Decimal("0.00"),
        "marks": [Decimal("91.00"), Decimal("94.00"), Decimal("88.00")],
    },
    {
        "first_name": "Hania",
        "last_name": "Amir",
        "urdu_name": "ہانیہ عامر",
        "gender": "Female",
        "guardian_name": "Amir Liaquat",
        "guardian_urdu_name": "عامر لیاقت",
        "guardian_relation": "Father",
        "guardian_phone": "03352223344",
        "guardian_whatsapp": "03352223344",
        "class_index": 2,
        "roll_number": "T-304",
        "discount": Decimal("0.00"),
        "marks": [Decimal("68.00"), Decimal("72.00"), Decimal("65.00")],
    },
    {
        "first_name": "Zayd",
        "last_name": "Ibrahim",
        "urdu_name": "زید ابراہیم",
        "gender": "Male",
        "guardian_name": "Ibrahim Khalil",
        "guardian_urdu_name": "ابراہیم خلیل",
        "guardian_relation": "Father",
        "guardian_phone": "03478887766",
        "guardian_whatsapp": "03478887766",
        "class_index": 2,
        "roll_number": "T-305",
        "discount": Decimal("500.00"),
        "marks": [Decimal("81.00"), Decimal("84.00"), Decimal("80.00")],
    },
]


def seed_demo_database(db_path: str, verbose: bool = True) -> dict:
    """
    Executes complete institutional pilot data seeding.

    Args:
        db_path: Target SQLite database file path.
        verbose: Whether to print console progress indicators.

    Returns:
        Summary dictionary with counts of inserted records.
    """
    if verbose:
        print(f"[*] Initializing and migrating database at: {db_path}")

    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = init_database(db_path)

    student_svc = StudentService(conn)
    fee_svc = FeeService(conn)
    att_svc = AttendanceService(conn)
    exam_svc = ExamService(conn)

    # 1. Academic Session
    if verbose:
        print("[1/7] Creating Academic Session 2026-2027...")
    session_id = student_svc.create_academic_session(
        name="2026-2027",
        start_date="2026-04-01",
        end_date="2027-03-31",
        is_active=True
    )

    # 2. Class Groups
    if verbose:
        print("[2/7] Creating 3 Class Groups (School & Academy models)...")
    # Clean up zero-state baseline placeholder if present before populating demo school model
    conn.execute("DELETE FROM class_groups WHERE name = 'Class 1' AND section_or_batch = 'Section A';")
    conn.execute("DELETE FROM sqlite_sequence WHERE name = 'class_groups';")
    class_groups = [
        student_svc.create_class_group(
            session_id=session_id,
            name="Class 9",
            section_or_batch="Green",
            group_type="SchoolClass",
            monthly_tuition_fee=Decimal("3500.00")
        ),
        student_svc.create_class_group(
            session_id=session_id,
            name="Class 10",
            section_or_batch="Gold",
            group_type="SchoolClass",
            monthly_tuition_fee=Decimal("4000.00")
        ),
        student_svc.create_class_group(
            session_id=session_id,
            name="Tuition Batch",
            section_or_batch="9th Physics",
            group_type="AcademyBatch",
            monthly_tuition_fee=Decimal("2500.00")
        ),
    ]

    # 3. Master Subjects & Fee Heads
    if verbose:
        print("[3/7] Registering master subjects and recurring fee heads...")

    def get_or_create_subject(name: str, urdu: str, code: str) -> int:
        cur = conn.cursor()
        cur.execute("SELECT id FROM subjects WHERE name = ?;", (name,))
        row = cur.fetchone()
        if row:
            return row["id"] if isinstance(row, sqlite3.Row) else row[0]
        return exam_svc.create_subject(name=name, urdu_name=urdu, code=code)

    def get_or_create_fee_head(name: str, urdu: str, is_recurring: bool = True) -> int:
        cur = conn.cursor()
        cur.execute("SELECT id FROM fee_heads WHERE name = ?;", (name,))
        row = cur.fetchone()
        if row:
            return row["id"] if isinstance(row, sqlite3.Row) else row[0]
        return fee_svc.create_fee_head(name=name, urdu_name=urdu, is_recurring=is_recurring)

    subject_ids = [
        get_or_create_subject("English", "انگریزی", "ENG-09"),
        get_or_create_subject("Mathematics", "ریاضی", "MTH-09"),
        get_or_create_subject("Physics", "طبیعیات", "PHY-09"),
        get_or_create_subject("Urdu", "اردو", "URD-09"),
        get_or_create_subject("Chemistry", "کیمیا", "CHM-09"),
    ]

    get_or_create_fee_head("Monthly Tuition Fee", "ماہانہ ٹیوشن فیس", is_recurring=True)
    get_or_create_fee_head("Examination Fee", "امتحانی فیس", is_recurring=False)
    get_or_create_fee_head("Lab & Computer Charges", "لیب چارجز", is_recurring=True)

    # 4. Enrolled Students
    if verbose:
        print(f"[4/7] Registering {len(DEMO_STUDENTS)} bilingual students and generating enrollments...")
    enrollment_ids = []
    student_ids = []

    for s_info in DEMO_STUDENTS:
        target_class_id = class_groups[s_info["class_index"]]
        dto = StudentDTO(
            first_name=s_info["first_name"],
            last_name=s_info["last_name"],
            urdu_name=s_info["urdu_name"],
            gender=s_info["gender"],
            guardian_name=s_info["guardian_name"],
            guardian_urdu_name=s_info["guardian_urdu_name"],
            guardian_relation=s_info["guardian_relation"],
            guardian_phone=s_info["guardian_phone"],
            guardian_whatsapp=s_info["guardian_whatsapp"],
            residential_address="Main Road, Model Town, Lahore",
            emergency_contact=s_info["guardian_phone"],
        )
        s_id, e_id = student_svc.register_student(
            student_data=dto,
            class_group_id=target_class_id,
            session_id=session_id,
            roll_number=s_info["roll_number"],
            custom_discount_amount=s_info["discount"],
            enrollment_date="2026-04-01"
        )
        student_ids.append(s_id)
        enrollment_ids.append(e_id)

    # 5. Fee Invoices & Payment Ledger
    if verbose:
        print("[5/7] Generating monthly fee billing cycle 2026-04 with receipts and defaulters...")
    invoices_created = fee_svc.generate_monthly_invoices(
        session_id=session_id,
        month_year="2026-04",
        issue_date="2026-04-01",
        due_date="2026-04-10",
        valid_until="2026-04-20"
    )

    # Query created invoices to record cash payments:
    cur = conn.cursor()
    cur.execute("SELECT id, enrollment_id, net_due FROM fee_invoices WHERE month_year = '2026-04' ORDER BY id ASC;")
    invoices = cur.fetchall()

    paid_count = 0
    partial_count = 0
    receipts_issued = []

    for idx, inv in enumerate(invoices):
        inv_id, enr_id, net_due_str = inv
        net_due = Decimal(str(net_due_str))

        if idx < 5:
            # 1. Paid in full
            rec_no = fee_svc.record_payment(
                invoice_id=inv_id,
                amount=net_due,
                payment_method="Cash",
                payment_date="2026-04-05",
                note="Full monthly fee paid in cash at counter"
            )
            receipts_issued.append(rec_no)
            paid_count += 1
        elif idx < 10:
            # 2. Partially paid (e.g. 1500.00 / 2000.00 paid)
            part_amt = Decimal("2000.00") if net_due >= Decimal("2000.00") else (net_due / Decimal("2"))
            rec_no = fee_svc.record_payment(
                invoice_id=inv_id,
                amount=part_amt,
                payment_method="Cash",
                payment_date="2026-04-07",
                note="Partial fee deposit; remaining balance promised by 15th"
            )
            receipts_issued.append(rec_no)
            partial_count += 1
        else:
            # 3. Unpaid Defaulters (idx 10 to 14)
            pass

    # 6. Daily Class Attendance Records (5 School Days)
    if verbose:
        print("[6/7] Logging 5 days of class attendance roll calls with WhatsApp notice triggers...")
    attendance_dates = ["2026-04-06", "2026-04-07", "2026-04-08", "2026-04-09", "2026-04-10"]
    total_att_records = 0

    for d_idx, a_date in enumerate(attendance_dates):
        entries = []
        for s_idx, e_id in enumerate(enrollment_ids):
            # Realistic attendance distribution:
            if d_idx == 1 and s_idx == 2:  # Usman Tariq absent on Day 2
                status = "Absent"
                reason = "Fever and doctor appointment"
            elif d_idx == 2 and s_idx == 7:  # Maryam Noor late on Day 3
                status = "Late"
                reason = "School van flat tyre"
            elif d_idx == 3 and s_idx == 11:  # Dua Fatima absent on Day 4
                status = "Absent"
                reason = "Family emergency"
            elif d_idx == 4 and s_idx == 4:  # Bilal Ahmed excused
                status = "Leave"
                reason = "Pre-approved sports event"
            else:
                status = "Present"
                reason = None

            entries.append({
                "enrollment_id": e_id,
                "status": status,
                "reason_note": reason
            })

        count = att_svc.save_bulk_attendance(date=a_date, entries=entries)
        total_att_records += count

    # 7. Examination Cycle, Grading Tiers & Marks Ledger
    if verbose:
        print("[7/7] Configuring First Term Exam 2026, BISE grading tiers, and entering student marks...")
    exam_svc.seed_default_grading_tiers(session_id=session_id)

    exam_id = exam_svc.create_exam(
        session_id=session_id,
        name="First Term Examination 2026",
        exam_type="TermExam",
        start_date="2026-05-02",
        end_date="2026-05-15",
        is_published=True
    )

    # Configure exam subjects for Class 9 and Class 10 (Eng, Math, Phy)
    exam_subject_ids = {}
    for c_id in class_groups[:2]:  # Class 9 & Class 10
        for sub_id in subject_ids[:3]:
            es_id = exam_svc.configure_exam_subject(
                exam_id=exam_id,
                class_group_id=c_id,
                subject_id=sub_id,
                maximum_marks=Decimal("100.00"),
                passing_marks=Decimal("33.00")
            )
            exam_subject_ids[(c_id, sub_id)] = es_id

    # Also configure Physics for Tuition Batch
    tb_phys_id = exam_svc.configure_exam_subject(
        exam_id=exam_id,
        class_group_id=class_groups[2],
        subject_id=subject_ids[2],  # Physics
        maximum_marks=Decimal("100.00"),
        passing_marks=Decimal("33.00")
    )
    exam_subject_ids[(class_groups[2], subject_ids[2])] = tb_phys_id

    # Enter student scores
    total_marks_entered = 0
    for s_idx, s_info in enumerate(DEMO_STUDENTS):
        e_id = enrollment_ids[s_idx]
        c_id = class_groups[s_info["class_index"]]

        if s_info["class_index"] in (0, 1):
            # 3 subjects for school classes
            for sub_idx, sub_id in enumerate(subject_ids[:3]):
                es_id = exam_subject_ids[(c_id, sub_id)]
                mark_val = s_info["marks"][sub_idx]
                exam_svc.record_student_marks(
                    exam_subject_id=es_id,
                    marks_entries=[{
                        "enrollment_id": e_id,
                        "marks_obtained": mark_val,
                        "is_absent": False,
                        "teacher_remarks": "Strong analytical problem solving" if mark_val >= Decimal("80") else "Needs regular revision"
                    }]
                )
                total_marks_entered += 1
        else:
            # Physics for tuition batch
            es_id = exam_subject_ids[(c_id, subject_ids[2])]
            mark_val = s_info["marks"][2]
            exam_svc.record_student_marks(
                exam_subject_id=es_id,
                marks_entries=[{
                    "enrollment_id": e_id,
                    "marks_obtained": mark_val,
                    "is_absent": False,
                    "teacher_remarks": "Demonstrates keen aptitude in experimental physics"
                }]
            )
            total_marks_entered += 1

    summary = {
        "database_path": db_path,
        "academic_session_id": session_id,
        "class_groups_created": len(class_groups),
        "students_registered": len(student_ids),
        "invoices_generated": invoices_created,
        "receipts_issued": len(receipts_issued),
        "paid_invoices": paid_count,
        "partial_invoices": partial_count,
        "defaulter_invoices": len(invoices) - paid_count - partial_count,
        "attendance_records_logged": total_att_records,
        "exam_id": exam_id,
        "marks_records_entered": total_marks_entered,
    }

    if verbose:
        print("\n" + "=" * 60)
        print("[SUCCESS] Pilot Demo Database Successfully Seeded!")
        print("=" * 60)
        for k, v in summary.items():
            print(f"  - {k.replace('_', ' ').capitalize()}: {v}")
        print("=" * 60 + "\n")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ClassFellow Realistic Punjab School Demo Data Seeder"
    )
    parser.add_argument(
        "--db-path",
        default=os.path.join(ROOT_DIR, "data", "classfellow.db"),
        help="Target SQLite database file path (default: data/classfellow.db)"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Remove existing database file before seeding fresh dataset"
    )
    args = parser.parse_args()

    if args.reset and os.path.exists(args.db_path):
        print(f"[*] Removing existing database at: {args.db_path}")
        try:
            os.remove(args.db_path)
            for companion in (f"{args.db_path}-wal", f"{args.db_path}-shm"):
                if os.path.exists(companion):
                    os.remove(companion)
        except Exception as exc:
            print(f"[!] Warning: Could not remove old database: {exc}")

    seed_demo_database(db_path=args.db_path, verbose=True)


if __name__ == "__main__":
    main()
