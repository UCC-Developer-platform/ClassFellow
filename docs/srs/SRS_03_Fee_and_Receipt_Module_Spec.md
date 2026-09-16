# SRS 03: ClassFellow - Fee & Receipt Module Specification

## Document Information
- **Document Identifier**: `CF-SRS-03`
- **Project**: ClassFellow School and Academy Management Software
- **Version**: 1.0.0
- **Status**: APPROVED
- **Subsystem**: Billing, Invoicing, Cashier Receipts, Ledger & 3-Panel A4 Vouchers

---

## 1. Module Overview & Financial Principles

The Fee & Receipt module is the commercial core of ClassFellow. It governs fee structure definitions, monthly invoice generation, cashier payment collection, discount policies, defaulter reporting, and A4 printable bank/school voucher generation.

### 1.1 Strict Financial Rules
1. **Decimal Precision**: All arithmetic must use Python `decimal.Decimal` and SQLite `TEXT` storage. Floating-point types are strictly prohibited.
2. **Auditable Append-Only Ledger**: Payments are financial events. A recorded receipt can never be edited or silently deleted. Corrections require an explicit reversing transaction.
3. **Fact-Derived Payment Status**: Invoice status (`Unpaid`, `Partially Paid`, `Paid`) is calculated from underlying financial records rather than manually assigned.
4. **Relational Deletion Protection**: Payments enforce `ON DELETE RESTRICT` against invoices. An invoice cannot be deleted if a valid payment receipt has been issued.

---

## 2. Relational Database Schema Specification

### 2.1 Table DDL

```sql
-- Dynamic Fee Categories (e.g., Tuition, Lab, Admission, Library, Transport)
CREATE TABLE fee_heads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,             -- English label: 'Tuition Fee'
    urdu_name TEXT,                        -- Urdu label: 'ٹیوشن فیس'
    is_recurring INTEGER NOT NULL DEFAULT 1 CHECK (is_recurring IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (DATETIME('now'))
);

-- Master Fee Invoice Record
CREATE TABLE fee_invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    enrollment_id INTEGER NOT NULL,
    session_id INTEGER NOT NULL,
    month_year TEXT NOT NULL,              -- Billing cycle: 'YYYY-MM' (e.g. '2025-10')
    issue_date TEXT NOT NULL,              -- ISO-8601 YYYY-MM-DD
    due_date TEXT NOT NULL,                -- Tier 1 Due Date (e.g., 10th of month)
    valid_until TEXT NOT NULL,             -- Tier 2 Bank Expiry Date (e.g., 20th of month)
    late_fee_surcharge TEXT NOT NULL DEFAULT '0.00', -- Fine applied after due_date
    total_payable TEXT NOT NULL DEFAULT '0.00',      -- Sum of line items
    discount_amount TEXT NOT NULL DEFAULT '0.00',    -- Sibling/scholarship discount
    net_due TEXT NOT NULL DEFAULT '0.00',            -- total_payable - discount + late_fee
    created_at TEXT NOT NULL DEFAULT (DATETIME('now')),
    FOREIGN KEY (enrollment_id) REFERENCES enrollments(id) ON DELETE RESTRICT,
    FOREIGN KEY (session_id) REFERENCES academic_sessions(id) ON DELETE RESTRICT,
    UNIQUE(enrollment_id, month_year)
);

-- Itemized Breakdown Lines on Fee Vouchers
CREATE TABLE fee_invoice_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL,
    fee_head_id INTEGER NOT NULL,
    amount TEXT NOT NULL,                  -- Monetary value as TEXT Decimal
    created_at TEXT NOT NULL DEFAULT (DATETIME('now')),
    FOREIGN KEY (invoice_id) REFERENCES fee_invoices(id) ON DELETE CASCADE,
    FOREIGN KEY (fee_head_id) REFERENCES fee_heads(id) ON DELETE RESTRICT
);

-- Auditable Financial Payment Ledger
CREATE TABLE payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL,
    amount TEXT NOT NULL,                  -- Received amount as TEXT Decimal
    payment_date TEXT NOT NULL,            -- ISO-8601 YYYY-MM-DD
    receipt_number TEXT NOT NULL UNIQUE,   -- Sequential receipt: 'REC-2025-00142'
    payment_method TEXT NOT NULL DEFAULT 'Cash' CHECK (payment_method IN ('Cash', 'BankTransfer', 'OnlineDeposit', 'Cheque')),
    status TEXT NOT NULL DEFAULT 'Issued' CHECK (status IN ('Issued', 'Reversed', 'Cancelled')),
    reversal_reason TEXT,                  -- Required if status is Reversed/Cancelled
    recorded_by_user_id INTEGER,           -- Cashier / Admin User ID
    note TEXT,
    created_at TEXT NOT NULL DEFAULT (DATETIME('now')),
    FOREIGN KEY (invoice_id) REFERENCES fee_invoices(id) ON DELETE RESTRICT
);
```

