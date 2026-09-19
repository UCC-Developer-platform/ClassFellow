"""
ClassFellow - Fee & Receipt Domain Service
==========================================
Governs fee structures, dynamic itemized monthly invoicing, cashier payment
collection, payment ledger with ON DELETE RESTRICT protection, two-tier due
dates, and fact-derived financial balance calculations as specified in CF-SRS-03.
"""

import os
import re
import datetime
import sqlite3
from decimal import Decimal
from typing import Optional, Any
from database import transaction, DEFAULT_DB_PATH
from models import StudentDTO


def generate_next_receipt_number(conn: sqlite3.Connection, year: Optional[int] = None) -> str:
    """
    Generates the next sequential receipt number for the given calendar year.
    Format: 'REC-YYYY-XXXXX' (e.g., 'REC-2025-00001').
    Must be called inside an active transaction write lock.
    """
    if year is None:
        year = datetime.date.today().year

    prefix = f"REC-{year}-"
    cursor = conn.cursor()
    cursor.execute(
        "SELECT receipt_number FROM payments WHERE receipt_number LIKE ? ORDER BY id DESC LIMIT 1;",
        (f"{prefix}%",)
    )
    row = cursor.fetchone()
    if not row:
        return f"{prefix}00001"

    last_receipt = row["receipt_number"] if isinstance(row, sqlite3.Row) else row[0]
    try:
        parts = last_receipt.split("-")
        seq = int(parts[-1])
        return f"{prefix}{seq + 1:05d}"
    except (ValueError, IndexError):
        return f"{prefix}00001"


