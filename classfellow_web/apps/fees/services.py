"""
ClassFellow Web - Fee Domain Web Service (FeeWebService)
Implements business logic for fee structures, itemized batch invoicing,
concurrency-safe cashier payments with sequential receipts, and defaulters ledger queries.
"""

import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.db import transaction
from django.db.models import F, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.core.models import AcademicSession
from apps.fees.models import (
    FeeHead,
    FeeInvoice,
    FeeInvoiceItem,
    Payment,
    PaymentMethod,
    PaymentStatus,
)
from apps.students.models import Enrollment, EnrollmentStatus


class FeeWebService:
    """Encapsulates fee management, itemized invoicing, and payment ledger workflows."""

    @staticmethod
    def generate_next_receipt_number(year: Optional[int] = None) -> str:
        """
        Generates the next sequential receipt number for the given calendar year.
        Format: 'REC-YYYY-XXXXX' (e.g., 'REC-2026-00001').
        Must be invoked inside an atomic transaction.
        """
        if year is None:
            year = datetime.date.today().year

        prefix = f"REC-{year}-"
        last_payment = (
            Payment.objects.select_for_update()
            .filter(receipt_number__startswith=prefix)
            .order_by("-id")
            .first()
        )
        if not last_payment:
            return f"{prefix}00001"

        try:
            parts = last_payment.receipt_number.split("-")
            seq = int(parts[-1])
            return f"{prefix}{seq + 1:05d}"
        except (ValueError, IndexError):
            return f"{prefix}00001"

    @classmethod
    @transaction.atomic
    def generate_monthly_invoices(
        cls,
        session_id: int,
        month_year: str,
        issue_date: datetime.date,
        due_date: datetime.date,
        valid_until: datetime.date,
        late_fee_surcharge: Decimal = Decimal("200.00"),
        specific_enrollment_id: Optional[int] = None,
        class_group_id: Optional[int] = None,
    ) -> int:
        """
        Generates itemized fee vouchers for enrolled students inside an atomic transaction.
        Skips enrollments that already have an invoice generated for the same month_year.
        """
        enrollments_qs = Enrollment.objects.filter(
            session_id=session_id,
            status=EnrollmentStatus.ACTIVE,
        ).select_related("class_group", "student")

        if specific_enrollment_id is not None:
            enrollments_qs = enrollments_qs.filter(id=specific_enrollment_id)

        if class_group_id is not None:
            enrollments_qs = enrollments_qs.filter(class_group_id=class_group_id)

        # Exclude enrollments with existing invoice for this month
        existing_enrollment_ids = set(
            FeeInvoice.objects.filter(
                session_id=session_id,
                month_year=month_year,
            ).values_list("enrollment_id", flat=True)
        )

        tuition_head, _ = FeeHead.objects.get_or_create(
            name="Tuition Fee",
            defaults={"urdu_name": "ٹیوشن فیس", "is_recurring": True},
        )

        invoices_to_create = []
        items_to_create = []
        created_count = 0

        for enrollment in enrollments_qs:
            if enrollment.id in existing_enrollment_ids:
                continue

            tuition_amount = enrollment.class_group.monthly_tuition_fee
            discount = enrollment.custom_discount_amount
            total_payable = tuition_amount
            discount_amount = discount
            net_due = max(Decimal("0.00"), total_payable - discount_amount)

            invoice = FeeInvoice(
                enrollment=enrollment,
                session_id=session_id,
                month_year=month_year,
                issue_date=issue_date,
                due_date=due_date,
                valid_until=valid_until,
                late_fee_surcharge=late_fee_surcharge,
                total_payable=total_payable,
                discount_amount=discount_amount,
                net_due=net_due,
            )
            invoices_to_create.append((invoice, tuition_amount))

        for invoice, tuition_amount in invoices_to_create:
            invoice.save()
            created_count += 1
            FeeInvoiceItem.objects.create(
                invoice=invoice,
                fee_head=tuition_head,
                amount=tuition_amount,
            )

        return created_count

    @classmethod
    @transaction.atomic
    def record_payment(
        cls,
        invoice_id: int,
        amount: Decimal,
        payment_date: Optional[datetime.date] = None,
        payment_method: str = PaymentMethod.CASH,
        receipt_number: Optional[str] = None,
        recorded_by_user_id: Optional[int] = None,
        note: str = "",
    ) -> Payment:
        """
        Concurrency-safe payment recording with sequential receipt numbering.
        """
        if amount <= Decimal("0.00"):
            raise ValueError(f"Payment amount must be greater than zero. Received: {amount}")

        invoice = FeeInvoice.objects.select_for_update().filter(id=invoice_id).first()
        if not invoice:
            raise ValueError(f"FeeInvoice id={invoice_id} does not exist.")

        if not receipt_number or not receipt_number.strip():
            year = payment_date.year if payment_date else timezone.now().year
            receipt_number = cls.generate_next_receipt_number(year)
        else:
            receipt_number = receipt_number.strip()
            if Payment.objects.filter(receipt_number=receipt_number).exists():
                raise ValueError(f"Receipt number '{receipt_number}' already exists.")

        payment = Payment.objects.create(
            invoice=invoice,
            amount=amount,
            payment_date=payment_date or timezone.now().date(),
            payment_method=payment_method,
            receipt_number=receipt_number,
            status=PaymentStatus.ISSUED,
            recorded_by_user_id=recorded_by_user_id,
            note=note.strip() if note else "",
        )

        return payment

    @staticmethod
    def calculate_invoice_balance(invoice: Any) -> Dict[str, Any]:
        """
        Calculates total payments and remaining balance for an invoice.
        Derives status: 'Unpaid', 'Partially Paid', 'Paid', 'Overpaid'.
        """
        if isinstance(invoice, (int, str)):
            inv = FeeInvoice.objects.filter(id=int(invoice)).first()
            if not inv:
                raise ValueError(f"FeeInvoice id={invoice} not found.")
        else:
            inv = invoice

        payments_agg = (
            Payment.objects.filter(invoice=inv, status=PaymentStatus.ISSUED)
            .aggregate(total_paid=Coalesce(Sum("amount"), Decimal("0.00")))
        )
        total_paid = payments_agg["total_paid"]
        current_balance = max(Decimal("0.00"), inv.net_due - total_paid)

        if total_paid == Decimal("0.00"):
            status = "Unpaid"
        elif total_paid < inv.net_due:
            status = "Partially Paid"
        elif total_paid == inv.net_due:
            status = "Paid"
        else:
            status = "Overpaid"

        return {
            "invoice_id": inv.id,
            "month_year": inv.month_year,
            "total_payable": inv.total_payable,
            "discount_amount": inv.discount_amount,
            "net_due": inv.net_due,
            "total_paid": total_paid,
            "current_balance": current_balance,
            "status": status,
        }

    @staticmethod
    def get_defaulters_list(
        session_id: Optional[int] = None,
        class_group_id: Optional[int] = None,
        as_of_date: Optional[datetime.date] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves active student invoices that remain unpaid or partially paid past valid_until.
        """
        if as_of_date is None:
            as_of_date = timezone.now().date()

        invoices_qs = (
            FeeInvoice.objects.filter(
                valid_until__lte=as_of_date,
                enrollment__status=EnrollmentStatus.ACTIVE,
            )
            .select_related("enrollment", "enrollment__student", "enrollment__class_group", "session")
            .annotate(
                total_paid=Coalesce(
                    Sum("payments__amount", filter=Q(payments__status=PaymentStatus.ISSUED)),
                    Decimal("0.00"),
                )
            )
            .filter(total_paid__lt=F("net_due"))
        )

        if session_id is not None:
            invoices_qs = invoices_qs.filter(session_id=session_id)

        if class_group_id is not None:
            invoices_qs = invoices_qs.filter(enrollment__class_group_id=class_group_id)

        defaulters = []
        for inv in invoices_qs.order_by("valid_until", "enrollment__roll_number"):
            balance = inv.net_due - inv.total_paid
            defaulters.append(
                {
                    "invoice_id": inv.id,
                    "student_id": inv.enrollment.student.id,
                    "admission_number": inv.enrollment.student.admission_number,
                    "student_name": f"{inv.enrollment.student.first_name} {inv.enrollment.student.last_name}".strip(),
                    "urdu_name": inv.enrollment.student.urdu_name,
                    "guardian_name": inv.enrollment.student.guardian_name,
                    "guardian_phone": inv.enrollment.student.guardian_phone,
                    "class_name": inv.enrollment.class_group.name,
                    "section": inv.enrollment.class_group.section_or_batch,
                    "month_year": inv.month_year,
                    "valid_until": inv.valid_until,
                    "net_due": inv.net_due,
                    "total_paid": inv.total_paid,
                    "balance": balance,
                }
            )

        return defaulters