### 2.2 Performance & Lookup Indexes

```sql
CREATE INDEX idx_fee_invoices_enrollment ON fee_invoices(enrollment_id);
CREATE INDEX idx_fee_invoices_cycle ON fee_invoices(month_year, session_id);
CREATE INDEX idx_fee_invoice_items_invoice ON fee_invoice_items(invoice_id);
CREATE INDEX idx_payments_invoice ON payments(invoice_id);
CREATE INDEX idx_payments_receipt_no ON payments(receipt_number);
```

---

## 3. Financial Calculation Rules & State Machine

### 3.1 Mathematical Formulation (`Decimal`)

For any given invoice:

$$\text{gross\_amount} = \sum (\text{fee\_invoice\_items.amount})$$
$$\text{total\_valid\_payments} = \sum (\text{payments.amount where status = 'Issued'})$$

$$\text{current\_balance} = \text{gross\_amount} - \text{discount\_amount} + \text{late\_fee} - \text{total\_valid\_payments}$$

### 3.2 Derived Status State Machine
- **`Unpaid`**: $\text{total\_valid\_payments} == 0 \land \text{current\_balance} > 0$
- **`Partially Paid`**: $\text{total\_valid\_payments} > 0 \land \text{current\_balance} > 0$
- **`Paid`**: $\text{current\_balance} == 0$
- **`Overpaid`**: $\text{current\_balance} < 0$ (Surplus credited to student account)

---

## 4. Pakistani Voucher Standards & Currency in Words

### 4.1 "Amount in Words" Generation (`num2words`)
All fee vouchers must print total payable amounts in words in both English and Urdu:

```python
# reports/currency_words.py
from num2words import num2words
from decimal import Decimal

def amount_in_words_en(amount: Decimal) -> str:
    rupees = int(amount)
    words = num2words(rupees, lang="en").replace("-", " ").title()
    return f"In Words: {words} Rupees Only"
```

---

## 5. ReportLab 3-Panel A4 Voucher Geometry & Urdu Shaping Pipeline

### 5.1 A4 Sheet Geometry Breakdown
- **Page Size**: Standard Portrait A4 ($595.27 \times 841.89$ points).
- **3 Horizontal Panels**: Each panel occupies ~270 points in height with 10pt margins.
  1. **Top Panel**: *School Copy* (Office copy archived in accounts register).
  2. **Middle Panel**: *Accounts / Bank Copy* (Surrendered to bank or school cashier).
  3. **Bottom Panel**: *Student / Parent Copy* (Retained by parent).
- **Dashed Cut Lines**: Separated by dashed rules `- - - ✂ Cut Here (یہاں سے کاٹیں) - - -`.

### 5.2 Urdu Ligature Shaping Pipeline (`arabic-reshaper` + `python-bidi`)
ReportLab requires pre-shaped glyphs and reversed bidirectional text for correct RTL rendering:

```python
# reports/urdu_formatter.py
import arabic_reshaper
from bidi.algorithm import get_display

def format_urdu(text: str) -> str:
    """Prepares Urdu strings for ReportLab PDF rendering with joint cursive ligatures."""
    if not text:
        return ""
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)
```

---

## 6. Service Layer Contracts (`services/fee_service.py`)

### 6.1 Core API Methods

1. `generate_monthly_invoices(session_id: int, month_year: str, due_date: str, valid_until: str) -> int`
   - Queries all active enrollments for the session.
   - Computes base tuition and standard recurring fee heads.
   - Subtracts student's approved `custom_discount_amount`.
   - Inserts `fee_invoices` and itemized `fee_invoice_items` inside a single atomic transaction.

2. `record_payment(invoice_id: int, amount: Decimal, payment_method: str, user_id: int, note: str = "") -> str`
   - Generates unique sequential receipt number (`REC-YYYY-XXXXX`).
   - Validates that amount does not violate payment policy.
   - Inserts payment record into ledger with status `Issued`.
   - Returns unique receipt number.

3. `reverse_payment(payment_id: int, reason: str, user_id: int) -> None`
   - Sets payment status to `Reversed`.
   - Records reversal reason and admin audit details.

4. `get_defaulters_list(session_id: int, month_year: str) -> list[dict]`
   - Queries students with active overdue balances after `valid_until`.
