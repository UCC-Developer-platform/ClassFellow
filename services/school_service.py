"""
ClassFellow - School & Institutional Profile Domain Service
============================================================
Handles institutional configuration, the onboarding "Mother Form" state,
branding assets, academic sessions setup, and dynamic regional fee heads.
"""

import sqlite3
from typing import Optional, Any
from decimal import Decimal
from database import transaction
from models import SchoolProfileDTO


def is_school_profile_configured(conn: sqlite3.Connection) -> bool:
    """
    Determines if the database has been configured via the Mother Form.
    A school is considered configured if:
      1. A school profile record exists.
      2. At least one active academic session exists.
      3. At least one class group exists.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM school_profiles LIMIT 1;")
    has_profile = cursor.fetchone() is not None

    cursor.execute("SELECT 1 FROM academic_sessions WHERE is_active = 1 LIMIT 1;")
    has_session = cursor.fetchone() is not None

    cursor.execute("SELECT 1 FROM class_groups LIMIT 1;")
    has_class = cursor.fetchone() is not None

    return has_profile and has_session and has_class


def get_school_profile(conn: sqlite3.Connection) -> Optional[dict[str, Any]]:
    """Retrieves the active institutional profile and branding information with dual aliases."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM school_profiles ORDER BY id ASC LIMIT 1;")
    row = cursor.fetchone()
    if not row:
        return None
    d = {k: row[k] for k in row.keys()}
    # Populate compatibility aliases
    d["school_name"] = d.get("name")
    d["school_urdu_name"] = d.get("urdu_name")
    d["contact_number"] = d.get("phone")
    d["registration_number"] = d.get("registration_code")
    return d


def save_school_profile(conn: sqlite3.Connection, profile: Any) -> int:
    """
    Inserts or updates the single institutional profile record in school_profiles table.
    Accepts SchoolProfileDTO or dict.
    """
    if isinstance(profile, SchoolProfileDTO):
        name = profile.get_name().strip()
        urdu_name = profile.get_urdu_name()
        campus = profile.campus_name or "Main Campus"
        reg_code = profile.get_registration_code()
        phone = profile.get_phone().strip()
        whatsapp = profile.whatsapp
        email = profile.email
        address = profile.address
        logo_path = profile.logo_path
    elif isinstance(profile, dict):
        name = (profile.get("name") or profile.get("school_name") or "").strip()
        urdu_name = profile.get("urdu_name") or profile.get("school_urdu_name")
        campus = profile.get("campus_name") or "Main Campus"
        reg_code = profile.get("registration_code") or profile.get("registration_number")
        phone = (profile.get("phone") or profile.get("contact_number") or "").strip()
        whatsapp = profile.get("whatsapp")
        email = profile.get("email")
        address = profile.get("address")
        logo_path = profile.get("logo_path")
    else:
        raise ValueError("Profile data must be SchoolProfileDTO or dict.")

    if not name:
        raise ValueError("School name cannot be empty.")

    with transaction(conn):
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM school_profiles ORDER BY id ASC LIMIT 1;")
        existing = cursor.fetchone()

        if existing:
            profile_id = existing["id"] if isinstance(existing, sqlite3.Row) else existing[0]
            cursor.execute(
                """
                UPDATE school_profiles SET
                    name = ?,
                    urdu_name = ?,
                    campus_name = ?,
                    registration_code = ?,
                    phone = ?,
                    whatsapp = ?,
                    email = ?,
                    address = ?,
                    logo_path = ?,
                    updated_at = DATETIME('now')
                WHERE id = ?;
                """,
                (
                    name,
                    urdu_name,
                    campus,
                    reg_code,
                    phone,
                    whatsapp,
                    email,
                    address,
                    logo_path,
                    profile_id
                )
            )
            return profile_id
        else:
            cursor.execute(
                """
                INSERT INTO school_profiles (
                    name, urdu_name, campus_name, registration_code,
                    phone, whatsapp, email, address, logo_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    name,
                    urdu_name,
                    campus,
                    reg_code,
                    phone,
                    whatsapp,
                    email,
                    address,
                    logo_path
                )
            )
            return cursor.lastrowid


def get_active_fee_heads(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Retrieves all active fee heads ordered by recurring vs one-time, then id."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, name, urdu_name, is_recurring, default_amount, is_active
        FROM fee_heads
        WHERE is_active = 1
        ORDER BY is_recurring DESC, id ASC;
        """
    )
    rows = cursor.fetchall()
    results = []
    for r in rows:
        d = {k: r[k] for k in r.keys()}
        d["default_amount"] = Decimal(str(d.get("default_amount") or "0.00"))
        results.append(d)
    return results


