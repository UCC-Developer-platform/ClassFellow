"""
ClassFellow Web - Monthly Audit Packet PDF Export Service
=========================================================
Generates an executive multi-page audit report in-memory using ReportLab:
- Section 1: Executive KPI Summary & Campus Collections Breakdown.
- Section 2: Defaulter Accounts Receivable Ledger.
- Section 3: Formal Institutional Audit Declaration & Multi-Role Sign-off.
"""

from decimal import Decimal
import io
from typing import Optional

from django.db.models import Sum
from django.db.models.functions import Coalesce
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, portrait
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from apps.core.models import AcademicSession, Campus, InstitutionProfile
from apps.fees.models import FeeInvoice, Payment, PaymentStatus
from apps.students.models import ClassGroup


class MonthlyAuditPacketService:
    """Encapsulates executive monthly financial audit packet compilation into PDF."""

    @classmethod
    def generate_monthly_audit_packet(
        cls,
        session_id: int,
        month_year: str,
        campus_id: Optional[int] = None,
    ) -> io.BytesIO:
        """
        Generates an executive multi-page audit report in-memory.
        Returns:
            io.BytesIO buffer positioned at offset 0.
        """
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=portrait(A4),
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "AuditTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#0F172A"),
            alignment=1,  # Center
        )
        subtitle_style = ParagraphStyle(
            "AuditSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#64748B"),
            alignment=1,
        )
        h2_style = ParagraphStyle(
            "AuditH2",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#1E293B"),
            spaceBefore=10,
            spaceAfter=6,
        )
        body_style = ParagraphStyle(
            "AuditBody",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#334155"),
        )
        cell_bold = ParagraphStyle(
            "CellBold",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#0F172A"),
        )
        cell_regular = ParagraphStyle(
            "CellRegular",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#334155"),
        )
        cell_white = ParagraphStyle(
            "CellWhite",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.white,
        )

        institution = InstitutionProfile.objects.first()
        inst_name = institution.name if institution else "CLASSFELLOW HIGH SCHOOL & ACADEMY"
        session_obj = AcademicSession.objects.filter(id=session_id).first()
        session_label = session_obj.name if session_obj else str(session_id)

        # ---------------------------------------------------------------------
        # Data Aggregation
        # ---------------------------------------------------------------------
        invoices_qs = FeeInvoice.objects.filter(
            enrollment__session_id=session_id,
            month_year=month_year,
        ).select_related("enrollment__student", "enrollment__class_group", "enrollment__class_group__campus")

        if campus_id:
            invoices_qs = invoices_qs.filter(enrollment__class_group__campus_id=campus_id)

        invoices = list(invoices_qs)
        total_invoiced = sum((inv.net_due for inv in invoices), Decimal("0.00"))

        payments = Payment.objects.filter(
            invoice__in=invoices,
            status=PaymentStatus.ISSUED,
        )
        total_collected = payments.aggregate(val=Coalesce(Sum("amount"), Decimal("0.00")))["val"]
        outstanding_balance = max(Decimal("0.00"), total_invoiced - total_collected)
        recovery_pct = (
            round((total_collected / total_invoiced) * Decimal("100.00"), 2)
            if total_invoiced > Decimal("0.00")
            else Decimal("100.00")
        )

        story = []

        # =====================================================================
        # PAGE 1: Header & Executive KPI Summary
        # =====================================================================
        story.append(Paragraph(inst_name.upper(), title_style))
        story.append(Spacer(1, 4))
        story.append(
            Paragraph(
                f"MONTHLY FINANCIAL AUDIT PACKET & RECOVERY ANALYSIS &bull; {month_year} (Session: {session_label})",
                subtitle_style,
            )
        )
        story.append(Spacer(1, 10))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1E293B"), spaceAfter=14))

        # KPI Tiles Grid Table
        kpi_data = [
            [
                Paragraph("<b>TOTAL BILLED</b>", cell_bold),
                Paragraph("<b>TOTAL COLLECTED</b>", cell_bold),
                Paragraph("<b>OUTSTANDING LEDGER</b>", cell_bold),
                Paragraph("<b>RECOVERY RATE</b>", cell_bold),
            ],
            [
                Paragraph(f"<font size=11><b>Rs. {total_invoiced:,.2f}</b></font>", cell_bold),
                Paragraph(
                    f"<font size=11 color='#059669'><b>Rs. {total_collected:,.2f}</b></font>",
                    cell_bold,
                ),
                Paragraph(
                    f"<font size=11 color='#E11D48'><b>Rs. {outstanding_balance:,.2f}</b></font>",
                    cell_bold,
                ),
                Paragraph(f"<font size=11 color='#059669'><b>{recovery_pct}%</b></font>", cell_bold),
            ],
        ]
        kpi_table = Table(kpi_data, colWidths=[130, 130, 130, 130])
        kpi_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ]
            )
        )
        story.append(kpi_table)
        story.append(Spacer(1, 18))

        # Section 1.2: Campus Breakdown Table
        story.append(Paragraph("1. Campus Collections & Recovery Breakdown", h2_style))
        campuses_qs = Campus.objects.filter(is_active=True)
        if campus_id:
            campuses_qs = campuses_qs.filter(id=campus_id)

        campus_table_data = [
            [
                Paragraph("Campus Name", cell_white),
                Paragraph("Active Classes", cell_white),
                Paragraph("Invoiced (Rs.)", cell_white),
                Paragraph("Collected (Rs.)", cell_white),
                Paragraph("Outstanding (Rs.)", cell_white),
                Paragraph("Recovery %", cell_white),
            ]
        ]

        for cmp in campuses_qs:
            cmp_invoices = [inv for inv in invoices if inv.enrollment.class_group.campus_id == cmp.id]
            cmp_inv_tot = sum((i.net_due for i in cmp_invoices), Decimal("0.00"))
            cmp_pay_tot = (
                Payment.objects.filter(invoice__in=cmp_invoices, status=PaymentStatus.ISSUED).aggregate(
                    val=Coalesce(Sum("amount"), Decimal("0.00"))
                )["val"]
                if cmp_invoices
                else Decimal("0.00")
            )
            cmp_out = max(Decimal("0.00"), cmp_inv_tot - cmp_pay_tot)
            cmp_rec = (
                round((cmp_pay_tot / cmp_inv_tot) * Decimal("100.00"), 1)
                if cmp_inv_tot > Decimal("0.00")
                else Decimal("100.0")
            )
            classes_cnt = ClassGroup.objects.filter(campus=cmp, session_id=session_id).count()

            campus_table_data.append(
                [
                    Paragraph(cmp.name, cell_regular),
                    Paragraph(str(classes_cnt), cell_regular),
                    Paragraph(f"{cmp_inv_tot:,.2f}", cell_regular),
                    Paragraph(f"{cmp_pay_tot:,.2f}", cell_regular),
                    Paragraph(f"{cmp_out:,.2f}", cell_regular),
                    Paragraph(f"<b>{cmp_rec}%</b>", cell_bold),
                ]
            )

        campus_table = Table(campus_table_data, colWidths=[150, 70, 75, 75, 80, 70])
        campus_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(campus_table)

        # =====================================================================
        # PAGE 2: Defaulter Accounts Receivable Ledger
        # =====================================================================
        story.append(PageBreak())
        story.append(Paragraph(inst_name.upper(), title_style))
        story.append(Spacer(1, 4))
        story.append(Paragraph(f"ACCOUNTS RECEIVABLE & DEFAULTER ROSTER &bull; {month_year}", subtitle_style))
        story.append(Spacer(1, 10))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1E293B"), spaceAfter=14))

        defaulter_invoices = []
        for inv in invoices:
            paid = (
                Payment.objects.filter(invoice=inv, status=PaymentStatus.ISSUED).aggregate(
                    val=Coalesce(Sum("amount"), Decimal("0.00"))
                )["val"]
            )
            bal = max(Decimal("0.00"), inv.net_due - paid)
            if bal > Decimal("0.00"):
                defaulter_invoices.append(
                    {
                        "invoice": inv,
                        "paid": paid,
                        "balance": bal,
                    }
                )

        defaulter_invoices.sort(key=lambda x: x["balance"], reverse=True)

        if defaulter_invoices:
            defaulter_table_data = [
                [
                    Paragraph("Adm #", cell_white),
                    Paragraph("Student Name", cell_white),
                    Paragraph("Class & Sec", cell_white),
                    Paragraph("Guardian Phone", cell_white),
                    Paragraph("Due Date", cell_white),
                    Paragraph("Billed (Rs.)", cell_white),
                    Paragraph("Paid (Rs.)", cell_white),
                    Paragraph("Balance (Rs.)", cell_white),
                ]
            ]
            for item in defaulter_invoices:
                inv = item["invoice"]
                stu = inv.enrollment.student
                cg = inv.enrollment.class_group
                stu_name = f"{stu.first_name} {stu.last_name}".strip()
                defaulter_table_data.append(
                    [
                        Paragraph(stu.admission_number, cell_regular),
                        Paragraph(stu_name[:18], cell_regular),
                        Paragraph(f"{cg.name} {cg.section_or_batch}", cell_regular),
                        Paragraph(stu.guardian_phone, cell_regular),
                        Paragraph(inv.due_date.strftime("%d-%b-%Y"), cell_regular),
                        Paragraph(f"{inv.net_due:,.2f}", cell_regular),
                        Paragraph(f"{item['paid']:,.2f}", cell_regular),
                        Paragraph(f"<font color='#E11D48'><b>{item['balance']:,.2f}</b></font>", cell_bold),
                    ]
                )

            def_table = Table(defaulter_table_data, colWidths=[65, 95, 80, 80, 65, 45, 45, 45])
            def_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            story.append(def_table)
        else:
            notice_msg = (
                "<b>Notice:</b> Zero defaulting accounts detected. "
                "100% fee recovery attained for this billing cycle."
            )
            story.append(Paragraph(notice_msg, body_style))

        # =====================================================================
        # PAGE 3 / FINAL: Institutional Audit Declaration & Sign-off
        # =====================================================================
        story.append(PageBreak())
        story.append(Paragraph(inst_name.upper(), title_style))
        story.append(Spacer(1, 4))
        story.append(Paragraph("INSTITUTIONAL AUDIT DECLARATION & FORMAL SIGN-OFF", subtitle_style))
        story.append(Spacer(1, 10))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1E293B"), spaceAfter=14))

        declaration_text = (
            "<b>AUDIT DECLARATION:</b><br/>"
            f"This monthly financial audit packet for billing cycle <b>{month_year}</b> has been compiled directly "
            "from the ClassFellow immutable financial ledger. All cash and bank transactions have been reconciled "
            "against physical day-closing summaries and authorized cashier scrolls. Outstanding accounts receivable "
            "have been logged into institutional accounts for active fee recovery."
        )
        story.append(Paragraph(declaration_text, body_style))
        story.append(Spacer(1, 36))

        # 3 Sign-off Slots
        signoff_data = [
            [
                Paragraph(
                    "__________________________<br/><b>Accounts Officer / Cashier</b><br/>Prepared & Reconciled",
                    cell_regular,
                ),
                Paragraph(
                    "__________________________<br/><b>Internal Auditor / Bursar</b><br/>Verified with Bank Scrolls",
                    cell_regular,
                ),
                Paragraph(
                    "__________________________<br/><b>Principal / Campus Head</b><br/>Approved & Closed",
                    cell_regular,
                ),
            ]
        ]
        signoff_table = Table(signoff_data, colWidths=[170, 170, 170])
        signoff_table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ]
            )
        )
        story.append(signoff_table)

        doc.build(story)
        buf.seek(0)
        return buf
