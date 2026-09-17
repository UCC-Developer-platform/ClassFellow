from django.conf import settings
from django.db import models
from django.utils import timezone


class PaymentMethod(models.TextChoices):
    CASH = "Cash", "Cash"
    BANK_TRANSFER = "BankTransfer", "Bank Transfer"
    ONLINE_DEPOSIT = "OnlineDeposit", "Online Deposit"
    CHEQUE = "Cheque", "Cheque"


class PaymentStatus(models.TextChoices):
    ISSUED = "Issued", "Issued"
    REVERSED = "Reversed", "Reversed"
    CANCELLED = "Cancelled", "Cancelled"


class FeeHead(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text="Tuition, Admission, Lab, etc.")
    urdu_name = models.CharField(max_length=150, blank=True, default="")
    is_recurring = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "fee_heads"
        verbose_name = "Fee Head"
        verbose_name_plural = "Fee Heads"

    def __str__(self):
        return self.name


class FeeInvoice(models.Model):
    enrollment = models.ForeignKey(
        "students.Enrollment",
        on_delete=models.RESTRICT,
        related_name="invoices",
    )
    session = models.ForeignKey(
        "core.AcademicSession",
        on_delete=models.RESTRICT,
        related_name="invoices",
    )
    month_year = models.CharField(max_length=10, help_text="Billing cycle (YYYY-MM).")
    issue_date = models.DateField()
    due_date = models.DateField()
    valid_until = models.DateField()
    late_fee_surcharge = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_payable = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    net_due = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "fee_invoices"
        verbose_name = "Fee Invoice"
        verbose_name_plural = "Fee Invoices"
        constraints = [
            models.UniqueConstraint(
                fields=["enrollment", "month_year"],
                name="uq_fee_invoices_enrollment_month",
            ),
        ]
        indexes = [
            models.Index(fields=["enrollment"], name="idx_fee_invoices_enrollment"),
            models.Index(fields=["month_year", "session"], name="idx_fee_invoices_cycle"),
            models.Index(fields=["valid_until"], name="idx_fee_invoices_valid_until"),
            models.Index(fields=["session", "valid_until"], name="idx_fee_invoices_session_valid"),
        ]

    def __str__(self):
        return f"Invoice #{self.pk} - {self.enrollment.student.admission_number} ({self.month_year})"


class FeeInvoiceItem(models.Model):
    invoice = models.ForeignKey(
        FeeInvoice,
        on_delete=models.CASCADE,
        related_name="items",
    )
    fee_head = models.ForeignKey(
        FeeHead,
        on_delete=models.RESTRICT,
        related_name="invoice_items",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "fee_invoice_items"
        verbose_name = "Fee Invoice Item"
        verbose_name_plural = "Fee Invoice Items"
        indexes = [
            models.Index(fields=["invoice"], name="idx_fee_invoice_items_invoice"),
        ]

    def __str__(self):
        return f"{self.fee_head.name}: Rs {self.amount}"


class Payment(models.Model):
    invoice = models.ForeignKey(
        FeeInvoice,
        on_delete=models.RESTRICT,
        related_name="payments",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateField(default=timezone.now)
    receipt_number = models.CharField(max_length=50, unique=True)
    payment_method = models.CharField(
        max_length=30,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
    )
    status = models.CharField(
        max_length=30,
        choices=PaymentStatus.choices,
        default=PaymentStatus.ISSUED,
    )
    reversal_reason = models.TextField(blank=True, default="")
    recorded_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_payments",
    )
    note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payments"
        verbose_name = "Payment Receipt"
        verbose_name_plural = "Payment Receipts"
        indexes = [
            models.Index(fields=["invoice"], name="idx_payments_invoice"),
            models.Index(fields=["invoice", "status", "amount"], name="idx_payments_inv_status_amt"),
            models.Index(fields=["receipt_number"], name="idx_payments_receipt_no"),
        ]

    def __str__(self):
        return f"{self.receipt_number} - Rs {self.amount} ({self.status})"
