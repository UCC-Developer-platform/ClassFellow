"""
ClassFellow - Fee & Receipt View (ui/fee_view.py)
================================================
Manages monthly billing cycles, payment collection ledger,
ReportLab 3-panel A4 fee voucher generation, and defaulters tracking.
"""

import logging
import os
from decimal import Decimal
from datetime import datetime
from typing import Optional, List, Dict, Any
import customtkinter as ctk

from services.fee_service import FeeService
from app.reports.fee_voucher_generator import generate_fee_voucher_pdf
from ui.base_view import BaseView, BaseModal, THEME_COLORS

logger = logging.getLogger(__name__)


class FeeView(BaseView):
    """Fee management and invoicing workspace."""

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, app, **kwargs)
        self.fee_service = FeeService(self.db_conn) if self.db_conn else None

        self._build_ui()
        self.refresh_data()

    def _build_ui(self) -> None:
        """Constructs invoice filters, action bar, and read-only ledger grid."""
        # 1. Header Banner
        self.create_header(
            title="Fee Management & Invoicing",
            subtitle="Itemized billing, 3-panel vouchers, cash collection, and defaulter tracking",
            actions=[
                ("➕ Generate Invoices", self._open_generate_invoices_modal, self.colors["brand_primary"]),
                ("🔄 Refresh", self.refresh_data, self.colors["brand_accent"]),
            ],
        )

        # 2. Filter & Defaulters Bar
        filter_card = ctk.CTkFrame(self, fg_color=self.colors["bg_card"], corner_radius=8)
        filter_card.pack(fill="x", padx=16, pady=(0, 12))

        ctk.CTkLabel(
            filter_card, text="Filter Status:", font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self.colors["text_primary"]
        ).pack(side="left", padx=(16, 6), pady=12)

        self.status_var = ctk.StringVar(value="All Invoices")
        self.status_menu = ctk.CTkOptionMenu(
            filter_card,
            values=["All Invoices", "Unpaid Only", "Partially Paid", "Paid", "Defaulters Only"],
            variable=self.status_var,
            command=lambda v: self.refresh_data(),
            width=150
        )
        self.status_menu.pack(side="left", padx=4, pady=12)

        ctk.CTkLabel(
            filter_card, text="Search:", font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self.colors["text_primary"]
        ).pack(side="left", padx=(20, 6), pady=12)

        self.search_entry = ctk.CTkEntry(
            filter_card, placeholder_text="Invoice #, student name, or admission #...", width=280
        )
        self.search_entry.pack(side="left", padx=4, pady=12)
        self.search_entry.bind("<Return>", lambda e: self.refresh_data())

        btn_filter = ctk.CTkButton(
            filter_card, text="Filter", width=70, command=self.refresh_data,
            fg_color=self.colors["brand_accent"]
        )
        btn_filter.pack(side="left", padx=6, pady=12)

        # 3. Table Header
        self.table_header_frame = ctk.CTkFrame(
            self, fg_color=self.colors["bg_card"], corner_radius=6, height=36
        )
        self.table_header_frame.pack(fill="x", padx=16, pady=(0, 4))

        columns = [
            ("Invoice #", 110),
            ("Student Name", 140),
            ("Class", 90),
            ("Period", 70),
            ("Total (PKR)", 90),
            ("Paid", 90),
            ("Balance", 90),
            ("Status", 90),
            ("Due Date", 80),
            ("Actions", 160),
        ]
        for name, width in columns:
            lbl = ctk.CTkLabel(
                self.table_header_frame,
                text=name,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=self.colors["text_secondary"],
                width=width,
                anchor="w"
            )
            lbl.pack(side="left", padx=4, pady=6)

        # 4. Scrollable Table Frame
        self.table_scroll = ctk.CTkScrollableFrame(
            self, fg_color=self.colors["bg_card"], corner_radius=8
        )
        self.table_scroll.pack(fill="both", expand=True, padx=16, pady=(0, 16))

    def refresh_data(self) -> None:
        """Loads invoices matching filters and populates read-only rows."""
        if not self.db_conn:
            return

        for w in self.table_scroll.winfo_children():
            w.destroy()

        status_filter = self.status_var.get()
        search_term = self.search_entry.get().strip().lower()

        try:
            cur = self.db_conn.cursor()
            query = """
                SELECT 
                    fi.id,
                    'INV-' || SUBSTR('00000' || fi.id, -5) AS invoice_number,
                    s.first_name || ' ' || COALESCE(s.last_name, '') AS student_name,
                    cg.name || ' (' || cg.section_or_batch || ')' AS class_name,
                    fi.month_year AS period,
                    fi.total_payable,
                    fi.net_due,
                    fi.due_date,
                    fi.enrollment_id
                FROM fee_invoices fi
                JOIN enrollments e ON fi.enrollment_id = e.id
                JOIN students s ON e.student_id = s.id
                JOIN class_groups cg ON e.class_group_id = cg.id
                ORDER BY fi.id DESC LIMIT 100;
            """
            cur.execute(query)
            invoices = cur.fetchall()

            if not invoices:
                no_lbl = ctk.CTkLabel(
                    self.table_scroll,
                    text="No invoice records found. Generate monthly invoices to begin.",
                    font=ctk.CTkFont(size=13),
                    text_color=self.colors["text_muted"]
                )
                no_lbl.pack(pady=30)
                return

            for idx, inv in enumerate(invoices):
                inv_id, inv_num, s_name, c_name, period, tot_payable, net_due, due_date, enroll_id = inv
                if search_term and (search_term not in inv_num.lower() and search_term not in s_name.lower()):
                    continue

                fin = self.fee_service.calculate_invoice_balance(inv_id)
                status = fin["status"]
                total_dec = fin["net_due"]
                paid_dec = fin["total_paid"]
                balance_dec = fin["current_balance"]

                if status_filter == "Unpaid Only" and status != "Unpaid":
                    continue
                elif status_filter == "Partially Paid" and status != "Partially Paid":
                    continue
                elif status_filter == "Paid" and status != "Paid":
                    continue
                elif status_filter == "Defaulters Only":
                    if status not in ("Unpaid", "Partially Paid"):
                        continue

                bg = self.colors["bg_app"] if idx % 2 == 0 else self.colors["bg_row_alt"]
                row_frame = ctk.CTkFrame(self.table_scroll, fg_color=bg, corner_radius=4, height=36)
                row_frame.pack(fill="x", pady=2, padx=2)

                if status == "Paid":
                    stat_color = self.colors["status_paid"]
                elif status == "Partially Paid":
                    stat_color = self.colors["status_partial"]
                else:
                    stat_color = self.colors["status_unpaid"]

                fields = [
                    (inv_num, 110, self.colors["brand_accent"], "bold"),
                    (s_name, 140, self.colors["text_primary"], "normal"),
                    (c_name, 90, self.colors["text_secondary"], "normal"),
                    (period, 70, self.colors["text_secondary"], "normal"),
                    (f"{total_dec:,.0f}", 90, self.colors["text_primary"], "bold"),
                    (f"{paid_dec:,.0f}", 90, self.colors["status_paid"], "normal"),
                    (f"{balance_dec:,.0f}", 90, self.colors["status_unpaid"] if balance_dec > 0 else self.colors["text_secondary"], "bold"),
                    (status, 90, stat_color, "bold"),
                    (due_date, 80, self.colors["text_secondary"], "normal"),
                ]

                for val, width, color, weight in fields:
                    lbl = ctk.CTkLabel(
                        row_frame,
                        text=val,
                        width=width,
                        font=ctk.CTkFont(size=11, weight=weight),
                        text_color=color,
                        anchor="w"
                    )
                    lbl.pack(side="left", padx=4, pady=4)

                # Action buttons on right
                action_box = ctk.CTkFrame(row_frame, fg_color="transparent")
                action_box.pack(side="left", padx=4, pady=4)

                if balance_dec > 0:
                    btn_pay = ctk.CTkButton(
                        action_box,
                        text="💳 Pay",
                        width=60,
                        height=24,
                        fg_color=self.colors["brand_primary"],
                        hover_color=self.colors["brand_accent"],
                        font=ctk.CTkFont(size=11, weight="bold"),
                        command=lambda i=inv_id, n=inv_num, b=balance_dec: self._open_payment_modal(i, n, b)
                    )
                    btn_pay.pack(side="left", padx=2)

                btn_pdf = ctk.CTkButton(
                    action_box,
                    text="📄 Voucher",
                    width=75,
                    height=24,
                    fg_color=self.colors["border_color"],
                    hover_color=self.colors["brand_accent"],
                    font=ctk.CTkFont(size=11),
                    command=lambda i=inv_id: self._generate_voucher(i)
                )
                btn_pdf.pack(side="left", padx=2)

        except Exception as exc:
            logger.error(f"Error loading fee ledger: {exc}", exc_info=True)

    def _open_payment_modal(self, invoice_id: int, invoice_number: str, balance: Decimal) -> None:
        """Opens focus-trapped cash payment recording modal."""
        FeePaymentModal(self, invoice_id=invoice_id, invoice_number=invoice_number, balance=balance)

    def _open_generate_invoices_modal(self) -> None:
        """Opens batch invoice generation modal."""
        GenerateInvoicesModal(self)

    def _generate_voucher(self, invoice_id: int) -> None:
        """Generates single-sheet 3-panel A4 fee voucher PDF."""
        try:
            out_dir = os.path.join("data", "vouchers")
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, f"voucher_inv_{invoice_id}.pdf")

            inv_data = self.fee_service.get_invoice_details(invoice_id)
            if not inv_data:
                raise ValueError(f"Invoice id={invoice_id} could not be retrieved.")

            generate_fee_voucher_pdf(
                invoice_data=inv_data,
                output=out_path,
                institution_name="ClassFellow Grammar School"
            )
            self.show_info("Voucher Generated", f"3-Panel A4 Voucher generated successfully:\n{out_path}")
        except Exception as exc:
            self.show_error("Voucher Generation Failed", str(exc))