def get_all_fee_heads(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Retrieves all fee heads in catalog."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, name, urdu_name, is_recurring, default_amount, is_active
        FROM fee_heads
        ORDER BY id ASC;
        """
    )
    rows = cursor.fetchall()
    results = []
    for r in rows:
        d = {k: r[k] for k in r.keys()}
        d["default_amount"] = Decimal(str(d.get("default_amount") or "0.00"))
        results.append(d)
    return results


def setup_initial_school(
    conn: sqlite3.Connection,
    profile_data: Any,
    session_data: dict[str, Any],
    classes_data: list[dict[str, Any]],
    fee_heads_data: Optional[list[dict[str, Any]]] = None
) -> tuple[int, int]:
    """
    Atomic setup wizard execution ("Mother Form").
    Saves:
      1. School Profile
      2. Academic Session
      3. Class Groups
      4. Fee Heads Catalog adjustments
    Returns (profile_id, session_id).
    """
    with transaction(conn):
        profile_id = save_school_profile(conn, profile_data)

        # Academic Session
        sess_name = (session_data.get("name") or "").strip()
        if not sess_name:
            raise ValueError("Academic session name is required.")
        start_date = session_data.get("start_date") or "2026-04-01"
        end_date = session_data.get("end_date") or "2027-03-31"

        cursor = conn.cursor()
        cursor.execute("SELECT id FROM academic_sessions WHERE name = ?;", (sess_name,))
        sess_row = cursor.fetchone()
        if sess_row:
            session_id = sess_row["id"] if isinstance(sess_row, sqlite3.Row) else sess_row[0]
            cursor.execute(
                """
                UPDATE academic_sessions SET start_date = ?, end_date = ?, is_active = 1
                WHERE id = ?;
                """,
                (start_date, end_date, session_id)
            )
        else:
            cursor.execute(
                """
                INSERT INTO academic_sessions (name, start_date, end_date, is_active)
                VALUES (?, ?, ?, 1);
                """,
                (sess_name, start_date, end_date)
            )
            session_id = cursor.lastrowid

        # Class Groups
        for cls in classes_data:
            cls_name = (cls.get("name") or "").strip()
            if not cls_name:
                continue
            section = (cls.get("section_or_batch") or "A").strip()
            group_type = cls.get("group_type") or "SchoolClass"
            tuition = Decimal(str(cls.get("monthly_tuition_fee") or "0.00"))

            cursor.execute(
                """
                SELECT id FROM class_groups
                WHERE session_id = ? AND name = ? AND section_or_batch = ?;
                """,
                (session_id, cls_name, section)
            )
            c_row = cursor.fetchone()
            if c_row:
                c_id = c_row["id"] if isinstance(c_row, sqlite3.Row) else c_row[0]
                cursor.execute(
                    """
                    UPDATE class_groups SET monthly_tuition_fee = ?, group_type = ?
                    WHERE id = ?;
                    """,
                    (str(tuition), group_type, c_id)
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO class_groups (session_id, name, section_or_batch, group_type, monthly_tuition_fee)
                    VALUES (?, ?, ?, ?, ?);
                    """,
                    (session_id, cls_name, section, group_type, str(tuition))
                )

        # Fee Heads Catalog
        if fee_heads_data:
            for fh in fee_heads_data:
                fh_id = fh.get("id")
                is_active = 1 if fh.get("is_active") else 0
                default_amount = str(fh.get("default_amount") or "0.00")
                if fh_id:
                    cursor.execute(
                        """
                        UPDATE fee_heads SET is_active = ?, default_amount = ?
                        WHERE id = ?;
                        """,
                        (is_active, default_amount, fh_id)
                    )
                else:
                    name = (fh.get("name") or "").strip()
                    if name:
                        cursor.execute("SELECT id FROM fee_heads WHERE name = ?;", (name,))
                        existing_fh = cursor.fetchone()
                        if existing_fh:
                            existing_id = existing_fh["id"] if isinstance(existing_fh, sqlite3.Row) else existing_fh[0]
                            cursor.execute(
                                """
                                UPDATE fee_heads SET is_active = ?, default_amount = ?
                                WHERE id = ?;
                                """,
                                (is_active, default_amount, existing_id)
                            )
                        else:
                            cursor.execute(
                                """
                                INSERT INTO fee_heads (name, urdu_name, is_recurring, default_amount, is_active)
                                VALUES (?, ?, ?, ?, ?);
                                """,
                                (
                                    name,
                                    fh.get("urdu_name"),
                                    1 if fh.get("is_recurring") else 0,
                                    default_amount,
                                    is_active
                                )
                            )

        return profile_id, session_id


class SchoolService:
    """Wrapper class around institutional profile operations."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def is_configured(self) -> bool:
        return is_school_profile_configured(self.conn)

    def get_profile(self) -> Optional[dict[str, Any]]:
        return get_school_profile(self.conn)

    def save_profile(self, profile: Any) -> int:
        return save_school_profile(self.conn, profile)

    def get_active_fee_heads(self) -> list[dict[str, Any]]:
        return get_active_fee_heads(self.conn)

    def get_all_fee_heads(self) -> list[dict[str, Any]]:
        return get_all_fee_heads(self.conn)

    def setup_initial_school(
        self,
        profile_data: Any,
        session_data: dict[str, Any],
        classes_data: list[dict[str, Any]],
        fee_heads_data: Optional[list[dict[str, Any]]] = None
    ) -> tuple[int, int]:
        return setup_initial_school(self.conn, profile_data, session_data, classes_data, fee_heads_data)