class FeeService:
    """Encapsulates fee management, itemized invoicing, and append-only payment ledgers."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # --- Fee Head Administration ---

    def create_fee_head(
        self,
        name: str,
        urdu_name: Optional[str] = None,
        is_recurring: bool = True
    ) -> int:
        """Creates a dynamic fee category (e.g., 'Tuition Fee', 'Lab Fee')."""
        if not name or not name.strip():
            raise ValueError("Fee head name cannot be empty.")

        with transaction(self.conn):
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO fee_heads (name, urdu_name, is_recurring)
                VALUES (?, ?, ?);
                """,
                (name.strip(), urdu_name.strip() if urdu_name else None, 1 if is_recurring else 0)
            )
            return cursor.lastrowid

    def get_fee_heads(self, recurring_only: bool = False) -> list[dict[str, Any]]:
        """Retrieves all registered fee heads."""
        cursor = self.conn.cursor()
        sql = "SELECT id, name, urdu_name, is_recurring FROM fee_heads"
        if recurring_only:
            sql += " WHERE is_recurring = 1"
        sql += " ORDER BY id ASC;"
        cursor.execute(sql)
        rows = cursor.fetchall()
        return [{k: r[k] for k in r.keys()} for r in rows]

    # --- Invoicing Engine ---

    def generate_monthly_invoices(
        self,
        session_id: int,
        month_year: str,
        issue_date: str,
        due_date: str,
        valid_until: str,
        late_fee_surcharge: Decimal = Decimal("200.00"),
        specific_enrollment_id: Optional[int] = None,
        class_group_id: Optional[int] = None
    ) -> int:
        """
        Generates itemized fee vouchers for enrolled students inside an atomic transaction.

        Args:
            session_id: Academic session ID.
            month_year: Billing cycle in 'YYYY-MM' format (e.g., '2025-10').
            issue_date: Date of voucher issuance (YYYY-MM-DD).
            due_date: Tier 1 standard due date (YYYY-MM-DD).
            valid_until: Tier 2 bank/cashier cutoff date (YYYY-MM-DD).
            late_fee_surcharge: Surcharge applied after due_date.
            specific_enrollment_id: Optional target single enrollment.
            class_group_id: Optional target class group.

        Returns:
            Number of newly generated invoices.
        """
        if not re.match(r"^\d{4}-\d{2}$", month_year):
            raise ValueError(f"Invalid month_year format '{month_year}'. Must be 'YYYY-MM' (e.g., '2025-10').")

        cursor = self.conn.cursor()

        # Verify session exists
        cursor.execute("SELECT id FROM academic_sessions WHERE id = ?;", (session_id,))
        if not cursor.fetchone():
            raise ValueError(f"Academic session id={session_id} does not exist.")

        # Resolve Tuition Fee Head ID
        cursor.execute("SELECT id FROM fee_heads WHERE name = 'Tuition Fee' LIMIT 1;")
        tf_row = cursor.fetchone()
        if not tf_row:
            # Create default Tuition Fee head if missing
            tuition_head_id = self.create_fee_head("Tuition Fee", "ٹیوشن فیس", is_recurring=True)
        else:
            tuition_head_id = tf_row["id"] if isinstance(tf_row, sqlite3.Row) else tf_row[0]

        # Query active enrollments
        sql = """
        SELECT 
            e.id AS enrollment_id,
            e.student_id,
            e.class_group_id,
            e.custom_discount_amount,
            cg.monthly_tuition_fee,
            cg.name AS class_name
        FROM enrollments e
        JOIN class_groups cg ON e.class_group_id = cg.id
        WHERE e.session_id = ? AND e.status = 'Active'
        """
        params: list[Any] = [session_id]
        if specific_enrollment_id:
            sql += " AND e.id = ?"
            params.append(specific_enrollment_id)
        if class_group_id:
            sql += " AND e.class_group_id = ?"
            params.append(class_group_id)

        cursor.execute(sql, params)
        enrollments = cursor.fetchall()

        invoices_created = 0

        with transaction(self.conn):
            for enr in enrollments:
                enr_id = enr["enrollment_id"]

                # Check if invoice already exists for this billing cycle
                cursor.execute(
                    "SELECT id FROM fee_invoices WHERE enrollment_id = ? AND month_year = ?;",
                    (enr_id, month_year)
                )
                if cursor.fetchone():
                    continue  # Idempotent skip for existing cycle

                tuition_amount = Decimal(str(enr["monthly_tuition_fee"]))
                discount_amount = Decimal(str(enr["custom_discount_amount"]))

                # Calculate invoice totals
                total_payable = tuition_amount  # Expandable with other recurring heads
                net_due = max(Decimal("0.00"), total_payable - discount_amount)

                # Insert fee_invoices header
                cursor.execute(
                    """
                    INSERT INTO fee_invoices (
                        enrollment_id, session_id, month_year, issue_date,
                        due_date, valid_until, late_fee_surcharge, total_payable,
                        discount_amount, net_due
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        enr_id,
                        session_id,
                        month_year,
                        issue_date,
                        due_date,
                        valid_until,
                        str(late_fee_surcharge),
                        str(total_payable),
                        str(discount_amount),
                        str(net_due)
                    )
                )
                invoice_id = cursor.lastrowid

                # Insert itemized tuition line item
                cursor.execute(
                    """
                    INSERT INTO fee_invoice_items (invoice_id, fee_head_id, amount)
                    VALUES (?, ?, ?);
                    """,
                    (invoice_id, tuition_head_id, str(tuition_amount))
                )

                invoices_created += 1

        return invoices_created

    # --- Financial State & Calculations ---

    def calculate_invoice_balance(self, invoice_id: int) -> dict[str, Any]:
        """
        Calculates fact-derived invoice financials, total payments, balance, and status.
        Follows the mathematical formulation defined in CF-SRS-03 Section 3.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT 
                id, enrollment_id, session_id, month_year, issue_date, due_date,
                valid_until, late_fee_surcharge, total_payable, discount_amount, net_due
            FROM fee_invoices
            WHERE id = ?;
            """,
            (invoice_id,)
        )
        inv = cursor.fetchone()
        if not inv:
            raise ValueError(f"Fee invoice id={invoice_id} does not exist.")

        total_payable = Decimal(str(inv["total_payable"]))
        discount_amount = Decimal(str(inv["discount_amount"]))
        late_fee_surcharge = Decimal(str(inv["late_fee_surcharge"]))
        net_due = Decimal(str(inv["net_due"]))

        # Query valid issued payments from append-only ledger
        cursor.execute(
            """
            SELECT COALESCE(SUM(CAST(amount AS NUMERIC)), 0) AS total_paid
            FROM payments
            WHERE invoice_id = ? AND status = 'Issued';
            """,
            (invoice_id,)
        )
        paid_row = cursor.fetchone()
        total_paid = Decimal(str(paid_row["total_paid"])) if paid_row else Decimal("0.00")

        current_balance = net_due - total_paid

        # Derived Status State Machine
        if total_paid == Decimal("0.00") and current_balance > Decimal("0.00"):
            status = "Unpaid"
        elif total_paid > Decimal("0.00") and current_balance > Decimal("0.00"):
            status = "Partially Paid"
        elif current_balance == Decimal("0.00"):
            status = "Paid"
        else:  # current_balance < 0
            status = "Overpaid"

        return {
            "invoice_id": invoice_id,
            "month_year": inv["month_year"],
            "total_payable": total_payable,
            "discount_amount": discount_amount,
            "late_fee_surcharge": late_fee_surcharge,
            "net_due": net_due,
            "net_due_with_late_fee": net_due + late_fee_surcharge,
            "total_paid": total_paid,
            "current_balance": current_balance,
            "status": status,
            "due_date": inv["due_date"],
            "valid_until": inv["valid_until"],
            "issue_date": inv["issue_date"]
        }

    def get_invoice_details(self, invoice_id: int) -> Optional[dict[str, Any]]:
        """
        Returns complete invoice data including student identity, breakdown items,
        payment ledger entries, and financial balance.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT 
                fi.*,
                s.id AS student_id,
                s.admission_number,
                s.first_name,
                s.last_name,
                TRIM(s.first_name || ' ' || COALESCE(s.last_name, '')) AS full_name,
                s.urdu_name AS student_urdu_name,
                s.guardian_name,
                s.guardian_urdu_name,
                s.guardian_phone,
                e.roll_number,
                cg.name AS class_name,
                cg.section_or_batch,
                cg.group_type,
                sess.name AS session_name
            FROM fee_invoices fi
            JOIN enrollments e ON fi.enrollment_id = e.id
            JOIN students s ON e.student_id = s.id
            JOIN class_groups cg ON e.class_group_id = cg.id
            JOIN academic_sessions sess ON fi.session_id = sess.id
            WHERE fi.id = ?;
            """,
            (invoice_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None

        inv_data = {k: row[k] for k in row.keys()}

        # Load itemized lines
        cursor.execute(
            """
            SELECT fii.id, fii.fee_head_id, fh.name AS fee_head_name, fh.urdu_name, fii.amount
            FROM fee_invoice_items fii
            JOIN fee_heads fh ON fii.fee_head_id = fh.id
            WHERE fii.invoice_id = ?
            ORDER BY fii.id ASC;
            """,
            (invoice_id,)
        )
        items = [{k: r[k] for k in r.keys()} for r in cursor.fetchall()]
        inv_data["items"] = items

        # Load payments ledger
        cursor.execute(
            """
            SELECT id, amount, payment_date, receipt_number, payment_method, status, note
            FROM payments
            WHERE invoice_id = ?
            ORDER BY id ASC;
            """,
            (invoice_id,)
        )
        payments = [{k: r[k] for k in r.keys()} for r in cursor.fetchall()]
        inv_data["payments"] = payments

        # Merge calculated balance and status
        financials = self.calculate_invoice_balance(invoice_id)
        inv_data["total_paid"] = financials["total_paid"]
        inv_data["current_balance"] = financials["current_balance"]
        inv_data["status"] = financials["status"]

        return inv_data

    # --- Cashier Ledger & Receipting ---

    def record_payment(
        self,
        invoice_id: int,
        amount: Decimal,
        payment_method: str = "Cash",
        recorded_by_user_id: Optional[int] = None,
        note: Optional[str] = None,
        payment_date: Optional[str] = None
    ) -> str:
        """
        Records an immutable payment transaction against an invoice.
        Enforces ON DELETE RESTRICT on the invoice ledger.

        Args:
            invoice_id: Target fee invoice.
            amount: Amount received as Decimal.
            payment_method: 'Cash', 'BankTransfer', 'OnlineDeposit', or 'Cheque'.
            recorded_by_user_id: Cashier / Admin ID.
            note: Cashier note.
            payment_date: Date of receipt (YYYY-MM-DD, defaults to today).

        Returns:
            Unique sequential receipt number (e.g. 'REC-2025-00001').
        """
        if amount <= Decimal("0.00"):
            raise ValueError(f"Payment amount must be greater than zero. Received: {amount}")

        valid_methods = ("Cash", "BankTransfer", "OnlineDeposit", "Cheque")
        if payment_method not in valid_methods:
            raise ValueError(f"Invalid payment_method '{payment_method}'. Allowed: {valid_methods}")

        if not payment_date:
            payment_date = datetime.date.today().isoformat()

        cursor = self.conn.cursor()
        cursor.execute("SELECT id, session_id FROM fee_invoices WHERE id = ?;", (invoice_id,))
        inv_row = cursor.fetchone()
        if not inv_row:
            raise ValueError(f"Invoice id={invoice_id} does not exist.")

        with transaction(self.conn):
            # Generate next receipt number inside exclusive lock
            receipt_no = generate_next_receipt_number(self.conn)

            cursor.execute(
                """
                INSERT INTO payments (
                    invoice_id, amount, payment_date, receipt_number,
                    payment_method, status, recorded_by_user_id, note
                ) VALUES (?, ?, ?, ?, ?, 'Issued', ?, ?);
                """,
                (
                    invoice_id,
                    str(amount),
                    payment_date,
                    receipt_no,
                    payment_method,
                    recorded_by_user_id,
                    note.strip() if note else None
                )
            )

        return receipt_no

    def reverse_payment(
        self,
        payment_id: int,
        reason: str,
        recorded_by_user_id: Optional[int] = None
    ) -> None:
        """
        Reverses an issued payment receipt with an audit explanation.
        """
        if not reason or not reason.strip():
            raise ValueError("Reversal reason is mandatory for financial audit.")

        cursor = self.conn.cursor()
        cursor.execute("SELECT id, status FROM payments WHERE id = ?;", (payment_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Payment record id={payment_id} does not exist.")

        if row["status"] != "Issued":
            raise ValueError(f"Only 'Issued' payments can be reversed. Current status: '{row['status']}'.")

        with transaction(self.conn):
            cursor.execute(
                """
                UPDATE payments SET
                    status = 'Reversed',
                    reversal_reason = ?,
                    note = COALESCE(note, '') || ' [Reversed by User ' || ? || ']'
                WHERE id = ?;
                """,
                (reason.strip(), recorded_by_user_id or "Admin", payment_id)
            )

    # --- Financial Defaulter Reporting & Relational Protection ---

    def get_defaulters_list(
        self,
        session_id: int,
        month_year: Optional[str] = None,
        overdue_as_of: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """
        Returns all students with overdue outstanding balances.
        Performs a single-pass indexed SQL query joining student identity,
        enrollment details, class information, and payment aggregation.
        """
        cursor = self.conn.cursor()
        sql = """
        WITH candidate_invoices AS (
            SELECT 
                fi.id AS invoice_id,
                fi.id,
                fi.enrollment_id,
                fi.session_id,
                fi.month_year,
                fi.issue_date,
                fi.due_date,
                fi.valid_until,
                fi.late_fee_surcharge,
                fi.total_payable,
                fi.discount_amount,
                fi.net_due,
                fi.created_at,
                COALESCE((
                    SELECT SUM(CAST(p.amount AS NUMERIC))
                    FROM payments p
                    WHERE p.invoice_id = fi.id AND p.status = 'Issued'
                ), 0.0) AS total_paid
            FROM fee_invoices fi
            WHERE fi.session_id = ?
        """
        params: list[Any] = [session_id]
        if month_year:
            sql += " AND fi.month_year = ?"
            params.append(month_year)
        if overdue_as_of:
            sql += " AND fi.valid_until < ?"
            params.append(overdue_as_of)

        sql += """
        )
        SELECT 
            ci.*,
            s.id AS student_id,
            s.admission_number,
            s.first_name,
            s.last_name,
            TRIM(s.first_name || ' ' || COALESCE(s.last_name, '')) AS full_name,
            s.urdu_name AS student_urdu_name,
            s.guardian_name,
            s.guardian_urdu_name,
            s.guardian_phone,
            e.roll_number,
            cg.name AS class_name,
            cg.section_or_batch,
            cg.group_type,
            sess.name AS session_name
        FROM candidate_invoices ci
        JOIN enrollments e ON ci.enrollment_id = e.id
        JOIN students s ON e.student_id = s.id
        JOIN class_groups cg ON e.class_group_id = cg.id
        JOIN academic_sessions sess ON ci.session_id = sess.id
        WHERE CAST(ci.net_due AS NUMERIC) > ci.total_paid
        ORDER BY ci.valid_until ASC, ci.invoice_id ASC;
        """

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        if not rows:
            return []

        col_names = [d[0] for d in cursor.description]
        defaulters = []
        for r in rows:
            row_dict = dict(zip(col_names, tuple(r)))
            net_due = Decimal(str(row_dict["net_due"]))
            total_paid = Decimal(str(row_dict["total_paid"]))
            current_balance = max(Decimal("0.00"), net_due - total_paid)
            late_fee = Decimal(str(row_dict["late_fee_surcharge"]))

            if total_paid == Decimal("0.00"):
                status = "Unpaid"
            elif current_balance > Decimal("0.00"):
                status = "Partially Paid"
            else:
                status = "Paid"

            row_dict["total_payable"] = Decimal(str(row_dict["total_payable"]))
            row_dict["discount_amount"] = Decimal(str(row_dict["discount_amount"]))
            row_dict["late_fee_surcharge"] = late_fee
            row_dict["net_due"] = net_due
            row_dict["net_due_with_late_fee"] = net_due + late_fee
            row_dict["total_paid"] = total_paid
            row_dict["current_balance"] = current_balance
            row_dict["status"] = status
            defaulters.append(row_dict)

        return defaulters

    def delete_invoice(self, invoice_id: int) -> None:
        """
        Deletes a fee invoice.
        Enforces ON DELETE RESTRICT: If payment receipts exist in the ledger,
        SQLite raises sqlite3.IntegrityError to prevent financial tampering.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM fee_invoices WHERE id = ?;", (invoice_id,))
        if not cursor.fetchone():
            raise ValueError(f"Invoice id={invoice_id} does not exist.")

        with transaction(self.conn):
            cursor.execute("DELETE FROM fee_invoices WHERE id = ?;", (invoice_id,))

    def calculate_sibling_discount(
        self,
        guardian_phone: str,
        base_tuition: Decimal,
        student_id: Optional[int] = None
    ) -> Decimal:
        """Wrapper calling calculate_sibling_discount with connection instance."""
        return calculate_sibling_discount(self.conn, guardian_phone, base_tuition, student_id)

    def get_prior_arrears(
        self,
        enrollment_id: int,
        current_month_year: str
    ) -> Decimal:
        """Wrapper calling get_prior_arrears with connection instance."""
        return get_prior_arrears(self.conn, enrollment_id, current_month_year)

    def process_walkin_admission(self, **kwargs) -> str:
        """Wrapper calling process_walkin_admission with connection instance."""
        return process_walkin_admission(self.conn, **kwargs)


def calculate_sibling_discount(
    conn: sqlite3.Connection,
    guardian_phone: str,
    base_tuition: Decimal,
    student_id: Optional[int] = None
) -> Decimal:
    """
    Calculates sibling concession discount based on child enrollment order.
    Queries active enrollments matching normalized guardian_phone ordered by enrollment_date ASC, s.id ASC.
    Discount formula:
      - 1st child: 0% discount
      - 2nd child: 25% discount
      - 3rd+ child: 50% discount
    """
    if not guardian_phone or not str(guardian_phone).strip():
        return Decimal("0.00")

    try:
        from services.student_service import normalize_pakistan_phone
        norm_phone = normalize_pakistan_phone(guardian_phone)
    except Exception:
        norm_phone = str(guardian_phone).strip()

    cur = conn.cursor()
    cur.execute(
        """
        SELECT s.id, MIN(e.enrollment_date) AS first_enrolled
        FROM students s
        JOIN enrollments e ON s.id = e.student_id
        WHERE (s.guardian_phone = ? OR s.guardian_phone = ?) AND e.status = 'Active'
        GROUP BY s.id
        ORDER BY first_enrolled ASC, s.id ASC;
        """,
        (norm_phone, str(guardian_phone).strip())
    )
    rows = cur.fetchall()
    sibling_ids = [r[0] if isinstance(r, (tuple, list)) else r["id"] for r in rows]

    if student_id is not None and student_id in sibling_ids:
        order_index = sibling_ids.index(student_id)
    else:
        order_index = len(sibling_ids)

    if order_index == 0:
        rate = Decimal("0.00")
    elif order_index == 1:
        rate = Decimal("0.25")
    else:
        rate = Decimal("0.50")

    return (Decimal(str(base_tuition)) * rate).quantize(Decimal("0.01"))


def get_prior_arrears(
    conn: sqlite3.Connection,
    enrollment_id: int,
    current_month_year: str
) -> Decimal:
    """
    Sums unpaid balances from all prior billing cycles (month_year < current_month_year)
    for a given enrollment.
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT 
            fi.id,
            fi.net_due,
            COALESCE((
                SELECT SUM(CAST(p.amount AS NUMERIC))
                FROM payments p
                WHERE p.invoice_id = fi.id AND p.status = 'Issued'
            ), 0.0) AS total_paid
        FROM fee_invoices fi
        WHERE fi.enrollment_id = ? AND fi.month_year < ?
        ORDER BY fi.month_year ASC;
        """,
        (enrollment_id, current_month_year)
    )
    rows = cur.fetchall()
    total_arrears = Decimal("0.00")
    for r in rows:
        net_due = Decimal(str(r["net_due"] if isinstance(r, sqlite3.Row) else r[1]))
        total_paid = Decimal(str(r["total_paid"] if isinstance(r, sqlite3.Row) else r[2]))
        unpaid = max(Decimal("0.00"), net_due - total_paid)
        total_arrears += unpaid

    return total_arrears.quantize(Decimal("0.01"))


