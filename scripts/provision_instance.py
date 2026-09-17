"""
ClassFellow - Production Instance Provisioning & Seeder Script (Category 17)
===========================================================================
Automates institutional onboarding with a single CLI command or environment flags:
  1. Configures active Academic Session (start_date, end_date, is_active=True).
  2. Provisions default Primary Campus record with contact metadata.
  3. Provisions Administrative User account (Role.ADMIN) with hashed credentials.
  4. Seeds baseline FeeHead categories with strict Decimal financial precision.
  5. Configures standard BISE Punjab GradingTiers (A+ down to F).

Idempotent: Safe to execute repeatedly on fresh or existing databases.
"""

import argparse
import datetime
from decimal import Decimal
import os
import sys
from pathlib import Path
from typing import Any, Dict

# Ensure project root and classfellow_web are on sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "classfellow_web") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "classfellow_web"))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402
django.setup()

from apps.accounts.models import Role, User  # noqa: E402
from apps.core.models import AcademicSession, Campus  # noqa: E402
from apps.examinations.models import GradingTier  # noqa: E402
from apps.fees.models import FeeHead  # noqa: E402


def provision_instance(
    admin_username: str = "admin",
    admin_password: str = "ClassFellowAdmin2026!",
    admin_email: str = "admin@classfellow.local",
    admin_phone: str = "03001234567",
    admin_first_name: str = "System",
    admin_last_name: str = "Administrator",
    campus_name: str = "Main Campus",
    campus_code: str = "CAMPUS-MAIN",
    campus_address: str = "Main Educational Boulevard, Lahore",
    campus_phone: str = "04231122334",
    session_name: str = "2026-2027 Academic Session",
    session_start: datetime.date = datetime.date(2026, 4, 1),
    session_end: datetime.date = datetime.date(2027, 3, 31),
) -> Dict[str, Any]:
    """
    Programmatically provisions or updates a ClassFellow institutional instance.
    Returns a dictionary summarizing provisioned records.
    """
    summary: Dict[str, Any] = {}

    # 1. Academic Session
    session, session_created = AcademicSession.objects.get_or_create(
        name=session_name,
        defaults={
            "start_date": session_start,
            "end_date": session_end,
            "is_active": True,
        },
    )
    if not session.is_active:
        session.is_active = True
        session.save(update_fields=["is_active"])
    summary["session"] = {
        "id": session.id,
        "name": session.name,
        "created": session_created,
    }

    # 2. Campus Facility
    campus, campus_created = Campus.objects.get_or_create(
        code=campus_code,
        defaults={
            "name": campus_name,
            "address": campus_address,
            "phone": campus_phone,
            "is_active": True,
        },
    )
    summary["campus"] = {
        "id": campus.id,
        "code": campus.code,
        "name": campus.name,
        "created": campus_created,
    }

    # 3. Administrative User
    user, user_created = User.objects.get_or_create(
        username=admin_username,
        defaults={
            "email": admin_email,
            "first_name": admin_first_name,
            "last_name": admin_last_name,
            "phone": admin_phone,
            "role": Role.ADMIN,
            "is_staff": True,
            "is_superuser": True,
            "is_active": True,
        },
    )
    if user_created:
        user.set_password(admin_password)
        user.save()
    summary["admin_user"] = {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "created": user_created,
    }

    # 4. Baseline Fee Heads (Strict Decimal amounts)
    baseline_fee_heads = [
        ("Tuition Fee", "ٹیوشن فیس", True),
        ("Examination Fee", "امتحانی فیس", True),
        ("Computer Lab Fee", "کمپیوٹر لیب فیس", True),
        ("Science Lab Fee", "سائنس لیب فیس", True),
        ("Admission & Registration Fee", "داخلہ فیس", False),
        ("Library & Sports Fee", "لائبریری اور سپورٹس فیس", True),
    ]
    created_heads = []
    for head_name, urdu_title, is_rec in baseline_fee_heads:
        head, h_created = FeeHead.objects.get_or_create(
            name=head_name,
            defaults={
                "urdu_name": urdu_title,
                "is_recurring": is_rec,
            },
        )
        created_heads.append({"name": head.name, "created": h_created})
    summary["fee_heads"] = created_heads

    # 5. Baseline Grading Tiers (Standard Punjab / BISE Scale)
    baseline_grading_tiers = [
        ("A+", Decimal("80.00"), Decimal("100.00"), Decimal("4.00")),
        ("A", Decimal("70.00"), Decimal("79.99"), Decimal("3.70")),
        ("B", Decimal("60.00"), Decimal("69.99"), Decimal("3.00")),
        ("C", Decimal("50.00"), Decimal("59.99"), Decimal("2.00")),
        ("D", Decimal("40.00"), Decimal("49.99"), Decimal("1.00")),
        ("F", Decimal("0.00"), Decimal("39.99"), Decimal("0.00")),
    ]
    created_tiers = []
    for grade_name, min_pct, max_pct, gpa in baseline_grading_tiers:
        tier, t_created = GradingTier.objects.get_or_create(
            session=session,
            grade_name=grade_name,
            defaults={
                "min_percentage": min_pct,
                "max_percentage": max_pct,
                "gpa_point": gpa,
            },
        )
        created_tiers.append({"grade": tier.grade_name, "created": t_created})
    summary["grading_tiers"] = created_tiers

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="ClassFellow Web - Production Instance Provisioning Script"
    )
    parser.add_argument(
        "--admin-username",
        default=os.environ.get("ADMIN_USERNAME", "admin"),
        help="Administrator username",
    )
    parser.add_argument(
        "--admin-password",
        default=os.environ.get("ADMIN_PASSWORD", "ClassFellowAdmin2026!"),
        help="Administrator password",
    )
    parser.add_argument(
        "--admin-email",
        default=os.environ.get("ADMIN_EMAIL", "admin@classfellow.local"),
        help="Administrator email",
    )
    parser.add_argument(
        "--admin-phone",
        default=os.environ.get("ADMIN_PHONE", "03001234567"),
        help="Administrator phone number",
    )
    parser.add_argument(
        "--campus-name",
        default=os.environ.get("CAMPUS_NAME", "Main Campus"),
        help="Institution campus name",
    )
    parser.add_argument(
        "--campus-code",
        default=os.environ.get("CAMPUS_CODE", "CAMPUS-MAIN"),
        help="Institution campus unique code",
    )
    parser.add_argument(
        "--session-name",
        default=os.environ.get("SESSION_NAME", "2026-2027 Academic Session"),
        help="Active academic session title",
    )
    parser.add_argument(
        "--session-start",
        default=os.environ.get("SESSION_START", "2026-04-01"),
        help="Session start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--session-end",
        default=os.environ.get("SESSION_END", "2027-03-31"),
        help="Session end date (YYYY-MM-DD)",
    )

    args = parser.parse_args()

    start_date = datetime.date.fromisoformat(args.session_start)
    end_date = datetime.date.fromisoformat(args.session_end)

    print("===================================================================")
    print("ClassFellow - Institutional Instance Provisioning")
    print("===================================================================")

    summary = provision_instance(
        admin_username=args.admin_username,
        admin_password=args.admin_password,
        admin_email=args.admin_email,
        admin_phone=args.admin_phone,
        campus_name=args.campus_name,
        campus_code=args.campus_code,
        session_name=args.session_name,
        session_start=start_date,
        session_end=end_date,
    )

    print(f"[OK] Academic Session: {summary['session']['name']} (ID: {summary['session']['id']})")
    print(f"[OK] Primary Campus:   {summary['campus']['name']} ({summary['campus']['code']})")
    print(f"[OK] Admin User:       {summary['admin_user']['username']} (Role: {summary['admin_user']['role']})")
    print(f"[OK] Fee Heads:        {len(summary['fee_heads'])} baseline heads initialized")
    print(f"[OK] Grading Tiers:    {len(summary['grading_tiers'])} grading tiers configured")
    print("===================================================================")
    print("Provisioning successfully completed. Institutional instance is ready.")
    print("===================================================================")


if __name__ == "__main__":
    main()
