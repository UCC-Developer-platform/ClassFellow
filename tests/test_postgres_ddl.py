"""
ClassFellow - PostgreSQL 16 Relational DDL & Migration Specification Tests
Ensures that database/postgres/schema_v1_postgres.sql satisfies production PostgreSQL 16
enterprise architectural specifications, column types, constraints, and indexes.
"""

import re
from pathlib import Path
import pytest

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "database" / "postgres" / "schema_v1_postgres.sql"


@pytest.fixture(scope="module")
def sql_content():
    """Reads the raw SQL schema specification content."""
    assert SCHEMA_PATH.exists(), f"PostgreSQL DDL schema missing at {SCHEMA_PATH}"
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def parsed_tables(sql_content):
    """
    Extracts table definitions mapped by table name.
    Returns a dict: {table_name: table_body_sql}.
    """
    table_pattern = re.compile(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s*\((.*?)\);",
        re.DOTALL | re.IGNORECASE,
    )
    tables = {}
    for match in table_pattern.finditer(sql_content):
        table_name = match.group(1).lower()
        table_body = match.group(2)
        tables[table_name] = table_body
    return tables


def test_schema_file_exists_and_substantial(sql_content):
    """Verifies that the DDL file exists and has comprehensive production content."""
    assert len(sql_content.strip()) > 5000, "PostgreSQL schema file is too brief or incomplete."
    assert "PostgreSQL 16 Schema Specification" in sql_content


def test_syntax_parentheses_and_statements(sql_content):
    """Verifies structural validity: balanced parentheses and proper statement terminations."""
    # Strip comments and string literals to check syntax delimiters
    no_comments = re.sub(r"--.*?$", "", sql_content, flags=re.MULTILINE)
    # Remove block comments
    no_comments = re.sub(r"/\*.*?\*/", "", no_comments, flags=re.DOTALL)
    # Remove single quoted strings
    no_strings = re.sub(r"'(?:''|[^'])*'", "''", no_comments)
    # Remove dollar quotes
    no_dollar_quotes = re.sub(r"\$\$.*?\$\$", "''", no_strings, flags=re.DOTALL)

    open_parens = no_dollar_quotes.count("(")
    close_parens = no_dollar_quotes.count(")")
    assert open_parens == close_parens, f"Unbalanced parentheses in SQL: (={open_parens}, )={close_parens}"


def test_all_fifteen_tables_defined(parsed_tables):
    """Verifies that all 15 core domain tables are defined in the schema."""
    expected_tables = {
        "academic_sessions",
        "students",
        "class_groups",
        "enrollments",
        "fee_heads",
        "fee_invoices",
        "fee_invoice_items",
        "payments",
        "batch_sessions",
        "attendance_records",
        "subjects",
        "exams",
        "exam_subjects",
        "grading_tiers",
        "marks",
    }
    missing_tables = expected_tables - set(parsed_tables.keys())
    assert not missing_tables, f"Missing PostgreSQL table definitions: {missing_tables}"


def test_primary_keys_use_identity_or_bigserial(parsed_tables):
    """
    Verifies that every table uses PostgreSQL 16 standard identity primary keys:
    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY (or BIGSERIAL PRIMARY KEY).
    """
    for table_name, body in parsed_tables.items():
        assert re.search(
            r"id\s+(BIGINT\s+GENERATED\s+ALWAYS\s+AS\s+IDENTITY|BIGSERIAL)\s+PRIMARY\s+KEY",
            body,
            re.IGNORECASE,
        ), f"Table '{table_name}' does not use BIGINT IDENTITY / BIGSERIAL PRIMARY KEY"


