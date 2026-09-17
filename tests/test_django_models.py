"""
ClassFellow - Django ORM Relational Models & Schema Alignment Verification Tests
Ensures that all Django 5 models, fields, precision, constraints, and indexes
mirror database/postgres/schema_v1_postgres.sql without divergence or migration conflicts.
"""

import os
import sys
from pathlib import Path
import pytest

# Ensure classfellow_web is on sys.path and DJANGO_SETTINGS_MODULE is set
WEB_DIR = Path(__file__).resolve().parent.parent / "classfellow_web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
# Use SQLite during unit tests for instant in-memory validation without live PG daemon
os.environ["DJANGO_DB_ENGINE"] = "sqlite"

import django
django.setup()

from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.db import models
from django.db.migrations.loader import MigrationLoader


@pytest.fixture(scope="module")
def django_apps():
    """Returns the initialized Django apps registry."""
    return apps


def test_django_settings_and_apps_registered(django_apps):
    """Verifies that Django setup succeeds and all 6 domain apps are registered."""
    expected_apps = {
        "accounts",
        "core",
        "students",
        "fees",
        "attendance",
        "examinations",
    }
    registered_app_names = {app_config.label for app_config in django_apps.get_app_configs()}
    assert expected_apps.issubset(registered_app_names), (
        f"Missing apps: {expected_apps - registered_app_names}"
    )


def test_custom_user_model_configured():
    """Verifies that AUTH_USER_MODEL is set to accounts.User with operational role choices."""
    assert settings.AUTH_USER_MODEL == "accounts.User"
    user_model = apps.get_model("accounts", "User")
    assert user_model is not None
    assert hasattr(user_model, "role")

    roles = [choice[0] for choice in user_model.role.field.choices]
    assert "Admin" in roles
    assert "Principal" in roles
    assert "Cashier" in roles


def test_all_fifteen_models_registered_and_tables_match(django_apps):
    """Verifies that all 15 core domain models exist and match schema_v1_postgres.sql table names."""
    expected_models_tables = {
        ("core", "AcademicSession"): "academic_sessions",
        ("core", "InstitutionProfile"): "institution_profiles",
        ("students", "Student"): "students",
        ("students", "ClassGroup"): "class_groups",
        ("students", "Enrollment"): "enrollments",
        ("fees", "FeeHead"): "fee_heads",
        ("fees", "FeeInvoice"): "fee_invoices",
        ("fees", "FeeInvoiceItem"): "fee_invoice_items",
        ("fees", "Payment"): "payments",
        ("attendance", "BatchSession"): "batch_sessions",
        ("attendance", "AttendanceRecord"): "attendance_records",
        ("examinations", "Subject"): "subjects",
        ("examinations", "Exam"): "exams",
        ("examinations", "ExamSubject"): "exam_subjects",
        ("examinations", "GradingTier"): "grading_tiers",
        ("examinations", "Mark"): "marks",
    }

    for (app_label, model_name), expected_table in expected_models_tables.items():
        model = django_apps.get_model(app_label, model_name)
        assert model is not None, f"Model {app_label}.{model_name} is missing from Django registry."
        assert model._meta.db_table == expected_table, (
            f"Model {app_label}.{model_name} db_table is '{model._meta.db_table}', expected '{expected_table}'."
        )


def test_primary_keys_use_bigautofield(django_apps):
    """Verifies that all domain models define BigAutoField primary keys."""
    for model in django_apps.get_models():
        if model._meta.app_label in {"core", "students", "fees", "attendance", "examinations", "accounts"}:
            pk_field = model._meta.pk
            assert isinstance(pk_field, models.BigAutoField), (
                f"Model {model.__name__} primary key is not BigAutoField: {type(pk_field)}"
            )


def test_monetary_fields_decimal_precision(django_apps):
    """
    Verifies that all monetary fields use DecimalField(max_digits=12, decimal_places=2)
    and mark fields use DecimalField(max_digits=6, decimal_places=2).
    """
    monetary_checks = [
        ("students", "ClassGroup", "monthly_tuition_fee", 12, 2),
        ("students", "Enrollment", "custom_discount_amount", 12, 2),
        ("fees", "FeeInvoice", "late_fee_surcharge", 12, 2),
        ("fees", "FeeInvoice", "total_payable", 12, 2),
        ("fees", "FeeInvoice", "discount_amount", 12, 2),
        ("fees", "FeeInvoice", "net_due", 12, 2),
        ("fees", "FeeInvoiceItem", "amount", 12, 2),
        ("fees", "Payment", "amount", 12, 2),
        ("examinations", "ExamSubject", "maximum_marks", 6, 2),
        ("examinations", "ExamSubject", "passing_marks", 6, 2),
        ("examinations", "Mark", "marks_obtained", 6, 2),
    ]

    for app_label, model_name, field_name, exp_digits, exp_places in monetary_checks:
        model = django_apps.get_model(app_label, model_name)
        field = model._meta.get_field(field_name)
        assert isinstance(field, models.DecimalField), (
            f"{model_name}.{field_name} is not a DecimalField."
        )
        assert field.max_digits == exp_digits, (
            f"{model_name}.{field_name} max_digits is {field.max_digits}, expected {exp_digits}."
        )
        assert field.decimal_places == exp_places, (
            f"{model_name}.{field_name} decimal_places is {field.decimal_places}, expected {exp_places}."
        )