def process_walkin_admission(
    conn: sqlite3.Connection,
    student_data: StudentDTO,
    class_group_id: int,
    session_id: Optional[int] = None,
    roll_number: Optional[str] = None,
    enrollment_date: Optional[str] = None,
    concession_discount: Decimal = Decimal("0.00"),
    month_year: Optional[str] = None,
    issue_date: Optional[str] = None,
    due_date: Optional[str] = None,
    valid_until: Optional[str] = None,
    admission_fee: Decimal = Decimal("0.00"),
    prospectus_fee: Decimal = Decimal("0.00"),
    security_deposit: Decimal = Decimal("0.00"),
    prior_arrears: Decimal = Decimal("0.00"),
    voucher_output_dir: Optional[str] = None,
    generate_voucher: bool = True,
    institution_name: str = "CLASSFELLOW HIGH SCHOOL & ACADEMY"
) -> str:
    """
    Executes atomic walk-in admission transaction:
      1. Registers student identity & guardian details in students table.
      2. Enrolls student in target class group & academic session.
      3. Generates itemized initial admission fee invoice (Tuition, Admission Fee,
         Registration/Prospectus, Security Deposit, Prior Arrears minus Concession).
      4. Renders a print-ready 3-panel A4 fee voucher PDF via ReportLab.

    Returns:
        The filesystem path of the generated 3-panel voucher PDF.
    """
    from services.student_service import StudentService
    from app.reports.fee_voucher_generator import generate_fee_voucher_pdf

    if not enrollment_date:
        enrollment_date = datetime.date.today().isoformat()
    if not month_year:
        month_year = datetime.date.today().strftime("%Y-%m")
    if not issue_date:
        issue_date = datetime.date.today().isoformat()
    if not due_date:
        due_date = f"{month_year}-10"
    if not valid_until:
        valid_until = f"{month_year}-20"

    cursor = conn.cursor()

    # Resolve active session if not explicitly provided
    if session_id is None:
        cursor.execute("SELECT session_id, monthly_tuition_fee FROM class_groups WHERE id = ?;", (class_group_id,))
        cg_row = cursor.fetchone()
        if not cg_row:
            raise ValueError(f"Class group id={class_group_id} does not exist.")
        session_id = cg_row["session_id"] if isinstance(cg_row, sqlite3.Row) else cg_row[0]
        base_tuition = Decimal(str(cg_row["monthly_tuition_fee"] if isinstance(cg_row, sqlite3.Row) else cg_row[1]))
    else:
        cursor.execute("SELECT monthly_tuition_fee FROM class_groups WHERE id = ?;", (class_group_id,))
        cg_row = cursor.fetchone()
        if not cg_row:
            raise ValueError(f"Class group id={class_group_id} does not exist.")
        base_tuition = Decimal(str(cg_row["monthly_tuition_fee"] if isinstance(cg_row, sqlite3.Row) else cg_row[0]))

    invoice_id = None
    adm_number = None

    with transaction(conn):
        student_svc = StudentService(conn)
        student_id, enrollment_id = student_svc.register_student(
            student_data=student_data,
            class_group_id=class_group_id,
            session_id=session_id,
            roll_number=roll_number,
            custom_discount_amount=concession_discount,
            enrollment_date=enrollment_date
        )

        st_rec = student_svc.get_student_by_id(student_id)
        adm_number = st_rec.get("admission_number", f"ID{student_id}") if st_rec else f"ID{student_id}"

        def _get_head_id(name: str, urdu: str, rec: int) -> int:
            cursor.execute("SELECT id FROM fee_heads WHERE name = ? LIMIT 1;", (name,))
            h_row = cursor.fetchone()
            if h_row:
                return h_row[0] if isinstance(h_row, (tuple, list)) else h_row["id"]
            cursor.execute("INSERT INTO fee_heads (name, urdu_name, is_recurring) VALUES (?, ?, ?);", (name, urdu, rec))
            return cursor.lastrowid

        items_to_create = [
            ("Tuition Fee", base_tuition, "ٹیوشن فیس", 1),
        ]
        if admission_fee > Decimal("0.00"):
            items_to_create.append(("Admission Fee", admission_fee, "داخلہ فیس", 0))
        if prospectus_fee > Decimal("0.00"):
            items_to_create.append(("Registration / Prospectus", prospectus_fee, "رجسٹریشن و پراسپیکٹس", 0))
        if security_deposit > Decimal("0.00"):
            items_to_create.append(("Security Deposit", security_deposit, "سیکیورٹی ڈپازٹ", 0))
        if prior_arrears > Decimal("0.00"):
            items_to_create.append(("Previous Arrears", prior_arrears, "سابقہ واجبات", 1))

        total_payable = sum(amt for _, amt, _, _ in items_to_create)
        discount_amount = concession_discount
        net_due = max(Decimal("0.00"), total_payable - discount_amount)

        cursor.execute(
            """
            INSERT INTO fee_invoices (
                enrollment_id, session_id, month_year, issue_date, due_date,
                valid_until, late_fee_surcharge, total_payable, discount_amount, net_due
            ) VALUES (?, ?, ?, ?, ?, ?, '200.00', ?, ?, ?);
            """,
            (
                enrollment_id,
                session_id,
                month_year,
                issue_date,
                due_date,
                valid_until,
                str(total_payable),
                str(discount_amount),
                str(net_due)
            )
        )
        invoice_id = cursor.lastrowid

        for head_name, amt, head_urdu, is_rec in items_to_create:
            hid = _get_head_id(head_name, head_urdu, is_rec)
            cursor.execute(
                "INSERT INTO fee_invoice_items (invoice_id, fee_head_id, amount) VALUES (?, ?, ?);",
                (invoice_id, hid, str(amt))
            )

    if not generate_voucher:
        return ""

    fee_svc = FeeService(conn)
    invoice_data = fee_svc.get_invoice_details(invoice_id)
    if not invoice_data:
        raise RuntimeError(f"Failed to fetch details for invoice {invoice_id}")

    if voucher_output_dir:
        out_dir = voucher_output_dir
    else:
        out_dir = os.path.join(os.path.dirname(os.path.abspath(DEFAULT_DB_PATH)), "vouchers")
    os.makedirs(out_dir, exist_ok=True)

    safe_adm = re.sub(r"[^\w\-]", "_", str(adm_number))
    pdf_path = os.path.join(out_dir, f"admission_voucher_{safe_adm}_{month_year}.pdf")
    generate_fee_voucher_pdf(invoice_data, pdf_path, institution_name=institution_name)

    return pdf_path
