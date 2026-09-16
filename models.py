"""
ClassFellow - Core Data Transfer Objects (DTOs)
================================================
Immutable dataclasses used across domain services and UI layers.
"""

from dataclasses import dataclass
from typing import Optional
from decimal import Decimal


# --- Academic Session & Class Group DTOs ---
@dataclass(frozen=True)
class AcademicSessionDTO:
    id: Optional[int] = None
    name: str = ""
    start_date: str = ""
    end_date: str = ""
    is_active: bool = True


@dataclass(frozen=True)
class ClassGroupDTO:
    id: Optional[int] = None
    session_id: int = 0
    name: str = ""
    section_or_batch: str = ""
    group_type: str = "SchoolClass"  # 'SchoolClass' or 'AcademyBatch'
    monthly_tuition_fee: Decimal = Decimal("0.00")


# --- Student & Enrollment DTOs ---
@dataclass(frozen=True)
class StudentDTO:
    id: Optional[int] = None
    admission_number: str = ""
    first_name: str = ""
    last_name: Optional[str] = None
    urdu_name: Optional[str] = None
    gender: str = "Male"
    date_of_birth: Optional[str] = None
    b_form_number: Optional[str] = None
    guardian_name: str = ""
    guardian_urdu_name: Optional[str] = None
    guardian_relation: str = "Father"
    guardian_phone: str = ""
    guardian_whatsapp: Optional[str] = None
    guardian_cnic: Optional[str] = None
    residential_address: Optional[str] = None
    emergency_contact: Optional[str] = None
    is_active: bool = True


@dataclass(frozen=True)
class EnrollmentDTO:
    id: Optional[int] = None
    student_id: int = 0
    class_group_id: int = 0
    session_id: int = 0
    roll_number: Optional[str] = None
    enrollment_date: str = ""
    status: str = "Active"  # 'Active', 'Transferred', 'Withdrawn', 'Graduated'
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
