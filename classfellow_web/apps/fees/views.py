"""
ClassFellow Web - Fees Application Views & PDF Streaming
Manages invoices, cashier payment processing, defaulters ledger, and in-memory A4 voucher streaming.
"""

import datetime
from decimal import Decimal
import io
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from app.reports.fee_voucher_generator import generate_fee_voucher_pdf
from apps.accounts.models import Role, User
from apps.core.models import AcademicSession, Campus, InstitutionProfile
from apps.fees.models import FeeInvoice, PaymentMethod
from apps.fees.reports import FeeExcelExportService
from apps.fees.services import CashierReconciliationService, FeeWebService
from apps.students.models import ClassGroup


@login_required
def fee_workspace_view(request: HttpRequest) -> HttpResponse:
    """Renders fee ledger, batch invoice generator, and overdue defaulters."""
    active_session = AcademicSession.objects.filter(is_active=True).first()
    sessions = AcademicSession.objects.all().order_by("-is_active", "-start_date")
    classes = ClassGroup.objects.all().order_by("name", "section_or_batch")

    current_month = datetime.date.today().strftime("%Y-%m")

    # Invoices list with live balances
    invoices_qs = (
        FeeInvoice.objects.select_related(
            "enrollment__student",
            "enrollment__class_group",
            "session",
        )
        .prefetch_related("items__fee_head", "payments")
        .order_by("-id")[:60]
    )

    invoices_with_balances = []
    for inv in invoices_qs:
        bal = FeeWebService.calculate_invoice_balance(inv)
        invoices_with_balances.append({
            "invoice": inv,
            "status": bal["status"],
            "total_paid": bal["total_paid"],
            "current_balance": bal["current_balance"],
        })

    # Defaulters list
    defaulters = []
    if active_session:
        defaulters = FeeWebService.get_defaulters_list(
            session_id=active_session.id,
            as_of_date=datetime.date.today(),
        )

    context = {
        "active_session": active_session,
        "sessions": sessions,
        "classes": classes,
        "current_month": current_month,
        "invoices": invoices_with_balances,
        "defaulters": defaulters,
        "payment_methods": PaymentMethod.choices,
        "today_str": datetime.date.today().isoformat(),
    }
    return render(request, "fees/fee_list.html", context)


@login_required
@require_http_methods(["POST"])
def record_payment_view(request: HttpRequest) -> HttpResponse:
    """Processes cashier payment submission inside an atomic transaction."""
    try:
        invoice_id = int(request.POST["invoice_id"])
        amount = Decimal(request.POST["amount"])
        payment_method = request.POST.get("payment_method", PaymentMethod.CASH)
        note = request.POST.get("note", "").strip()

        payment = FeeWebService.record_payment(
            invoice_id=invoice_id,
            amount=amount,
            payment_method=payment_method,
            recorded_by_user_id=request.user.id,
            note=note,
        )

        messages.success(
            request,
            f"Payment of Rs. {payment.amount:,.2f} recorded successfully! "
            f"Receipt Number: {payment.receipt_number}",
        )
    except Exception as e:
        messages.error(request, f"Payment failed: {str(e)}")

    return redirect("/fees/")


@login_required
@require_http_methods(["POST"])
def generate_invoices_view(request: HttpRequest) -> HttpResponse:
    """Generates monthly batch fee invoices."""
    try:
        session_id = int(request.POST["session_id"])
        month_year = request.POST["month_year"].strip()
        issue_date = datetime.date.fromisoformat(request.POST["issue_date"])
        due_date = datetime.date.fromisoformat(request.POST["due_date"])
        valid_until = datetime.date.fromisoformat(request.POST["valid_until"])
        late_fee = Decimal(request.POST.get("late_fee_surcharge", "200.00"))

        class_id_val = request.POST.get("class_group_id")
        class_group_id = int(class_id_val) if class_id_val else None

        count = FeeWebService.generate_monthly_invoices(
            session_id=session_id,
            month_year=month_year,
            issue_date=issue_date,
            due_date=due_date,
            valid_until=valid_until,
            late_fee_surcharge=late_fee,
            class_group_id=class_group_id,
        )

        messages.success(request, f"Successfully created {count} new fee invoice vouchers for {month_year}!")
    except Exception as e:
        messages.error(request, f"Invoice generation failed: {str(e)}")

    return redirect("/fees/")


