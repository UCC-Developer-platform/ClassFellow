"""
tests/test_staff_and_cloud_sync.py
===================================
Automated verification test suite for Category 13:
- Staff and StaffSubjectAllocation models, decimal precision, and unique constraints.
- Role-protected staff_list_view and staff_create_view with phone normalization.
- Desktop-to-cloud backup sync upload API (/api/v1/sync/upload/) security,
  token authorization, SHA-256 checksum verification, and file persistence.
"""

import datetime
from decimal import Decimal
import hashlib
import os
import pytest

os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
os.environ["DJANGO_DB_ENGINE"] = "sqlite"

import django  # noqa: E402
django.setup()

from django.conf import settings  # noqa: E402
from django.core.files.uploadedfile import SimpleUploadedFile  # noqa: E402
from django.db import IntegrityError  # noqa: E402
from django.test import Client  # noqa: E402

from apps.accounts.models import Role, User  # noqa: E402
from apps.core.models import AcademicSession, Campus, InstitutionBackupSnapshot  # noqa: E402
from apps.examinations.models import Subject  # noqa: E402
from apps.staff.models import Staff, StaffSubjectAllocation  # noqa: E402
from apps.students.models import ClassGroup, GroupType  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database():
    """Ensures clean database state between tests."""
    StaffSubjectAllocation.objects.all().delete()
    Staff.objects.all().delete()
    InstitutionBackupSnapshot.objects.all().delete()
    User.objects.filter(username__startswith="staff_test_").delete()
    yield


@pytest.fixture
def campus_fixture():
    campus, _ = Campus.objects.get_or_create(
        code="MBC-TEST",
        defaults={
            "name": "Main Boys Campus",
            "address": "123 Education Boulevard, Lahore",
            "phone": "04235881234",
        },
    )
    return campus


@pytest.fixture
def session_fixture():
    session, _ = AcademicSession.objects.get_or_create(
        name="2026-2027 Staff Session",
        defaults={
            "start_date": datetime.date(2026, 4, 1),
            "end_date": datetime.date(2027, 3, 31),
            "is_active": True,
        },
    )
    return session


@pytest.fixture
def class_fixture(session_fixture, campus_fixture):
    class_grp, _ = ClassGroup.objects.get_or_create(
        session=session_fixture,
        name="Class 10 Staff Test",
        section_or_batch="Section A",
        defaults={
            "campus": campus_fixture,
            "group_type": GroupType.SCHOOL_CLASS,
            "monthly_tuition_fee": Decimal("5000.00"),
        },
    )
    return class_grp


@pytest.fixture
def subject_fixture():
    subject, _ = Subject.objects.get_or_create(
        code="PHY-10-TEST",
        defaults={
            "name": "Physics Test Subject",
            "urdu_name": "طبیعیات",
        },
    )
    return subject


@pytest.fixture
def admin_user():
    return User.objects.create_user(
        username="staff_test_admin",
        password="Password123!",
        role=Role.ADMIN,
        first_name="Director",
        last_name="Administration",
    )


@pytest.fixture
def cashier_user():
    return User.objects.create_user(
        username="staff_test_cashier",
        password="Password123!",
        role=Role.CASHIER,
        first_name="Usman",
        last_name="Cashier",
    )


# =============================================================================
# 1. Model & Domain Logic Tests
# =============================================================================

def test_staff_model_and_salary_precision(campus_fixture):
    """Verifies Staff model fields, properties, string representation, and Decimal(12, 2) precision."""
    staff = Staff.objects.create(
        employee_id="EMP-1001",
        first_name="Tariq",
        last_name="Mehmood",
        urdu_name="طارق محمود",
        designation="Senior Physics Teacher",
        department="Science",
        campus=campus_fixture,
        phone="03001234567",
        email="tariq@classfellow.edu.pk",
        national_id_cnic="35201-1234567-1",
        basic_salary=Decimal("65432.50"),
        joining_date=datetime.date(2025, 8, 15),
        is_active=True,
    )

    assert staff.id is not None
    assert staff.full_name == "Tariq Mehmood"
    assert "EMP-1001" in str(staff)
    assert "Tariq Mehmood" in str(staff)
    assert staff.basic_salary == Decimal("65432.50")

    # Verify reloading from database maintains exact Decimal precision
    refetched = Staff.objects.get(id=staff.id)
    assert refetched.basic_salary == Decimal("65432.50")
    assert refetched.urdu_name == "طارق محمود"
    assert refetched.campus.name == "Main Boys Campus"


