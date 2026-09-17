"""
ClassFellow Web - Staff Views
Provides views for staff directory, filtering, and staff registration.
"""

import datetime
from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.decorators import role_required
from apps.accounts.models import Role
from apps.core.models import Campus
from apps.staff.models import Staff
from apps.students.services import normalize_pakistan_phone


@role_required([Role.ADMIN, Role.PRINCIPAL])
def staff_list_view(request: HttpRequest) -> HttpResponse:
    """Renders the searchable staff management directory with campus filtering and status toggles."""
    query = request.GET.get("q", "").strip()
    campus_id_str = request.GET.get("campus_id", "").strip()
    status_filter = request.GET.get("status", "active").strip().lower()

    qs = Staff.objects.select_related("campus", "user").all()

    # Search filter
    if query:
        qs = qs.filter(
            Q(employee_id__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(urdu_name__icontains=query)
            | Q(phone__icontains=query)
            | Q(designation__icontains=query)
            | Q(department__icontains=query)
        )

    # Campus filter
    selected_campus_id = None
    if campus_id_str.isdigit():
        selected_campus_id = int(campus_id_str)
        qs = qs.filter(campus_id=selected_campus_id)

    # Status filter
    if status_filter == "active":
        qs = qs.filter(is_active=True)
    elif status_filter == "inactive":
        qs = qs.filter(is_active=False)

    staff_members = qs.order_by("employee_id")
    campuses = Campus.objects.filter(is_active=True).order_by("name")

    # KPI Aggregates
    total_staff = Staff.objects.count()
    active_staff = Staff.objects.filter(is_active=True).count()
    total_payroll = Staff.objects.filter(is_active=True).aggregate(
        val=Coalesce(Sum("basic_salary"), Decimal("0.00"))
    )["val"]

    # Suggested next employee code
    next_emp_num = total_staff + 1001
    suggested_employee_id = f"EMP-{next_emp_num}"

    context = {
        "staff_members": staff_members,
        "campuses": campuses,
        "query": query,
        "selected_campus_id": selected_campus_id,
        "selected_status": status_filter,
        "total_staff": total_staff,
        "active_staff": active_staff,
        "total_payroll": total_payroll,
        "suggested_employee_id": suggested_employee_id,
    }
    return render(request, "staff/staff_list.html", context)


@role_required([Role.ADMIN, Role.PRINCIPAL])
def staff_create_view(request: HttpRequest) -> HttpResponse:
    """Handles atomic staff member registration with phone normalization and salary validation."""
    if request.method != "POST":
        return redirect("/staff/")

    employee_id = request.POST.get("employee_id", "").strip().upper()
    first_name = request.POST.get("first_name", "").strip()
    last_name = request.POST.get("last_name", "").strip()
    urdu_name = request.POST.get("urdu_name", "").strip()
    designation = request.POST.get("designation", "").strip()
    department = request.POST.get("department", "").strip() or "Administration"
    campus_id_str = request.POST.get("campus_id", "").strip()
    raw_phone = request.POST.get("phone", "").strip()
    email = request.POST.get("email", "").strip()
    national_id_cnic = request.POST.get("national_id_cnic", "").strip()
    basic_salary_str = request.POST.get("basic_salary", "0.00").strip()
    joining_date_str = request.POST.get("joining_date", "").strip()

    # Mandatory field checks
    if not employee_id or not first_name or not designation or not campus_id_str or not raw_phone:
        messages.error(request, "Required fields missing: Employee ID, First Name, Designation, Campus, and Phone.")
        return redirect("/staff/")

    # Uniqueness check
    if Staff.objects.filter(employee_id=employee_id).exists():
        messages.error(request, f"Employee ID '{employee_id}' is already registered in the system.")
        return redirect("/staff/")

    # Phone normalization
    try:
        normalized_phone = normalize_pakistan_phone(raw_phone)
    except ValueError as err:
        messages.error(request, str(err))
        return redirect("/staff/")

    # Salary parsing
    try:
        salary = Decimal(basic_salary_str)
        if salary < Decimal("0.00"):
            raise ValueError("Salary cannot be negative.")
    except (InvalidOperation, ValueError):
        messages.error(request, f"Invalid basic salary amount: '{basic_salary_str}'. Must be a valid positive number.")
        return redirect("/staff/")

    # Campus lookup
    campus = get_object_or_404(Campus, id=int(campus_id_str))

    # Joining date
    joining_date = None
    if joining_date_str:
        try:
            joining_date = datetime.date.fromisoformat(joining_date_str)
        except ValueError:
            messages.error(request, "Invalid joining date format. Use YYYY-MM-DD.")
            return redirect("/staff/")

    # Atomic creation
    with transaction.atomic():
        staff = Staff.objects.create(
            employee_id=employee_id,
            first_name=first_name,
            last_name=last_name,
            urdu_name=urdu_name,
            designation=designation,
            department=department,
            campus=campus,
            phone=normalized_phone,
            email=email,
            national_id_cnic=national_id_cnic,
            basic_salary=salary,
            joining_date=joining_date,
            is_active=True,
        )

    messages.success(
        request,
        f"Staff member {staff.full_name} ({staff.employee_id}) successfully registered.",
    )
    return redirect("/staff/")