# =============================================================================
# Modal Dialogs: Collect Payment & Generate Invoices
# =============================================================================

class FeePaymentModal(BaseModal):
    """Focus-trapped dialog for recording cash fee payments."""

    def __init__(self, parent_view: FeeView, invoice_id: int, invoice_number: str, balance: Decimal):
        super().__init__(
            parent_view,
            title=f"Record Payment — {invoice_number}",
            width=460,
            height=340
        )
        self.parent_view = parent_view
        self.fee_service = parent_view.fee_service
        self.invoice_id = invoice_id
        self.balance = balance

        self._build_form(invoice_number)

    def _build_form(self, invoice_number: str) -> None:
        content = ctk.CTkFrame(self.card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=16, pady=8)

        # Balance display
        bal_lbl = ctk.CTkLabel(
            content,
            text=f"Remaining Balance: PKR {self.balance:,.2f}",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=THEME_COLORS["status_partial"]
        )
        bal_lbl.pack(anchor="w", pady=(0, 12))

        # Amount Entry
        ctk.CTkLabel(content, text="Payment Amount (PKR) *:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        self.amount_entry = ctk.CTkEntry(content, width=280)
        self.amount_entry.insert(0, str(self.balance))
        self.amount_entry.pack(anchor="w", pady=(2, 10))

        # Remarks Entry
        ctk.CTkLabel(content, text="Receipt Remarks (Optional):", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        self.remarks_entry = ctk.CTkEntry(content, placeholder_text="e.g. Cash collected at counter", width=280)
        self.remarks_entry.pack(anchor="w", pady=(2, 16))

        # Buttons
        btn_box = ctk.CTkFrame(self.card, fg_color="transparent")
        btn_box.pack(fill="x", padx=16, pady=(0, 16))

        btn_cancel = ctk.CTkButton(btn_box, text="Cancel", command=self.close, fg_color=THEME_COLORS["border_color"], width=90)
        btn_cancel.pack(side="right", padx=6)

        btn_save = ctk.CTkButton(
            btn_box, text="Save Receipt", command=self._submit_payment,
            fg_color=THEME_COLORS["brand_primary"], font=ctk.CTkFont(size=12, weight="bold"), width=120
        )
        btn_save.pack(side="right", padx=6)

    def _submit_payment(self) -> None:
        amt_str = self.amount_entry.get().strip()
        remarks = self.remarks_entry.get().strip() or None

        try:
            amt = Decimal(amt_str)
            if amt <= Decimal("0.00"):
                raise ValueError("Payment amount must be greater than zero.")
        except Exception as exc:
            self.parent_view.show_error("Invalid Amount", str(exc))
            return

        try:
            receipt_no = self.fee_service.record_payment(
                invoice_id=self.invoice_id,
                amount=amt,
                note=remarks
            )
            self.parent_view.show_info(
                "Payment Recorded",
                f"Receipt issued: {receipt_no}\nAmount: PKR {amt:,.2f}"
            )
            self.parent_view.refresh_data()
            self.close()
        except Exception as exc:
            self.parent_view.show_error("Payment Failed", str(exc))


class GenerateInvoicesModal(BaseModal):
    """Dialog to batch generate monthly invoices for a class group."""

    def __init__(self, parent_view: FeeView):
        super().__init__(parent_view, title="Generate Monthly Invoices", width=480, height=440)
        self.parent_view = parent_view
        self.fee_service = parent_view.fee_service
        self._build_form()

    def _build_form(self) -> None:
        content = ctk.CTkFrame(self.card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=16, pady=8)

        # Class Group
        ctk.CTkLabel(content, text="Select Class *:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        self.classes_map: Dict[str, int] = {}
        if self.parent_view.db_conn:
            cur = self.parent_view.db_conn.cursor()
            cur.execute("SELECT id, name, section_or_batch FROM class_groups ORDER BY name;")
            for r in cur.fetchall():
                self.classes_map[f"{r[1]} ({r[2]})"] = r[0]

        class_opts = list(self.classes_map.keys()) or ["None"]
        self.class_var = ctk.StringVar(value=class_opts[0])
        self.class_menu = ctk.CTkOptionMenu(content, values=class_opts, variable=self.class_var, width=280)
        self.class_menu.pack(anchor="w", pady=(2, 8))

        # Academic Session
        ctk.CTkLabel(content, text="Academic Session *:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        self.sessions_map: Dict[str, int] = {}
        if self.parent_view.db_conn:
            cur = self.parent_view.db_conn.cursor()
            cur.execute("SELECT id, name FROM academic_sessions WHERE is_active=1;")
            for r in cur.fetchall():
                self.sessions_map[r[1]] = r[0]

        sess_opts = list(self.sessions_map.keys()) or ["None"]
        self.sess_var = ctk.StringVar(value=sess_opts[0])
        self.sess_menu = ctk.CTkOptionMenu(content, values=sess_opts, variable=self.sess_var, width=280)
        self.sess_menu.pack(anchor="w", pady=(2, 8))

        # Month & Year
        now = datetime.now()
        ctk.CTkLabel(content, text="Month (1-12) & Year (YYYY):", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        my_frame = ctk.CTkFrame(content, fg_color="transparent")
        my_frame.pack(anchor="w", pady=(2, 8))
        self.month_entry = ctk.CTkEntry(my_frame, width=80)
        self.month_entry.insert(0, str(now.month))
        self.month_entry.pack(side="left", padx=(0, 8))
        self.year_entry = ctk.CTkEntry(my_frame, width=100)
        self.year_entry.insert(0, str(now.year))
        self.year_entry.pack(side="left")

        # Due Date
        ctk.CTkLabel(content, text="Due Date (YYYY-MM-DD):", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        self.due_entry = ctk.CTkEntry(content, width=200)
        self.due_entry.insert(0, f"{now.year}-{now.month:02d}-10")
        self.due_entry.pack(anchor="w", pady=(2, 16))

        # Buttons
        btn_box = ctk.CTkFrame(self.card, fg_color="transparent")
        btn_box.pack(fill="x", padx=16, pady=(0, 16))

        btn_cancel = ctk.CTkButton(btn_box, text="Cancel", command=self.close, fg_color=THEME_COLORS["border_color"], width=90)
        btn_cancel.pack(side="right", padx=6)

        btn_gen = ctk.CTkButton(
            btn_box, text="Generate", command=self._submit_generate,
            fg_color=THEME_COLORS["brand_primary"], font=ctk.CTkFont(size=12, weight="bold"), width=110
        )
        btn_gen.pack(side="right", padx=6)

    def _submit_generate(self) -> None:
        cid = self.classes_map.get(self.class_var.get())
        sid = self.sessions_map.get(self.sess_var.get())

        if not cid or not sid:
            self.parent_view.show_error("Selection Error", "Please select a valid class group and academic session.")
            return

        try:
            m = int(self.month_entry.get().strip())
            y = int(self.year_entry.get().strip())
            due = self.due_entry.get().strip()
        except Exception:
            self.parent_view.show_error("Validation Error", "Invalid month, year, or due date format.")
            return

        try:
            m_str = f"{y}-{m:02d}"
            issue_d = f"{y}-{m:02d}-01"
            valid_d = f"{y}-{m:02d}-20"
            created = self.fee_service.generate_monthly_invoices(
                session_id=sid,
                month_year=m_str,
                issue_date=issue_d,
                due_date=due,
                valid_until=valid_d
            )
            self.parent_view.show_info(
                "Invoices Generated",
                f"Generated {created} monthly fee invoices for billing cycle {m_str}."
            )
            self.parent_view.refresh_data()
            self.close()
        except Exception as exc:
            self.parent_view.show_error("Generation Failed", str(exc))