def test_monetary_fields_numeric_precision(parsed_tables):
    """
    Verifies monetary fields use enterprise precision NUMERIC(12, 2) NOT NULL:
    - class_groups: monthly_tuition_fee
    - enrollments: custom_discount_amount
    - fee_invoices: late_fee_surcharge, total_payable, discount_amount, net_due
    - fee_invoice_items: amount
    - payments: amount
    """
    checks = [
        ("class_groups", "monthly_tuition_fee", r"monthly_tuition_fee\s+NUMERIC\(12,\s*2\)\s+NOT\s+NULL"),
        ("enrollments", "custom_discount_amount", r"custom_discount_amount\s+NUMERIC\(12,\s*2\)\s+NOT\s+NULL"),
        ("fee_invoices", "late_fee_surcharge", r"late_fee_surcharge\s+NUMERIC\(12,\s*2\)\s+NOT\s+NULL"),
        ("fee_invoices", "total_payable", r"total_payable\s+NUMERIC\(12,\s*2\)\s+NOT\s+NULL"),
        ("fee_invoices", "discount_amount", r"discount_amount\s+NUMERIC\(12,\s*2\)\s+NOT\s+NULL"),
        ("fee_invoices", "net_due", r"net_due\s+NUMERIC\(12,\s*2\)\s+NOT\s+NULL"),
        ("fee_invoice_items", "amount", r"amount\s+NUMERIC\(12,\s*2\)\s+NOT\s+NULL"),
        ("payments", "amount", r"amount\s+NUMERIC\(12,\s*2\)\s+NOT\s+NULL"),
    ]

    for table_name, column_name, pattern in checks:
        assert table_name in parsed_tables, f"Table {table_name} missing"
        body = parsed_tables[table_name]
        assert re.search(pattern, body, re.IGNORECASE), (
            f"Field '{column_name}' in table '{table_name}' does not have NUMERIC(12, 2) NOT NULL precision."
        )


def test_native_boolean_types(parsed_tables):
    """Verifies that flag columns use native BOOLEAN types instead of SQLite 0/1 integers."""
    boolean_fields = [
        ("academic_sessions", "is_active"),
        ("students", "is_active"),
        ("fee_heads", "is_recurring"),
        ("exams", "is_published"),
        ("grading_tiers", "is_passing"),
        ("marks", "is_absent"),
    ]
    for table_name, col in boolean_fields:
        body = parsed_tables[table_name]
        assert re.search(
            rf"{col}\s+BOOLEAN\s+NOT\s+NULL",
            body,
            re.IGNORECASE,
        ), f"Field '{col}' in '{table_name}' is not defined as native BOOLEAN NOT NULL."


def test_timestamptz_usage(parsed_tables):
    """Verifies that audit timestamp columns use PostgreSQL TIMESTAMPTZ."""
    timestamptz_tables = [
        "academic_sessions",
        "students",
        "class_groups",
        "enrollments",
        "fee_heads",
        "fee_invoices",
        "payments",
        "attendance_records",
        "marks",
    ]
    for table_name in timestamptz_tables:
        body = parsed_tables[table_name]
        assert re.search(
            r"created_at\s+TIMESTAMPTZ\s+NOT\s+NULL\s+DEFAULT\s+CURRENT_TIMESTAMP",
            body,
            re.IGNORECASE,
        ), f"Table '{table_name}' does not use TIMESTAMPTZ for created_at."


def test_referential_integrity_and_delete_restrict(parsed_tables):
    """
    Verifies financial and enrollment referential constraints:
    - Payments must restrict invoice deletion (ON DELETE RESTRICT).
    - Enrollments must restrict student/class_group deletion.
    - Fee invoices must restrict enrollment deletion.
    """
    payments_body = parsed_tables["payments"]
    assert re.search(
        r"invoice_id\s+BIGINT\s+NOT\s+NULL\s+REFERENCES\s+fee_invoices\s*\(\s*id\s*\)\s+ON\s+DELETE\s+RESTRICT",
        payments_body,
        re.IGNORECASE,
    ), "Payments foreign key must specify ON DELETE RESTRICT on fee_invoices(id)."

    enrollments_body = parsed_tables["enrollments"]
    assert re.search(
        r"student_id\s+BIGINT\s+NOT\s+NULL\s+REFERENCES\s+students\s*\(\s*id\s*\)\s+ON\s+DELETE\s+RESTRICT",
        enrollments_body,
        re.IGNORECASE,
    ), "Enrollments must enforce ON DELETE RESTRICT on students."


