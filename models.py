"""
ClassFellow - Core Data Transfer Objects (DTOs)
================================================
Immutable dataclasses used across domain services and UI layers.
"""

from dataclasses import dataclass
from typing import Optional
from decimal import Decimal


# --- Student & Enrollment DTOs ---
@dataclass(frozen=True)
class StudentDTO:
    id: Optional[int]
    admission_number: str
    first_name: str
    last_name: Optional[str]
    urdu_name: Optional[str]
    gender: str
    guardian_name: str
    guardian_urdu_name: Optional[str]
    guardian_phone: str
    residential_address: Optional[str] = None
    is_active: bool = True


@dataclass(frozen=True)
class EnrollmentDTO:
    id: Optional[int]
    student_id: int
    class_group_id: int
    session_id: int
    roll_number: Optional[str]
    enrollment_date: str
    status: str = "Active"
    custom_discount_amount: Decimal = Decimal("0.00")


# --- Fee & Receipt DTOs ---
@dataclass(frozen=True)
class FeeHeadDTO:
    id: Optional[int]
    name: str
    urdu_name: Optional[str]
    is_recurring: bool = True


@dataclass(frozen=True)
class FeeInvoiceItemDTO:
    id: Optional[int]
    invoice_id: int
    fee_head_id: int
    fee_head_name: str
    amount: Decimal


@dataclass(frozen=True)
class FeeInvoiceDTO:
    id: Optional[int]
    enrollment_id: int
    session_id: int
    month_year: str
    issue_date: str
    due_date: str
    valid_until: str
    late_fee_surcharge: Decimal
    total_payable: Decimal
    discount_amount: Decimal
    net_due: Decimal
    status: str = "Unpaid"
    items: tuple[FeeInvoiceItemDTO, ...] = ()


@dataclass(frozen=True)
class PaymentDTO:
    id: Optional[int]
    invoice_id: int
    amount: Decimal
    payment_date: str
    receipt_number: str
    payment_method: str = "Cash"
    status: str = "Issued"
    recorded_by_user_id: Optional[int] = None
    note: Optional[str] = None


# --- Attendance DTOs ---
@dataclass(frozen=True)
class AttendanceEntryDTO:
    enrollment_id: int
    student_name: str
    roll_number: Optional[str]
    status: str  # 'Present', 'Absent', 'Late', 'Leave'
    reason_note: Optional[str] = None


@dataclass(frozen=True)
class AttendanceSummaryDTO:
    enrollment_id: int
    total_days: int
    present_days: int
    absent_days: int
    leave_days: int
    late_days: int
    percentage: float