def test_staff_subject_allocation_unique_constraint(campus_fixture, session_fixture, class_fixture, subject_fixture):
    """Verifies teacher subject allocation and checks enforcement of unique composite constraint."""
    staff = Staff.objects.create(
        employee_id="EMP-1002",
        first_name="Amina",
        last_name="Bibi",
        designation="Science Teacher",
        campus=campus_fixture,
        phone="03019876543",
        basic_salary=Decimal("48000.00"),
    )

    allocation = StaffSubjectAllocation.objects.create(
        staff=staff,
        class_group=class_fixture,
        subject=subject_fixture,
        academic_session=session_fixture,
    )

    assert allocation.id is not None
    assert "Amina Bibi" in str(allocation)
    assert "Physics" in str(allocation)

    # Duplicate allocation with identical (staff, class_group, subject, academic_session) MUST fail
    with pytest.raises(IntegrityError):
        StaffSubjectAllocation.objects.create(
            staff=staff,
            class_group=class_fixture,
            subject=subject_fixture,
            academic_session=session_fixture,
        )


# =============================================================================
# 2. Web View & RBAC Tests
# =============================================================================

def test_staff_list_view_rbac_and_filtering(admin_user, cashier_user, campus_fixture):
    """Verifies RBAC access restrictions and staff filtering in staff_list_view."""
    # Create two staff members
    Staff.objects.create(
        employee_id="EMP-1001",
        first_name="Zahid",
        last_name="Khan",
        designation="Principal",
        campus=campus_fixture,
        phone="03001112233",
        basic_salary=Decimal("95000.00"),
        is_active=True,
    )
    Staff.objects.create(
        employee_id="EMP-1002",
        first_name="Farooq",
        last_name="Ahmad",
        designation="Junior Clerk",
        campus=campus_fixture,
        phone="03214445566",
        basic_salary=Decimal("35000.00"),
        is_active=False,
    )

    client = Client()

    # Cashier role is forbidden from Staff Administration workspace
    client.login(username="staff_test_cashier", password="Password123!")
    resp = client.get("/staff/")
    assert resp.status_code == 403

    # Admin role is granted access
    client.login(username="staff_test_admin", password="Password123!")
    resp = client.get("/staff/")
    assert resp.status_code == 200
    assert b"Staff & Faculty Administration" in resp.content
    assert b"Zahid" in resp.content
    assert b"EMP-1001" in resp.content
    assert b"Rs. 95000.00" in resp.content

    # Search filter: by name
    resp_search = client.get("/staff/?q=Zahid")
    assert resp_search.status_code == 200
    assert b"Zahid" in resp_search.content
    assert b"Farooq" not in resp_search.content

    # Campus filter
    resp_campus = client.get(f"/staff/?campus_id={campus_fixture.id}")
    assert resp_campus.status_code == 200
    assert b"Zahid" in resp_campus.content


def test_staff_create_view_post_success_and_phone_normalization(admin_user, campus_fixture):
    """Verifies POST /staff/create/ with phone normalization and database record creation."""
    client = Client()
    client.login(username="staff_test_admin", password="Password123!")

    post_data = {
        "employee_id": "emp-2005",  # lowercase, should be upper-cased
        "first_name": "Rashid",
        "last_name": "Minhas",
        "urdu_name": "راشد منہاس",
        "designation": "Mathematics Teacher",
        "department": "Mathematics",
        "campus_id": str(campus_fixture.id),
        "phone": "+92-300-7654321",  # un-normalized phone
        "email": "rashid@classfellow.edu.pk",
        "national_id_cnic": "35201-9876543-1",
        "basic_salary": "52500.00",
        "joining_date": "2026-05-01",
    }

    resp = client.post("/staff/create/", data=post_data)
    assert resp.status_code == 302
    assert resp.url == "/staff/"

    # Verify created record in database
    staff = Staff.objects.get(employee_id="EMP-2005")
    assert staff.first_name == "Rashid"
    assert staff.phone == "03007654321"  # successfully normalized
    assert staff.basic_salary == Decimal("52500.00")
    assert staff.joining_date == datetime.date(2026, 5, 1)