def test_foreign_key_referential_integrity_rules(django_apps):
    """
    Verifies that critical ledger and relationship foreign keys enforce on_delete=RESTRICT.
    """
    restrict_checks = [
        ("fees", "Payment", "invoice"),
        ("students", "Enrollment", "student"),
        ("students", "Enrollment", "class_group"),
        ("students", "Enrollment", "session"),
        ("fees", "FeeInvoice", "enrollment"),
        ("attendance", "AttendanceRecord", "enrollment"),
        ("examinations", "Mark", "enrollment"),
    ]

    for app_label, model_name, field_name in restrict_checks:
        model = django_apps.get_model(app_label, model_name)
        field = model._meta.get_field(field_name)
        assert field.remote_field.on_delete == models.RESTRICT, (
            f"{model_name}.{field_name} on_delete is not RESTRICT."
        )


def test_composite_unique_constraints(django_apps):
    """
    Verifies composite unique constraints matching schema_v1_postgres.sql:
    - attendance_records: (enrollment, attendance_date)
    - fee_invoices: (enrollment, month_year)
    - exam_subjects: (exam, class_group, subject)
    - class_groups: (session, name, section_or_batch)
    - enrollments: (student, class_group, session)
    - exams: (session, name)
    - grading_tiers: (session, grade_name)
    - marks: (exam_subject, enrollment)
    """
    constraint_checks = [
        ("attendance", "AttendanceRecord", "uq_attendance_enrollment_date", ("enrollment", "attendance_date")),
        ("fees", "FeeInvoice", "uq_fee_invoices_enrollment_month", ("enrollment", "month_year")),
        ("examinations", "ExamSubject", "uq_exam_class_subject", ("exam", "class_group", "subject")),
        ("students", "ClassGroup", "uq_class_groups_session_name_section", ("session", "name", "section_or_batch")),
        ("students", "Enrollment", "uq_enrollments_student_class_session", ("student", "class_group", "session")),
        ("examinations", "Exam", "uq_exams_session_name", ("session", "name")),
        ("examinations", "GradingTier", "uq_grading_tiers_session_grade", ("session", "grade_name")),
        ("examinations", "Mark", "uq_marks_exam_subject_enrollment", ("exam_subject", "enrollment")),
    ]

    for app_label, model_name, constraint_name, expected_fields in constraint_checks:
        model = django_apps.get_model(app_label, model_name)
        constraints = {c.name: c for c in model._meta.constraints if isinstance(c, models.UniqueConstraint)}
        assert constraint_name in constraints, (
            f"Missing constraint '{constraint_name}' in {model_name}."
        )
        assert tuple(constraints[constraint_name].fields) == expected_fields, (
            f"Constraint '{constraint_name}' fields do not match {expected_fields}."
        )


def test_btree_indexes_defined_on_models(django_apps):
    """Verifies that all 20 explicit B-Tree covering indexes exist across the models."""
    expected_indexes = {
        ("students", "Student"): ["idx_students_admission_no", "idx_students_names", "idx_students_guardian_phone"],
        ("students", "Enrollment"): ["idx_enrollments_student", "idx_enrollments_class_session", "idx_enrollments_status"],
        ("fees", "FeeInvoice"): ["idx_fee_invoices_enrollment", "idx_fee_invoices_cycle", "idx_fee_invoices_valid_until", "idx_fee_invoices_session_valid"],
        ("fees", "FeeInvoiceItem"): ["idx_fee_invoice_items_invoice"],
        ("fees", "Payment"): ["idx_payments_invoice", "idx_payments_inv_status_amt", "idx_payments_receipt_no"],
        ("attendance", "AttendanceRecord"): ["idx_attendance_enrollment_date", "idx_attendance_date_status", "idx_attendance_batch"],
        ("examinations", "ExamSubject"): ["idx_exam_subjects_lookup"],
        ("examinations", "Mark"): ["idx_marks_enrollment", "idx_marks_lookup"],
    }

    for (app_label, model_name), index_names in expected_indexes.items():
        model = django_apps.get_model(app_label, model_name)
        model_indexes = {idx.name for idx in model._meta.indexes}
        for idx_name in index_names:
            assert idx_name in model_indexes, (
                f"Missing index '{idx_name}' on model {app_label}.{model_name}."
            )


def test_migrations_loader_and_graph_consistency():
    """Verifies that Django's migration graph loads without conflicts and all 6 apps have initial migrations."""
    from django.db import connection
    loader = MigrationLoader(connection)
    graph = loader.graph

    domain_apps = ["accounts", "core", "students", "fees", "attendance", "examinations"]
    for app_label in domain_apps:
        initial_key = (app_label, "0001_initial")
        assert initial_key in graph.nodes, f"Migration {initial_key} is missing in migration graph."

    # Validate that makemigrations detects zero pending changes
    try:
        call_command("makemigrations", check=True, dry_run=True)
    except SystemExit as exc:
        pytest.fail(f"makemigrations --check failed with exit code: {exc}")
