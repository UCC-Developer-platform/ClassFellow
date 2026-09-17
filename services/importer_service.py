"""
ClassFellow - Student & Enrollment Bulk Excel Importer (services/importer_service.py)
====================================================================================
Provides automated, resilient bulk student ingestion from standardized Excel (.xlsx)
and CSV spreadsheets with Pakistani phone normalization, validation guards, and
strict atomic rollback guarantees.
"""

import os
import csv
import re
import logging
import sqlite3
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import Optional, List, Dict, Any, Tuple

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from models import StudentDTO
from services.student_service import (
    StudentService,
    normalize_pakistan_phone,
    generate_next_admission_number,
)
from database import transaction

logger = logging.getLogger(__name__)


class StudentImporterService:
    """
    Bulk ingestion engine for importing student rosters and guardian metadata
    from standardized Excel (.xlsx) and CSV files into ClassFellow.
    """

    TEMPLATE_COLUMNS = [
        "Roll Number",
        "First Name *",
        "Last Name",
        "Urdu Name",
        "Gender * (Male/Female)",
        "Guardian Name *",
        "Guardian Phone * (03XXXXXXXXX)",
        "Admission Number (Optional)",
        "Date of Birth (YYYY-MM-DD)",
        "Address",
        "Monthly Discount",
    ]

    SAMPLE_DATA = [
        [
            "101",
            "Usman",
            "Tariq",
            "محمد عثمان طارق",
            "Male",
            "Tariq Mehmood",
            "03001234567",
            "",
            "2010-03-15",
            "House 12, Street 4, Lahore",
            "0.00",
        ],
        [
            "102",
            "Fatima",
            "Zahra",
            "فاطمہ زہرا",
            "Female",
            "Muhammad Zahid",
            "03219876543",
            "",
            "2010-07-22",
            "Canal View, Faisalabad",
            "500.00",
        ],
        [
            "103",
            "Ali",
            "Hassan",
            "علی حسن",
            "Male",
            "Hassan Raza",
            "03335554433",
            "CF-2026-0099",
            "2011-01-10",
            "Satellite Town, Rawalpindi",
            "0.00",
        ],
    ]

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.student_service = StudentService(conn)

    def generate_excel_template(self, target_path: str) -> str:
        """
        Generates a standardized, annotated .xlsx template using openpyxl
        with column headers, sample rows, and validation instructions.

        Args:
            target_path: Destination file path for .xlsx template.

        Returns:
            Absolute file path of generated template.
        """
        wb = openpyxl.Workbook()

        # --- Sheet 1: Student Roster Entry Grid ---
        ws = wb.active
        ws.title = "Student Roster"

        # Theme styles (Slate Header + Emerald Accent)
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

        sample_font = Font(name="Calibri", size=10, italic=True, color="475569")
        sample_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
        sample_align = Alignment(horizontal="left", vertical="center")

        thin_side = Side(border_style="thin", color="CBD5E1")
        border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)

        # Write header row
        ws.row_dimensions[1].height = 30
        for col_idx, col_name in enumerate(self.TEMPLATE_COLUMNS, 1):
            cell = ws.cell(row=1, column=col_idx, value=col_name)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align
            cell.border = border

        # Write sample rows
        for row_offset, row_data in enumerate(self.SAMPLE_DATA, 2):
            ws.row_dimensions[row_offset].height = 22
            for col_idx, val in enumerate(row_data, 1):
                cell = ws.cell(row=row_offset, column=col_idx, value=val)
                cell.font = sample_font
                cell.fill = sample_fill
                cell.alignment = sample_align
                cell.border = border

        # Adjust column widths dynamically
        for col_idx in range(1, len(self.TEMPLATE_COLUMNS) + 1):
            col_letter = get_column_letter(col_idx)
            header_len = len(self.TEMPLATE_COLUMNS[col_idx - 1])
            ws.column_dimensions[col_letter].width = max(header_len + 4, 16)

        # --- Sheet 2: Field Instructions & Rules ---
        ws_info = wb.create_sheet(title="Instructions")
        ws_info.column_dimensions["A"].width = 24
        ws_info.column_dimensions["B"].width = 16
        ws_info.column_dimensions["C"].width = 60

        info_headers = ["Field Name", "Required", "Format & Validation Rules"]
        for c_idx, h in enumerate(info_headers, 1):
            cell = ws_info.cell(row=1, column=c_idx, value=h)
            cell.font = header_font
            cell.fill = PatternFill(start_color="10B981", end_color="10B981", fill_type="solid")
            cell.alignment = header_align
            cell.border = border

        rules = [
            ("Roll Number", "Optional", "Class roll number (e.g., 101, 102)."),
            ("First Name *", "YES", "Student's legal first name. Cannot be empty."),
            ("Last Name", "Optional", "Student's surname or family name."),
            ("Urdu Name", "Optional", "Bilingual student name in Urdu Naskh/Nastaliq script."),
            ("Gender *", "YES", "Must be 'Male', 'Female', or 'Other'."),
            ("Guardian Name *", "YES", "Father or legal guardian full name."),
            ("Guardian Phone *", "YES", "Valid Pakistani mobile (e.g., 03001234567, 0321-9876543, +923001234567)."),
            ("Admission Number", "Optional", "Leave blank to auto-generate sequential CF-YYYY-XXXX."),
            ("Date of Birth", "Optional", "Standard YYYY-MM-DD format (e.g., 2010-03-15)."),
            ("Address", "Optional", "Residential street address and city."),
            ("Monthly Discount", "Optional", "Fixed recurring fee discount in PKR (defaults to 0.00)."),
        ]

        for r_idx, (fname, req, desc) in enumerate(rules, 2):
            ws_info.row_dimensions[r_idx].height = 20
            c1 = ws_info.cell(row=r_idx, column=1, value=fname)
            c2 = ws_info.cell(row=r_idx, column=2, value=req)
            c3 = ws_info.cell(row=r_idx, column=3, value=desc)
            for c in (c1, c2, c3):
                c.border = border
                c.font = Font(name="Calibri", size=10)
            c2.alignment = Alignment(horizontal="center")
            if req == "YES":
                c2.font = Font(name="Calibri", size=10, bold=True, color="DC2626")

        target_dir = os.path.dirname(os.path.abspath(target_path))
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)

        wb.save(target_path)
        logger.info(f"Student import template generated at: {target_path}")
        return os.path.abspath(target_path)

    def import_students_from_excel(
        self,
        file_path: str,
        class_group_id: int,
        session_id: int
    ) -> Dict[str, Any]:
        """
        Parses an Excel (.xlsx) or CSV file, validates student and guardian metadata,
        and atomically registers enrollments into the database.

        Args:
            file_path: Absolute or relative path to .xlsx or .csv file.
            class_group_id: Target class_group ID for student enrollments.
            session_id: Target academic session ID.

        Returns:
            Dict containing:
                - total_rows: Total non-empty candidate rows processed.
                - imported_count: Total students successfully enrolled.
                - failed_count: Total rows rejected due to validation errors.
                - errors: List of error dictionaries [{"row": int, "student_name": str, "error": str}].
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Import file not found: '{file_path}'")

        # 1. Verify target class and session foreign keys
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM academic_sessions WHERE id = ?;", (session_id,))
        if not cursor.fetchone():
            raise ValueError(f"Academic session with id={session_id} does not exist.")

        cursor.execute("SELECT id FROM class_groups WHERE id = ? AND session_id = ?;", (class_group_id, session_id))
        if not cursor.fetchone():
            raise ValueError(f"Class group id={class_group_id} does not exist in session id={session_id}.")

        # 2. Parse file into raw row dictionaries
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".csv":
            raw_rows = self._parse_csv_file(file_path)
        elif ext in (".xlsx", ".xlsm"):
            raw_rows = self._parse_excel_file(file_path)
        else:
            raise ValueError(f"Unsupported file format '{ext}'. Must be .xlsx or .csv.")

        if not raw_rows:
            return {
                "total_rows": 0,
                "imported_count": 0,
                "failed_count": 0,
                "errors": [],
            }

        # 3. Process and ingest rows with transactional atomicity
        imported_count = 0
        errors: List[Dict[str, Any]] = []
        batch_seen_admission_numbers = set()

        try:
            for row_idx, data in raw_rows:
                disp_name = f"{data.get('first_name', '')} {data.get('last_name', '')}".strip() or f"Row {row_idx}"

                validation_err = self._validate_and_normalize_row(data, batch_seen_admission_numbers)
                if validation_err:
                    errors.append({
                        "row": row_idx,
                        "student_name": disp_name,
                        "error": validation_err,
                    })
                    continue

                try:
                    student_dto = StudentDTO(
                        admission_number=data.get("admission_number") or "",
                        first_name=data["first_name"],
                        last_name=data.get("last_name"),
                        urdu_name=data.get("urdu_name"),
                        gender=data["gender"],
                        date_of_birth=data.get("date_of_birth"),
                        guardian_name=data["guardian_name"],
                        guardian_relation="Father",
                        guardian_phone=data["guardian_phone"],
                        residential_address=data.get("address"),
                        is_active=True,
                    )

                    self.student_service.register_student(
                        student_data=student_dto,
                        class_group_id=class_group_id,
                        session_id=session_id,
                        roll_number=data.get("roll_number"),
                        custom_discount_amount=data.get("monthly_discount", Decimal("0.00")),
                    )
                    imported_count += 1

                except Exception as exc:
                    errors.append({
                        "row": row_idx,
                        "student_name": disp_name,
                        "error": str(exc),
                    })

            # If all rows failed, log diagnostic warning
            if imported_count == 0 and errors:
                logger.warning(f"All {len(errors)} rows failed validation during bulk student import.")

        except Exception as exc:
            logger.error(f"Catastrophic error during bulk student import: {exc}", exc_info=True)
            raise

        return {
            "total_rows": len(raw_rows),
            "imported_count": imported_count,
            "failed_count": len(errors),
            "errors": errors,
        }

    # --- Internal File Parsing Helpers ---

    def _normalize_header(self, header: str) -> str:
        """Strips asterisks, parentheses, brackets, and extra spaces to match canonical keys."""
        cleaned = re.sub(r"[\*\(\)\[\]]", "", str(header or "")).strip().lower()
        cleaned = re.sub(r"\s+", "_", cleaned)
        return cleaned

    def _map_header_to_field(self, norm_h: str) -> Optional[str]:
        """Maps diverse header labels to canonical student fields."""
        # Phone must precede generic 'guardian' to prevent 'guardian_phone' matching 'guardian'
        if any(k in norm_h for k in ("phone", "mobile", "contact", "cell")):
            return "guardian_phone"
        if any(k in norm_h for k in ("guardian_name", "father_name", "parent_name", "guardian", "father", "parent")):
            return "guardian_name"
        if any(k in norm_h for k in ("roll", "roll_number", "roll_no")):
            return "roll_number"
        if any(k in norm_h for k in ("first_name", "firstname", "first", "student_name", "student")):
            return "first_name"
        if any(k in norm_h for k in ("last_name", "lastname", "surname")):
            return "last_name"
        if any(k in norm_h for k in ("urdu_name", "urdu", "naam")):
            return "urdu_name"
        if any(k in norm_h for k in ("gender", "sex")):
            return "gender"
        if any(k in norm_h for k in ("admission", "adm_no", "adm_num", "reg_no", "gr_no")):
            return "admission_number"
        if any(k in norm_h for k in ("birth", "dob")):
            return "date_of_birth"
        if any(k in norm_h for k in ("address", "residence", "city")):
            return "address"
        if any(k in norm_h for k in ("discount", "concession", "fee_discount")):
            return "monthly_discount"
        return None

    def _parse_excel_file(self, file_path: str) -> List[Tuple[int, Dict[str, Any]]]:
        """Reads rows from active sheet of an Excel workbook."""
        wb = openpyxl.load_workbook(file_path, data_only=True)
        ws = wb.active

        header_map: Dict[int, str] = {}
        parsed_rows: List[Tuple[int, Dict[str, Any]]] = []

        for row_idx, row in enumerate(ws.iter_rows(values_only=True), 1):
            if row_idx == 1:
                for col_idx, cell_val in enumerate(row):
                    if cell_val is not None:
                        norm = self._normalize_header(str(cell_val))
                        field = self._map_header_to_field(norm)
                        if field:
                            header_map[col_idx] = field
                continue

            # Check if row is completely empty
            if not row or all(c is None or str(c).strip() == "" for c in row):
                continue

            row_dict: Dict[str, Any] = {}
            for col_idx, cell_val in enumerate(row):
                field = header_map.get(col_idx)
                if field and cell_val is not None:
                    row_dict[field] = cell_val

            if row_dict:
                parsed_rows.append((row_idx, row_dict))

        return parsed_rows

    def _parse_csv_file(self, file_path: str) -> List[Tuple[int, Dict[str, Any]]]:
        """Reads rows from a CSV file with automatic encoding fallback."""
        lines = []
        for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
            try:
                with open(file_path, "r", encoding=enc, newline="") as f:
                    lines = list(csv.reader(f))
                break
            except (UnicodeDecodeError, Exception):
                continue

        if not lines:
            return []

        header_map: Dict[int, str] = {}
        parsed_rows: List[Tuple[int, Dict[str, Any]]] = []

        for col_idx, cell_val in enumerate(lines[0]):
            norm = self._normalize_header(cell_val)
            field = self._map_header_to_field(norm)
            if field:
                header_map[col_idx] = field

        for row_idx, row in enumerate(lines[1:], 2):
            if not row or all(str(c).strip() == "" for c in row):
                continue

            row_dict: Dict[str, Any] = {}
            for col_idx, cell_val in enumerate(row):
                field = header_map.get(col_idx)
                if field and cell_val is not None and str(cell_val).strip() != "":
                    row_dict[field] = cell_val.strip()

            if row_dict:
                parsed_rows.append((row_idx, row_dict))

        return parsed_rows

    def _validate_and_normalize_row(
        self,
        data: Dict[str, Any],
        seen_admissions: set
    ) -> Optional[str]:
        """
        Validates row data and normalizes fields in place.
        Returns error message string if invalid, or None if valid.
        """
        # 1. First Name
        fn = str(data.get("first_name", "")).strip()
        if not fn:
            return "Student first name is mandatory."
        data["first_name"] = fn

        # 2. Last Name & Urdu Name
        ln = str(data.get("last_name", "")).strip()
        data["last_name"] = ln if ln else None

        un = str(data.get("urdu_name", "")).strip()
        data["urdu_name"] = un if un else None

        # 3. Gender
        g_raw = str(data.get("gender", "")).strip().lower()
        if g_raw in ("male", "m", "boy"):
            data["gender"] = "Male"
        elif g_raw in ("female", "f", "girl"):
            data["gender"] = "Female"
        elif g_raw in ("other", "o"):
            data["gender"] = "Other"
        else:
            return f"Invalid gender '{data.get('gender')}'. Must be 'Male', 'Female', or 'Other'."

        # 4. Guardian Name
        gn = str(data.get("guardian_name", "")).strip()
        if not gn:
            return "Guardian name is mandatory."
        data["guardian_name"] = gn

        # 5. Guardian Phone
        gp_val = data.get("guardian_phone", "")
        if isinstance(gp_val, float) and gp_val.is_integer():
            gp_raw = str(int(gp_val))
        else:
            gp_raw = str(gp_val).strip()

        if not gp_raw:
            return "Guardian phone number is mandatory."

        # Handle dropped leading zero from integer cells (e.g. 3001234567 -> 03001234567)
        digits_only = re.sub(r"\D", "", gp_raw)
        if len(digits_only) == 10 and digits_only.startswith("3"):
            gp_raw = "0" + digits_only

        try:
            data["guardian_phone"] = normalize_pakistan_phone(gp_raw)
        except ValueError as exc:
            return f"Invalid phone format '{gp_raw}': {exc}"

        # 6. Admission Number (Optional or User-Supplied)
        adm = str(data.get("admission_number", "")).strip()
        if adm:
            if adm in seen_admissions:
                return f"Duplicate admission number '{adm}' repeated within spreadsheet."
            seen_admissions.add(adm)
            # Check DB uniqueness
            cursor = self.conn.cursor()
            cursor.execute("SELECT id FROM students WHERE admission_number = ?;", (adm,))
            if cursor.fetchone():
                return f"Admission number '{adm}' is already registered in database."
            data["admission_number"] = adm
        else:
            data["admission_number"] = None

        # 7. Date of Birth
        dob_val = data.get("date_of_birth")
        if dob_val is not None:
            if isinstance(dob_val, (datetime, date)):
                data["date_of_birth"] = dob_val.strftime("%Y-%m-%d")
            else:
                dob_str = str(dob_val).strip()
                if dob_str:
                    try:
                        # Attempt standard ISO or common formats
                        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
                            try:
                                dt = datetime.strptime(dob_str, fmt)
                                data["date_of_birth"] = dt.strftime("%Y-%m-%d")
                                break
                            except ValueError:
                                continue
                        else:
                            return f"Invalid date of birth '{dob_str}'. Expected YYYY-MM-DD."
                    except Exception:
                        return f"Invalid date of birth format '{dob_str}'."
                else:
                    data["date_of_birth"] = None
        else:
            data["date_of_birth"] = None

        # 8. Address & Roll Number
        addr = str(data.get("address", "")).strip()
        data["address"] = addr if addr else None

        roll_val = data.get("roll_number")
        if roll_val is not None:
            if isinstance(roll_val, float) and roll_val.is_integer():
                roll_str = str(int(roll_val))
            else:
                roll_str = str(roll_val).strip()
        else:
            roll_str = ""
        data["roll_number"] = roll_str if roll_str else None

        # 9. Monthly Discount
        disc_val = data.get("monthly_discount")
        if disc_val is None or str(disc_val).strip() == "":
            data["monthly_discount"] = Decimal("0.00")
        else:
            try:
                dec_disc = Decimal(str(disc_val).strip().replace(",", ""))
                if dec_disc < Decimal("0.00"):
                    return f"Monthly discount cannot be negative ({dec_disc})."
                data["monthly_discount"] = dec_disc
            except (InvalidOperation, Exception):
                return f"Invalid monthly discount value '{disc_val}'. Must be a valid number."

        return None