def test_staff_create_view_validation_failures(admin_user, campus_fixture):
    """Verifies rejection of invalid phone, duplicate employee code, or invalid salary."""
    client = Client()
    client.login(username="staff_test_admin", password="Password123!")

    # 1. Invalid phone
    resp_bad_phone = client.post("/staff/create/", data={
        "employee_id": "EMP-3001",
        "first_name": "Ali",
        "designation": "Teacher",
        "campus_id": str(campus_fixture.id),
        "phone": "0421234567",  # landline, invalid for mobile
        "basic_salary": "40000.00",
    })
    assert resp_bad_phone.status_code == 302
    assert not Staff.objects.filter(employee_id="EMP-3001").exists()

    # Create a valid staff member
    Staff.objects.create(
        employee_id="EMP-3002",
        first_name="Kashif",
        designation="Teacher",
        campus=campus_fixture,
        phone="03001112233",
        basic_salary=Decimal("40000.00"),
    )

    # 2. Duplicate employee ID
    resp_duplicate = client.post("/staff/create/", data={
        "employee_id": "EMP-3002",
        "first_name": "Another",
        "designation": "Teacher",
        "campus_id": str(campus_fixture.id),
        "phone": "03009998877",
        "basic_salary": "40000.00",
    })
    assert resp_duplicate.status_code == 302
    assert Staff.objects.filter(employee_id="EMP-3002").count() == 1

    # 3. Invalid negative salary
    resp_bad_salary = client.post("/staff/create/", data={
        "employee_id": "EMP-3003",
        "first_name": "Bilal",
        "designation": "Teacher",
        "campus_id": str(campus_fixture.id),
        "phone": "03009998877",
        "basic_salary": "-5000.00",
    })
    assert resp_bad_salary.status_code == 302
    assert not Staff.objects.filter(employee_id="EMP-3003").exists()


# =============================================================================
# 3. Desktop-to-Cloud Backup Sync API Tests (/api/v1/sync/upload/)
# =============================================================================

def test_sync_upload_rejects_non_post():
    """Verifies GET /api/v1/sync/upload/ returns 405 Method Not Allowed."""
    client = Client()
    resp = client.get("/api/v1/sync/upload/")
    assert resp.status_code == 405
    data = resp.json()
    assert data["status"] == "error"
    assert "Only POST is supported" in data["message"]


def test_sync_upload_rejects_unauthorized_token():
    """Verifies rejection with 401 when Authorization header is missing or incorrect."""
    client = Client()
    payload = b"SQLite format 3\x00\x10\x00dummy-database-data"
    uploaded = SimpleUploadedFile("backup.db", payload, content_type="application/octet-stream")

    # 1. Missing header
    resp1 = client.post("/api/v1/sync/upload/", {"backup_file": uploaded})
    assert resp1.status_code == 401
    assert resp1.json()["status"] == "error"

    # 2. Invalid bearer token
    uploaded.seek(0)
    resp2 = client.post(
        "/api/v1/sync/upload/",
        {"backup_file": uploaded},
        HTTP_AUTHORIZATION="Bearer invalid-token-xyz",
    )
    assert resp2.status_code == 401
    assert "Invalid institutional sync bearer token" in resp2.json()["message"]


def test_sync_upload_rejects_corrupted_checksum():
    """Verifies rejection with 400 when client SHA-256 does not match computed checksum."""
    client = Client()
    token = settings.INSTITUTION_SYNC_TOKEN
    payload = b"SQLite format 3\x00\x10\x00sample-database-content-for-checksum"
    uploaded = SimpleUploadedFile("classfellow_2026.db", payload, content_type="application/octet-stream")

    bad_checksum = "0000000000000000000000000000000000000000000000000000000000000000"

    resp = client.post(
        "/api/v1/sync/upload/",
        {"backup_file": uploaded},
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_BACKUP_SHA256=bad_checksum,
    )
    assert resp.status_code == 400
    data = resp.json()
    assert data["status"] == "error"
    assert "SHA-256 checksum mismatch" in data["message"]
    assert InstitutionBackupSnapshot.objects.count() == 0


def test_sync_upload_success_and_persistence(tmp_path):
    """Verifies valid multipart backup upload, file persistence, and audit record creation."""
    client = Client()
    token = settings.INSTITUTION_SYNC_TOKEN

    # Generate synthetic backup payload
    payload = b"SQLite format 3\x00\x10\x00\x01\x01test-sync-snapshot-payload-12345678"
    expected_sha256 = hashlib.sha256(payload).hexdigest()
    uploaded = SimpleUploadedFile("classfellow_auto_backup.db", payload, content_type="application/octet-stream")

    resp = client.post(
        "/api/v1/sync/upload/",
        {
            "backup_file": uploaded,
            "desktop_machine_id": "DESKTOP-PUNJAB-001",
        },
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_BACKUP_SHA256=expected_sha256,
        REMOTE_ADDR="192.168.1.100",
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "success"
    assert "snapshot_id" in data
    assert "uploaded_at" in data

    # Verify database record
    snapshot = InstitutionBackupSnapshot.objects.get(id=data["snapshot_id"])
    assert snapshot.filename == "classfellow_auto_backup.db"
    assert snapshot.file_size_bytes == len(payload)
    assert snapshot.sha256_hash == expected_sha256
    assert snapshot.desktop_machine_id == "DESKTOP-PUNJAB-001"
    assert snapshot.ip_address == "192.168.1.100"

    # Verify stored file content matches payload
    with snapshot.backup_file.open("rb") as f:
        stored_bytes = f.read()
    assert stored_bytes == payload