@login_required
def stream_fee_voucher_pdf(request: HttpRequest, invoice_id: int) -> HttpResponse:
    """
    Renders and streams a 3-panel A4 fee voucher PDF in-memory via ReportLab and io.BytesIO.
    """
    invoice = (
        FeeInvoice.objects.select_related(
            "enrollment__student",
            "enrollment__class_group",
            "session",
        )
        .prefetch_related("items__fee_head")
        .filter(id=invoice_id)
        .first()
    )
    if not invoice:
        raise Http404("Fee invoice not found.")

    student = invoice.enrollment.student
    class_grp = invoice.enrollment.class_group
    institution = InstitutionProfile.objects.first()
    inst_name = institution.name if institution else "CLASSFELLOW HIGH SCHOOL & ACADEMY"

    items = []
    for item in invoice.items.all():
        items.append({
            "fee_head_name": item.fee_head.name,
            "urdu_name": item.fee_head.urdu_name,
            "amount": item.amount,
        })

    bal = FeeWebService.calculate_invoice_balance(invoice)

    invoice_data = {
        "id": invoice.id,
        "month_year": invoice.month_year,
        "issue_date": str(invoice.issue_date),
        "due_date": str(invoice.due_date),
        "valid_until": str(invoice.valid_until),
        "admission_number": student.admission_number,
        "first_name": student.first_name,
        "last_name": student.last_name,
        "full_name": f"{student.first_name} {student.last_name}".strip(),
        "student_urdu_name": student.urdu_name,
        "guardian_name": student.guardian_name,
        "guardian_phone": student.guardian_phone,
        "roll_number": invoice.enrollment.roll_number,
        "class_name": class_grp.name,
        "section_or_batch": class_grp.section_or_batch,
        "items": items,
        "total_payable": invoice.total_payable,
        "discount_amount": invoice.discount_amount,
        "late_fee_surcharge": invoice.late_fee_surcharge,
        "net_due": invoice.net_due,
        "current_balance": bal["current_balance"],
        "status": bal["status"],
    }

    pdf_buffer = io.BytesIO()
    generate_fee_voucher_pdf(
        invoice_data=invoice_data,
        output=pdf_buffer,
        institution_name=inst_name,
    )

    pdf_bytes = pdf_buffer.getvalue()
    pdf_buffer.close()

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="Fee_Voucher_{invoice.month_year}_{invoice.id}.pdf"'
    return response


@login_required
def reconciliation_view(request: HttpRequest) -> HttpResponse:
    """Renders cashier day-closing financial reconciliation summary and audit ledger."""
    date_str = request.GET.get("date", "").strip()
    if date_str:
        try:
            target_date = datetime.date.fromisoformat(date_str)
        except ValueError:
            target_date = datetime.date.today()
    else:
        target_date = datetime.date.today()

    cashier_id_val = request.GET.get("cashier_id", "").strip()
    cashier_id = int(cashier_id_val) if cashier_id_val.isdigit() else None

    campus_id_val = request.GET.get("campus_id", "").strip()
    campus_id = int(campus_id_val) if campus_id_val.isdigit() else None

    summary = CashierReconciliationService.generate_daily_closing_summary(
        target_date=target_date,
        user_id=cashier_id,
        campus_id=campus_id,
    )

    cashiers = User.objects.filter(role__in=[Role.CASHIER, Role.ADMIN]).order_by("username")
    campuses = Campus.objects.filter(is_active=True).order_by("name")
    institution = InstitutionProfile.objects.first()

    context = {
        "summary": summary,
        "target_date": target_date,
        "target_date_str": target_date.isoformat(),
        "selected_cashier_id": cashier_id,
        "selected_campus_id": campus_id,
        "cashiers": cashiers,
        "campuses": campuses,
        "institution": institution,
    }
    return render(request, "fees/reconciliation.html", context)


@login_required
def export_monthly_collection_xlsx(request: HttpRequest) -> HttpResponse:
    """Streams a styled openpyxl Excel spreadsheet for fee collection audit."""
    session_id_val = request.GET.get("session_id", "").strip()
    if session_id_val.isdigit():
        session_id = int(session_id_val)
    else:
        active_session = AcademicSession.objects.filter(is_active=True).first()
        session_id = active_session.id if active_session else 1

    month_year = request.GET.get("month_year", "").strip()
    if not month_year:
        month_year = datetime.date.today().strftime("%Y-%m")

    campus_id_val = request.GET.get("campus_id", "").strip()
    campus_id = int(campus_id_val) if campus_id_val.isdigit() else None

    xlsx_buffer = FeeExcelExportService.export_monthly_collection_workbook(
        session_id=session_id,
        month_year=month_year,
        campus_id=campus_id,
    )

    response = HttpResponse(
        xlsx_buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    filename = f"Monthly_Collection_{month_year}.xlsx"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