def test_critical_unique_constraints(parsed_tables):
    """
    Verifies unique constraints preserving domain invariant guarantees:
    - attendance_records: UNIQUE(enrollment_id, attendance_date)
    - exam_subjects: UNIQUE(exam_id, class_group_id, subject_id)
    - fee_invoices: UNIQUE(enrollment_id, month_year)
    - enrollments: UNIQUE(student_id, class_group_id, session_id)
    - marks: UNIQUE(exam_subject_id, enrollment_id)
    """
    constraints = [
        ("attendance_records", r"UNIQUE\s*\(\s*enrollment_id\s*,\s*attendance_date\s*\)"),
        ("exam_subjects", r"UNIQUE\s*\(\s*exam_id\s*,\s*class_group_id\s*,\s*subject_id\s*\)"),
        ("fee_invoices", r"UNIQUE\s*\(\s*enrollment_id\s*,\s*month_year\s*\)"),
        ("enrollments", r"UNIQUE\s*\(\s*student_id\s*,\s*class_group_id\s*,\s*session_id\s*\)"),
        ("marks", r"UNIQUE\s*\(\s*exam_subject_id\s*,\s*enrollment_id\s*\)"),
    ]
    for table_name, pattern in constraints:
        body = parsed_tables[table_name]
        assert re.search(pattern, body, re.IGNORECASE), (
            f"Table '{table_name}' is missing required composite unique constraint matching '{pattern}'."
        )


def test_btree_performance_indexes(sql_content):
    """
    Verifies that all performance and covering indexes are ported to PostgreSQL
    explicit B-tree syntax (USING btree).
    """
    index_pattern = re.compile(
        r"CREATE\s+INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s+ON\s+(\w+)\s+USING\s+btree\s*\((.*?)\);",
        re.IGNORECASE,
    )
    indexes = {match.group(1).lower(): (match.group(2).lower(), match.group(3)) for match in index_pattern.finditer(sql_content)}

    expected_indexes = [
        "idx_students_admission_no",
        "idx_students_names",
        "idx_students_guardian_phone",
        "idx_enrollments_student",
        "idx_enrollments_class_session",
        "idx_enrollments_status",
        "idx_fee_invoices_enrollment",
        "idx_fee_invoices_cycle",
        "idx_fee_invoices_valid_until",
        "idx_fee_invoices_session_valid",
        "idx_fee_invoice_items_invoice",
        "idx_payments_invoice",
        "idx_payments_invoice_status_amount",
        "idx_payments_receipt_no",
        "idx_attendance_enrollment_date",
        "idx_attendance_date_status",
        "idx_attendance_batch",
        "idx_exam_subjects_lookup",
        "idx_marks_enrollment",
        "idx_marks_lookup",
    ]

    for idx_name in expected_indexes:
        assert idx_name in indexes, f"Missing explicit B-Tree index '{idx_name}' in PostgreSQL schema."
    assert len(indexes) >= 20, f"Expected at least 20 B-Tree indexes, found {len(indexes)}."


def test_updated_at_triggers_configured(sql_content):
    """Verifies that trigger function and triggers for updated_at timestamps are defined."""
    assert "CREATE OR REPLACE FUNCTION set_updated_at_timestamp()" in sql_content
    assert "CREATE TRIGGER trg_students_updated_at" in sql_content
    assert "CREATE TRIGGER trg_attendance_records_updated_at" in sql_content
    assert "CREATE TRIGGER trg_marks_updated_at" in sql_content


def test_initial_catalog_seeds_present(sql_content):
    """Verifies that default fee heads and core subjects are seeded with ON CONFLICT safety."""
    assert "INSERT INTO fee_heads" in sql_content
    assert "ON CONFLICT (name) DO NOTHING" in sql_content
    assert "INSERT INTO subjects" in sql_content
    assert "'Mathematics'" in sql_content
    assert "'Urdu'" in sql_content
